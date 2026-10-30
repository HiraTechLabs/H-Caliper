"""Common SQLAlchemy column helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, JSON, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, mapped_column

JSONType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def uuid_pk():
    # Stored as VARCHAR(36) for consistent string identifiers across PostgreSQL
    # and SQLite. Generated in Python so no database extension is required.
    return mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )


def created_at():
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


def updated_at():
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=utcnow,
    )


def json_col(default: Any = None):
    return mapped_column(JSONType, nullable=False, default=default if default is not None else dict)
