# Graph and System Modeling Principles

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
