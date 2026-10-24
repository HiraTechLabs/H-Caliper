import re
from typing import Any
from urllib.parse import quote

import httpx


class OpenCodeFailure(RuntimeError):
    def __init__(self, code: str = "opencode_unavailable"):
        super().__init__(code)
        self.code = code


class OpenCodeHttpAdapter:
    def __init__(self, base_url: str = "http://127.0.0.1:4096", timeout_seconds: float = 8):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def health(self) -> dict[str, Any]:
        return await self._request("GET", "/global/health")

    async def providers(self) -> dict[str, Any]:
        return await self._request("GET", "/provider")

    async def auth_methods(self) -> dict[str, Any]:
        return await self._request("GET", "/provider/auth")

    async def set_auth(self, provider_id: str, payload: dict[str, Any]) -> bool:
        return bool(
            await self._request("PUT", f"/auth/{self._provider_path(provider_id)}", json=payload)
        )

    async def remove_auth(self, provider_id: str) -> bool:
        return bool(await self._request("DELETE", f"/auth/{self._provider_path(provider_id)}"))

    async def authorize(
        self, provider_id: str, method: int, inputs: dict[str, str]
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/provider/{self._provider_path(provider_id)}/oauth/authorize",
            json={"method": method, "inputs": inputs},
        )

    async def oauth_callback(self, provider_id: str, method: int, code: str) -> bool:
        return bool(
            await self._request(
                "POST",
                f"/provider/{self._provider_path(provider_id)}/oauth/callback",
                json={"method": method, "code": code},
            )
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.request(method, f"{self.base_url}{path}", **kwargs)
            if response.status_code >= 400 or len(response.content) > 8 * 1024 * 1024:
                raise OpenCodeFailure("opencode_request_failed")
            return response.json()
        except OpenCodeFailure:
            raise
        except (httpx.HTTPError, ValueError) as error:
            raise OpenCodeFailure() from error

    @staticmethod
    def _provider_path(provider_id: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", provider_id):
            raise ValueError("Invalid provider identifier")
        return quote(provider_id, safe="")
