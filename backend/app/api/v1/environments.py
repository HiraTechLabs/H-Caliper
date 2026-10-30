from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    get_current_user,
    get_owned_project,
    require_operator,
)
from app.core.errors import not_found
from app.models.project import Environment, Project
from app.models.user import User
from app.schemas import EnvironmentCreate, EnvironmentOut, EnvironmentUpdate
from app.services import project_service
from app.services.audit import audit

router = APIRouter(tags=["environments"])


@router.get("/projects/{project_id}/environments", response_model=list[EnvironmentOut])
async def list_environments(
    project: Project = Depends(get_owned_project),
    db: AsyncSession = Depends(get_db),
) -> list[Environment]:
    return list(
        (
            await db.execute(
                select(Environment)
                .where(Environment.project_id == project.id)
                .order_by(Environment.kind, Environment.name)
            )
        )
        .scalars()
        .all()
    )


@router.post(
    "/projects/{project_id}/environments", response_model=EnvironmentOut, status_code=201
)
async def create_environment(
    payload: EnvironmentCreate,
    project: Project = Depends(get_owned_project),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_operator),
) -> Environment:
    return await project_service.create_environment(db, project, payload, user)


@router.patch("/environments/{environment_id}", response_model=EnvironmentOut)
async def update_environment(
    environment_id: str,
    payload: EnvironmentUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_operator),
) -> Environment:
    env = await db.get(Environment, environment_id)
    if not env:
        raise not_found("Environment")
    await get_owned_project(env.project_id, user, db, write=True)
    data = payload.model_dump(exclude_unset=True)
    if env.kind == "PRODUCTION" and data.get("deployment_enabled"):
        if user.role != "ADMIN":
            from app.core.errors import forbidden

            raise forbidden("Only an administrator can enable production deployment")
    for key, value in data.items():
        setattr(env, key, value)
    await audit(
        db,
        action="environment.update",
        entity_type="environment",
        actor_type="user",
        actor_id=user.email,
        entity_id=env.id,
        detail={k: v for k, v in data.items() if k not in {"secrets"}},
    )
    await db.commit()
    await db.refresh(env)
    return env


@router.post("/environments/{environment_id}/check", response_model=dict)
async def check_environment(
    environment_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    env = await db.get(Environment, environment_id)
    if not env:
        raise not_found("Environment")
    await get_owned_project(env.project_id, user, db, write=False)
    return await project_service.check_environment(db, env)


@router.delete("/environments/{environment_id}", status_code=204, response_class=Response, response_model=None)
async def delete_environment(
    environment_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_operator),
) -> None:
    env = await db.get(Environment, environment_id)
    if not env:
        raise not_found("Environment")
    await get_owned_project(env.project_id, user, db, write=True)
    await db.delete(env)
    await audit(
        db,
        action="environment.delete",
        entity_type="environment",
        actor_type="user",
        actor_id=user.email,
        entity_id=environment_id,
    )
    await db.commit()
