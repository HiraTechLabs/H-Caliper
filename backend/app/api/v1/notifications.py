from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.governance import Notification
from app.models.user import User
from app.schemas import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
) -> list[Notification]:
    rows = await db.execute(
        select(Notification)
        .where((Notification.user_id == user.id) | (Notification.user_id.is_(None)))
        .order_by(Notification.created_at.desc())
        .limit(100)
    )
    return list(rows.scalars().all())


@router.post("/read-all")
async def read_all(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    await db.execute(
        update(Notification)
        .where((Notification.user_id == user.id) | (Notification.user_id.is_(None)))
        .values(is_read=True)
    )
    await db.commit()
    return {"ok": True}


@router.post("/{notification_id}/read")
async def read_one(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    item = await db.get(Notification, notification_id)
    if item and (item.user_id in {None, user.id}):
        item.is_read = True
        await db.commit()
    return {"ok": True}
