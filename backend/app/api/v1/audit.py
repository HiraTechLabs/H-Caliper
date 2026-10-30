from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import Pagination, require_admin
from app.models.governance import AuditLog
from app.models.user import User
from app.schemas import AuditOut

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def list_audit_logs(
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    pagination: Pagination = Depends(),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))
    filters = []
    if action:
        filters.append(AuditLog.action.ilike(f"%{action}%"))
    if entity_type:
        filters.append(AuditLog.entity_type == entity_type)
    if entity_id:
        filters.append(AuditLog.entity_id == entity_id)
    if actor_id:
        filters.append(AuditLog.actor_id == actor_id)
    if since:
        filters.append(AuditLog.created_at >= since)
    if until:
        filters.append(AuditLog.created_at <= until)
    for item in filters:
        query = query.where(item)
        count_query = count_query.where(item)
    total = (await db.execute(count_query)).scalar_one()
    rows = list(
        (
            await db.execute(
                query.order_by(AuditLog.created_at.desc())
                .offset(pagination.offset)
                .limit(pagination.limit)
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [AuditOut.model_validate(a).model_dump() for a in rows],
        "total": total,
        "page": pagination.page,
        "page_size": pagination.page_size,
    }
