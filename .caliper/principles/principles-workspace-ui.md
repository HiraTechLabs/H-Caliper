# Principles Workspace UI Principles

Render canonical files as a navigable visual workspace; do not create a separate visual-only source of truth.

Required views: Principles, Manifest, Decisions, and Graph. Include safe rendered Markdown, search, tags/categories, cross-links, decision cards, and an interactive graph sourced from `graph.yaml`. Display repository, branch, revision, last successful sync, and sync status.

The UI must be accessible, keyboard navigable, responsive, and consistent with shadcn/ui. Do not rely on color alone for status.

On sync, show pending state and prevent duplicate submissions. Show success only after synchronization and validation complete, then update the visible content from the confirmed revision. On failure, show an actionable error and mark retained content as stale. Never silently present stale content as current.

For mutations, update from server-confirmed state without requiring manual refresh. Optimistic updates are allowed only with tested rollback behavior. Provide useful loading, empty, error, and success states.
