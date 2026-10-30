from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ProviderStatus
from app.models.base import Base, created_at, json_col, updated_at, uuid_pk


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[str] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    base_url: Mapped[Optional[str]] = mapped_column(String(1024))
    api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=ProviderStatus.UNKNOWN.value
    )
    capabilities: Mapped[Dict] = json_col({})
    config: Mapped[Dict] = json_col({})
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    models: Mapped[List["ProviderModel"]] = relationship(
        back_populates="provider", cascade="all, delete-orphan"
    )


class ProviderModel(Base):
    __tablename__ = "provider_models"

    id: Mapped[str] = uuid_pk()
    provider_id: Mapped[str] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_id: Mapped[str] = mapped_column(String(250), nullable=False)
    display_name: Mapped[str] = mapped_column(String(250), nullable=False, default="")
    capabilities: Mapped[Dict] = json_col({})
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    discovered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    provider: Mapped[Provider] = relationship(back_populates="models")


class AgentConfiguration(Base):
    __tablename__ = "agent_configurations"

    id: Mapped[str] = uuid_pk()
    project_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    provider_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("providers.id", ondelete="SET NULL")
    )
    model: Mapped[Optional[str]] = mapped_column(String(250))
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)
    max_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=8192)
    config: Mapped[Dict] = json_col({})
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()
