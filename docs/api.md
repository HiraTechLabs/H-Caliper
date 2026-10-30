# API reference

REST prefix: `/api/v1`. OpenAPI docs: `/api/docs` when not production. Cookie-authenticated mutations require `X-CSRF-Token` matching `hcaliper_csrf`. Bearer tokens are also supported.

| Group | Purpose |
| --- | --- |
| `/auth/*` | Bootstrap status/setup, login/logout, current user |
| `/users` | Admin user management |
| `/projects` | Projects, repositories, memberships |
| `/projects/{id}/environments`, `/environments/*` | Environment metadata and checks |
| `/providers/*` | Provider types, configuration, tests, models |
| `/projects/{id}/caliper`, `/caliper/*` | Principles, versions, proposals, decisions |
| `/tasks/*` | Task submit/list/detail/events/artifacts/diff/cancel/replan |
| `/approvals`, `/deployments/*` | Human decisions and deployment records |
| `/dashboard` | Factory summary |
| `/audit` | Admin-only searchable audit trail |
| `/notifications` | User/system notifications |
| `/health`, `/health/ready` | Liveness/readiness |

See generated OpenAPI for exact schemas. Unsupported/incomplete provider capabilities are explicit rather than claimed as working.
