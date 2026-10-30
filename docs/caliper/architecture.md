# Clean Architecture Principles

## Purpose
Keep the system modular, testable and adaptable to change.

## Scope
Module boundaries, dependency direction, interfaces, persistence and integration design.

## Mandatory Rules
- Dependencies point inward: domain logic does not import transport, framework or vendor SDK code.
- External integrations sit behind explicit interfaces (ports) with adapters.
- Business rules are independently testable without a database or network.
- One module owns one responsibility; cross-module access goes through a public interface.
- Database schema changes use migrations and preserve referential integrity.

## Recommended Practices
- Composition root wires adapters; domain code receives dependencies explicitly.
- Prefer small, focused services over god objects.
- Use design patterns only when they remove real duplication or instability.

## Forbidden Practices
- Importing provider SDKs directly into domain services.
- Duplicating business rules in the UI and API.
- Circular dependencies or hidden global state.

## Validation Criteria
- Import-boundary review confirms dependency direction.
- New integrations implement an existing interface or define one.

## Exceptions
Documented transitional code with a removal task.

## Approval Requirements
Boundary or persistence-technology changes require reviewer approval.

## Version History
- v1 — initial constitutional version.
