from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    ConnectionType,
    EnvironmentKind,
    ProjectStatus,
)
from app.models.base import Base, created_at, json_col, updated_at, uuid_pk

if TYPE_CHECKING:  # pragma: no cover
    from app.models.user import ProjectMember


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = uuid_pk()
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ProjectStatus.ACTIVE.value
    )
    owner_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    # Per-project defaults keep users from re-selecting models every task.
    default_planning_provider_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("providers.id", ondelete="SET NULL")
    )
    default_planning_model: Mapped[Optional[str]] = mapped_column(String(200))
    default_execution_provider_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("providers.id", ondelete="SET NULL")
    )
    default_execution_model: Mapped[Optional[str]] = mapped_column(String(200))
    default_review_provider_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("providers.id", ondelete="SET NULL")
    )
    default_review_model: Mapped[Optional[str]] = mapped_column(String(200))
    default_documentation_provider_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("providers.id", ondelete="SET NULL")
    )
    default_documentation_model: Mapped[Optional[str]] = mapped_column(String(200))
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    default_branch: Mapped[str] = mapped_column(String(200), nullable=False, default="main")
    quality_gates: Mapped[Dict] = json_col([])
    settings: Mapped[Dict] = json_col({})
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    members: Mapped[List["ProjectMember"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    workspaces: Mapped[List["Workspace"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    environments: Mapped[List["Environment"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = uuid_pk()
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="default")
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(40), nullable=False, default="local")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="READY")
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    project: Mapped[Project] = relationship(back_populates="workspaces")


class RepositoryConnection(Base):
    __tablename__ = "repository_connections"

    id: Mapped[str] = uuid_pk()
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="github")
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    auth_type: Mapped[str] = mapped_column(String(40), nullable=False, default="none")
    secret_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    default_branch: Mapped[str] = mapped_column(String(200), nullable=False, default="main")
    github_owner: Mapped[Optional[str]] = mapped_column(String(200))
    github_repo: Mapped[Optional[str]] = mapped_column(String(200))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class Environment(Base):
    __tablename__ = "environments"

    id: Mapped[str] = uuid_pk()
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(
        String(20), nullable=False, default=EnvironmentKind.DEVELOPMENT.value, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    connection_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ConnectionType.LOCAL.value
    )
    config: Mapped[Dict] = json_col({})
    secrets_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deployment_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    health_status: Mapped[str] = mapped_column(String(30), nullable=False, default="UNKNOWN")
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    project: Mapped[Project] = relationship(back_populates="environments")


class EnvironmentVariable(Base):
    __tablename__ = "environment_variables"

    id: Mapped[str] = uuid_pk()
    environment_id: Mapped[str] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    value_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = created_at()
