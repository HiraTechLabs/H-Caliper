import asyncio

import httpx
import pytest

from caliper.adapters.ollama.discovery import MAX_RESPONSE_BYTES, OllamaHttpDiscoveryAdapter
from caliper.application.ollama_provider import OllamaProviderFailure


def test_ollama_discovery_reads_only_model_identifiers():
    requests: list[httpx.Request] = []

    async def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "models": [{"name": "qwen:latest", "digest": "ignored"}, {"name": "qwen:latest"}]
            },
        )

    models = asyncio.run(
        OllamaHttpDiscoveryAdapter(transport=httpx.MockTransport(respond)).discover(
            "http://ollama:11434"
        )
    )

    assert models == ["qwen:latest"]
    assert requests[0].url.path == "/api/tags"
    assert requests[0].url.query == b""


@pytest.mark.parametrize(
    "endpoint",
    [
        "ftp://ollama:11434",
        "http://user:password@ollama:11434",
        "http://ollama:11434/api/tags",
        "http://ollama:11434?token=secret",
    ],
)
def test_ollama_discovery_rejects_unsafe_endpoint_forms(endpoint: str):
    async def respond(_request: httpx.Request) -> httpx.Response:
        pytest.fail("The adapter must reject endpoint forms before making a request")

    with pytest.raises(OllamaProviderFailure, match="invalid_endpoint"):
        asyncio.run(
            OllamaHttpDiscoveryAdapter(transport=httpx.MockTransport(respond)).discover(endpoint)
        )


def test_ollama_discovery_rejects_redirects_and_oversized_responses():
    async def redirect(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://169.254.169.254/"})

    with pytest.raises(OllamaProviderFailure, match="ollama_unreachable"):
        asyncio.run(
            OllamaHttpDiscoveryAdapter(transport=httpx.MockTransport(redirect)).discover(
                "http://ollama:11434"
            )
        )

    async def oversized(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-length": str(MAX_RESPONSE_BYTES + 1)})

    with pytest.raises(OllamaProviderFailure, match="response_too_large"):
        asyncio.run(
            OllamaHttpDiscoveryAdapter(transport=httpx.MockTransport(oversized)).discover(
                "http://ollama:11434"
            )
        )
