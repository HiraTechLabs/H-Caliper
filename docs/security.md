# Security guide

## Required controls

1. Use unique random `SECRET_KEY` and Fernet `ENCRYPTION_KEY`; back up the encryption key separately.
2. Run `ENV=production`, `COOKIE_SECURE=true`, terminate TLS at a trusted proxy, and correctly configure trusted proxy counts.
3. Use unique DB credentials; firewall Postgres and management ports. Compose defaults publish the database/API for local convenience and must be changed for public deployment.
4. Keep production deployment disabled until explicitly configured, reviewed, and tested. Never give agents production credentials.
5. Use fine-grained short-lived Git tokens; never embed credentials in URLs. Rotate them at the source.
6. Scope `ALLOWED_LOCAL_REPO_ROOTS` narrowly. Do not expose root/home directories to local repository cloning.
7. Restrict provider URLs/egress. LAN provider support can create SSRF risk if untrusted users can register arbitrary endpoints.
8. Run task execution on a dedicated, least-privileged isolated host/container with resource limits and restricted network access.

## Application controls

Argon2 password hashing; HttpOnly session cookie; CSRF on unsafe cookie-authenticated requests; rate-limited API requests; ADMIN/OPERATOR/VIEWER roles; project membership checks; encrypted provider/repository secrets; audit-detail redaction; production startup secret validation; task-specific branches; argument-vector command execution with executable allowlist; secret and change-policy gates. Missing scanners are not reported as passed.

These controls do not make arbitrary repository code safe to execute. A build script may exploit worker OS permissions, tools, dependencies, filesystem access, or network routes. The Docker socket is not mounted by default; access to it is effectively host-root.

## Limitations and response

No built-in OIDC/SSO, MFA, distributed rate limiting, or external vault is included. Provider URL validation is not a substitute for egress firewalling. If compromised, disable the provider/user, rotate credentials, inspect audit/task history, preserve logs, and restore from known-good backups. Key rotation needs a ciphertext migration; changing Fernet key alone makes stored secrets unreadable.
