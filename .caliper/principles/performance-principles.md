# Performance Principles

- Measure before optimizing; never sacrifice correctness or security for speed.
- Keep HTTP handlers bounded. Run long model/Git operations as durable background tasks.
- Use PostgreSQL indexes based on query plans and observed workloads; avoid N+1 queries and unbounded results.
- Set explicit timeouts. Retry only operations safe to retry; use idempotency/deduplication where needed.
- Give immediate UI feedback that an operation was accepted, but do not claim completion prematurely.
- Update the UI from confirmed results. Use SSE/WebSockets only when live progress adds value; events are not the source of truth.
- Bound task concurrency, queue length, subprocess resources, memory, and execution time.
- Support cancellation and graceful shutdown without leaving false success states.
- Report performance measurements with environment, workload, and method; do not invent benchmarks.
