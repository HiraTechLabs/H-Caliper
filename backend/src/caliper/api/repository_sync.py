import os
from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from caliper.adapters.git.repository_sync import GitRepositorySyncAdapter
from caliper.adapters.postgres.database import get_session
from caliper.adapters.postgres.repository_sync_repository import SqlRepositorySyncRepository
from caliper.adapters.secret_store.fernet_store import FernetFileSecretStore
from caliper.api.auth import require_admin
from caliper.application.repository_sync import (
    KnowledgeDocument,
    ProjectNotFound,
    RepositorySourceChanged,
    RepositorySync,
    RepositorySyncFailed,
    SyncAlreadyRunning,
)

router = APIRouter(
    prefix="/api/projects/{project_id}",
    tags=["repository sync"],
    dependencies=[Depends(require_admin)],
)


class SyncInput(BaseModel):
    credential_id: UUID | None = None


EMPTY_SYNC_INPUT = SyncInput()


class SyncOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    project_id: UUID
    status: str
    source_url: str
    branch: str
    revision: str | None
    attempted_at: datetime
    last_success_at: datetime | None
    error_code: str | None
    document_count: int


class KnowledgeOutput(BaseModel):
    path: str
    revision: str
    sha256: str
    content: str
    synced_at: datetime


def service(session: Annotated[AsyncSession, Depends(get_session)]) -> RepositorySync:
    repository_root = Path(os.environ.get("CALIPER_REPOSITORY_ROOT", "/tmp/caliper-repositories"))
    local_root = Path(
        os.environ.get("CALIPER_LOCAL_REPOSITORY_ROOT", "/var/lib/caliper/local-repositories")
    )
    git = GitRepositorySyncAdapter(
        repository_root,
        local_root,
        allow_local_repositories=os.environ.get("CALIPER_ALLOW_LOCAL_REPOSITORIES", "false").lower()
        == "true",
        known_hosts_path=Path(
            os.environ.get("CALIPER_SSH_KNOWN_HOSTS", "/etc/caliper/ssh/known_hosts")
        ),
    )
    secrets = FernetFileSecretStore(
        Path(os.environ.get("CALIPER_SECRET_DATA_DIR", "/var/lib/caliper/secret-data")),
        Path(os.environ.get("CALIPER_SECRET_KEYRING", "/var/lib/caliper/keyring/keyring.json")),
    )
    return RepositorySync(SqlRepositorySyncRepository(session), secrets, git)


@router.get("/sync", response_model=SyncOutput)
async def get_sync_state(
    project_id: UUID, sync: Annotated[RepositorySync, Depends(service)]
) -> SyncOutput:
    try:
        return SyncOutput.model_validate(await sync.state(project_id))
    except ProjectNotFound as error:
        raise HTTPException(status_code=404, detail="Project not found") from error


@router.get("/knowledge", response_model=list[KnowledgeOutput])
async def get_knowledge(
    project_id: UUID, sync: Annotated[RepositorySync, Depends(service)]
) -> list[KnowledgeDocument]:
    try:
        return await sync.documents(project_id)
    except ProjectNotFound as error:
        raise HTTPException(status_code=404, detail="Project not found") from error


@router.post("/sync", response_model=SyncOutput)
async def run_sync(
    project_id: UUID,
    sync: Annotated[RepositorySync, Depends(service)],
    payload: SyncInput = EMPTY_SYNC_INPUT,
) -> SyncOutput:
    try:
        return SyncOutput.model_validate(await sync.sync(project_id, payload.credential_id))
    except ProjectNotFound as error:
        raise HTTPException(status_code=404, detail="Project not found") from error
    except RepositorySyncFailed as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"message": "Repository synchronization failed", "state": error.state.__dict__},
        ) from error
    except (RepositorySourceChanged, SyncAlreadyRunning) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except (ValueError, LookupError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
