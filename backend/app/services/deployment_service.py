"""Controlled production deployment.

Disabled by default.  Requires an explicit administrator request, a
project-scoped production environment with ``deployment_enabled``, the global
``ALLOW_PRODUCTION_DEPLOYMENT`` switch, and (unless the environment explicitly
disables it) a human DEPLOY approval.  AI agents cannot invoke this service.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import (
    ApprovalKind,
    ApprovalStatus,
    ConnectionType,
    DeploymentStatus,
    EnvironmentKind,
    ReviewDecision,
    TaskStatus,
)
from app.core.errors import bad_request, conflict, forbidden, not_found
from app.models.governance import Approval, Deployment
from app.models.project import Environment, Project
from app.models.task import Review, Task
from app.models.user import User
from app.services.audit import audit, notify
from app.services.providers.base import validate_outbound_url
from app.services.providers.process import run_command


async def request_deployment(
    db: AsyncSession, task: Task, environment_id: str, actor: User
) -> Deployment:
    if task.status not in {TaskStatus.RELEASE_READY.value, TaskStatus.COMPLETED.value}:
        raise conflict(
            "Only a release-ready task can be deployed", "task_not_release_ready"
        )
    if not settings.ALLOW_PRODUCTION_DEPLOYMENT:
        raise forbidden(
            "Production deployment is disabled by server policy "
            "(ALLOW_PRODUCTION_DEPLOYMENT=false)",
            "production_deployment_disabled",
        )
    env = await db.get(Environment, environment_id)
    if not env or env.project_id != task.project_id:
        raise not_found("Production environment")
    if env.kind != EnvironmentKind.PRODUCTION.value:
        raise bad_request("Selected environment is not a production environment", "not_production")
    if not env.is_active or not env.deployment_enabled:
        raise conflict(
            "Production environment is not enabled for deployment", "environment_not_enabled"
        )
    review = (
        await db.execute(
            select(Review)
            .where(
                Review.task_id == task.id,
                Review.decision == ReviewDecision.ACCEPTED.value,
            )
            .order_by(Review.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if not review:
        raise conflict("Task has no accepted review", "review_not_accepted")

    approval = Approval(
        task_id=task.id,
        kind=ApprovalKind.DEPLOY.value,
        requested_by=actor.email,
        status=ApprovalStatus.PENDING.value
        if env.requires_approval
        else ApprovalStatus.APPROVED.value,
        notes=f"Deployment to {env.name}",
        decided_by=actor.email if not env.requires_approval else None,
        decided_at=None if env.requires_approval else datetime.now(timezone.utc),
    )
    db.add(approval)
    await db.flush()
    deployment = Deployment(
        environment_id=env.id,
        task_id=task.id,
        status=DeploymentStatus.PENDING.value,
        approved_by=actor.email if not env.requires_approval else None,
        detail={
            "environment": env.name,
            "approval_id": approval.id,
            "requires_approval": env.requires_approval,
            "connection_type": env.connection_type,
            "commit": task.head_commit,
        },
    )
    db.add(deployment)
    await db.flush()
    await audit(
        db,
        action="deployment.request",
        entity_type="deployment",
        actor_type="user",
        actor_id=actor.email,
        entity_id=deployment.id,
        detail={"task_id": task.id, "environment": env.name},
    )
    await db.commit()
    await db.refresh(deployment)
    if not env.requires_approval:
        await execute_deployment(db, deployment, actor)
        await db.refresh(deployment)
    return deployment


async def approve_and_deploy(
    db: AsyncSession, deployment: Deployment, *, approve: bool, notes: str, actor: User
) -> Deployment:
    if deployment.status != DeploymentStatus.PENDING.value:
        raise conflict("Deployment is not pending", "deployment_not_pending")
    approval_id = (deployment.detail or {}).get("approval_id")
    approval = await db.get(Approval, approval_id) if approval_id else None
    if not approval:
        raise conflict("Deployment has no linked approval", "approval_missing")
    if not approve:
        approval.status = ApprovalStatus.REJECTED.value
        approval.decided_by = actor.email
        approval.decided_at = datetime.now(timezone.utc)
        approval.notes = notes
        deployment.status = DeploymentStatus.BLOCKED.value
        deployment.finished_at = datetime.now(timezone.utc)
        await audit(
            db,
            action="deployment.rejected",
            entity_type="deployment",
            actor_type="user",
            actor_id=actor.email,
            entity_id=deployment.id,
            detail={"notes": notes},
        )
        await db.commit()
        return deployment
    approval.status = ApprovalStatus.APPROVED.value
    approval.decided_by = actor.email
    approval.decided_at = datetime.now(timezone.utc)
    approval.notes = notes
    deployment.status = DeploymentStatus.RUNNING.value
    deployment.approved_by = actor.email
    await db.commit()
    await execute_deployment(db, deployment, actor)
    await db.refresh(deployment)
    return deployment


async def execute_deployment(
    db: AsyncSession, deployment: Deployment, actor: User
) -> Deployment:
    env = await db.get(Environment, deployment.environment_id)
    task = await db.get(Task, deployment.task_id) if deployment.task_id else None
    if not env or not task:
        deployment.status = DeploymentStatus.FAILED.value
        deployment.output = "Environment or task no longer exists"
        deployment.finished_at = datetime.now(timezone.utc)
        await db.commit()
        return deployment
    deployment.status = DeploymentStatus.RUNNING.value
    project = await db.get(Project, task.project_id)
    output = ""
    success = False
    try:
        if env.connection_type == ConnectionType.WEBHOOK.value:
            url = env.config.get("url")
            if not url:
                raise RuntimeError("Webhook URL is not configured")
            validate_outbound_url(url, allow_private=settings.ALLOW_PRIVATE_PROVIDER_HOSTS)
            payload = {
                "task_id": task.id,
                "project": project.slug,
                "commit": task.head_commit,
                "branch": task.branch,
                "environment": env.name,
            }
            async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
                response = await client.post(url, json=payload)
            output = f"Webhook responded HTTP {response.status_code}: {response.text[:2000]}"
            success = 200 <= response.status_code < 300
        elif env.connection_type == ConnectionType.COMMAND.value or env.connection_type == "LOCAL":
            command = env.config.get("command")
            if not command:
                raise RuntimeError(
                    "No deployment command configured; edit the production environment"
                )
            allowed = settings.DEPLOYMENT_COMMAND_ALLOWLIST
            parts = command.split()
            if not allowed or parts[0] not in allowed:
                raise RuntimeError(
                    "Deployment command is not in DEPLOYMENT_COMMAND_ALLOWLIST"
                )
            import shlex

            result = await run_command(
                shlex.split(command),
                cwd=env.config.get("cwd", "/tmp"),
                timeout=int(env.config.get("timeout", 900)),
            )
            output = f"$ {command}\n{result.stdout}\n{result.stderr}"
            success = result.exit_code == 0
        elif env.connection_type == ConnectionType.DOCKER.value:
            raise RuntimeError(
                "Docker deployment is not configured. Register a webhook or an allowlisted "
                "command deployment."
            )
        else:
            raise RuntimeError(
                f"Connection type {env.connection_type} is NOT CONFIGURED for deployment"
            )
    except Exception as exc:
        output = f"Deployment failed: {type(exc).__name__}: {exc}"
        success = False

    deployment.output = output[:20000]
    deployment.status = (
        DeploymentStatus.SUCCEEDED.value if success else DeploymentStatus.FAILED.value
    )
    deployment.finished_at = datetime.now(timezone.utc)
    if success:
        task.status = TaskStatus.COMPLETED.value
        task.current_stage = "COMPLETED"
        task.completed_at = datetime.now(timezone.utc)
    else:
        task.status = TaskStatus.RELEASE_READY.value
        task.error = output[:4000]
    await notify(
        db,
        user_id=task.created_by,
        title=(
            f"Deployment {'succeeded' if success else 'failed'}: {task.title}"
        ),
        body=output[:1000],
        level="INFO" if success else "ERROR",
        task_id=task.id,
    )
    await audit(
        db,
        action="deployment.execute",
        entity_type="deployment",
        actor_type="user",
        actor_id=actor.email,
        entity_id=deployment.id,
        detail={"success": success, "environment": env.name, "task_id": task.id},
    )
    await db.commit()
    return deployment
