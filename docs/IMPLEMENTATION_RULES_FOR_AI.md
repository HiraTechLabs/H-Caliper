# Implementation Rules for AI Coding Agents

1. Read AGENTS.md and all relevant manifest, decisions, graph, and principles before coding.
2. Treat Proposed decisions as proposals, not silently approved choices. Ask for approval for unresolved major architectural decisions.
3. Inspect the actual repository, branch, working tree, and runtime; do not invent file paths or assume deployed code matches the checkout.
4. Start with a concise plan and acceptance criteria.
5. Implement one complete vertical slice at a time: UI, API, application/domain behavior, persistence, tests, and documentation as applicable.
6. For mutations, verify durable state, a fresh read, and UI updates without manual refresh.
7. Use PostgreSQL-backed integration tests for persistence-sensitive behavior.
8. Keep secrets out of plaintext operational fields, frontend state, logs, and reports.
9. Never weaken authentication, authorization, SSH host verification, or security checks to make tests pass.
10. Preserve user changes, persistent volumes, data, and encryption keys.
11. Never run destructive tests against production or user data.
12. Update docs/WORK_LOG.md and a task report following repository rules.
13. Update decisions and graph when architecture, data ownership, security boundaries, or responsibilities change.
14. Follow branch conventions: feature/<name>, FIX/<name>, REFACTOR/<name>.
15. Do not merge, push, or deploy without explicit authorization.
16. Report exact commands, results, skipped checks, limitations, and manual prerequisites.
17. Do not claim completion based only on HTTP 200, a green mocked test, or the presence of a button.
18. Keep graph nodes marked planned until code and verification support implemented status.
19. Prefer a small complete vertical slice over scaffolding many unfinished features.
