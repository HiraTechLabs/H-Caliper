"""The 12 mandatory CALIPER principle documents.

Each document follows the governance structure required by the specification.
The thirteenth slot is reserved but intentionally not invented.
"""

from __future__ import annotations

from typing import Dict

CALIPER_DOCUMENTS = [
    {
        "slug": "test",
        "title": "Test Principles",
        "content": """# Test Principles

## Purpose
Prove that behaviour is correct, stable and repeatable before any change is accepted.

## Scope
All production code, migrations, API contracts, UI flows and infrastructure changes.

## Mandatory Rules
- Every behaviour change ships with an automated test at the lowest effective level.
- Bug fixes include a regression test that fails before the fix.
- Tests are deterministic: no wall-clock, network or ordering dependence without an explicit fixture.
- A failing mandatory test blocks acceptance; a skipped test is not a passing test.
- Tests must not depend on production credentials or production data.

## Recommended Practices
- Prefer unit tests for domain rules, integration tests for persistence and contract tests at service boundaries.
- Keep one logical assertion per test and name tests after behaviour.
- Use fixtures and factories instead of copy-pasted setup.

## Forbidden Practices
- Deleting or weakening a test to make a build pass.
- Asserting only that a function was called when observable behaviour can be asserted.
- Mocking the unit under test.

## Validation Criteria
- Test suite exits zero in the isolated development environment.
- New or changed behaviour has at least one test referencing the change.
- Coverage of touched critical paths does not decrease.

## Exceptions
Documentation-only changes may omit tests with a recorded justification.

## Approval Requirements
Any test removal or coverage reduction requires reviewer approval with a recorded reason.

## Version History
- v1 — initial constitutional version.
""",
    },
    {
        "slug": "logs",
        "title": "Logging Principles",
        "content": """# Logging Principles

## Purpose
Make production behaviour observable, diagnosable and auditable without leaking sensitive data.

## Scope
Application logs, audit logs, metrics, traces and agent execution records.

## Mandatory Rules
- Logs are structured and machine-readable.
- Never log secrets, tokens, passwords, private keys or full request bodies containing them.
- Every task-scoped log entry includes task, project, agent role, provider, model and stage when available.
- Errors are logged with a stable error category and enough context to reproduce.
- Audit events are separate from diagnostic logs and are retained according to policy.

## Recommended Practices
- Include correlation identifiers and durations.
- Use severity consistently: INFO for lifecycle, WARNING for recoverable anomalies, ERROR for failed operations.
- Prefer event names in the past tense (`task.completed`, `provider.failed`).

## Forbidden Practices
- `print`/`console.log` as the only diagnostic mechanism.
- Logging credentials even at DEBUG level.
- Unbounded log payloads.

## Validation Criteria
- Grep of changed code finds no credential logging.
- New operations emit at least one lifecycle event and failures emit an error event.

## Exceptions
None for credential redaction.

## Approval Requirements
Changes to audit retention or redaction policy require administrator approval.

## Version History
- v1 — initial constitutional version.
""",
    },
    {
        "slug": "graph",
        "title": "Graph and System Modeling Principles",
        "content": """# Graph and System Modeling Principles

## Purpose
Keep a truthful model of system components, data flows and dependencies.

## Scope
Architecture diagrams, dependency graphs, state machines and data lineage.

## Mandatory Rules
- Every new component or external dependency is reflected in the system model.
- State machines enumerate all states and transitions, including failure and cancellation paths.
- Diagrams are generated from or checked against the code where practical.
- A change that invalidates a diagram must update it in the same task.

## Recommended Practices
- Use Mermaid for version-controlled diagrams.
- Model trust boundaries explicitly (user, factory, development environment, production).

## Forbidden Practices
- Diagrams that contradict the implementation.
- Undocumented circular dependencies between modules.

## Validation Criteria
- Referenced diagram files exist and parse.
- New pipeline states appear in the state model.

## Exceptions
Exploratory spikes outside the main branch.

## Approval Requirements
Architecture boundary changes require reviewer approval.

## Version History
- v1 — initial constitutional version.
""",
    },
    {
        "slug": "security",
        "title": "Security Principles",
        "content": """# Security Principles

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
""",
    },
    {
        "slug": "business",
        "title": "Business Principles",
        "content": """# Business Principles

## Purpose
Ensure engineering work delivers the intended business outcome and preserves user trust.

## Scope
Feature scope, acceptance criteria, pricing-affecting behaviour, data handling and user communication.

## Mandatory Rules
- Every task states the business objective and measurable acceptance criteria.
- Scope changes are explicit and documented; no silent expansion.
- User-visible behaviour changes are documented for release notes.
- Data retention and privacy obligations are respected.

## Recommended Practices
- Link tasks to the problem, not only the requested solution.
- Prefer the smallest change that satisfies the objective.

## Forbidden Practices
- Implementing unrequested features that create operational risk.
- Breaking existing customer workflows without a migration path.

## Validation Criteria
- Acceptance criteria are testable and demonstrated in the task report.
- Documentation records the user-visible impact.

## Exceptions
Emergency fixes may be documented retrospectively within 24 hours.

## Approval Requirements
Changes affecting billing, authentication or data deletion require human approval.

## Version History
- v1 — initial constitutional version.
""",
    },
    {
        "slug": "architecture",
        "title": "Clean Architecture and Design Pattern Principles",
        "content": """# Clean Architecture Principles

## Purpose
Keep the system modular, testable and adaptable to change.

## Scope
Module boundaries, dependency direction, interfaces, persistence and integration design.

## Mandatory Rules
- Dependencies point inward: domain logic does not import transport, framework or vendor SDK code.
- External integrations sit behind explicit interfaces (ports) with adapters.
- Business rules are independently testable without a database or network.
- One module owns one responsibility; cross-module access goes through a public interface.
- Database schema changes use migrations and preserve referential integrity.

## Recommended Practices
- Composition root wires adapters; domain code receives dependencies explicitly.
- Prefer small, focused services over god objects.
- Use design patterns only when they remove real duplication or instability.

## Forbidden Practices
- Importing provider SDKs directly into domain services.
- Duplicating business rules in the UI and API.
- Circular dependencies or hidden global state.

## Validation Criteria
- Import-boundary review confirms dependency direction.
- New integrations implement an existing interface or define one.

## Exceptions
Documented transitional code with a removal task.

## Approval Requirements
Boundary or persistence-technology changes require reviewer approval.

## Version History
- v1 — initial constitutional version.
""",
    },
    {
        "slug": "ui-ux",
        "title": "UI/UX Principles",
        "content": """# UI/UX Principles

## Purpose
Deliver an interface that is clear, responsive and safe for enterprise operators.

## Scope
All web screens, forms, navigation, status displays and error messages.

## Mandatory Rules
- Every destructive action is confirmed and reversible where possible.
- Loading, empty, error and success states are designed for every screen.
- Status is never conveyed by colour alone.
- Forms validate input and preserve user input on failure.
- The interface is usable with keyboard and at mobile widths.

## Recommended Practices
- Show provenance (provider, model, timestamp) for AI-generated content.
- Stream live task progress and make logs accessible.
- Avoid unnecessary modals and dead-end pages.

## Forbidden Practices
- Non-functional buttons or placeholder actions presented as working.
- Hiding failures behind generic success toasts.
- Displaying secrets in the UI.

## Validation Criteria
- All required pages render with real data and explicit empty/error states.
- Accessibility checks for labels, focus and contrast pass.

## Exceptions
Internal debug screens may be less polished but must still be functional.

## Approval Requirements
Branding or navigation changes affecting all users require product approval.

## Version History
- v1 — initial constitutional version.
""",
    },
    {
        "slug": "git-branches",
        "title": "Git Branching Principles",
        "content": """# Git Branching Principles

## Purpose
Keep history traceable and prevent unreviewed changes from reaching protected branches.

## Scope
Branches, commits, merges, pull requests and release tagging.

## Mandatory Rules
- Each task uses an isolated branch named `hcaliper/task-{task-id}`.
- Never commit directly to the default branch.
- Never overwrite or discard user changes.
- Commits are small, meaningful and reference the task.
- Merging requires explicit human approval after review.
- Rejected work is preserved, not deleted.

## Recommended Practices
- Rebase or merge from the default branch before final review.
- Sign commits when infrastructure supports it.
- Tag releases with a semantic version.

## Forbidden Practices
- Force-pushing shared branches.
- Committing generated secrets or large binaries.
- Automatic merging by an AI agent.

## Validation Criteria
- Task diff is isolated to its branch.
- No protected-branch mutation without an approval record.

## Exceptions
Emergency hotfix process with incident approval.

## Approval Requirements
Merge and release actions require an authorized approver.

## Version History
- v1 — initial constitutional version.
""",
    },
    {
        "slug": "decisions",
        "title": "Technical and Architectural Decisions",
        "content": """# Decision Records

## Purpose
Preserve the reasoning behind significant technical choices.

## Scope
Architecture, vendor selection, data model, security posture and operational process.

## Mandatory Rules
- Every significant decision records context, options, decision, consequences and status.
- Superseded decisions are marked, never deleted.
- Decisions referenced by code are linked to the implementing change.

## Recommended Practices
- Use ADR format (`docs/decisions/NNNN-title.md`).
- Record rejected options and why they were rejected.

## Forbidden Practices
- Retroactive rewriting of decision history.
- Undocumented irreversible choices.

## Validation Criteria
- New architectural dependency or storage change has an ADR.
- Decision index is current.

## Exceptions
Reversible local implementation details.

## Approval Requirements
Decisions affecting security or data residency require administrator approval.

## Version History
- v1 — initial constitutional version.
""",
    },
    {
        "slug": "tech-stack",
        "title": "Technology Stack Principles",
        "content": """# Technology Stack Principles

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
""",
    },
    {
        "slug": "clean-code",
        "title": "Clean Code Principles",
        "content": """# Clean Code Principles

## Purpose
Make code easy to read, change and debug.

## Scope
Naming, structure, functions, comments, error handling and duplication.

## Mandatory Rules
- Names describe intent; no cryptic abbreviations.
- Functions have one reason to change and bounded complexity.
- Errors are handled explicitly; no silent exception swallowing.
- Comments explain why, not what.
- No dead code, commented-out blocks or duplicated business logic.

## Recommended Practices
- Keep modules cohesive and files focused.
- Prefer early returns and guard clauses.
- Make invalid states unrepresentable.

## Forbidden Practices
- Magic numbers without named constants.
- Copy-paste implementation of an existing behaviour.
- Broad `except Exception: pass`.

## Validation Criteria
- Linter and formatter pass.
- Review finds no duplicated logic or swallowed errors in the diff.

## Exceptions
None for swallowed errors.

## Approval Requirements
Not applicable.

## Version History
- v1 — initial constitutional version.
""",
    },
    {
        "slug": "performance",
        "title": "Performance Principles",
        "content": """# Performance Principles

## Purpose
Keep the system responsive and resource-efficient under realistic load.

## Scope
API latency, database queries, background jobs, agent execution and frontend rendering.

## Mandatory Rules
- No unbounded queries, loops or payloads on request paths.
- Database access uses indexes for filtered and joined columns.
- Long-running work runs in background workers, not request handlers.
- Expensive operations have timeouts and cancellation paths.

## Recommended Practices
- Measure before optimizing; record the baseline.
- Batch external calls and cache stable data where safe.
- Paginate all list endpoints.

## Forbidden Practices
- N+1 query patterns in new code.
- Loading entire tables into memory.
- Ignoring provider timeouts.

## Validation Criteria
- List endpoints paginate.
- New query paths have supporting indexes.
- Background jobs enforce timeouts.

## Exceptions
One-off administrative scripts with documented bounds.

## Approval Requirements
Performance-budget changes require reviewer approval.

## Version History
- v1 — initial constitutional version.
""",
    },
]

RESERVED_SLOT = {
    "slot": 13,
    "slug": "reserved-13",
    "title": "Reserved Principle Slot (not yet defined)",
    "content": """# Reserved Principle Slot

This slot is intentionally empty. The source specification mentions thirteen
CALIPER principles but defines only twelve. No thirteenth principle has been
invented.

An administrator may define and activate this principle through the CALIPER
management interface. Until then it is not loaded into agent context.
""",
}

BY_SLUG: Dict[str, dict] = {doc["slug"]: doc for doc in CALIPER_DOCUMENTS}
