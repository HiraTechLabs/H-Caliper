"""OpenAI-compatible HTTP provider (FreeLLMAPI, LM Studio, generic)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.core.enums import Capability, ProviderStatus
from app.services.providers.base import (
    BaseProvider,
    ProviderAuthenticationError,
    ProviderHealth,
    ProviderRateLimited,
    ProviderResponseError,
    ProviderTimeout,
    ProviderUnavailable,
    validate_outbound_url,
)


class OpenAICompatibleProvider(BaseProvider):
    type = "openai_compatible"
    capabilities = {
        Capability.CHAT,
        Capability.MODEL_DISCOVERY,
        Capability.STREAMING,
    }

    def _endpoint(self, path: str) -> str:
        base = self.base_url.rstrip("/")
        if base.endswith("/v1"):
            return f"{base}{path}"
        return f"{base}/v1{path}"

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _client(self, timeout: float) -> httpx.AsyncClient:
        if not self.base_url:
            raise ProviderUnavailable("Provider base URL is not configured")
        validate_outbound_url(
            self.base_url, allow_private=settings.ALLOW_PRIVATE_PROVIDER_HOSTS
        )
        return httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=settings.PROVIDER_CONNECT_TIMEOUT),
            follow_redirects=False,
        )

    async def list_models(self) -> List[str]:
        async with await self._client(settings.PROVIDER_CONNECT_TIMEOUT) as client:
            try:
                response = await client.get(self._endpoint("/models"), headers=self._headers())
            except httpx.TimeoutException as exc:
                raise ProviderTimeout("Model discovery timed out") from exc
            except httpx.HTTPError as exc:
                raise ProviderUnavailable(f"Provider unreachable: {exc}") from exc
        self._raise_for_status(response)
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderResponseError("Provider returned non-JSON model list") from exc
        items = data.get("data", data if isinstance(data, list) else [])
        models = []
        for item in items:
            if isinstance(item, dict):
                model_id = item.get("id") or item.get("name")
            else:
                model_id = str(item)
            if model_id:
                models.append(str(model_id))
        return sorted(set(models))

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
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        async with await self._client(settings.PROVIDER_REQUEST_TIMEOUT) as client:
            try:
                response = await client.post(
                    self._endpoint("/chat/completions"),
                    headers=self._headers(),
                    json=payload,
                )
            except httpx.TimeoutException as exc:
                raise ProviderTimeout("Chat completion timed out") from exc
            except httpx.HTTPError as exc:
                raise ProviderUnavailable(f"Provider unreachable: {exc}") from exc
        self._raise_for_status(response)
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderResponseError("Unexpected chat completion payload") from exc
        if isinstance(content, list):
            return "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return content or ""

    async def health(self) -> ProviderHealth:
        try:
            models = await self.list_models()
            return ProviderHealth(
                connected=True, status=ProviderStatus.HEALTHY.value, models=models
            )
        except ProviderAuthenticationError as exc:
            return ProviderHealth(
                connected=False, status=ProviderStatus.AUTH_FAILED.value, message=exc.message
            )
        except ProviderTimeout as exc:
            return ProviderHealth(
                connected=False, status=ProviderStatus.UNREACHABLE.value, message=exc.message
            )
        except Exception as exc:
            return ProviderHealth(
                connected=False, status=ProviderStatus.UNREACHABLE.value, message=str(exc)
            )

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code in (401, 403):
            raise ProviderAuthenticationError("Provider rejected the credentials")
        if response.status_code == 429:
            raise ProviderRateLimited("Provider rate limit reached")
        if response.status_code >= 500:
            raise ProviderUnavailable(f"Provider server error ({response.status_code})")
        if response.status_code >= 400:
            raise ProviderResponseError(
                f"Provider request failed ({response.status_code}): "
                f"{response.text[:500]}"
            )


class FreeLLMAPIProvider(OpenAICompatibleProvider):
    type = "freellmapi"


class LMStudioProvider(OpenAICompatibleProvider):
    type = "lmstudio"
