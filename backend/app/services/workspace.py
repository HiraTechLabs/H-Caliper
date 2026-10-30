"""Workspace layout and isolation.

Layout (under WORKSPACE_ROOT/<project-slug>):

    repository/            mirror clone owned by the factory
    CALIPER/               rendered constitutions
    tasks/<task-id>/
        attempt-<n>/repository/   isolated git worktree for one attempt
        attempt-<n>/reports/
    artifacts/
    history/
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

from app.core.config import settings
from app.core.errors import bad_request, forbidden
from app.services import git_manager

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    slug = slug[:76].strip("-")
    if len(slug) < 2:
        slug = f"project-{slug or 'new'}"
    return slug


def validate_slug(slug: str) -> str:
    if not SLUG_RE.match(slug):
        raise bad_request("Slug must be 3-80 lowercase letters, digits or hyphens", "invalid_slug")
    return slug


def workspace_root() -> str:
    return os.path.realpath(settings.WORKSPACE_ROOT)


def project_path(slug: str) -> str:
    root = workspace_root()
    path = os.path.realpath(os.path.join(root, slug))
    if not (path == root or path.startswith(root + os.sep)):
        raise forbidden("Workspace path escapes the workspace root", "path_traversal")
    return path


def safe_join(root: str, *parts: str) -> str:
    resolved_root = os.path.realpath(root)
    candidate = os.path.realpath(os.path.join(resolved_root, *parts))
    if candidate != resolved_root and not candidate.startswith(resolved_root + os.sep):
        raise forbidden("Path escapes the workspace", "path_traversal")
    return candidate


@dataclass
class TaskWorktree:
    path: str
    branch: str
    base_commit: str


async def ensure_project_workspace(
    slug: str,
    *,
    repository_url: Optional[str],
    token: Optional[str],
    default_branch: str,
) -> str:
    root = project_path(slug)
    for sub in (
        "",
        "repository",
        "CALIPER",
        "tasks",
        "reports",
        "artifacts",
        "history",
    ):
        os.makedirs(os.path.join(root, sub), exist_ok=True)
    if repository_url:
        mirror = os.path.join(root, "repository")
        await git_manager.ensure_base(
            mirror, repository_url, token=token, default_branch=default_branch
        )
    return root


async def prepare_task_worktree(
    *,
    slug: str,
    task_id: str,
    attempt: int,
    branch: str,
    repository_url: Optional[str],
    token: Optional[str],
    default_branch: str,
) -> TaskWorktree:
    root = project_path(slug)
    mirror = os.path.join(root, "repository")
    if not os.path.isdir(os.path.join(mirror, ".git")):
        if not repository_url:
            raise bad_request(
                "Project has no repository configured; connect a repository first",
                "repository_not_configured",
            )
        await git_manager.ensure_base(mirror, repository_url, token=token, default_branch=default_branch)
    # Never discard changes in the mirror. It is factory-owned, so a dirty state
    # indicates a previous interrupted operation: fail closed.
    if await git_manager.is_dirty(mirror):
        raise git_manager.GitError(
            "Factory mirror repository has uncommitted changes; refusing to reuse it"
        )
    base_ref = f"origin/{default_branch}"
    try:
        base_commit = await git_manager.resolve_ref(mirror, base_ref)
    except git_manager.GitError:
        base_commit = await git_manager.resolve_ref(mirror, default_branch)
    path = os.path.join(root, "tasks", task_id, f"attempt-{attempt}", "repository")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.isdir(os.path.join(path, ".git")) or os.path.isfile(os.path.join(path, ".git")):
        import shutil

        shutil.rmtree(path, ignore_errors=True)
    commit = await git_manager.create_worktree(
        mirror, path, branch, base_commit, token=token
    )
    return TaskWorktree(path=path, branch=branch, base_commit=commit)


async def current_diff(path: str, base_commit: str) -> git_manager.DiffSummary:
    return await git_manager.diff_against(path, base_commit)
