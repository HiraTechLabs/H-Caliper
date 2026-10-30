# Logging Principles

## Purpose
Make production behaviour observable, diagnosable and auditable without leaking sensitive data.

## Scope
Application logs, audit logs, metrics, traces and agent execution records.

## Mandatory Rules
- Logs are structured and machine-readable.
- Never log secrets, tokens, passwords, private keys or full request bodies containing them.
- Every task-scoped log entry includes task, project, agent role, provider, model and stage when available.
- Errors are logged with a stable error category and enough context to reproduce.
- Audit events are separate from diagnostic logs and are retained according to policy.

## Recommended Practices
- Include correlation identifiers and durations.
- Use severity consistently: INFO for lifecycle, WARNING for recoverable anomalies, ERROR for failed operations.
- Prefer event names in the past tense (`task.completed`, `provider.failed`).

## Forbidden Practices
- `print`/`console.log` as the only diagnostic mechanism.
- Logging credentials even at DEBUG level.
- Unbounded log payloads.

## Validation Criteria
- Grep of changed code finds no credential logging.
- New operations emit at least one lifecycle event and failures emit an error event.

## Exceptions
None for credential redaction.

## Approval Requirements
Changes to audit retention or redaction policy require administrator approval.

## Version History
- v1 — initial constitutional version.
