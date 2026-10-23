import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from caliper.adapters.git.repository_sync import GitRepositorySyncAdapter
from caliper.application.repository_sync import GitSyncError


def git(cwd: Path, *arguments: str) -> None:
    subprocess.run(["git", *arguments], cwd=cwd, check=True, capture_output=True)


def test_sync_reads_only_knowledge_and_redacts_credentials(tmp_path: Path):
    working = tmp_path / "working"
    working.mkdir()
    git(working, "init", "--initial-branch=main")
    git(working, "config", "user.email", "test@example.invalid")
    git(working, "config", "user.name", "Caliper test")
    (working / "docs").mkdir()
    (working / "docs" / "guide.md").write_text("token=secret-value", encoding="utf-8")
    (working / "application.py").write_text("must not be indexed", encoding="utf-8")
    git(working, "add", ".")
    git(working, "commit", "-m", "initial knowledge")
    local_root = tmp_path / "local"
    local_root.mkdir()
    bare = local_root / "source.git"
    git(tmp_path, "clone", "--bare", str(working), str(bare))

    adapter = GitRepositorySyncAdapter(
        tmp_path / "scratch", local_root, allow_local_repositories=True
    )
    result = adapter.sync(uuid4(), bare.as_uri(), "main", None, None, [b"secret-value"])

    assert len(result.revision) == 40
    assert [document.path for document in result.documents] == ["docs/guide.md"]
    assert result.documents[0].content == "token=[REDACTED]"
    assert result.documents[0].sha256
    assert list((tmp_path / "scratch").iterdir()) == []


def test_sync_rejects_urls_that_could_embed_or_leak_credentials(tmp_path: Path):
    adapter = GitRepositorySyncAdapter(tmp_path / "scratch", tmp_path / "local")
    for url in (
        "https://example.test/repo.git?token=sensitive-value",
        "https://user:password@example.test/repo.git",
        "ssh://-oProxyCommand=unsafe@example.test/repo.git",
        "git@example.test:repo.git#secret",
        "file:///outside/repository.git",
    ):
        with pytest.raises(GitSyncError):
            adapter._validated_url(url)
