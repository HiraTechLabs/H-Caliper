"""Audit trail helper. Every security- or pipeline-significant action is recorded."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import redact_mapping
from app.models.governance import AuditLog, Notification


async def audit(
    db: AsyncSession,
    *,
    action: str,
    entity_type: str,
    actor_type: str = "system",
    actor_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    entry = AuditLog(
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else None,
        detail=redact_mapping(detail or {}),
        ip_address=ip_address,
    )
    db.add(entry)
    await db.flush()
    return entry


async def notify(
    db: AsyncSession,
    *,
    user_id: Optional[str],
    title: str,
    body: str = "",
    level: str = "INFO",
    task_id: Optional[str] = None,
) -> Notification:
    item = Notification(
        user_id=user_id, title=title, body=body, level=level, task_id=task_id
    )
    db.add(item)
    await db.flush()
    return item


async def prune_audit_logs(db: AsyncSession) -> None:
    """Retention cleanup; called by the worker once per day."""
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.AUDIT_RETENTION_DAYS)
    await db.execute(delete(AuditLog).where(AuditLog.created_at < cutoff))
    await db.commit()
