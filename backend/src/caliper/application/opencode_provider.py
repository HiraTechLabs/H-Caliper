from typing import Any, Protocol
from urllib.parse import urlparse

from caliper.adapters.opencode.client import OpenCodeFailure
from caliper.adapters.opencode.runtime import OpenCodeRuntime
from caliper.adapters.postgres.opencode_settings_repository import (
    OpenCodeSettings,
)
from caliper.application.secret_store import SecretStore


class OpenCodeSettingsRepository(Protocol):
    async def get(self) -> OpenCodeSettings: ...
    async def save_profile(self, secret_ref) -> OpenCodeSettings: ...
    async def record_status(self, status: str, error_code: str | None) -> OpenCodeSettings: ...
    async def select_model(self, provider_id: str, model_id: str) -> OpenCodeSettings: ...
    async def clear_selection(self) -> OpenCodeSettings: ...


class OpenCodeAdapter(Protocol):
    async def health(self) -> dict[str, Any]: ...
    async def providers(self) -> dict[str, Any]: ...
    async def auth_methods(self) -> dict[str, Any]: ...
    async def set_auth(self, provider_id: str, payload: dict[str, Any]) -> bool: ...
    async def remove_auth(self, provider_id: str) -> bool: ...
    async def authorize(
        self, provider_id: str, method: int, inputs: dict[str, str]
    ) -> dict[str, Any]: ...
    async def oauth_callback(self, provider_id: str, method: int, code: str) -> bool: ...


