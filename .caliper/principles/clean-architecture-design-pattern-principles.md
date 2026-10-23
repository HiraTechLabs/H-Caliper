# Clean Architecture and Design Pattern Principles

## Dependency direction
Frameworks/drivers → interface adapters → application use cases → domain. Dependencies point inward.

## Responsibilities
- **Domain:** entities, value objects, invariants, and domain errors; no I/O or framework dependencies.
- **Application:** use cases, orchestration, transaction policy, and ports for persistence, secrets, Git, model invocation, clock, and task execution as needed.
- **Adapters:** translate HTTP, database, Git, secret store, and provider-specific details into application contracts.
- **Infrastructure:** implement PostgreSQL, migrations, secret storage, process execution, model adapters, and container integrations.

## Patterns to use deliberately
- Repository/UoW where they clarify persistence and transaction boundaries; avoid empty wrappers.
- Adapter for Ollama, OpenCode, provider login, Git, and secret storage.
- State machine for task lifecycle and constrained workflows.
- Strategy when multiple implementations share a stable contract.
- Dependency injection at composition boundaries; avoid global service locators.
- Outbox/durable event patterns only when required to keep state changes and event publication consistent.
- Avoid speculative abstractions, unnecessary inheritance, and generic frameworks.

## Consistency
A mutation is successful only when required durable work succeeds. Cross-store operations may not share one ACID transaction; define ordering, intermediate states, compensation, and recovery. Never hide failed side effects behind broad exception handlers. Architecture changes must update decisions and graph when meaningful.
