# User guide

## Submit work

Choose an active project with a Git repository, open **New task**, enter a specific title/request and acceptance criteria, verify the Planning/Execution/Review/Documentation provider/model selections, choose a bounded retry limit, and submit. Project defaults prefill agent selections; task choices override them.

## Monitor and review

Task view refreshes from persisted task/events. Inspect current stage, provider/model, retries, branch, event log, plan, diff, quality gates, independent review, docs, and artifacts. Gate states include PASSED, FAILED, WARNING, NOT_CONFIGURED, and SKIPPED. A missing scanner is not a pass; a failed required gate blocks acceptance. Review the diff yourself.

Cancel requests stop at a safe checkpoint and preserve artifacts. Replan is available for eligible failed/blocked/awaiting-approval tasks subject to retry limits.

## CALIPER and permissions

CALIPER documents are project-specific and versioned. Protected changes require admin authorization; proposals are inactive until approved. Slot 13 is intentionally unspecified until defined by an administrator.

- Viewer: read accessible projects/tasks.
- Operator: submit tasks and manage permitted project settings.
- Administrator: manage global users/providers/audit and approve governance, merge, deployment decisions.

Non-admins need project membership. Request membership from an administrator when a project is not visible.
