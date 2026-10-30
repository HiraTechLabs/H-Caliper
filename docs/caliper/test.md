# Test Principles

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
