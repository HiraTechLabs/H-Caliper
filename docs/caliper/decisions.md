# Decision Records

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
