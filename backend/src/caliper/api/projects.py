from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from caliper.adapters.postgres.database import get_session
from caliper.adapters.postgres.project_repository import SqlProjectRepository
from caliper.api.auth import require_admin
from caliper.application.projects import ProjectNotFound, Projects
from caliper.domain.project import Project, ProjectNameRequired

router = APIRouter(prefix="/api/projects", tags=["projects"], dependencies=[Depends(require_admin)])


class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    repository_url: str | None = Field(default=None, max_length=2048)
    default_branch: str = Field(default="main", min_length=1, max_length=255)

    @field_validator("repository_url")
    @classmethod
    def valid_repository_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("https://", "ssh://", "git@")):
            raise ValueError("Repository URL must use HTTPS or SSH")
        return value

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Project name cannot be blank")
        return value


class ProjectOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str
    repository_url: str | None
    default_branch: str
    created_at: datetime
    updated_at: datetime


def service(session: Annotated[AsyncSession, Depends(get_session)]) -> Projects:
    return Projects(SqlProjectRepository(session))


@router.get("", response_model=list[ProjectOutput])
async def list_projects(projects: Annotated[Projects, Depends(service)]) -> list[Project]:
    return await projects.list()


@router.post("", response_model=ProjectOutput, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectInput, projects: Annotated[Projects, Depends(service)]
) -> Project:
    try:
        return await projects.create(**payload.model_dump())
    except ProjectNameRequired as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/{project_id}", response_model=ProjectOutput)
async def get_project(project_id: UUID, projects: Annotated[Projects, Depends(service)]) -> Project:
    try:
        return await projects.get(project_id)
    except ProjectNotFound as error:
        raise HTTPException(status_code=404, detail="Project not found") from error


@router.put("/{project_id}", response_model=ProjectOutput)
async def update_project(
    project_id: UUID, payload: ProjectInput, projects: Annotated[Projects, Depends(service)]
) -> Project:
    try:
        return await projects.update(project_id, **payload.model_dump())
    except ProjectNotFound as error:
        raise HTTPException(status_code=404, detail="Project not found") from error
    except ProjectNameRequired as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID, projects: Annotated[Projects, Depends(service)]
) -> Response:
    try:
        await projects.delete(project_id)
    except ProjectNotFound as error:
        raise HTTPException(status_code=404, detail="Project not found") from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
