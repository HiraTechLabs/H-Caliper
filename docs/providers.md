# Provider integration guide

The registry exposes declared capabilities. Configure providers, test connectivity, and verify actual model IDs. A health/model-list test and a real agent-task acceptance test are distinct.

| Adapter | Interface/config | Notes |
| --- | --- | --- |
| FreeLLMAPI | Configured OpenAI-compatible HTTP endpoint, optional key | Service compatibility and routing vary |
| LM Studio | Configured OpenAI-compatible HTTP endpoint | Usually local/LAN; verify network from backend host |
| OpenAI-compatible | HTTP base URL and optional key | Advertised capabilities are adapter claims; verify server behavior |
| Ollama | Ollama HTTP base URL | Local model availability is host-specific |
| OpenCode | Local CLI | Default container does not install/authenticate CLI |
| Codex | Local CLI/account | Authentication and subscription constraints apply; absent by default |
| Antigravity | Local CLI | Host install/auth is required; absent by default |
| Mock | Built-in test provider | Test-only; never proof of live AI connectivity |

For LAN services, configure an address reachable from the backend/container; browser `localhost` is not the backend host. Restrict egress using firewalls. Do not allow untrusted users to configure arbitrary provider URLs: this can create SSRF access. CLI adapters need a reviewed worker image, least-privileged noninteractive auth, version verification, harmless task test, and credential isolation. Never mount a developer home/token store wholesale.

Troubleshooting: UNREACHABLE—DNS/routing/base path; AUTH_FAILED—credential/scope; empty model discovery—provider does not implement discovery, add actual model manually; chat succeeds but task fails—inspect agent capability/schema, worker logs, and gates.
