# Git Branching Principles

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
