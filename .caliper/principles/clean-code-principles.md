# Clean Code Principles

- Prefer clarity over cleverness; use names that express domain intent.
- Keep functions cohesive and modules aligned with business capabilities or clear technical responsibilities.
- Avoid duplicated business rules, hidden global state, speculative abstractions, and unrelated refactoring.
- Keep I/O and side effects at explicit boundaries.
- Use specific errors for validation, authorization, missing configuration, external failure, timeout, and internal defects.
- Do not catch exceptions to continue with stale or fabricated data.
- Do not report success before required durable work completes.
- Keep changes scoped, remove dead code introduced by a task, and do not suppress checks without justification.
- Comments explain why or constraints, not what the code already says.
