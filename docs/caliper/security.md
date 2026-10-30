# Security Principles

## Purpose
Protect credentials, customer data, production systems and the factory itself.

## Scope
Authentication, authorization, secrets, input handling, network access, agent execution and deployment.

## Mandatory Rules
- Deny by default: every endpoint and capability requires explicit authorization.
- Secrets are encrypted at rest, redacted in logs and never returned to clients.
- All inputs are validated server-side; output is encoded for its context.
- Commands are executed without a shell, with argument allowlists and timeouts.
- Filesystem access is confined to the task workspace; path traversal is rejected.
- Outbound provider calls validate endpoints and block link-local/metadata addresses.
- Production access is disabled unless explicitly configured and approved.
- Dependencies are scanned for known vulnerabilities before release.

## Recommended Practices
- Least privilege for tokens, containers and database roles.
- Short-lived credentials and rotation support.
- Security tests for authorization boundaries and injection attempts.

## Forbidden Practices
- Hardcoded credentials or default administrator passwords.
- Disabling TLS verification globally.
- Granting AI agents unrestricted production shell access.
- Trusting AI-generated commands as authorization.

## Validation Criteria
- Secret scan is clean.
- Authorization tests pass for every role/project boundary.
- No shell=True, eval or unsafe deserialization introduced.

## Exceptions
Time-boxed exceptions require an administrator-approved record with an expiry date.

## Approval Requirements
Any relaxation of a mandatory security rule requires administrator approval.

## Version History
- v1 — initial constitutional version.
