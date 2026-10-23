import os
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from caliper.adapters.git.remote_validator import GitRemoteValidator
from caliper.adapters.postgres.credential_repository import SqlCredentialRepository
from caliper.adapters.postgres.database import get_session
from caliper.adapters.secret_store.fernet_store import FernetFileSecretStore
from caliper.api.auth import require_admin
from caliper.application.credentials import (
    Credential,
    CredentialNameRequired,
    CredentialNotFound,
    Credentials,
    ProjectNotFound,
)
from caliper.application.secret_store import SecretStoreError

router = APIRouter(
    prefix="/api/projects/{project_id}/credentials",
    tags=["credentials"],
    dependencies=[Depends(require_admin)],
)


class CredentialInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["https_token"] = "https_token"
    username: str = Field(default="x-access-token", min_length=1, max_length=255)
    secret: SecretStr = Field(min_length=1, max_length=16384)


class CredentialEnabledInput(BaseModel):
    enabled: bool


class CredentialOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    name: str
    kind: str
    username: str
    enabled: bool
    status: str
    deletion_pending: bool
    cleanup_pending: bool
    created_at: datetime
    updated_at: datetime
    last_checked_at: datetime | None


def service(session: Annotated[AsyncSession, Depends(get_session)]) -> Credentials:
    secret_store = FernetFileSecretStore(
        Path(os.environ.get("CALIPER_SECRET_DATA_DIR", "/var/lib/caliper/secret-data")),
        Path(os.environ.get("CALIPER_SECRET_KEYRING", "/var/lib/caliper/keyring/keyring.json")),
    )
    return Credentials(SqlCredentialRepository(session), secret_store, GitRemoteValidator())


@router.get("", response_model=list[CredentialOutput])
async def list_credentials(
    project_id: UUID, credentials: Annotated[Credentials, Depends(service)]
) -> list[Credential]:
    try:
        return await credentials.list(project_id)
    except ProjectNotFound as error:
        raise HTTPException(status_code=404, detail="Project not found") from error


@router.post("", response_model=CredentialOutput, status_code=status.HTTP_201_CREATED)
async def create_credential(
    project_id: UUID,
    payload: CredentialInput,
    credentials: Annotated[Credentials, Depends(service)],
) -> Credential:
    try:
        return await credentials.create(
            project_id,
            payload.name,
            payload.username,
            payload.secret.get_secret_value().encode("utf-8"),
        )
    except ProjectNotFound as error:
        raise HTTPException(status_code=404, detail="Project not found") from error
    except CredentialNameRequired as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except IntegrityError as error:
        raise HTTPException(status_code=409, detail="Credential name already exists") from error
    except SecretStoreError as error:
        raise HTTPException(status_code=503, detail="Secret store is unavailable") from error


@router.put("/{credential_id}", response_model=CredentialOutput)
async def replace_credential(
    project_id: UUID,
    credential_id: UUID,
    payload: CredentialInput,
    credentials: Annotated[Credentials, Depends(service)],
) -> Credential:
    try:
        return await credentials.replace(
            project_id,
            credential_id,
            payload.name,
            payload.username,
            payload.secret.get_secret_value().encode("utf-8"),
        )
    except CredentialNotFound as error:
        raise HTTPException(status_code=404, detail="Credential not found") from error
    except CredentialNameRequired as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except SecretStoreError as error:
        raise HTTPException(status_code=503, detail="Secret cleanup is pending") from error


@router.patch("/{credential_id}", response_model=CredentialOutput)
async def set_credential_enabled(
    project_id: UUID,
    credential_id: UUID,
    payload: CredentialEnabledInput,
    credentials: Annotated[Credentials, Depends(service)],
) -> Credential:
    try:
        return await credentials.set_enabled(project_id, credential_id, payload.enabled)
    except CredentialNotFound as error:
        raise HTTPException(status_code=404, detail="Credential not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    project_id: UUID,
    credential_id: UUID,
    credentials: Annotated[Credentials, Depends(service)],
) -> Response:
    try:
        await credentials.delete(project_id, credential_id)
    except CredentialNotFound as error:
        raise HTTPException(status_code=404, detail="Credential not found") from error
    except SecretStoreError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return Response(status_code=204)


@router.post("/{credential_id}/validate", response_model=CredentialOutput)
async def validate_credential(
    project_id: UUID,
    credential_id: UUID,
    credentials: Annotated[Credentials, Depends(service)],
) -> Credential:
    try:
        return await credentials.validate(project_id, credential_id)
    except CredentialNotFound as error:
        raise HTTPException(status_code=404, detail="Credential not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except SecretStoreError as error:
        raise HTTPException(status_code=503, detail="Secret store is unavailable") from error
