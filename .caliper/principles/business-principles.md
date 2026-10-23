# Business Principles

Caliper is a software factory, not merely a dashboard or prompt launcher. It should manage project context and guide work from planning through implementation, verification, review, and controlled delivery.

- Reliability before feature breadth: project, credential, sync, and task operations must work end to end before expanding automation.
- A visible button or HTTP 200 does not establish feature completion.
- Each project owns its repository mapping, knowledge revision, credentials, policies, tasks, and execution history.
- Never leak context or secrets across projects.
- Keep humans in control of destructive operations, permission changes, external publication, and production deployment unless an approved policy explicitly allows automation.
- Distinguish configured, validated, connected, synchronized, stale, running, succeeded, and failed.
- Show timestamps and evidence for status claims where relevant.
- Never present stale cached content as freshly synchronized.
- Define acceptance criteria before coding; maintain an explicit distinction between planned, implemented, and verified.
- Do not merge, push, or deploy without authorization.
