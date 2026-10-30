# Clean Code Principles

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
