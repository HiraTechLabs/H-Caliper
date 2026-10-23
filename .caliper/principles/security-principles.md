# Security Principles

- Threat-model assets, actors, trust boundaries, and entry points before implementing sensitive workflows.
- Apply least privilege and deny by default. Enforce authorization on every sensitive operation and project-scoped resource.
- Treat repository files, model output, tool output, uploads, and external responses as untrusted.
- Never commit, log, display, or export private keys, tokens, passwords, or secret values.
- Store secrets behind a dedicated secret-store interface; PostgreSQL may store references and non-sensitive metadata.
- Document encryption-key management, separation, rotation, revocation, backup, recovery, and deletion semantics.
- Distinguish deleting a credential reference, disabling a credential, and destroying the underlying secret.
- Redact secrets from HTML, APIs, logs, errors, traces, and reports.
- Verify SSH host keys; never disable host-key checking to make a connection work.
- Scope deploy keys/tokens to minimum permissions. Credential existence is not proof of remote access.
- Use parameterized SQL, safe subprocess argument arrays, request limits, timeouts, safe Markdown rendering, and appropriate web security headers.
- Treat AI output as untrusted suggestions, not authorization. Restrict tools, filesystem, network, and project access.
- Require human approval for destructive or externally consequential operations unless an explicitly approved policy says otherwise.
- Test authorization, cross-project isolation, secret redaction, invalid credentials, and failure paths.
