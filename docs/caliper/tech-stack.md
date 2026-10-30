# Technology Stack Principles

## Purpose
Keep the stack supportable, secure and intentionally small.

## Scope
Languages, frameworks, libraries, databases, infrastructure and build tooling.

## Mandatory Rules
- Pin production dependency versions and commit lock files.
- Prefer maintained libraries with a clear security record.
- New runtime dependencies require justification and review.
- The stack must be reproducible from a clean environment.

## Recommended Practices
- Prefer standard-library or already-present solutions before adding a dependency.
- Automate dependency and container vulnerability scanning.
- Keep development and production runtime versions aligned.

## Forbidden Practices
- Unpinned `latest` images or dependencies in production.
- Abandoned or unlicensed dependencies.
- Introducing a second tool for a problem already solved in the stack.

## Validation Criteria
- Build succeeds from lock files.
- Dependency scan has no unmitigated critical findings.

## Exceptions
Temporary evaluation dependencies confined to a spike branch.

## Approval Requirements
Database, framework or hosting changes require administrator approval.

## Version History
- v1 — initial constitutional version.
