from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import accessible_project_ids, get_current_user
from app.core.enums import GateStatus, TaskStatus
from app.models.project import Project
from app.models.provider import Provider
from app.models.task import QualityGateResult, Task, TaskEvent
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def dashboard(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    project_ids = await accessible_project_ids(db, user)
    project_query = select(Project)
    task_query = select(Task)
    if project_ids is not None:
        project_query = project_query.where(Project.id.in_(project_ids))
        task_query = task_query.where(Task.project_id.in_(project_ids))

    projects = (await db.execute(project_query)).scalars().all()
    tasks = (await db.execute(task_query)).scalars().all()
    status_counts = Counter(task.status for task in tasks)
    active_states = {
        TaskStatus.CONTEXT_COLLECTION.value,
        TaskStatus.PLANNING.value,
        TaskStatus.PLAN_REVIEW.value,
        TaskStatus.READY_FOR_EXECUTION.value,
        TaskStatus.EXECUTING.value,
        TaskStatus.AUTOMATED_VALIDATION.value,
        TaskStatus.AI_REVIEW.value,
        TaskStatus.REPLANNING.value,
        TaskStatus.DOCUMENTATION.value,
        TaskStatus.RELEASE_READY.value,
        TaskStatus.DEPLOYING.value,
    }
    providers = (await db.execute(select(Provider).order_by(Provider.name))).scalars().all()

    task_ids = [t.id for t in tasks]
    gates = []
    if task_ids:
        gates = (
            (
                await db.execute(
                    select(QualityGateResult).where(QualityGateResult.task_id.in_(task_ids))
                )
            )
            .scalars()
            .all()
        )
    gate_counts = Counter(g.status for g in gates)

    recent_events = []
    if task_ids:
        recent_events = (
            (
                await db.execute(
                    select(TaskEvent)
                    .where(TaskEvent.task_id.in_(task_ids))
                    .order_by(TaskEvent.created_at.desc())
                    .limit(20)
                )
            )
            .scalars()
            .all()
        )

    awaiting_approval = []
    if task_ids:
        awaiting_approval = (
            (
                await db.execute(
                    select(Task)
                    .where(Task.status == TaskStatus.AWAITING_APPROVAL.value)
                    .order_by(Task.updated_at.desc())
                    .limit(10)
                )
            )
            .scalars()
            .all()
        )

    # Last 7 days of task creation, for the activity chart.
    now = datetime.now(timezone.utc)
    daily = []
    for offset in range(6, -1, -1):
        day = (now - timedelta(days=offset)).date()
        count = sum(1 for t in tasks if t.created_at.date() == day)
        daily.append({"date": day.isoformat(), "count": count})

    return {
        "projects": {
            "total": len(projects),
            "active": sum(1 for p in projects if p.status == "ACTIVE"),
        },
        "tasks": {
            "total": len(tasks),
            "active": sum(1 for t in tasks if t.status in active_states),
            "completed": status_counts.get(TaskStatus.COMPLETED.value, 0)
            + status_counts.get(TaskStatus.RELEASE_READY.value, 0),
            "failed": status_counts.get(TaskStatus.FAILED.value, 0),
            "blocked": status_counts.get(TaskStatus.BLOCKED.value, 0),
            "awaiting_approval": status_counts.get(TaskStatus.AWAITING_APPROVAL.value, 0),
            "by_status": dict(status_counts),
        },
        "providers": {
            "total": len(providers),
            "healthy": sum(1 for p in providers if p.status == "HEALTHY"),
            "items": [
                {
                    "id": p.id,
                    "name": p.name,
                    "type": p.type,
                    "status": p.status,
                    "enabled": p.enabled,
                    "last_checked_at": p.last_checked_at,
                }
                for p in providers
            ],
        },
        "gates": {
            "by_status": dict(gate_counts),
            "passed": gate_counts.get(GateStatus.PASSED.value, 0),
            "failed": gate_counts.get(GateStatus.FAILED.value, 0),
            "warning": gate_counts.get(GateStatus.WARNING.value, 0),
            "not_configured": gate_counts.get(GateStatus.NOT_CONFIGURED.value, 0),
        },
        "recent_activity": [
            {
                "id": e.id,
                "task_id": e.task_id,
                "event_type": e.event_type,
                "severity": e.severity,
                "message": e.message,
                "created_at": e.created_at,
            }
            for e in recent_events
        ],
        "awaiting_approval": [
            {
                "id": t.id,
                "title": t.title,
                "project_id": t.project_id,
                "updated_at": t.updated_at,
            }
            for t in awaiting_approval
        ],
        "activity_7d": daily,
    }
