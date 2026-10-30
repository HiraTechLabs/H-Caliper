"""Unified AI provider contract.

Capabilities are explicit.  An adapter that cannot perform a capability raises
``UnsupportedCapabilityError`` instead of pretending to succeed.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from app.core.enums import Capability


class ProviderError(Exception):
    code = "provider_error"
    retryable = False

    def __init__(self, message: str, *, detail: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or {}


class ProviderUnavailable(ProviderError):
    code = "provider_unavailable"
    retryable = True


class ProviderAuthenticationError(ProviderError):
    code = "provider_authentication"
    retryable = False


class ProviderRateLimited(ProviderError):
    code = "provider_rate_limit"
    retryable = True


class ProviderTimeout(ProviderError):
    code = "provider_timeout"
    retryable = True


class ProviderResponseError(ProviderError):
    code = "provider_response_invalid"
    retryable = False


class UnsupportedCapabilityError(ProviderError):
    code = "unsupported_capability"
    retryable = False


class UnsafeEndpointError(ProviderError):
    code = "unsafe_endpoint"
    retryable = False


@dataclass
class ProviderHealth:
    connected: bool
    status: str
    message: str = ""
    models: List[str] = field(default_factory=list)
    version: Optional[str] = None


@dataclass
class AgentRunResult:
    output: str
    exit_code: int
    duration_ms: int
    changed_files: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseProvider:
    type: str = "base"
    capabilities: set[Capability] = {Capability.CHAT}

    def __init__(
        self,
        *,
        name: str,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.name = name
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.config = config or {}

    def supports(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def capability_map(self) -> Dict[str, bool]:
        return {cap.value: cap in self.capabilities for cap in Capability}

    async def health(self) -> ProviderHealth:
        raise NotImplementedError

    async def list_models(self) -> List[str]:
        raise UnsupportedCapabilityError(
            f"{self.type} does not support model discovery"
        )

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> str:
        raise UnsupportedCapabilityError(f"{self.type} does not support chat completion")

    async def run_agent(
        self,
        *,
        workspace: str,
        prompt: str,
        model: str,
        timeout: int,
    ) -> AgentRunResult:
        raise UnsupportedCapabilityError(
            f"{self.type} has no agent runtime; it can be used for planning, review and "
            "documentation only"
        )


BLOCKED_HOSTS = {
    "metadata.google.internal",
    "metadata",
}

BLOCKED_NETWORKS = [
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fd00:ec2::254/128"),
]


def validate_outbound_url(url: str, *, allow_private: bool) -> str:
    """Reject non-HTTP, credential-bearing, loopback/metadata endpoints.

    Private LAN addresses remain usable (FreeLLMAPI/LM Studio live on the LAN)
    when explicitly allowed by configuration, but cloud metadata endpoints are
    always blocked.  DNS is resolved once here so a host cannot silently redirect
    the request to a metadata service.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeEndpointError("Provider endpoint must use http or https")
    if parsed.username or parsed.password:
        raise UnsafeEndpointError("Credentials must not be embedded in the URL")
    host = parsed.hostname
    if not host:
        raise UnsafeEndpointError("Provider endpoint has no hostname")
    if host in BLOCKED_HOSTS:
        raise UnsafeEndpointError("Metadata endpoints are not permitted")
    try:
        infos = socket.getaddrinfo(host, parsed.port or 80, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ProviderUnavailable(f"Cannot resolve provider host '{host}'") from exc
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if any(ip in network for network in BLOCKED_NETWORKS):
            raise UnsafeEndpointError("Link-local/metadata addresses are not permitted")
        if ip.is_loopback and not allow_private:
            raise UnsafeEndpointError("Loopback endpoints are disabled by policy")
        if (ip.is_private or ip.is_loopback) and not allow_private:
            raise UnsafeEndpointError("Private network endpoints are disabled by policy")
    return url