class OpenCodeProvider:
    def __init__(
        self,
        repository: OpenCodeSettingsRepository,
        secrets: SecretStore,
        adapter: OpenCodeAdapter,
        runtime: OpenCodeRuntime,
    ):
        self._repository = repository
        self._secrets = secrets
        self._adapter = adapter
        self._runtime = runtime

    async def capture_runtime_profile(self) -> None:
        settings = await self._repository.get()
        saved = self._secrets.get(settings.auth_secret_ref) if settings.auth_secret_ref else b"{}"
        if self._runtime.read_profile() != saved:
            await self._persist_profile()

    async def snapshot(self) -> dict[str, Any]:
        settings = await self._repository.get()
        if self._runtime.profile_error:
            current = await self._repository.record_status("failed", "profile_unavailable")
            return {
                "status": current.status,
                "error_code": current.error_code,
                "checked_at": current.checked_at,
                "version": None,
                "providers": [],
                "connected_provider_ids": [],
                "auth_methods": {},
                "selected_provider_id": current.selected_provider_id,
                "selected_model_id": current.selected_model_id,
            }
        try:
            health = await self._adapter.health()
            payload = await self._adapter.providers()
            methods = await self._adapter.auth_methods()
            providers = self._sanitize_providers(payload)
            connected = payload.get("connected", [])
            if not isinstance(connected, list):
                raise OpenCodeFailure("invalid_provider_catalog")
            connected_ids = {item for item in connected if isinstance(item, str)}
            status = (
                "connected"
                if connected_ids
                else "configured"
                if settings.auth_secret_ref
                else "not_configured"
            )
            current = await self._repository.record_status(status, None)
            return {
                "status": current.status,
                "error_code": None,
                "checked_at": current.checked_at,
                "version": str(health.get("version", "")),
                "providers": providers,
                "connected_provider_ids": sorted(connected_ids),
                "auth_methods": self._sanitize_methods(methods),
                "selected_provider_id": current.selected_provider_id,
                "selected_model_id": current.selected_model_id,
            }
        except (OpenCodeFailure, ValueError, TypeError):
            current = await self._repository.record_status("failed", "opencode_unavailable")
            return {
                "status": current.status,
                "error_code": current.error_code,
                "checked_at": current.checked_at,
                "version": None,
                "providers": [],
                "connected_provider_ids": [],
                "auth_methods": {},
                "selected_provider_id": current.selected_provider_id,
                "selected_model_id": current.selected_model_id,
            }

    async def connect_api_key(
        self, provider_id: str, api_key: str, metadata: dict[str, str]
    ) -> dict[str, Any]:
        if not api_key or len(api_key) > 8192:
            raise ValueError("Enter a valid API key")
        methods = await self._adapter.auth_methods()
        candidates = methods.get(provider_id)
        if not isinstance(candidates, list) or not any(
            isinstance(item, dict) and item.get("type") == "api" for item in candidates
        ):
            raise ValueError("This provider does not support API-key authentication")
        payload: dict[str, Any] = {"type": "api", "key": api_key}
        if metadata:
            if len(metadata) > 20 or any(
                not isinstance(key, str)
                or not isinstance(value, str)
                or not key
                or len(key) > 128
                or len(value) > 1024
                for key, value in metadata.items()
            ):
                raise ValueError("Provider authentication metadata is invalid")
            payload["metadata"] = metadata
        if not await self._adapter.set_auth(provider_id, payload):
            raise OpenCodeFailure("provider_auth_rejected")
        await self._persist_profile()
        return await self.snapshot()

    async def authorize(
        self, provider_id: str, method: int, inputs: dict[str, str]
    ) -> dict[str, str]:
        await self._oauth_method(provider_id, method)
        self._validate_inputs(inputs)
        result = await self._adapter.authorize(provider_id, method, inputs)
        url = result.get("url")
        if not isinstance(url, str) or urlparse(url).scheme != "https":
            raise OpenCodeFailure("invalid_authorization_response")
        return {
            "url": url,
            "method": str(result.get("method", "code")),
            "instructions": str(result.get("instructions", ""))[:1000],
        }

    async def oauth_callback(self, provider_id: str, method: int, code: str) -> dict[str, Any]:
        await self._oauth_method(provider_id, method)
        if not code or len(code) > 4096:
            raise ValueError("Enter a valid authorization code")
        if not await self._adapter.oauth_callback(provider_id, method, code):
            raise OpenCodeFailure("provider_auth_failed")
        await self._persist_profile()
        return await self.snapshot()

    async def disconnect(self, provider_id: str) -> dict[str, Any]:
        if not await self._adapter.remove_auth(provider_id):
            raise OpenCodeFailure("provider_disconnect_failed")
        await self._persist_profile()
        settings = await self._repository.get()
        if settings.selected_provider_id == provider_id:
            await self._repository.clear_selection()
        return await self.snapshot()

    async def select_model(self, provider_id: str, model_id: str) -> dict[str, Any]:
        if not model_id or len(model_id) > 256:
            raise ValueError("Choose a valid model")
        payload = await self._adapter.providers()
        connected = payload.get("connected", [])
        provider = next(
            (
                item
                for item in payload.get("all", [])
                if isinstance(item, dict) and item.get("id") == provider_id
            ),
            None,
        )
        models = provider.get("models", {}) if provider else {}
        if provider_id not in connected or not isinstance(models, dict) or model_id not in models:
            raise ValueError("Choose a model from a connected provider")
        settings = await self._repository.select_model(provider_id, model_id)
        return {
            "status": settings.status,
            "selected_provider_id": settings.selected_provider_id,
            "selected_model_id": settings.selected_model_id,
        }

    async def _persist_profile(self) -> None:
        settings = await self._repository.get()
        old_profile = (
            self._secrets.get(settings.auth_secret_ref) if settings.auth_secret_ref else b"{}"
        )
        profile = self._runtime.read_profile()
        secret_ref = self._secrets.put(profile) if profile != b"{}" else None
        try:
            await self._repository.save_profile(secret_ref)
        except Exception:
            self._secrets.delete(secret_ref)
            try:
                await self._runtime.reload_profile(old_profile)
            except ValueError:
                pass
            raise
        if settings.auth_secret_ref:
            self._secrets.delete(settings.auth_secret_ref)

    @staticmethod
    def _sanitize_providers(payload: dict[str, Any]) -> list[dict[str, Any]]:
        all_providers = payload.get("all", [])
        if not isinstance(all_providers, list) or len(all_providers) > 500:
            raise OpenCodeFailure("invalid_provider_catalog")
        result = []
        for provider in all_providers:
            if not isinstance(provider, dict):
                continue
            provider_id = provider.get("id")
            name = provider.get("name")
            if not isinstance(provider_id, str) or not isinstance(name, str):
                continue
            models = provider.get("models", {})
            safe_models = []
            if isinstance(models, dict):
                for model_id, model in list(models.items())[:3000]:
                    if isinstance(model_id, str) and isinstance(model, dict):
                        safe_models.append(
                            {"id": model_id, "name": str(model.get("name", model_id))[:160]}
                        )
            result.append({"id": provider_id, "name": name[:160], "models": safe_models})
        return result

    @staticmethod
    def _sanitize_methods(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        safe: dict[str, list[dict[str, Any]]] = {}
        for provider_id, methods in payload.items():
            if not isinstance(provider_id, str) or not isinstance(methods, list):
                continue
            safe_methods = []
            for method in methods[:20]:
                if not isinstance(method, dict) or method.get("type") not in {"api", "oauth"}:
                    continue
                prompts = []
                for prompt in method.get("prompts", [])[:20]:
                    if not isinstance(prompt, dict):
                        continue
                    prompts.append(
                        {
                            key: prompt[key]
                            for key in ("type", "key", "message", "placeholder", "options", "when")
                            if key in prompt
                        }
                    )
                safe_methods.append(
                    {
                        "type": method["type"],
                        "label": str(method.get("label", ""))[:160],
                        "prompts": prompts,
                    }
                )
            safe[provider_id] = safe_methods
        return safe

    @staticmethod
    def _validate_method_index(method: int) -> None:
        if method < 0 or method > 50:
            raise ValueError("Choose a valid authentication method")

    async def _oauth_method(self, provider_id: str, method: int) -> None:
        self._validate_method_index(method)
        available = (await self._adapter.auth_methods()).get(provider_id)
        if not isinstance(available, list) or method >= len(available):
            raise ValueError("Choose a current authentication method")
        selected = available[method]
        if not isinstance(selected, dict) or selected.get("type") != "oauth":
            raise ValueError("The selected method is not OAuth")

    @staticmethod
    def _validate_inputs(inputs: dict[str, str]) -> None:
        if len(inputs) > 20 or any(
            not isinstance(key, str)
            or not isinstance(value, str)
            or not key
            or len(key) > 128
            or len(value) > 1024
            for key, value in inputs.items()
        ):
            raise ValueError("Authentication inputs are invalid")
