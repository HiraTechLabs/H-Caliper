from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_at, updated_at, uuid_pk


class CaliperDocument(Base):
    __tablename__ = "caliper_documents"

    id: Mapped[str] = uuid_pk()
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_protected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    versions: Mapped[List["CaliperVersion"]] = relationship(
        back_populates="document", cascade="all, delete-orphan",
        order_by="CaliperVersion.version",
    )
    proposals: Mapped[List["CaliperProposal"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class CaliperVersion(Base):
    __tablename__ = "caliper_versions"

    id: Mapped[str] = uuid_pk()
    document_id: Mapped[str] = mapped_column(
        ForeignKey("caliper_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    related_task_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL")
    )
    author: Mapped[str] = mapped_column(String(200), nullable=False, default="system")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="APPROVED")
    approved_by: Mapped[Optional[str]] = mapped_column(String(320))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()

    document: Mapped[CaliperDocument] = relationship(back_populates="versions")


class CaliperProposal(Base):
    __tablename__ = "caliper_proposals"

    id: Mapped[str] = uuid_pk()
    document_id: Mapped[str] = mapped_column(
        ForeignKey("caliper_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    base_version: Mapped[int] = mapped_column(Integer, nullable=False)
    proposed_content: Mapped[str] = mapped_column(Text, nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    related_task_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL")
    )
    author: Mapped[str] = mapped_column(String(200), nullable=False, default="agent")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(320))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()

    document: Mapped[CaliperDocument] = relationship(back_populates="proposals")
