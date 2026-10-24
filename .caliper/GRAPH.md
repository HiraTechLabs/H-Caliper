# Caliper Architecture Graph

`.caliper/graph.yaml` is the machine-readable graph used by visual rendering. This Markdown file explains the intended responsibilities. All graph nodes are planned until implementation and verification support a different status.

## Components
- **web-ui:** shadcn/ui application and visual Principles Workspace.
- **api:** request validation, authorization, and stable transport contracts.
- **application-services:** use cases, orchestration, transaction policy, and result mapping.
- **domain:** framework-independent business entities and invariants.
- **postgresql:** authoritative operational data.
- **secret-store:** Fernet-encrypted secret files with a separately persisted keyring; PostgreSQL stores references only.
- **repository-adapter:** Bounded Git access with strict SSH host verification, branch/revision inspection, and sanitized knowledge synchronization. Repository files are untrusted; only selected documentation formats enter PostgreSQL snapshots.
- **knowledge-files:** version-controlled manifest, principles, decisions, and graph.
- **principles-workspace:** Authenticated UI for searching and navigating revisioned manifest, principles, decisions, and validated architecture graph snapshots.
- **model-router:** shared internal model invocation contract.
- **provider-login-adapter:** documented provider-account authorization where supported.
- **ollama-adapter:** Ollama endpoint validation and model discovery; inference is not implemented yet.
- **Ollama connection settings:** A single-administrator connection record stores the configured endpoint, last checked status, discovered model identifiers, and selected model. Endpoint credentials and invocation are outside this slice.
- **opencode-adapter:** OpenCode CLI/API provider discovery, documented API-key/OAuth authentication, encrypted-profile lifecycle, and model selection.
- **task-runner:** durable task lifecycle and background execution.
- **event-stream:** optional progress delivery for long-running work; never authoritative state.
- **tests:** unit, PostgreSQL integration, contract, security, UI, and end-to-end tests.
- **container-platform:** images, Compose, health checks, configuration, and persistent volumes.
- **tls-gateway:** Caddy HTTPS termination and persistent internal certificate authority.
- **administrator-auth:** single administrator password verification and revocable sessions.

OpenCode credentials are stored as one encrypted Secret Store profile. OpenCode receives a temporary runtime copy from a memory-backed directory; PostgreSQL stores only the encrypted-profile reference and selected model identifier.

## Required flow
UI → TLS gateway → API authentication → application use case → domain rules and infrastructure ports → PostgreSQL/secret store/repository/model adapter. PostgreSQL keeps project-scoped credential references and lifecycle metadata; secret payloads live only in the encrypted secret store. A mutation reports success only after required durable work succeeds. The UI then renders the server-confirmed result. Long-running work persists status; events only communicate progress. Knowledge sync records repository, branch, revision, timestamp, and outcome; selected files are bounded, credential-redacted, and stored as derived snapshots while the repository remains the source of truth. Administrator passwords are Argon2id hashes; session tokens are only stored as hashes.

## Dependency rule
Dependencies point inward. Domain code must not import web frameworks, ORM entities, PostgreSQL drivers, UI libraries, provider SDKs, or Git CLI details. Infrastructure adapters implement ports defined by inner layers.
