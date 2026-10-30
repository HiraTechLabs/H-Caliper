"""Task creation, model resolution, and human approval operations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import (
    AgentRole,
    ApprovalKind,
    ApprovalStatus,
    Capability,
    ProjectStatus,
    ReviewDecision,
    TaskStatus,
)
from app.core.errors import bad_request, conflict, not_found
from app.models.governance import Approval
from app.models.project import Project, RepositoryConnection
from app.models.provider import ProviderModel
from app.models.task import GitOperation, Review, Task
from app.models.user import User
from app.schemas import ModelSelection, TaskCreate
from app.services import git_manager
from app.services.audit import audit, notify
from app.services.providers.registry import get_handle
from app.services.security_context import decrypt_repository_token


async def _resolve_selection(
    db: AsyncSession,
    *,
    project: Project,
    role: AgentRole,
    selection: Optional[ModelSelection],
    task_config: Dict,
) -> Dict[str, Optional[str]]:
    provider_id = selection.provider_id if selection else None
    model = selection.model if selection else None
    default_provider_id = getattr(project, f"default_{role.value.lower()}_provider_id", None)
    default_model = getattr(project, f"default_{role.value.lower()}_model", None)
    if not provider_id:
        provider_id = default_provider_id
    if not model and provider_id == default_provider_id:
        model = default_model
    if not provider_id:
        raise bad_request(
            f"No {role.value.lower()} provider selected and the project has no default. "
            "Configure the project defaults or select a provider.",
            "agent_model_not_configured",
        )
    handle = await get_handle(db, provider_id)
    if role in {AgentRole.PLANNING, AgentRole.REVIEW, AgentRole.DOCUMENTATION} and not handle.adapter.supports(
        Capability.CHAT
    ):
        raise bad_request(
            f"Provider '{handle.record.name}' cannot be used for the {role.value.lower()} agent.",
            "capability_missing",
        )
    if role == AgentRole.EXECUTION and not (
        handle.adapter.supports(Capability.AGENT) or handle.adapter.supports(Capability.CHAT)
    ):
        raise bad_request(
            f"Provider '{handle.record.name}' cannot execute tasks.",
            "capability_missing",
        )
    if not model:
        row = await db.execute(
            select(ProviderModel)
            .where(
                ProviderModel.provider_id == provider_id,
                ProviderModel.enabled.is_(True),
            )
            .order_by(ProviderModel.model_id)
            .limit(1)
        )
        fallback = row.scalar_one_or_none()
        model = fallback.model_id if fallback else None
    else:
        registered = await db.execute(
            select(ProviderModel.id).where(
                ProviderModel.provider_id == provider_id,
                ProviderModel.model_id == model,
                ProviderModel.enabled.is_(True),
            )
        )
        if registered.scalar_one_or_none() is None:
            raise bad_request(
                f"Model '{model}' is not enabled for the selected {role.value.lower()} provider.",
                "model_not_available",
            )
    if not model:
        raise bad_request(
            f"No model selected for the {role.value.lower()} agent on provider "
            f"'{handle.record.name}'.",
            "model_not_configured",
        )
    return {"provider_id": provider_id, "model": model}


async def create_task(
    db: AsyncSession, project: Project, payload: TaskCreate, actor: User
) -> Task:
    if project.status != ProjectStatus.ACTIVE.value:
        raise conflict("Project is archived", "project_archived")
    repo_row = await db.execute(
        select(RepositoryConnection).where(RepositoryConnection.project_id == project.id)
    )
    if not repo_row.scalar_one_or_none():
        raise bad_request(
            "Connect a Git repository before creating tasks",
            "repository_not_configured",
        )
    agents: Dict[str, Dict] = {}
    for role, selection in (
        (AgentRole.PLANNING, payload.planning),
        (AgentRole.EXECUTION, payload.execution),
        (AgentRole.REVIEW, payload.review),
        (AgentRole.DOCUMENTATION, payload.documentation),
    ):
        agents[role.value.lower()] = await _resolve_selection(
            db, project=project, role=role, selection=selection, task_config={}
        )
    max_retries = payload.max_retries if payload.max_retries is not None else project.max_retries
    task = Task(
        project_id=project.id,
        title=payload.title,
        description=payload.description,
        status=TaskStatus.CREATED.value,
        created_by=actor.id,
        max_retries=max_retries,
        config={
            "agents": agents,
            "validation_requirements": payload.validation_requirements or {},
        },
    )
    db.add(task)
    await db.flush()
    await audit(
        db,
        action="task.create",
        entity_type="task",
        actor_type="user",
        actor_id=actor.email,
        entity_id=task.id,
        detail={"project_id": project.id, "title": task.title, "models": agents},
    )
    await db.commit()
    await db.refresh(task)
    return task


async def cancel_task(db: AsyncSession, task: Task, actor: User, reason: str) -> Task:
    if task.status in {
        TaskStatus.COMPLETED.value,
        TaskStatus.CANCELLED.value,
        TaskStatus.FAILED.value,
    }:
        raise conflict("Task is already finished", "task_finished")
    task.cancel_requested = True
    task.error = (reason or "Cancelled by user")[:4000]
    await audit(
        db,
        action="task.cancel_request",
        entity_type="task",
        actor_type="user",
        actor_id=actor.email,
        entity_id=task.id,
        detail={"reason": reason},
    )
    await db.commit()
    await db.refresh(task)
    return task


async def replan_task(db: AsyncSession, task: Task, actor: User, reason: str) -> Task:
    if task.status not in {
        TaskStatus.BLOCKED.value,
        TaskStatus.FAILED.value,
        TaskStatus.AWAITING_APPROVAL.value,
    }:
        raise conflict(
            "Only blocked, failed or awaiting-approval tasks can be sent back to planning",
            "task_not_replannable",
        )
    if task.retry_count > task.max_retries:
        raise conflict("Retry limit reached; increase the task retry limit first", "retry_limit")
    task.status = TaskStatus.REPLANNING.value
    task.current_stage = "REPLANNING"
    task.error = None
    task.cancel_requested = False
    await notify(
        db,
        user_id=task.created_by,
        title=f"Task returned to planning: {task.title}",
        body=reason[:1000],
        level="WARNING",
        task_id=task.id,
    )
    await audit(
        db,
        action="task.replan",
        entity_type="task",
        actor_type="user",
        actor_id=actor.email,
        entity_id=task.id,
        detail={"reason": reason},
    )
    await db.commit()
    await db.refresh(task)
    return task


async def decide_approval(
    db: AsyncSession,
    approval: Approval,
    *,
    approve: bool,
    notes: str,
    actor: User,
) -> Approval:
    if approval.status != ApprovalStatus.PENDING.value:
        raise conflict("Approval has already been decided", "approval_already_decided")
    approval.status = (
        ApprovalStatus.APPROVED.value if approve else ApprovalStatus.REJECTED.value
    )
    approval.decided_by = actor.email
    approval.decided_at = datetime.now(timezone.utc)
    approval.notes = (approval.notes or "") + ("\n" + notes if notes else "")
    task = await db.get(Task, approval.task_id) if approval.task_id else None
    if not task:
        raise not_found("Task")
    await audit(
        db,
        action="approval.decide",
        entity_type="approval",
        actor_type="user",
        actor_id=actor.email,
        entity_id=approval.id,
        detail={"approve": approve, "kind": approval.kind, "task_id": task.id},
    )
    if not approve:
        task.status = TaskStatus.BLOCKED.value
        task.current_stage = "APPROVAL_REJECTED"
        task.error = ("Human approval rejected: " + notes)[:4000]
        await notify(
            db,
            user_id=task.created_by,
            title=f"Task blocked by approval decision: {task.title}",
            body=notes[:1000],
            level="WARNING",
            task_id=task.id,
        )
        await db.commit()
        return approval

    if approval.kind == ApprovalKind.MERGE.value:
        if task.status != TaskStatus.AWAITING_APPROVAL.value:
            raise conflict(
                f"Task is not awaiting approval (status={task.status})",
                "task_not_awaiting_approval",
            )
        project = await db.get(Project, task.project_id)
        repo_row = await db.execute(
            select(RepositoryConnection).where(RepositoryConnection.project_id == project.id)
        )
        repo = repo_row.scalar_one_or_none()
        if not repo:
            raise conflict("Repository connection is missing", "repository_missing")
        mirror = f"{settings.WORKSPACE_ROOT}/{project.slug}/repository"
        token = decrypt_repository_token(repo)
        merge_sha = None
        error = None
        try:
            link_row = await db.execute(
                select(Review)
                .where(
                    Review.task_id == task.id,
                    Review.decision == ReviewDecision.ACCEPTED.value,
                )
                .order_by(Review.created_at.desc())
                .limit(1)
            )
            if not link_row.scalar_one_or_none():
                raise conflict(
                    "No accepted review exists for this task; merging is not allowed",
                    "review_not_accepted",
                )
            await git_manager.fetch(mirror, token=token)
            merge_sha = await git_manager.merge_into_default(
                mirror,
                task.branch,
                project.default_branch,
                push=bool(project.settings.get("push_on_merge", False)),
                token=token,
            )
            task.head_commit = merge_sha
        except Exception as exc:
            error = str(exc)
        db.add(
            GitOperation(
                task_id=task.id,
                project_id=project.id,
                operation="merge",
                status="FAILED" if error else "SUCCEEDED",
                detail={"sha": merge_sha, "error": error},
            )
        )
        if error:
            task.error = f"Merge failed: {error}"[:4000]
            await audit(
                db,
                action="task.merge_failed",
                entity_type="task",
                actor_id=actor.email,
                entity_id=task.id,
                detail={"error": error[:2000]},
            )
            await db.commit()
            raise bad_request(
                f"Merge failed: {error}", "merge_failed"
            )
        task.status = TaskStatus.RELEASE_READY.value
        task.current_stage = "RELEASE_READY"
        task.completed_at = datetime.now(timezone.utc)
        await notify(
            db,
            user_id=task.created_by,
            title=f"Task release ready: {task.title}",
            body=f"Merged as {merge_sha}",
            level="INFO",
            task_id=task.id,
        )
        await db.commit()
        return approval
