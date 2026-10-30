"""Reusable FastAPI dependencies: authentication, authorization, pagination."""

from __future__ import annotations

from typing import Optional, Sequence

from fastapi import Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.enums import Role
from app.core.errors import forbidden, not_found, unauthorized
from app.core.security import decode_access_token
from app.models.project import Project
from app.models.user import ProjectMember, User

AUTH_COOKIE = "hcaliper_session"
CSRF_COOKIE = "hcaliper_csrf"
CSRF_HEADER = "x-csrf-token"


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    token = request.cookies.get(AUTH_COOKIE)
    if not token:
        header = request.headers.get("authorization", "")
        if header.lower().startswith("bearer "):
            token = header[7:].strip()
    if not token:
        raise unauthorized()
    try:
        payload = decode_access_token(token)
    except Exception:
        raise unauthorized("Session expired or invalid")
    user_id = payload.get("sub")
    if not user_id:
        raise unauthorized("Session expired or invalid")
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise unauthorized("Account is disabled")
    return user


def require_roles(*roles: Role):
    allowed = {r.value for r in roles}

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise forbidden("Your role does not allow this operation")
        return user

    return dependency


require_admin = require_roles(Role.ADMIN)
require_operator = require_roles(Role.ADMIN, Role.OPERATOR)


async def get_owned_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    write: bool = False,
) -> Project:
    project = await db.get(Project, project_id)
    if not project:
        raise not_found("Project")
    if user.role == Role.ADMIN.value:
        return project
    member = (
        await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id, ProjectMember.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if not member:
        raise forbidden("You do not have access to this project")
    if write and member.role not in {Role.ADMIN.value, Role.OPERATOR.value}:
        raise forbidden("Project role does not allow this operation")
    return project


async def ensure_project_access(
    db: AsyncSession, user: User, project_id: str, write: bool = False
) -> Project:
    project = await db.get(Project, project_id)
    if not project:
        raise not_found("Project")
    if user.role == Role.ADMIN.value:
        return project
    member = (
        await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if not member:
        raise forbidden("You do not have access to this project")
    if write and member.role not in {Role.ADMIN.value, Role.OPERATOR.value}:
        raise forbidden("Project role does not allow this operation")
    return project


async def accessible_project_ids(db: AsyncSession, user: User) -> Optional[Sequence[str]]:
    """Return None when the user can access every project."""
    if user.role == Role.ADMIN.value:
        return None
    rows = await db.execute(
        select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)
    )
    return [r for r in rows.scalars().all()]


class Pagination:
    def __init__(
        self,
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=25, ge=1, le=200),
    ) -> None:
        self.page = page
        self.page_size = page_size
        self.offset = (page - 1) * page_size
        self.limit = page_size
