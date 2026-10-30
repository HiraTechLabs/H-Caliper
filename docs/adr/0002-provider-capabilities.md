# ADR 0002: Explicit provider capabilities

**Status:** Accepted

## Decision

Provider adapters expose a common interface and explicit capabilities. Chat-only providers use a structured patch protocol; CLI agents are only enabled through their actual installed/authenticated runtime. Mock remains test-only.

## Rationale

Providers differ in chat, tools, file editing, terminal, streaming, model discovery, and auth. Explicit capabilities prevent silent claims that unsupported operations work.

## Consequences

Adapter registration is not proof of availability. Health/model tests and real task acceptance must be reported separately. Provider-specific limits remain visible to users.
