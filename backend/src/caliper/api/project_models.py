from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from caliper.adapters.ollama.discovery import OllamaHttpDiscoveryAdapter
from caliper.adapters.opencode.client import OpenCodeHttpAdapter
from caliper.adapters.postgres.database import get_session
from caliper.adapters.postgres.ollama_settings_repository import SqlOllamaSettingsRepository
from caliper.adapters.postgres.opencode_settings_repository import (
    SqlOpenCodeSettingsRepository,
)
from caliper.adapters.postgres.project_model_repository import SqlProjectModelRepository
from caliper.api.auth import require_admin
from caliper.application.ollama_provider import OllamaProvider
from caliper.application.opencode_provider import OpenCodeProvider
from caliper.application.project_models import (
    AvailableProjectModel,
    ProjectModels,
    ProjectModelSelection,
    ProjectModelUnavailable,
)

router = APIRouter(
    prefix="/api/projects/{project_id}/model",
    tags=["project model"],
    dependencies=[Depends(require_admin)],
)


class ModelOption(BaseModel):
    provider_type: Literal["ollama", "opencode"]
    provider_id: str
    provider_name: str
    model_id: str
    model_name: str


class SelectionInput(BaseModel):
    provider_type: Literal["ollama", "opencode"]
    provider_id: str = Field(min_length=1, max_length=128)
    model_id: str = Field(min_length=1, max_length=256)


class SelectionOutput(BaseModel):
    provider_type: str
    provider_id: str
    model_id: str
    updated_at: datetime


class ProjectModelOutput(BaseModel):
    selection: SelectionOutput | None
    options: list[ModelOption]


async def _options(session: AsyncSession, request: Request) -> list[ModelOption]:
    runtime = request.app.state.opencode_runtime
    opencode = OpenCodeProvider(
        SqlOpenCodeSettingsRepository(session),
        request.app.state.opencode_secret_store,
        OpenCodeHttpAdapter(runtime.base_url),
        runtime,
    )
    ollama = OllamaProvider(SqlOllamaSettingsRepository(session), OllamaHttpDiscoveryAdapter())
    opencode_snapshot = await opencode.snapshot()
    connected = set(opencode_snapshot["connected_provider_ids"])
    result = [
        ModelOption(
            provider_type="opencode",
            provider_id=provider["id"],
            provider_name=provider["name"],
            model_id=model["id"],
            model_name=model["name"],
        )
        for provider in opencode_snapshot["providers"]
        if provider["id"] in connected
        for model in provider["models"]
    ]
    settings = await ollama.settings()
    if settings.status == "reachable":
        result.extend(
            ModelOption(
                provider_type="ollama",
                provider_id="ollama",
                provider_name="Ollama",
                model_id=model,
                model_name=model,
            )
            for model in settings.models
        )
    return result


def _application_options(options: list[ModelOption]) -> list[AvailableProjectModel]:
    return [AvailableProjectModel(**option.model_dump()) for option in options]


def _http_options(options: list[AvailableProjectModel]) -> list[ModelOption]:
    return [
        ModelOption(
            provider_type=option.provider_type,
            provider_id=option.provider_id,
            provider_name=option.provider_name,
            model_id=option.model_id,
            model_name=option.model_name,
        )
        for option in options
    ]


def _selection_output(selection: ProjectModelSelection | None) -> SelectionOutput | None:
    if selection is None:
        return None
    return SelectionOutput(
        provider_type=selection.provider_type,
        provider_id=selection.provider_id,
        model_id=selection.model_id,
        updated_at=selection.updated_at,
    )


@router.get("", response_model=ProjectModelOutput)
async def get_project_model(
    project_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProjectModelOutput:
    options = _application_options(await _options(session, request))
    try:
        selection, available = await ProjectModels(SqlProjectModelRepository(session)).get(
            project_id, options
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Project not found") from error
    return ProjectModelOutput(
        selection=_selection_output(selection), options=_http_options(available)
    )


@router.put("", response_model=ProjectModelOutput)
async def select_project_model(
    project_id: UUID,
    payload: SelectionInput,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProjectModelOutput:
    options = _application_options(await _options(session, request))
    try:
        selection, available = await ProjectModels(SqlProjectModelRepository(session)).select(
            project_id,
            provider_type=payload.provider_type,
            provider_id=payload.provider_id,
            model_id=payload.model_id,
            options=options,
        )
    except LookupError as error:
        if isinstance(error, ProjectModelUnavailable):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Connect the provider and choose a model from its current catalog",
            ) from error
        raise HTTPException(status_code=404, detail="Project not found") from error
    return ProjectModelOutput(
        selection=_selection_output(selection), options=_http_options(available)
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_project_model(
    project_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    try:
        await ProjectModels(SqlProjectModelRepository(session)).clear(project_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Project not found") from error
