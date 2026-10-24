import asyncio

import pytest

from caliper.application.ollama_provider import (
    OllamaConfigurationChanged,
    OllamaModelNotAvailable,
    OllamaProvider,
    OllamaProviderFailure,
    OllamaSettings,
)


class SettingsRepository:
    def __init__(self):
        self.value = OllamaSettings("", None, "not_configured", None, None, [])

    async def get(self):
        return self.value

    async def configure(self, endpoint_url):
        self.value = OllamaSettings(endpoint_url, None, "configured", None, None, [])
        return self.value

    async def save_discovery(self, expected_endpoint, status, models, error_code, checked_at):
        if self.value.endpoint_url != expected_endpoint:
            raise OllamaConfigurationChanged
        selected = self.value.selected_model_id if self.value.selected_model_id in models else None
        self.value = OllamaSettings(
            expected_endpoint, selected, status, checked_at, error_code, models
        )
        return self.value

    async def select_model(self, model_id):
        if self.value.status != "reachable" or model_id not in self.value.models:
            raise OllamaModelNotAvailable(model_id)
        self.value = OllamaSettings(
            self.value.endpoint_url,
            model_id,
            self.value.status,
            self.value.checked_at,
            self.value.error_code,
            self.value.models,
        )
        return self.value


class DiscoveryAdapter:
    def __init__(self, models=None, failure=None, on_discover=None):
        self.models = models or []
        self.failure = failure
        self.on_discover = on_discover

    async def discover(self, _endpoint_url):
        if self.on_discover:
            self.on_discover()
        if self.failure:
            raise self.failure
        return self.models


def test_ollama_configuration_discovers_then_selects_only_available_models():
    repository = SettingsRepository()
    provider = OllamaProvider(repository, DiscoveryAdapter(["qwen:latest", "llama:8b"]))

    async def run():
        saved = await provider.configure(" http://ollama:11434/ ")
        checked = await provider.validate()
        selected = await provider.select_model("qwen:latest")
        return saved, checked, selected

    saved, checked, selected = asyncio.run(run())

    assert saved.endpoint_url == "http://ollama:11434"
    assert saved.status == "configured"
    assert checked.status == "reachable"
    assert checked.models == ["qwen:latest", "llama:8b"]
    assert selected.selected_model_id == "qwen:latest"

    with pytest.raises(OllamaModelNotAvailable):
        asyncio.run(provider.select_model("not-discovered"))


def test_ollama_configuration_rejects_credentials_and_paths_before_persisting():
    repository = SettingsRepository()
    provider = OllamaProvider(repository, DiscoveryAdapter())

    for endpoint in (
        "ftp://ollama:11434",
        "http://user:token@ollama:11434",
        "http://ollama:11434/api",
        "http://ollama:99999",
    ):
        with pytest.raises(ValueError):
            asyncio.run(provider.configure(endpoint))
    assert repository.value.status == "not_configured"


def test_ollama_validation_persists_failure_without_claiming_reachability():
    repository = SettingsRepository()
    provider = OllamaProvider(
        repository, DiscoveryAdapter(failure=OllamaProviderFailure("ollama_unreachable"))
    )
    asyncio.run(provider.configure("http://ollama:11434"))

    failed = asyncio.run(provider.validate())

    assert failed.status == "failed"
    assert failed.error_code == "ollama_unreachable"
    assert failed.models == []
    assert failed.checked_at is not None


def test_ollama_validation_does_not_save_results_for_a_changed_endpoint():
    repository = SettingsRepository()
    repository.value = OllamaSettings("http://ollama-a:11434", None, "configured", None, None, [])

    def change_endpoint():
        repository.value = OllamaSettings(
            "http://ollama-b:11434", None, "configured", None, None, []
        )

    provider = OllamaProvider(
        repository, DiscoveryAdapter(["qwen:latest"], on_discover=change_endpoint)
    )

    with pytest.raises(OllamaConfigurationChanged):
        asyncio.run(provider.validate())

    assert repository.value.endpoint_url == "http://ollama-b:11434"
    assert repository.value.status == "configured"
