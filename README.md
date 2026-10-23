# Caliper v2 — Foundation Workspace

**Status:** Proposed foundation; review and approve before implementation.  
**Stack constraints:** Python backend, PostgreSQL operational database, shadcn/ui component system, Dockerized application and required services.

## Canonical files
- `.caliper/manifest.yaml`: project identity, constraints, and release gates.
- `.caliper/DECISIONS.md`: proposed architectural decisions and their status.
- `.caliper/GRAPH.md` and `.caliper/graph.yaml`: human and machine architecture graph.
- `.caliper/principles/`: engineering, security, performance, testing, business, clean architecture, clean code, model-provider, and workspace UI principles.
- `docs/INITIAL_ACCEPTANCE_CRITERIA.md`: initial release gates.
- `docs/IMPLEMENTATION_RULES_FOR_AI.md`: instructions for coding agents.

## Source-of-truth policy
- Version-controlled files are authoritative for project principles, decisions, manifest, and architecture graph.
- PostgreSQL is authoritative for operational data: projects, task records, approvals, provider configuration metadata, and execution state.
- Secret values live behind a dedicated secret-store interface, never in ordinary database fields as plaintext.
- UI state is a projection of server-confirmed state. Caches are disposable and rebuildable.
- Sync must record source repository, branch, revision, time, and outcome; stale data must be labelled stale.

## Principles Workspace visual requirements
The workspace must render and connect the canonical files rather than maintain a separate visual copy. Provide navigation for Principles, Manifest, Decisions, and Graph; safe Markdown rendering; search and cross-links; a visual graph based on `graph.yaml`; decision cards; revision and sync metadata; accessible keyboard interaction; responsive layout; and explicit loading, empty, success, stale, and failure states. Never show cached content as current after a failed sync.

## Model connection methods
Caliper must support three distinct methods:
1. Provider login/authenticated account, only through a legitimate documented flow supported by that provider.
2. Ollama endpoint with connection validation and model discovery where supported.
3. OpenCode CLI integration using its configured provider/model identifiers.

These methods have different authentication, discovery, diagnostics, and lifecycle semantics. They require separate adapters.

## Delivery rule
Prove project persistence, credential lifecycle, truthful status, repository sync, and UI refresh behavior before building broad autonomous execution/deployment capabilities.
