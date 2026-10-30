"""Project, repository, and environment application services."""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    ConnectionType,
    EnvironmentKind,
    ProjectStatus,
    Role,
)
from app.core.errors import bad_request, conflict, not_found
from app.core.security import encrypt_secret
from app.models.project import (
    Environment,
    Project,
    RepositoryConnection,
    Workspace,
)
from app.models.user import ProjectMember, User
from app.schemas import EnvironmentCreate, ProjectCreate, ProjectUpdate
from app.services import caliper_service, git_manager, workspace as workspace_service
from app.services.audit import audit


async def create_project(
    db: AsyncSession, payload: ProjectCreate, owner: User
) -> Project:
    slug = payload.slug or workspace_service.slugify(payload.name)
    workspace_service.validate_slug(slug)
    existing = (
        await db.execute(select(Project).where(Project.slug == slug))
    ).scalar_one_or_none()
    if existing:
        raise conflict(f"Project slug '{slug}' is already in use", "slug_exists")

    repository_url = payload.repository_url
    token = payload.repository_token
    if repository_url:
        repository_url = git_manager.validate_repository_url(repository_url)

    project = Project(
        slug=slug,
        name=payload.name,
        description=payload.description,
        status=ProjectStatus.ACTIVE.value,
        owner_id=owner.id,
        max_retries=payload.max_retries,
        default_branch=payload.default_branch,
        quality_gates=payload.quality_gates,
        settings={},
    )
    db.add(project)
    await db.flush()
    db.add(
        ProjectMember(
            project_id=project.id, user_id=owner.id, role=Role.OPERATOR.value
        )
    )

    if repository_url:
        github = git_manager.parse_github(repository_url)
        db.add(
            RepositoryConnection(
                project_id=project.id,
                provider="github" if github else "generic",
                url=repository_url,
                auth_type=payload.repository_auth_type,
                secret_encrypted=encrypt_secret(token),
                default_branch=payload.default_branch,
                github_owner=github[0] if github else None,
                github_repo=github[1] if github else None,
            )
        )
    await caliper_service.seed_project_caliper(db, project.id, author=owner.email)
    db.add(
        Environment(
            project_id=project.id,
            kind=EnvironmentKind.DEVELOPMENT.value,
            name="Local development",
            connection_type=ConnectionType.LOCAL.value,
            config={"workspaces": True},
            is_active=True,
            requires_approval=False,
        )
    )
    db.add(
        Workspace(
            project_id=project.id,
            name="default",
            storage_path=workspace_service.project_path(slug),
            storage_backend="local",
            status="READY",
        )
    )
    await db.flush()

    if repository_url:
        try:
            await workspace_service.ensure_project_workspace(
                slug,
                repository_url=repository_url,
                token=token,
                default_branch=payload.default_branch,
            )
        except Exception as exc:
            await db.rollback()
            shutil.rmtree(workspace_service.project_path(slug), ignore_errors=True)
            raise bad_request(
                f"Could not clone the repository: {exc}", "repository_clone_failed"
            ) from exc
    else:
        await workspace_service.ensure_project_workspace(
            slug,
            repository_url=None,
            token=None,
            default_branch=payload.default_branch,
        )

    await audit(
        db,
        action="project.create",
        entity_type="project",
        actor_type="user",
        actor_id=owner.email,
        entity_id=project.id,
        detail={"slug": slug, "repository": bool(repository_url)},
    )
    await db.commit()
    await db.refresh(project)
    return project


async def update_project(
    db: AsyncSession, project: Project, payload: ProjectUpdate, actor: User
) -> Project:
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key in {"quality_gates", "settings"} and value is None:
            continue
        setattr(project, key, value)
    await audit(
        db,
        action="project.update",
        entity_type="project",
        actor_type="user",
        actor_id=actor.email,
        entity_id=project.id,
        detail={k: v for k, v in data.items() if k != "settings"},
    )
    await db.commit()
    await db.refresh(project)
    return project


