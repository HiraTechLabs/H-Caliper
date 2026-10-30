"""Ollama native API adapter."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.core.enums import Capability, ProviderStatus
from app.services.providers.base import (
    BaseProvider,
    ProviderHealth,
    ProviderResponseError,
    ProviderTimeout,
    ProviderUnavailable,
    validate_outbound_url,
)


class OllamaProvider(BaseProvider):
    type = "ollama"
    capabilities = {Capability.CHAT, Capability.MODEL_DISCOVERY, Capability.STREAMING}

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.base_url = (self.base_url or "http://127.0.0.1:11434").rstrip("/")

    async def _client(self, timeout: float) -> httpx.AsyncClient:
        validate_outbound_url(
            self.base_url, allow_private=settings.ALLOW_PRIVATE_PROVIDER_HOSTS
        )
        return httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=settings.PROVIDER_CONNECT_TIMEOUT)
        )

    async def list_models(self) -> List[str]:
        async with await self._client(settings.PROVIDER_CONNECT_TIMEOUT) as client:
            try:
                response = await client.get(f"{self.base_url}/api/tags")
            except httpx.TimeoutException as exc:
                raise ProviderTimeout("Ollama model discovery timed out") from exc
            except httpx.HTTPError as exc:
                raise ProviderUnavailable(f"Ollama unreachable: {exc}") from exc
        if response.status_code >= 400:
            raise ProviderResponseError(f"Ollama returned HTTP {response.status_code}")
        data = response.json()
        return sorted({m.get("name") for m in data.get("models", []) if m.get("name")})

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        async with await self._client(settings.PROVIDER_REQUEST_TIMEOUT) as client:
            try:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
            except httpx.TimeoutException as exc:
                raise ProviderTimeout("Ollama completion timed out") from exc
            except httpx.HTTPError as exc:
                raise ProviderUnavailable(f"Ollama unreachable: {exc}") from exc
        if response.status_code >= 400:
            raise ProviderResponseError(
                f"Ollama request failed ({response.status_code}): {response.text[:300]}"
            )
        try:
            return response.json()["message"]["content"]
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderResponseError("Unexpected Ollama response payload") from exc

    async def health(self) -> ProviderHealth:
        try:
            models = await self.list_models()
            return ProviderHealth(
                connected=True, status=ProviderStatus.HEALTHY.value, models=models
            )
        except Exception as exc:
            return ProviderHealth(
                connected=False, status=ProviderStatus.UNREACHABLE.value, message=str(exc)
            )
