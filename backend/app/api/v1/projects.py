from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    accessible_project_ids,
    get_current_user,
    get_owned_project,
    ensure_project_access,
    require_admin,
    require_operator,
)
from app.core.enums import ProjectStatus
from app.core.errors import not_found
from app.models.project import Project, RepositoryConnection, Workspace
from app.models.user import ProjectMember, User
from app.schemas import (
    MemberCreate,
    ProjectCreate,
    ProjectDetail,
    ProjectMemberOut,
    ProjectOut,
    ProjectUpdate,
    RepositoryOut,
    WorkspaceOut,
)
from app.services import project_service
from app.services.audit import audit

router = APIRouter(prefix="/projects", tags=["projects"])


def _detail(project: Project, repo: Optional[RepositoryConnection], workspaces) -> ProjectDetail:
    return ProjectDetail(
        **ProjectOut.model_validate(project).model_dump(),
        repository=RepositoryOut.model_validate(repo) if repo else None,
        workspaces=[WorkspaceOut.model_validate(w) for w in workspaces],
    )


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    status: Optional[str] = Query(default=None, pattern=r"^(ACTIVE|ARCHIVED)$"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Project]:
    ids = await accessible_project_ids(db, user)
    query = select(Project).order_by(Project.created_at.desc())
    if ids is not None:
        query = query.where(Project.id.in_(ids))
    if status:
        query = query.where(Project.status == status)
    return list((await db.execute(query)).scalars().all())


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    payload: ProjectCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_operator),
) -> Project:
    return await project_service.create_project(db, payload, user)


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project(
    project: Project = Depends(get_owned_project),
    db: AsyncSession = Depends(get_db),
) -> ProjectDetail:
    repo = (
        await db.execute(
            select(RepositoryConnection).where(RepositoryConnection.project_id == project.id)
        )
    ).scalar_one_or_none()
    workspaces = (
        (
            await db.execute(
                select(Workspace).where(Workspace.project_id == project.id)
            )
        )
        .scalars()
        .all()
    )
    return _detail(project, repo, workspaces)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    payload: ProjectUpdate,
    project: Project = Depends(get_owned_project),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_operator),
) -> Project:
    await ensure_project_access(db, user, project.id, write=True)
    return await project_service.update_project(db, project, payload, user)


@router.delete("/{project_id}", status_code=204, response_class=Response, response_model=None)
async def archive_project(
    project: Project = Depends(get_owned_project),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
) -> None:
    project.status = ProjectStatus.ARCHIVED.value
    await audit(
        db,
        action="project.archive",
        entity_type="project",
        actor_type="user",
        actor_id=user.email,
        entity_id=project.id,
    )
    await db.commit()


@router.put("/{project_id}/repository", response_model=RepositoryOut)
async def set_repository(
    project_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_operator),
) -> RepositoryConnection:
    project = await get_owned_project(project_id, user, db, write=True)
    from app.core.errors import bad_request

    url = str(payload.get("url", "")).strip()
    if not url:
        raise bad_request("Repository URL is required", "repository_url_required")
    return await project_service.update_repository(
        db,
        project,
        url=url,
        auth_type=str(payload.get("auth_type", "none")),
        token=payload.get("token"),
        default_branch=str(payload.get("default_branch", project.default_branch)),
        actor=user,
    )


@router.get("/{project_id}/members", response_model=list[ProjectMemberOut])
async def list_members(
    project: Project = Depends(get_owned_project),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectMemberOut]:
    rows = (
        await db.execute(
            select(ProjectMember, User)
            .join(User, User.id == ProjectMember.user_id)
            .where(ProjectMember.project_id == project.id)
        )
    ).all()
    return [
        ProjectMemberOut(
            id=member.id,
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=member.role,
        )
        for member, user in rows
    ]


@router.post("/{project_id}/members", response_model=ProjectMemberOut, status_code=201)
async def add_member(
    payload: MemberCreate,
    project: Project = Depends(get_owned_project),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
) -> ProjectMemberOut:
    member = await project_service.add_member(
        db, project, payload.user_id, payload.role, user
    )
    member_user = await db.get(User, member.user_id)
    return ProjectMemberOut(
        id=member.id,
        user_id=member.user_id,
        email=member_user.email,
        full_name=member_user.full_name,
        role=member.role,
    )


@router.delete("/{project_id}/members/{member_id}", status_code=204, response_class=Response, response_model=None)
async def remove_member(
    member_id: str,
    project: Project = Depends(get_owned_project),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
) -> None:
    member = await db.get(ProjectMember, member_id)
    if not member or member.project_id != project.id:
        raise not_found("Project member")
    if member.user_id == project.owner_id:
        from app.core.errors import conflict

        raise conflict("The project owner cannot be removed", "owner_removal")
    await db.delete(member)
    await audit(
        db,
        action="project.member_remove",
        entity_type="project",
        actor_type="user",
        actor_id=user.email,
        entity_id=project.id,
        detail={"member_id": member_id},
    )
    await db.commit()
