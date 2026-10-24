from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from caliper.adapters.ollama.discovery import OllamaHttpDiscoveryAdapter
from caliper.adapters.postgres.database import get_session
from caliper.adapters.postgres.ollama_settings_repository import SqlOllamaSettingsRepository
from caliper.api.auth import require_admin
from caliper.application.ollama_provider import (
    OllamaConfigurationChanged,
    OllamaModelNotAvailable,
    OllamaProvider,
)

router = APIRouter(
    prefix="/api/providers/ollama",
    tags=["model providers"],
    dependencies=[Depends(require_admin)],
)


class EndpointInput(BaseModel):
    endpoint_url: str = Field(min_length=1, max_length=512)


class ModelInput(BaseModel):
    model_id: str = Field(min_length=1, max_length=256)


class OllamaSettingsOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    endpoint_url: str
    selected_model_id: str | None
    status: str
    checked_at: datetime | None
    error_code: str | None
    models: list[str]


def service(session: Annotated[AsyncSession, Depends(get_session)]) -> OllamaProvider:
    return OllamaProvider(SqlOllamaSettingsRepository(session), OllamaHttpDiscoveryAdapter())


@router.get("", response_model=OllamaSettingsOutput)
async def get_ollama_settings(
    provider: Annotated[OllamaProvider, Depends(service)],
) -> OllamaSettingsOutput:
    return OllamaSettingsOutput.model_validate(await provider.settings())


@router.put("", response_model=OllamaSettingsOutput)
async def configure_ollama(
    payload: EndpointInput,
    provider: Annotated[OllamaProvider, Depends(service)],
) -> OllamaSettingsOutput:
    try:
        return OllamaSettingsOutput.model_validate(await provider.configure(payload.endpoint_url))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/validate", response_model=OllamaSettingsOutput)
async def validate_ollama(
    provider: Annotated[OllamaProvider, Depends(service)],
) -> OllamaSettingsOutput:
    try:
        return OllamaSettingsOutput.model_validate(await provider.validate())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except OllamaConfigurationChanged as error:
        raise HTTPException(
            status_code=409, detail="Ollama endpoint changed during validation; retry"
        ) from error


@router.put("/model", response_model=OllamaSettingsOutput)
async def select_ollama_model(
    payload: ModelInput,
    provider: Annotated[OllamaProvider, Depends(service)],
) -> OllamaSettingsOutput:
    try:
        return OllamaSettingsOutput.model_validate(await provider.select_model(payload.model_id))
    except OllamaModelNotAvailable as error:
        raise HTTPException(
            status_code=409, detail="Validate the endpoint and choose a discovered model"
        ) from error
