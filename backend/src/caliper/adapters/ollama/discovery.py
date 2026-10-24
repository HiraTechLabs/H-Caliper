import json
from urllib.parse import urlsplit

import httpx

from caliper.application.ollama_provider import OllamaProviderFailure

MAX_RESPONSE_BYTES = 1024 * 1024
MAX_MODELS = 500


class OllamaHttpDiscoveryAdapter:
    def __init__(
        self,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 4.0,
    ):
        self._transport = transport
        self._timeout = timeout_seconds

    async def discover(self, endpoint_url: str) -> list[str]:
        try:
            parsed = urlsplit(endpoint_url)
            valid = (
                parsed.scheme in {"http", "https"}
                and parsed.hostname is not None
                and (parsed.port is None or 0 < parsed.port < 65536)
                and parsed.username is None
                and parsed.password is None
                and not parsed.query
                and not parsed.fragment
                and parsed.path in {"", "/"}
            )
        except ValueError:
            valid = False
        if not valid:
            raise OllamaProviderFailure("invalid_endpoint")
        try:
            async with (
                httpx.AsyncClient(
                    timeout=self._timeout,
                    follow_redirects=False,
                    trust_env=False,
                    transport=self._transport,
                ) as client,
                client.stream("GET", f"{endpoint_url.rstrip('/')}/api/tags") as response,
            ):
                if response.is_error or response.is_redirect:
                    raise OllamaProviderFailure("ollama_unreachable")
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > MAX_RESPONSE_BYTES:
                    raise OllamaProviderFailure("response_too_large")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise OllamaProviderFailure("response_too_large")
        except OllamaProviderFailure:
            raise
        except (httpx.HTTPError, ValueError, OSError):
            raise OllamaProviderFailure("ollama_unreachable") from None
        try:
            payload = json.loads(body)
        except (ValueError, RecursionError):
            raise OllamaProviderFailure("invalid_model_catalog") from None

        models = payload.get("models") if isinstance(payload, dict) else None
        if not isinstance(models, list) or len(models) > MAX_MODELS:
            raise OllamaProviderFailure("invalid_model_catalog")
        identifiers: list[str] = []
        for model in models:
            if not isinstance(model, dict):
                raise OllamaProviderFailure("invalid_model_catalog")
            name = model.get("name")
            if not isinstance(name, str) or not name or len(name) > 256:
                raise OllamaProviderFailure("invalid_model_catalog")
            if name not in identifiers:
                identifiers.append(name)
        return identifiers
