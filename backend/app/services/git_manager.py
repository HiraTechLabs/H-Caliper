"""Safe Git operations.

The factory owns a mirror clone per project and creates an isolated ``git
worktree`` per task attempt.  All commands use argument lists and run with a
scrubbed environment.  Credentials are injected through Git's environment-based
config so they never appear in process arguments or audit records.
"""

from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import urlparse

from app.core.config import settings
from app.core.errors import bad_request, forbidden
from app.services.providers.process import run_command


class GitError(Exception):
    pass


@dataclass
class DiffSummary:
    diff: str
    stat: str
    files: List[str]
    additions: int
    deletions: int


GITHUB_HTTPS = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")


def parse_github(url: str) -> Optional[tuple[str, str]]:
    match = GITHUB_HTTPS.match(url.strip())
    return (match.group(1), match.group(2)) if match else None


def validate_repository_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise bad_request("Repository URL is required", "invalid_repository_url")
    if url.startswith(("https://", "http://")):
        parsed = urlparse(url)
        if parsed.username or parsed.password:
            raise bad_request("Do not embed credentials in the repository URL", "credentials_in_url")
        if not parsed.hostname:
            raise bad_request("Repository URL has no host", "invalid_repository_url")
        return url
    if url.startswith("git@"):
        raise bad_request(
            "SSH repository URLs are not supported yet; use an HTTPS URL",
            "unsupported_repository_transport",
        )
    # Local fixture repositories are only allowed below explicitly configured roots.
    if os.path.isabs(url):
        resolved = os.path.realpath(url)
        for root in settings.ALLOWED_LOCAL_REPO_ROOTS:
            root_path = os.path.realpath(root)
            if resolved == root_path or resolved.startswith(root_path + os.sep):
                return resolved
        raise forbidden(
            "Local repository paths are only allowed below ALLOWED_LOCAL_REPO_ROOTS",
            "local_repo_not_allowed",
        )
    raise bad_request("Unsupported repository URL", "invalid_repository_url")


def _git_env(token: Optional[str] = None, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    env = dict(extra or {})
    env.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": settings.GIT_AUTHOR_NAME,
            "GIT_AUTHOR_EMAIL": settings.GIT_AUTHOR_EMAIL,
            "GIT_COMMITTER_NAME": settings.GIT_AUTHOR_NAME,
            "GIT_COMMITTER_EMAIL": settings.GIT_AUTHOR_EMAIL,
        }
    )
    if token:
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env.update(
            {
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "http.extraheader",
                "GIT_CONFIG_VALUE_0": f"Authorization: Basic {basic}",
            }
        )
    return env


async def _run_git(
    args: List[str], *, cwd: str, token: Optional[str] = None, timeout: int = 300
) -> str:
    result = await run_command(
        ["git", *args], cwd=cwd, timeout=timeout, env=_git_env(token), max_output=500_000
    )
    if result.timed_out:
        raise GitError(f"git {args[0]} timed out")
    if result.exit_code != 0:
        message = (result.stderr or result.stdout).strip()[:1500]
        raise GitError(f"git {args[0]} failed: {message}")
    return result.stdout


async def clone_repository(
    url: str, destination: str, *, token: Optional[str] = None, branch: Optional[str] = None
) -> str:
    args = ["clone", "--no-hardlinks", "--quiet"]
    if branch:
        args += ["--branch", branch]
    args += [url, destination]
    await _run_git(args, cwd=os.path.dirname(destination) or "/tmp", token=token, timeout=900)
    return destination


async def fetch(destination: str, *, token: Optional[str] = None, remote: str = "origin") -> None:
    await _run_git(["fetch", "--prune", remote], cwd=destination, token=token)


async def resolve_ref(destination: str, ref: str) -> str:
    return (await _run_git(["rev-parse", ref], cwd=destination)).strip()


async def is_dirty(destination: str) -> bool:
    output = await _run_git(["status", "--porcelain"], cwd=destination)
    return bool(output.strip())


async def status_porcelain(destination: str) -> str:
    return await _run_git(["status", "--porcelain"], cwd=destination)


async def create_worktree(
    mirror: str, path: str, branch: str, base_ref: str, *, token: Optional[str] = None
) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        await _run_git(
            ["worktree", "add", "-b", branch, path, base_ref],
            cwd=mirror,
            token=token,
            timeout=600,
        )
    except GitError:
        # Attempt retries may reuse the branch name after an interrupted run.
        await _run_git(
            ["worktree", "add", "-B", branch, path, base_ref],
            cwd=mirror,
            token=token,
            timeout=600,
        )
    return await resolve_ref(path, "HEAD")


