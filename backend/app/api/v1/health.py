from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.enums import ProviderStatus
from app.models.project import Environment
from app.models.provider import Provider

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def liveness() -> dict:
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "environment": settings.ENV,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready")
async def readiness(db: AsyncSession = Depends(get_db)) -> dict:
    components: dict[str, dict] = {}
    try:
        await db.execute(text("SELECT 1"))
        components["database"] = {"status": "PASSED"}
    except Exception as exc:
        components["database"] = {"status": "FAILED", "message": str(exc)}
    try:
        os.makedirs(settings.WORKSPACE_ROOT, exist_ok=True)
        probe = os.path.join(settings.WORKSPACE_ROOT, ".health")
        with open(probe, "w", encoding="utf-8") as handle:
            handle.write("ok")
        os.remove(probe)
        usage = shutil.disk_usage(settings.WORKSPACE_ROOT)
        components["storage"] = {
            "status": "PASSED",
            "free_bytes": usage.free,
            "path": settings.WORKSPACE_ROOT,
        }
    except Exception as exc:
        components["storage"] = {"status": "FAILED", "message": str(exc)}

    providers = (
        (await db.execute(select(Provider).where(Provider.enabled.is_(True)))).scalars().all()
    )
    provider_rows = []
    for provider in providers:
        provider_rows.append(
            {
                "id": provider.id,
                "name": provider.name,
                "type": provider.type,
                "status": provider.status,
                "last_checked_at": provider.last_checked_at,
            }
        )
    healthy = [p for p in providers if p.status == ProviderStatus.HEALTHY.value]
    components["providers"] = {
        "status": "PASSED" if healthy else "WARNING",
        "configured": len(providers),
        "healthy": len(healthy),
        "items": provider_rows,
    }
    envs = (
        (await db.execute(select(Environment).where(Environment.is_active.is_(True)))).scalars().all()
    )
    components["environments"] = {
        "status": "PASSED"
        if any(e.health_status == "HEALTHY" for e in envs) or not envs
        else "WARNING",
        "count": len(envs),
    }
    overall = "PASSED" if all(c["status"] != "FAILED" for c in components.values()) else "FAILED"
    return {"status": overall, "components": components, "timestamp": datetime.now(timezone.utc).isoformat()}
