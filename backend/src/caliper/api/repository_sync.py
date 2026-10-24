from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from caliper.adapters.postgres.database import get_session
from caliper.adapters.repository_sync_factory import build_repository_sync
from caliper.api.auth import require_admin
from caliper.application.repository_sync import (
    KnowledgeDocument,
    ProjectNotFound,
    RepositorySourceChanged,
    RepositorySync,
    SyncAlreadyRunning,
    TaskQueueFull,
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
    task_id: UUID | None


class KnowledgeOutput(BaseModel):
    path: str
    revision: str
    sha256: str
    content: str
    synced_at: datetime


def service(session: Annotated[AsyncSession, Depends(get_session)]) -> RepositorySync:
    return build_repository_sync(session)


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


@router.post("/sync", response_model=SyncOutput, status_code=status.HTTP_202_ACCEPTED)
async def run_sync(
    project_id: UUID,
    sync: Annotated[RepositorySync, Depends(service)],
    payload: SyncInput = EMPTY_SYNC_INPUT,
) -> SyncOutput:
    try:
        return SyncOutput.model_validate(await sync.enqueue(project_id, payload.credential_id))
    except ProjectNotFound as error:
        raise HTTPException(status_code=404, detail="Project not found") from error
    except (RepositorySourceChanged, SyncAlreadyRunning) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except TaskQueueFull as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
    except (ValueError, LookupError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