async def changed_files(path: str) -> List[str]:
    output = await _run_git(["status", "--porcelain"], cwd=path)
    files: List[str] = []
    for line in output.splitlines():
        if len(line) > 3:
            name = line[3:].strip()
            if " -> " in name:
                name = name.split(" -> ", 1)[1]
            files.append(name)
    return sorted(set(files))


async def diff_against(path: str, base_commit: str) -> DiffSummary:
    diff = await _run_git(
        ["diff", "--no-color", "--unified=3", base_commit], cwd=path, timeout=300
    )
    stat = await _run_git(["--no-pager", "diff", "--stat", base_commit], cwd=path)
    files_out = await _run_git(["diff", "--name-only", base_commit], cwd=path)
    additions = deletions = 0
    for line in stat.splitlines():
        match = re.search(r"(\d+) insertions?\(\+\)", line)
        if match:
            additions += int(match.group(1))
        match = re.search(r"(\d+) deletions?\(-\)", line)
        if match:
            deletions += int(match.group(1))
    return DiffSummary(
        diff=diff[: settings.MAX_ARTIFACT_BYTES],
        stat=stat,
        files=[f for f in files_out.splitlines() if f],
        additions=additions,
        deletions=deletions,
    )


async def untracked_files(path: str) -> List[str]:
    output = await _run_git(["ls-files", "--others", "--exclude-standard"], cwd=path)
    return [f for f in output.splitlines() if f]


async def stage_all(path: str) -> None:
    # Runtime artefacts must never enter a task commit. Exclusions are applied
    # as Git pathspecs rather than deleting anything from the user's tree.
    await _run_git(
        [
            "add",
            "--all",
            "--",
            ".",
            ":(exclude,glob)**/__pycache__/**",
            ":(exclude,glob)**/*.pyc",
            ":(exclude,glob)**/.pytest_cache/**",
            ":(exclude,glob)**/node_modules/**",
            ":(exclude,glob)**/.next/**",
            ":(exclude,glob)**/.venv/**",
            ":(exclude,glob)**/target/**",
            ":(exclude,glob)**/dist/**",
            ":(exclude,glob)**/build/**",
        ],
        cwd=path,
    )


async def commit_all(path: str, message: str) -> Optional[str]:
    await stage_all(path)
    if not (await is_dirty(path)):
        return None
    await _run_git(["commit", "-m", message], cwd=path, timeout=300)
    return (await resolve_ref(path, "HEAD")).strip()


async def log(path: str, limit: int = 10) -> List[Dict[str, str]]:
    output = await _run_git(
        ["log", f"-{limit}", "--pretty=format:%H%x1f%an%x1f%ae%x1f%ad%x1f%s", "--date=iso"],
        cwd=path,
    )
    entries = []
    for line in output.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 5:
            entries.append(
                {"sha": parts[0], "author": parts[1], "email": parts[2], "date": parts[3], "subject": parts[4]}
            )
    return entries


async def ensure_base(mirror: str, url: str, *, token: Optional[str] = None, default_branch: str = "main") -> str:
    if not os.path.isdir(os.path.join(mirror, ".git")):
        parent = os.path.dirname(mirror)
        os.makedirs(parent, exist_ok=True)
        await clone_repository(url, mirror, token=token, branch=default_branch)
    else:
        await fetch(mirror, token=token)
    base_ref = f"origin/{default_branch}" if os.path.isdir(os.path.join(mirror, ".git")) else default_branch
    try:
        return await resolve_ref(mirror, base_ref)
    except GitError:
        return await resolve_ref(mirror, "HEAD")


async def merge_into_default(
    mirror: str, branch: str, default_branch: str, *, push: bool = False, token: Optional[str] = None
) -> str:
    """Merge a reviewed task branch.  Only ever called after explicit approval."""
    await _run_git(["checkout", default_branch], cwd=mirror, timeout=120)
    await _run_git(["merge", "--no-ff", "--no-edit", branch], cwd=mirror, timeout=300)
    sha = (await resolve_ref(mirror, "HEAD")).strip()
    if push:
        await _run_git(["push", "origin", default_branch], cwd=mirror, token=token, timeout=600)
    return sha


async def create_pull_request(
    *,
    token: str,
    owner: str,
    repo: str,
    title: str,
    body: str,
    head: str,
    base: str,
) -> Dict:
    import httpx

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"https://api.github.com/repos/{owner}/{repo}/pulls",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={"title": title, "body": body, "head": head, "base": base},
        )
    if response.status_code >= 400:
        raise GitError(f"GitHub PR creation failed ({response.status_code}): {response.text[:500]}")
    data = response.json()
    return {"url": data.get("html_url"), "number": data.get("number")}
