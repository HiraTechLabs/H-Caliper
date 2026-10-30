from __future__ import annotations

import subprocess

import pytest

from app.core.config import settings
from app.services import git_manager, quality_gates


def git(cwd: str, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


@pytest.mark.asyncio
async def test_gate_policy_reports_real_outcomes(tmp_path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / "ok.py").write_text("print('ok')\n", encoding="utf-8")
    outcome = await quality_gates.run_command_gate(
        quality_gates.GateInput("python-syntax", "python3 -m py_compile ok.py", required=True),
        str(workspace),
    )
    assert outcome.status == "PASSED"
    invalid = await quality_gates.run_command_gate(
        quality_gates.GateInput("unsafe", "python3 -c 'print(1)' && whoami"), str(workspace)
    )
    assert invalid.status == "NOT_CONFIGURED"
    assert "Shell operators" in invalid.output


@pytest.mark.asyncio
async def test_secret_scan_and_protected_change_policy(tmp_path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / "settings.py").write_text('API_KEY = "sk-1234567890123456789012345678"\n', encoding="utf-8")
    secret = await quality_gates.secret_scan(str(workspace), ["settings.py"])
    assert secret.status == "FAILED"
    blocked = await quality_gates.worktree_hygiene(str(workspace), ["CALIPER/manifest.md"], ["CALIPER/manifest.md"])
    assert blocked.status == "FAILED"


@pytest.mark.asyncio
async def test_git_worktree_isolation_commit_and_diff(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    (root / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=root, check=True)
    base = git(str(root), "rev-parse", "HEAD")
    first = tmp_path / "task-one"
    second = tmp_path / "task-two"
    await git_manager.create_worktree(str(root), str(first), "hcaliper/task-one", base)
    await git_manager.create_worktree(str(root), str(second), "hcaliper/task-two", base)
    (first / "README.md").write_text("changed\n", encoding="utf-8")
    (first / "__pycache__").mkdir()
    (first / "__pycache__" / "junk.pyc").write_bytes(b"runtime")
    sha = await git_manager.commit_all(str(first), "test change")
    assert sha
    assert await git_manager.resolve_ref(str(second), "HEAD") == base
    assert "__pycache__" not in git(str(first), "show", "--pretty=", "--name-only", "HEAD")
    diff = await git_manager.diff_against(str(first), base)
    assert "README.md" in diff.files
    assert diff.additions >= 1


def test_repository_url_rejects_embedded_credentials_and_ssh():
    with pytest.raises(Exception):
        git_manager.validate_repository_url("https://user:pass@github.com/org/repo.git")
    with pytest.raises(Exception):
        git_manager.validate_repository_url("git@github.com:org/repo.git")


def test_local_repository_must_be_under_explicit_root(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    denied = tmp_path / "denied"
    allowed.mkdir()
    denied.mkdir()
    monkeypatch.setattr(settings, "ALLOWED_LOCAL_REPO_ROOTS", [str(allowed)])
    assert git_manager.validate_repository_url(str(allowed)) == str(allowed)
    with pytest.raises(Exception):
        git_manager.validate_repository_url(str(denied))
