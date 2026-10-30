from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ApprovalStatus, DeploymentStatus
from app.models.base import Base, created_at, json_col, uuid_pk


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = uuid_pk()
    task_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False, default="MERGE")
    requested_by: Mapped[Optional[str]] = mapped_column(String(320))
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=ApprovalStatus.PENDING.value, index=True
    )
    decided_by: Mapped[Optional[str]] = mapped_column(String(320))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = uuid_pk()
    actor_type: Mapped[str] = mapped_column(String(30), nullable=False, default="user")
    actor_id: Mapped[Optional[str]] = mapped_column(String(320))
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(120), index=True)
    detail: Mapped[Dict] = json_col({})
    ip_address: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = created_at()


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="INFO")
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    task_id: Mapped[Optional[str]] = mapped_column(String(36))
    created_at: Mapped[datetime] = created_at()


class Deployment(Base):
    __tablename__ = "deployments"

    id: Mapped[str] = uuid_pk()
    environment_id: Mapped[str] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=DeploymentStatus.PENDING.value
    )
    approved_by: Mapped[Optional[str]] = mapped_column(String(320))
    detail: Mapped[Dict] = json_col({})
    output: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
