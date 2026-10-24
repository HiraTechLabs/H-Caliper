from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import urlsplit


@dataclass(frozen=True)
class OllamaSettings:
    endpoint_url: str
    selected_model_id: str | None
    status: str
    checked_at: datetime | None
    error_code: str | None
    models: list[str]


class OllamaSettingsRepository(Protocol):
    async def get(self) -> OllamaSettings: ...
    async def configure(self, endpoint_url: str) -> OllamaSettings: ...
    async def save_discovery(
        self,
        expected_endpoint: str,
        status: str,
        models: list[str],
        error_code: str | None,
        checked_at: datetime,
    ) -> OllamaSettings: ...
    async def select_model(self, model_id: str) -> OllamaSettings: ...


class OllamaDiscoveryAdapter(Protocol):
    async def discover(self, endpoint_url: str) -> list[str]: ...


class OllamaProviderFailure(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class OllamaModelNotAvailable(LookupError):
    pass


class OllamaConfigurationChanged(RuntimeError):
    pass


class OllamaProvider:
    def __init__(self, repository: OllamaSettingsRepository, adapter: OllamaDiscoveryAdapter):
        self._repository = repository
        self._adapter = adapter

    async def settings(self) -> OllamaSettings:
        return await self._repository.get()

    async def configure(self, endpoint_url: str) -> OllamaSettings:
        normalized = endpoint_url.strip().rstrip("/")
        if len(normalized) > 512:
            raise ValueError("Ollama endpoint URL is too long")
        try:
            parsed = urlsplit(normalized)
            valid = (
                parsed.scheme in {"http", "https"}
                and parsed.hostname is not None
                and (parsed.port is None or 0 < parsed.port < 65536)
                and parsed.username is None
                and parsed.password is None
                and parsed.path in {"", "/"}
                and not parsed.query
                and not parsed.fragment
            )
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("Use an HTTP or HTTPS Ollama endpoint without credentials or a path")
        return await self._repository.configure(normalized)

    async def validate(self) -> OllamaSettings:
        current = await self._repository.get()
        if not current.endpoint_url:
            raise ValueError("Configure an Ollama endpoint before validating it")
        checked_at = datetime.now(UTC)
        try:
            models = await self._adapter.discover(current.endpoint_url)
        except OllamaProviderFailure as error:
            return await self._repository.save_discovery(
                current.endpoint_url, "failed", [], error.code, checked_at
            )
        return await self._repository.save_discovery(
            current.endpoint_url, "reachable", models, None, checked_at
        )

    async def select_model(self, model_id: str) -> OllamaSettings:
        if not model_id or len(model_id) > 256:
            raise ValueError("Choose a valid Ollama model identifier")
        return await self._repository.select_model(model_id)
