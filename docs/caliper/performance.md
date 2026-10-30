# Performance Principles

## Purpose
Keep the system responsive and resource-efficient under realistic load.

## Scope
API latency, database queries, background jobs, agent execution and frontend rendering.

## Mandatory Rules
- No unbounded queries, loops or payloads on request paths.
- Database access uses indexes for filtered and joined columns.
- Long-running work runs in background workers, not request handlers.
- Expensive operations have timeouts and cancellation paths.

## Recommended Practices
- Measure before optimizing; record the baseline.
- Batch external calls and cache stable data where safe.
- Paginate all list endpoints.

## Forbidden Practices
- N+1 query patterns in new code.
- Loading entire tables into memory.
- Ignoring provider timeouts.

## Validation Criteria
- List endpoints paginate.
- New query paths have supporting indexes.
- Background jobs enforce timeouts.

## Exceptions
One-off administrative scripts with documented bounds.

## Approval Requirements
Performance-budget changes require reviewer approval.

## Version History
- v1 — initial constitutional version.
