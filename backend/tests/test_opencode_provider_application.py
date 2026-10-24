import asyncio
import json
from dataclasses import dataclass, replace

import pytest

from caliper.adapters.opencode.client import OpenCodeFailure
from caliper.application.opencode_provider import OpenCodeProvider


@dataclass
class Settings:
    auth_secret_ref: str | None = None
    selected_provider_id: str | None = None
    selected_model_id: str | None = None
    status: str = "not_configured"
    checked_at: str | None = None
    error_code: str | None = None


class Repository:
    def __init__(self):
        self.settings = Settings()

    async def get(self):
        return self.settings

    async def save_profile(self, ref):
        self.settings = replace(self.settings, auth_secret_ref=ref)
        return self.settings

    async def record_status(self, status, error_code):
        self.settings = replace(self.settings, status=status, error_code=error_code)
        return self.settings

    async def select_model(self, provider_id, model_id):
        self.settings = replace(
            self.settings,
            selected_provider_id=provider_id,
            selected_model_id=model_id,
        )
        return self.settings

    async def clear_selection(self):
        self.settings = replace(self.settings, selected_provider_id=None, selected_model_id=None)
        return self.settings


class Secrets:
    def __init__(self):
        self.values = {}

    def put(self, value):
        self.values["ref-1"] = value
        return "ref-1"

    def get(self, ref):
        return self.values[ref]

    def delete(self, ref):
        self.values.pop(ref, None)


class Runtime:
    profile_error = False

    def __init__(self):
        self.profile = b"{}"

    def read_profile(self):
        return self.profile

    async def reload_profile(self, payload):
        self.profile = payload
        return True


class Adapter:
    def __init__(self):
        self.profile = {}

    async def health(self):
        return {"healthy": True, "version": "1.19.4"}

    async def providers(self):
        return {
            "connected": ["provider"],
            "all": [
                {
                    "id": "provider",
                    "name": "Provider",
                    "key": "must-not-leak",
                    "models": {"model": {"name": "Safe model", "api_key": "must-not-leak"}},
                }
            ],
        }

    async def auth_methods(self):
        return {"provider": [{"type": "api", "label": "API key", "prompts": []}]}

    async def set_auth(self, provider_id, payload):
        self.profile[provider_id] = payload
        self.runtime.profile = json.dumps(self.profile).encode()
        return True

    async def remove_auth(self, provider_id):
        self.profile.pop(provider_id, None)
        self.runtime.profile = json.dumps(self.profile).encode()
        return True

    async def authorize(self, provider_id, method, inputs):
        return {
            "url": "https://accounts.example/authorize",
            "method": "code",
            "instructions": "Sign in",
        }

    async def oauth_callback(self, provider_id, method, code):
        return True


def make_service():
    repository, secrets, runtime, adapter = Repository(), Secrets(), Runtime(), Adapter()
    adapter.runtime = runtime
    return (
        OpenCodeProvider(repository, secrets, adapter, runtime),
        repository,
        secrets,
        runtime,
        adapter,
    )


def test_provider_snapshot_strips_untrusted_secret_fields():
    service, *_ = make_service()
    result = asyncio.run(service.snapshot())
    rendered = repr(result)
    assert "must-not-leak" not in rendered
    assert result["providers"] == [
        {"id": "provider", "name": "Provider", "models": [{"id": "model", "name": "Safe model"}]}
    ]


def test_api_key_is_saved_to_secret_store_and_never_returned():
    service, repository, secrets, runtime, _ = make_service()
    result = asyncio.run(service.connect_api_key("provider", "test-key-value", {}))
    assert repository.settings.auth_secret_ref == "ref-1"
    assert secrets.values["ref-1"] == b'{"provider": {"type": "api", "key": "test-key-value"}}'
    assert runtime.profile_error is False
    assert "test-key-value" not in repr(result)


def test_oauth_runtime_profile_is_captured_to_encrypted_store():
    service, repository, secrets, runtime, _ = make_service()
    runtime.profile = b'{"provider": {"type": "oauth", "access": "acceptance-token"}}'
    asyncio.run(service.capture_runtime_profile())
    assert repository.settings.auth_secret_ref == "ref-1"
    assert secrets.values["ref-1"] == runtime.profile
    assert "acceptance-token" not in repr(repository.settings)


def test_api_key_connection_rejects_provider_without_api_auth():
    service, _, _, _, adapter = make_service()
    adapter.auth_methods = lambda: _no_api_methods()
    with pytest.raises(ValueError, match="does not support"):
        asyncio.run(service.connect_api_key("provider", "test-key-value", {}))


async def _no_api_methods():
    return {"provider": [{"type": "oauth", "prompts": []}]}


def test_oauth_requires_https_authorization_url():
    service, _, _, _, adapter = make_service()
    adapter.auth_methods = _oauth_methods
    adapter.authorize = _insecure_authorize
    with pytest.raises(OpenCodeFailure, match="invalid_authorization_response"):
        asyncio.run(service.authorize("provider", 0, {}))


async def _oauth_methods():
    return {"provider": [{"type": "oauth", "prompts": []}]}


async def _insecure_authorize(provider_id, method, inputs):
    return {"url": "http://accounts.example/authorize"}
