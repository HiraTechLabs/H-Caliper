"""Logging, redaction, and small observability helpers."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Iterable

from app.core.config import settings

_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization)\s*[:=]\s*[\"']?([^\s\"',}]+)"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
]


def redact(value: str, limit: int = 20_000) -> str:
    if value is None:
        return ""
    text = str(value)
    for pattern in _SECRET_PATTERNS:
        if pattern.groups >= 2:
            text = pattern.sub(lambda m: f"{m.group(1)}=***", text)
        else:
            text = pattern.sub(lambda m: f"{m.group(1)}***", text)
    if len(text) > limit:
        text = text[:limit] + f"\n… truncated ({len(text) - limit} chars)"
    return text


def redact_mapping(data: Dict[str, Any], sensitive_keys: Iterable[str] | None = None) -> Dict[str, Any]:
    sensitive = {k.lower() for k in (sensitive_keys or ())}
    defaults = {"api_key", "password", "secret", "token", "authorization", "private_key"}
    result: Dict[str, Any] = {}
    for key, value in data.items():
        if key.lower() in sensitive or key.lower() in defaults or key.lower().endswith("_secret"):
            result[key] = "***" if value else value
        elif isinstance(value, dict):
            result[key] = redact_mapping(value)
        elif isinstance(value, str):
            result[key] = redact(value, limit=4000)
        else:
            result[key] = value
    return result


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage(), limit=8000),
        }
        for key in (
            "task_id",
            "project_id",
            "workspace_id",
            "agent_role",
            "provider",
            "model",
            "execution_ms",
            "status",
            "error_category",
            "retry_count",
            "stage",
            "request_id",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info), limit=8000)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    if settings.LOG_FORMAT == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)
    root.setLevel(settings.LOG_LEVEL.upper())
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def log_event(logger: logging.Logger, message: str, **fields: Any) -> None:
    logger.info(message, extra={k: v for k, v in fields.items() if v is not None})
