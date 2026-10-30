from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import Pagination, accessible_project_ids, get_current_user, require_admin
from app.core.errors import conflict, not_found
from app.models.governance import Approval, Deployment
from app.models.task import Task
from app.models.user import User
from app.schemas import (
    ApprovalDecision,
    ApprovalOut,
    DeploymentOut,
)
from app.services import task_service
from app.services.deployment_service import approve_and_deploy

router = APIRouter(tags=["approvals"])


@router.get("/approvals")
async def list_approvals(
    status: Optional[str] = Query(default=None, pattern=r"^(PENDING|APPROVED|REJECTED)$"),
    task_id: Optional[str] = None,
    pagination: Pagination = Depends(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    query = select(Approval)
    count_query = select(func.count(Approval.id))
    project_ids = await accessible_project_ids(db, user)
    if project_ids is not None:
        visible_tasks = select(Task.id).where(Task.project_id.in_(project_ids))
        query = query.where(Approval.task_id.in_(visible_tasks))
        count_query = count_query.where(Approval.task_id.in_(visible_tasks))
    if status:
        query = query.where(Approval.status == status)
        count_query = count_query.where(Approval.status == status)
    if task_id:
        query = query.where(Approval.task_id == task_id)
        count_query = count_query.where(Approval.task_id == task_id)
    total = (await db.execute(count_query)).scalar_one()
    rows = list(
        (
            await db.execute(
                query.order_by(Approval.created_at.desc())
                .offset(pagination.offset)
                .limit(pagination.limit)
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [ApprovalOut.model_validate(a).model_dump() for a in rows],
        "total": total,
        "page": pagination.page,
        "page_size": pagination.page_size,
    }


@router.post("/approvals/{approval_id}/decision", response_model=ApprovalOut)
async def decide_approval(
    approval_id: str,
    payload: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Approval:
    approval = await db.get(Approval, approval_id)
    if not approval:
        raise not_found("Approval")
    if approval.kind == "DEPLOY":
        deployment = (
            await db.execute(
                select(Deployment).where(
                    Deployment.detail["approval_id"].as_string() == approval.id
                )
            )
        ).scalar_one_or_none()
        if not deployment:
            # JSON path comparison differs across databases; fall back to scanning.
            candidates = (
                (await db.execute(select(Deployment).order_by(Deployment.created_at.desc()).limit(200)))
                .scalars()
                .all()
            )
            deployment = next(
                (d for d in candidates if (d.detail or {}).get("approval_id") == approval.id),
                None,
            )
        if not deployment:
            raise conflict("Linked deployment not found", "deployment_missing")
        await approve_and_deploy(
            db, deployment, approve=payload.approve, notes=payload.notes, actor=admin
        )
        await db.refresh(approval)
        return approval
    return await task_service.decide_approval(
        db, approval, approve=payload.approve, notes=payload.notes, actor=admin
    )


@router.get("/deployments")
async def list_deployments(
    status: Optional[str] = None,
    pagination: Pagination = Depends(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    query = select(Deployment)
    count_query = select(func.count(Deployment.id))
    project_ids = await accessible_project_ids(db, user)
    if project_ids is not None:
        visible_tasks = select(Task.id).where(Task.project_id.in_(project_ids))
        query = query.where(Deployment.task_id.in_(visible_tasks))
        count_query = count_query.where(Deployment.task_id.in_(visible_tasks))
    if status:
        query = query.where(Deployment.status == status)
        count_query = count_query.where(Deployment.status == status)
    total = (await db.execute(count_query)).scalar_one()
    rows = list(
        (
            await db.execute(
                query.order_by(Deployment.created_at.desc())
                .offset(pagination.offset)
                .limit(pagination.limit)
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [DeploymentOut.model_validate(d).model_dump() for d in rows],
        "total": total,
        "page": pagination.page,
        "page_size": pagination.page_size,
    }


@router.get("/deployments/{deployment_id}", response_model=DeploymentOut)
async def get_deployment(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Deployment:
    deployment = await db.get(Deployment, deployment_id)
    if not deployment:
        raise not_found("Deployment")
    return deployment


@router.post("/deployments/{deployment_id}/decision", response_model=DeploymentOut)
async def decide_deployment(
    deployment_id: str,
    payload: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Deployment:
    deployment = await db.get(Deployment, deployment_id)
    if not deployment:
        raise not_found("Deployment")
    return await approve_and_deploy(
        db, deployment, approve=payload.approve, notes=payload.notes, actor=admin
    )
