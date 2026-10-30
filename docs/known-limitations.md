# Known limitations and roadmap

## Limitations

- Provider adapters require real endpoints, credentials, and deployment-specific verification. CLI tools are absent from default image.
- GitHub live operations require scoped credentials; SSH clone transport is not supported.
- Worker queue uses PostgreSQL polling; suitable for modest scale, not high-throughput orchestration.
- Task command runner is not a hardened hostile-code sandbox. Shell-free allowlisting does not isolate kernel/filesystem/dependency/network access.
- Workspaces are local shared volume; no S3 backend or remote executor.
- SSH environment is represented but not a general remote shell execution integration.
- Production deployment is disabled by default and requires separate secure configuration/testing.
- No OIDC/SSO, MFA, distributed rate limiting, or external secret vault in this initial release.
- SQLite tests do not prove all PostgreSQL semantics; container and migrations need deployment CI.
- Frontend bundle-size advisory should be resolved with route-based lazy loading for constrained clients.

## Roadmap

1. CI with PostgreSQL integration/migration tests, container scanning, SBOM, frontend checks.
2. Hardened per-task sandboxing, resource/egress limits, safe dependency caches.
3. Real provider contract tests on explicitly configured runners; publish verified versions/capabilities.
4. GitHub App auth, tested PR workflow, safer credential rotation.
5. External vault and encryption-key rotation tooling.
6. Object storage/artifact retention, SSO/MFA, distributed throttling.
7. Signed deployment artifacts, rollback, and production health verification.
