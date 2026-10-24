from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from caliper.adapters.opencode.client import OpenCodeFailure, OpenCodeHttpAdapter
from caliper.adapters.postgres.database import get_session
from caliper.adapters.postgres.opencode_settings_repository import (
    SqlOpenCodeSettingsRepository,
)
from caliper.api.auth import require_admin
from caliper.application.opencode_provider import OpenCodeProvider

router = APIRouter(
    prefix="/api/providers/opencode",
    tags=["model providers"],
    dependencies=[Depends(require_admin)],
)


class ApiKeyInput(BaseModel):
    api_key: SecretStr
    metadata: dict[str, str] = Field(default_factory=dict, max_length=20)


class OAuthAuthorizeInput(BaseModel):
    method: int = Field(ge=0, le=50)
    inputs: dict[str, str] = Field(default_factory=dict, max_length=20)


class OAuthCallbackInput(BaseModel):
    method: int = Field(ge=0, le=50)
    code: SecretStr


class ModelInput(BaseModel):
    provider_id: str = Field(min_length=1, max_length=128)
    model_id: str = Field(min_length=1, max_length=256)


def service(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> OpenCodeProvider:
    runtime = request.app.state.opencode_runtime
    return OpenCodeProvider(
        SqlOpenCodeSettingsRepository(session),
        request.app.state.opencode_secret_store,
        OpenCodeHttpAdapter(runtime.base_url),
        runtime,
    )


async def _run(operation):
    try:
        return await operation
    except OpenCodeFailure as error:
        raise HTTPException(status_code=503, detail=error.code) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("")
async def get_opencode_settings(
    provider: Annotated[OpenCodeProvider, Depends(service)],
) -> dict[str, Any]:
    return await provider.snapshot()


@router.post("/validate")
async def validate_opencode(
    provider: Annotated[OpenCodeProvider, Depends(service)],
) -> dict[str, Any]:
    await _run(provider.capture_runtime_profile())
    return await provider.snapshot()


@router.put("/auth/{provider_id}/api-key")
async def connect_api_key(
    provider_id: str,
    payload: ApiKeyInput,
    provider: Annotated[OpenCodeProvider, Depends(service)],
) -> dict[str, Any]:
    return await _run(
        provider.connect_api_key(provider_id, payload.api_key.get_secret_value(), payload.metadata)
    )


@router.post("/auth/{provider_id}/oauth/authorize")
async def authorize_oauth(
    provider_id: str,
    payload: OAuthAuthorizeInput,
    provider: Annotated[OpenCodeProvider, Depends(service)],
) -> dict[str, str]:
    return await _run(provider.authorize(provider_id, payload.method, payload.inputs))


@router.post("/auth/{provider_id}/oauth/callback")
async def oauth_callback(
    provider_id: str,
    payload: OAuthCallbackInput,
    provider: Annotated[OpenCodeProvider, Depends(service)],
) -> dict[str, Any]:
    return await _run(
        provider.oauth_callback(provider_id, payload.method, payload.code.get_secret_value())
    )


@router.delete("/auth/{provider_id}")
async def disconnect_provider(
    provider_id: str,
    provider: Annotated[OpenCodeProvider, Depends(service)],
) -> dict[str, Any]:
    return await _run(provider.disconnect(provider_id))


@router.put("/model")
async def select_model(
    payload: ModelInput,
    provider: Annotated[OpenCodeProvider, Depends(service)],
) -> dict[str, Any]:
    return await _run(provider.select_model(payload.provider_id, payload.model_id))