async def update_repository(
    db: AsyncSession,
    project: Project,
    *,
    url: str,
    auth_type: str,
    token: Optional[str],
    default_branch: str,
    actor: User,
) -> RepositoryConnection:
    url = git_manager.validate_repository_url(url)
    row = await db.execute(
        select(RepositoryConnection).where(RepositoryConnection.project_id == project.id)
    )
    repo = row.scalar_one_or_none()
    github = git_manager.parse_github(url)
    if not repo:
        repo = RepositoryConnection(project_id=project.id, url=url)
        db.add(repo)
    repo.url = url
    repo.auth_type = auth_type
    repo.default_branch = default_branch
    repo.provider = "github" if github else "generic"
    repo.github_owner = github[0] if github else None
    repo.github_repo = github[1] if github else None
    if token is not None:
        repo.secret_encrypted = encrypt_secret(token)
    project.default_branch = default_branch
    await db.flush()
    await workspace_service.ensure_project_workspace(
        project.slug, repository_url=url, token=token, default_branch=default_branch
    )
    await audit(
        db,
        action="repository.update",
        entity_type="project",
        actor_type="user",
        actor_id=actor.email,
        entity_id=project.id,
        detail={"url": url, "auth_type": auth_type},
    )
    await db.commit()
    await db.refresh(repo)
    return repo


async def add_member(
    db: AsyncSession, project: Project, user_id: str, role: Role, actor: User
) -> ProjectMember:
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise not_found("User")
    existing = (
        await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id, ProjectMember.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.role = role.value
        member = existing
    else:
        member = ProjectMember(project_id=project.id, user_id=user_id, role=role.value)
        db.add(member)
    await audit(
        db,
        action="project.member_update",
        entity_type="project",
        actor_type="user",
        actor_id=actor.email,
        entity_id=project.id,
        detail={"user_id": user_id, "role": role.value},
    )
    await db.commit()
    return member


async def create_environment(
    db: AsyncSession, project: Project, payload: EnvironmentCreate, actor: User
) -> Environment:
    if payload.kind == EnvironmentKind.PRODUCTION.value:
        # Production is registered disabled unless an administrator opts in.
        env = Environment(
            project_id=project.id,
            kind=payload.kind,
            name=payload.name,
            connection_type=payload.connection_type,
            config=payload.config,
            is_active=payload.is_active,
            deployment_enabled=False,
            requires_approval=True,
        )
    else:
        env = Environment(
            project_id=project.id,
            kind=payload.kind,
            name=payload.name,
            connection_type=payload.connection_type,
            config=payload.config,
            is_active=payload.is_active,
            deployment_enabled=payload.deployment_enabled,
            requires_approval=payload.requires_approval,
        )
    db.add(env)
    await db.flush()
    await audit(
        db,
        action="environment.create",
        entity_type="environment",
        actor_type="user",
        actor_id=actor.email,
        entity_id=env.id,
        detail={"kind": payload.kind, "name": payload.name, "type": payload.connection_type},
    )
    await db.commit()
    await db.refresh(env)
    return env


async def check_environment(
    db: AsyncSession, env: Environment
) -> dict:
    if env.connection_type == ConnectionType.LOCAL.value:
        path = workspace_service.project_path(
            (await db.get(Project, env.project_id)).slug
        )
        ok = os.path.isdir(path)
        env.health_status = "HEALTHY" if ok else "UNREACHABLE"
    elif env.connection_type == ConnectionType.DOCKER.value:
        container = env.config.get("container")
        if not container:
            env.health_status = "NOT_CONFIGURED"
        else:
            from app.services.providers.process import run_command

            result = await run_command(
                ["docker", "inspect", "--format", "{{.State.Running}}", str(container)],
                cwd="/tmp",
                timeout=20,
            )
            env.health_status = (
                "HEALTHY" if result.stdout.strip() == "true" else "UNREACHABLE"
            )
    elif env.connection_type == ConnectionType.SSH.value:
        env.health_status = "NOT_CONFIGURED"
    elif env.connection_type == ConnectionType.WEBHOOK.value:
        url = env.config.get("health_url")
        if not url:
            env.health_status = "NOT_CONFIGURED"
        else:
            import httpx

            try:
                async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
                    response = await client.get(url)
                env.health_status = "HEALTHY" if response.status_code < 400 else "DEGRADED"
            except Exception:
                env.health_status = "UNREACHABLE"
    else:
        env.health_status = "NOT_CONFIGURED"
    env.last_checked_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": env.health_status, "checked_at": env.last_checked_at}
