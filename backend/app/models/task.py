from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import TaskStatus
from app.models.base import Base, created_at, json_col, updated_at, uuid_pk


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = uuid_pk()
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default=TaskStatus.CREATED.value, index=True
    )
    created_by: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    branch: Mapped[Optional[str]] = mapped_column(String(250))
    base_commit: Mapped[Optional[str]] = mapped_column(String(64))
    head_commit: Mapped[Optional[str]] = mapped_column(String(64))
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_stage: Mapped[str] = mapped_column(String(60), nullable=False, default="CREATED")
    config: Mapped[Dict] = json_col({})
    error: Mapped[Optional[str]] = mapped_column(Text)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    locked_by: Mapped[Optional[str]] = mapped_column(String(120))
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    executions: Mapped[List["TaskExecution"]] = relationship(
        back_populates="task", cascade="all, delete-orphan",
        order_by="TaskExecution.attempt",
    )
    stages: Mapped[List["PipelineStage"]] = relationship(
        back_populates="task", cascade="all, delete-orphan",
    )
    artifacts: Mapped[List["Artifact"]] = relationship(
        back_populates="task", cascade="all, delete-orphan",
    )


class TaskExecution(Base):
    __tablename__ = "task_executions"

    id: Mapped[str] = uuid_pk()
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="RUNNING")
    workspace_path: Mapped[Optional[str]] = mapped_column(String(1024))
    started_at: Mapped[datetime] = created_at()
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error: Mapped[Optional[str]] = mapped_column(Text)

    task: Mapped[Task] = relationship(back_populates="executions")


class PipelineStage(Base):
    __tablename__ = "pipeline_stages"

    id: Mapped[str] = uuid_pk()
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    execution_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("task_executions.id", ondelete="CASCADE"), index=True
    )
    stage: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="RUNNING")
    started_at: Mapped[datetime] = created_at()
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    detail: Mapped[Dict] = json_col({})

    task: Mapped[Task] = relationship(back_populates="stages")


class TaskEvent(Base):
    __tablename__ = "task_events"

    id: Mapped[str] = uuid_pk()
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="INFO")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[Dict] = json_col({})
    created_at: Mapped[datetime] = created_at()


class AgentExecution(Base):
    __tablename__ = "agent_executions"

    id: Mapped[str] = uuid_pk()
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[str] = mapped_column(String(60), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_id: Mapped[Optional[str]] = mapped_column(String(36))
    provider_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    provider_type: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(250), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="RUNNING")
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    error: Mapped[Optional[str]] = mapped_column(Text)
    output: Mapped[Dict] = json_col({})
    created_at: Mapped[datetime] = created_at()
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[str] = uuid_pk()
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    structured: Mapped[Dict] = json_col({})
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT")
    created_at: Mapped[datetime] = created_at()
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = uuid_pk()
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("plans.id", ondelete="SET NULL")
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[Dict] = json_col({})
    violated_principles: Mapped[Dict] = json_col([])
    required_corrections: Mapped[Dict] = json_col([])
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="MAJOR")
    created_at: Mapped[datetime] = created_at()


class QualityGateResult(Base):
    __tablename__ = "quality_gate_results"

    id: Mapped[str] = uuid_pk()
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    execution_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("task_executions.id", ondelete="CASCADE"), index=True
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    command: Mapped[str] = mapped_column(Text, nullable=False, default="")
    output: Mapped[str] = mapped_column(Text, nullable=False, default="")
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = created_at()


class GitOperation(Base):
    __tablename__ = "git_operations"

    id: Mapped[str] = uuid_pk()
    task_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    operation: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="SUCCEEDED")
    detail: Mapped[Dict] = json_col({})
    created_at: Mapped[datetime] = created_at()


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = uuid_pk()
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    path: Mapped[Optional[str]] = mapped_column(String(1024))
    content_type: Mapped[str] = mapped_column(String(120), nullable=False, default="text/plain")
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = created_at()

    task: Mapped[Task] = relationship(back_populates="artifacts")


class DocumentationRecord(Base):
    __tablename__ = "documentation_records"

    id: Mapped[str] = uuid_pk()
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    files: Mapped[Dict] = json_col([])
    commit_sha: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = created_at()
