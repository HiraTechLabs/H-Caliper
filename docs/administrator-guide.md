# Administrator guide

## Initial setup

Use the first-run setup to create an administrator. Bootstrap succeeds only while no user exists; no default credentials are seeded. Secure the public ingress before deployment.

## Providers and project defaults

Register an actual adapter and endpoint, test connectivity, discover models or add exact manual IDs. Health does not imply every capability works. Set enabled providers/models for all four roles in project defaults. Rotate keys at their source; stored credentials are write-only.

## Projects and gates

Create project and connect HTTPS Git repository. Private repositories should use least-privilege token. Configure validation commands appropriate to the project stack. Executables are allowlisted and shell operators rejected. Set required gates for blockers; optional gate failures are warnings.

## Accounts and approvals

Create users with secure temporary passwords and least privilege. Add them to only required projects. Review actual task diff, gate output, review report, and documentation before merge approval. Remote push behavior requires explicit project configuration and credentials. Production environment creation leaves deployment disabled; production requires separate enablement, authorization, approval, and target test.

## Operations

Inspect audit history, readiness, worker logs, free disk, failed tasks, provider checks, and backups. Configure `AUDIT_RETENTION_DAYS` deliberately. Perform restore drills. Review [security](security.md) and [deployment](deployment.md).
