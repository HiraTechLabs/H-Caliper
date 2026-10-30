"""Provider registry and persistence helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Type

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProviderType
from app.core.errors import bad_request, not_found
from app.core.security import decrypt_secret
from app.models.provider import Provider, ProviderModel
from app.services.providers.base import BaseProvider
from app.services.providers.cli import (
    AntigravityProvider,
    CodexProvider,
    OpenCodeProvider,
)
from app.services.providers.mock import MockProvider
from app.services.providers.ollama import OllamaProvider
from app.services.providers.openai_compat import (
    FreeLLMAPIProvider,
    LMStudioProvider,
    OpenAICompatibleProvider,
)

logger = logging.getLogger(__name__)

REGISTRY: Dict[str, Type[BaseProvider]] = {
    ProviderType.OPENAI_COMPATIBLE.value: OpenAICompatibleProvider,
    ProviderType.FREELLMAPI.value: FreeLLMAPIProvider,
    ProviderType.LMSTUDIO.value: LMStudioProvider,
    ProviderType.OLLAMA.value: OllamaProvider,
    ProviderType.OPENCODE.value: OpenCodeProvider,
    ProviderType.CODEX.value: CodexProvider,
    ProviderType.ANTIGRAVITY.value: AntigravityProvider,
    ProviderType.MOCK.value: MockProvider,
}


@dataclass
class ProviderHandle:
    record: Provider
    adapter: BaseProvider


def adapter_for(record: Provider) -> BaseProvider:
    cls = REGISTRY.get(record.type)
    if not cls:
        raise bad_request(f"Unsupported provider type '{record.type}'", "unsupported_provider")
    class_caps = cls.capabilities
    default_caps = {cap.value: True for cap in class_caps}
    caps = {**default_caps, **(record.capabilities or {})}
    adapter = cls(
        name=record.name,
        base_url=record.base_url,
        api_key=decrypt_secret(record.api_key_encrypted),
        config={**(record.config or {}), "capabilities": caps},
    )
    return adapter


async def get_handle(db: AsyncSession, provider_id: str) -> ProviderHandle:
    record = await db.get(Provider, provider_id)
    if not record:
        raise not_found("Provider")
    if not record.enabled:
        raise bad_request("Provider is disabled", "provider_disabled")
    return ProviderHandle(record=record, adapter=adapter_for(record))


async def check_health(db: AsyncSession, provider: Provider, *, commit: bool = True) -> Dict:
    adapter = adapter_for(provider)
    health = await adapter.health()
    provider.status = health.status
    provider.last_checked_at = datetime.now(timezone.utc)
    provider.last_error = None if health.connected else (health.message or "Unavailable")[:4000]
    if commit:
        await db.commit()
    return {
        "connected": health.connected,
        "status": health.status,
        "message": health.message,
        "models": health.models,
        "version": health.version,
    }


async def sync_models(db: AsyncSession, provider: Provider) -> List[ProviderModel]:
    adapter = adapter_for(provider)
    try:
        model_ids = await adapter.list_models()
    except Exception as exc:
        provider.last_error = str(exc)[:4000]
        provider.last_checked_at = datetime.now(timezone.utc)
        await db.commit()
        raise
    existing_rows = await db.execute(
        select(ProviderModel).where(ProviderModel.provider_id == provider.id)
    )
    existing = {m.model_id: m for m in existing_rows.scalars().all()}
    seen = set()
    for model_id in model_ids:
        seen.add(model_id)
        if model_id in existing:
            existing[model_id].discovered = True
            existing[model_id].enabled = True
        else:
            db.add(
                ProviderModel(
                    provider_id=provider.id,
                    model_id=model_id,
                    display_name=model_id,
                    discovered=True,
                    enabled=True,
                )
            )
    for model_id, model in existing.items():
        if model_id not in seen and model.discovered:
            model.enabled = False
    provider.last_error = None
    provider.last_checked_at = datetime.now(timezone.utc)
    await db.commit()
    rows = await db.execute(
        select(ProviderModel)
        .where(ProviderModel.provider_id == provider.id)
        .order_by(ProviderModel.model_id)
    )
    return list(rows.scalars().all())


async def capability_snapshot(provider_type: str) -> Dict[str, bool]:
    cls = REGISTRY.get(provider_type)
    if not cls:
        return {}
    from app.core.enums import Capability

    return {cap.value: cap in cls.capabilities for cap in Capability}
