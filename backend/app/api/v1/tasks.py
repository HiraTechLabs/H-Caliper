from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    Pagination,
    accessible_project_ids,
    get_current_user,
    get_owned_project,
    require_operator,
)
from app.core.errors import not_found
from app.models.project import Project
from app.models.task import (
    AgentExecution,
    Artifact,
    DocumentationRecord,
    PipelineStage,
    Plan,
    QualityGateResult,
    Review,
    Task,
    TaskEvent,
)
from app.models.user import User
from app.schemas import (
    AgentExecutionOut,
    ArtifactDetail,
    ArtifactOut,
    DocumentationOut,
    GateOut,
    PlanOut,
    ReviewOut,
    StageOut,
    TaskCancel,
    TaskCreate,
    TaskDetail,
    TaskEventOut,
    TaskOut,
    TaskSummary,
)
from app.services import task_service
from app.services.audit import audit
from app.services.deployment_service import request_deployment

router = APIRouter(tags=["tasks"])


async def _load_task(db: AsyncSession, task_id: str, user: User, *, write: bool = False) -> Task:
    task = await db.get(Task, task_id)
    if not task:
        raise not_found("Task")
    await get_owned_project(task.project_id, user, db, write=write)
    return task


@router.post("/tasks", response_model=TaskOut, status_code=201)
async def create_task(
    payload: TaskCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_operator),
) -> Task:
    project = await get_owned_project(payload.project_id, user, db, write=True)
    task = await task_service.create_task(db, project, payload, user)
    await audit(
        db,
        action="task.submit",
        entity_type="task",
        actor_type="user",
        actor_id=user.email,
        entity_id=task.id,
        detail={"project_id": project.id, "title": task.title},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return task


@router.get("/tasks")
async def list_tasks(
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    pagination: Pagination = Depends(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    ids = await accessible_project_ids(db, user)
    query = select(Task, Project).join(Project, Project.id == Task.project_id)
    count_query = select(func.count(Task.id)).select_from(Task)
    filters = []
    if ids is not None:
        filters.append(Task.project_id.in_(ids))
    if project_id:
        await get_owned_project(project_id, user, db, write=False)
        filters.append(Task.project_id == project_id)
    if status:
        filters.append(Task.status == status)
    if search:
        filters.append(
            or_(Task.title.ilike(f"%{search}%"), Task.description.ilike(f"%{search}%"))
        )
    for item in filters:
        query = query.where(item)
        count_query = count_query.where(item)
    total = (await db.execute(count_query)).scalar_one()
    rows = (
        await db.execute(
            query.order_by(Task.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
    ).all()
    return {
        "items": [
            TaskSummary(
                **TaskOut.model_validate(task).model_dump(),
                project_name=project.name,
                project_slug=project.slug,
            ).model_dump()
            for task, project in rows
        ],
        "total": total,
        "page": pagination.page,
        "page_size": pagination.page_size,
    }


@router.get("/tasks/{task_id}", response_model=TaskDetail)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskDetail:
    task = await _load_task(db, task_id, user)
    project = await db.get(Project, task.project_id)
    plan = (
        await db.execute(
            select(Plan).where(Plan.task_id == task.id).order_by(Plan.version.desc()).limit(1)
        )
    ).scalar_one_or_none()
    review = (
        await db.execute(
            select(Review)
            .where(Review.task_id == task.id)
            .order_by(Review.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    documentation = (
        await db.execute(
            select(DocumentationRecord)
            .where(DocumentationRecord.task_id == task.id)
            .order_by(DocumentationRecord.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    stages = list(
        (
            await db.execute(
                select(PipelineStage)
                .where(PipelineStage.task_id == task.id)
                .order_by(PipelineStage.started_at)
            )
        )
        .scalars()
        .all()
    )
    agent_runs = list(
        (
            await db.execute(
                select(AgentExecution)
                .where(AgentExecution.task_id == task.id)
                .order_by(AgentExecution.created_at)
            )
        )
        .scalars()
        .all()
    )
    gates = list(
        (
            await db.execute(
                select(QualityGateResult)
                .where(QualityGateResult.task_id == task.id)
                .order_by(QualityGateResult.created_at)
            )
        )
        .scalars()
        .all()
    )
    artifacts = list(
        (
            await db.execute(
                select(Artifact)
                .where(Artifact.task_id == task.id)
                .order_by(Artifact.created_at)
            )
        )
        .scalars()
        .all()
    )
    diff_artifact = next((a for a in reversed(artifacts) if a.kind == "diff"), None)
    return TaskDetail(
        **TaskOut.model_validate(task).model_dump(),
        project_name=project.name if project else "",
        project_slug=project.slug if project else "",
        plan=PlanOut.model_validate(plan) if plan else None,
        review=ReviewOut.model_validate(review) if review else None,
        documentation=DocumentationOut.model_validate(documentation) if documentation else None,
        stages=[StageOut.model_validate(s) for s in stages],
        agent_executions=[AgentExecutionOut.model_validate(a) for a in agent_runs],
        gates=[GateOut.model_validate(g) for g in gates],
        artifacts=[ArtifactOut.model_validate(a) for a in artifacts],
        diff=diff_artifact.content if diff_artifact else None,
    )


@router.get("/tasks/{task_id}/events", response_model=list[TaskEventOut])
async def get_task_events(
    task_id: str,
    after: Optional[str] = None,
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TaskEvent]:
    await _load_task(db, task_id, user)
    query = select(TaskEvent).where(TaskEvent.task_id == task_id)
    if after:
        from datetime import datetime

        try:
            query = query.where(TaskEvent.created_at > datetime.fromisoformat(after))
        except ValueError:
            pass
    rows = (
        await db.execute(query.order_by(TaskEvent.created_at.desc()).limit(limit))
    ).scalars().all()
    return list(reversed(rows))


@router.get("/tasks/{task_id}/artifacts/{artifact_id}", response_model=ArtifactDetail)
async def get_artifact(
    task_id: str,
    artifact_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Artifact:
    await _load_task(db, task_id, user)
    artifact = await db.get(Artifact, artifact_id)
    if not artifact or artifact.task_id != task_id:
        raise not_found("Artifact")
    return artifact


@router.get("/tasks/{task_id}/diff")
async def get_diff(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    await _load_task(db, task_id, user)
    artifact = (
        await db.execute(
            select(Artifact)
            .where(Artifact.task_id == task_id, Artifact.kind == "diff")
            .order_by(Artifact.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return {"diff": artifact.content if artifact else "", "artifact_id": artifact.id if artifact else None}


@router.post("/tasks/{task_id}/cancel", response_model=TaskOut)
async def cancel_task(
    task_id: str,
    payload: TaskCancel,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_operator),
) -> Task:
    task = await _load_task(db, task_id, user, write=True)
    return await task_service.cancel_task(db, task, user, payload.reason)


@router.post("/tasks/{task_id}/replan", response_model=TaskOut)
async def replan_task(
    task_id: str,
    payload: TaskCancel,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_operator),
) -> Task:
    task = await _load_task(db, task_id, user, write=True)
    return await task_service.replan_task(db, task, user, payload.reason)


@router.post("/tasks/{task_id}/deployments")
async def deploy_task(
    task_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_operator),
) -> dict:
    task = await _load_task(db, task_id, user, write=True)
    environment_id = str(payload.get("environment_id", ""))
    if not environment_id:
        from app.core.errors import bad_request

        raise bad_request("environment_id is required", "environment_required")
    deployment = await request_deployment(db, task, environment_id, user)
    return {
        "id": deployment.id,
        "status": deployment.status,
        "task_id": deployment.task_id,
        "environment_id": deployment.environment_id,
        "detail": deployment.detail,
    }
