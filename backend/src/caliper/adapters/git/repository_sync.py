import base64
import hashlib
import os
import re
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import url2pathname
from uuid import UUID

from caliper.application.repository_sync import GitSyncError, GitSyncResult, KnowledgeDocument

MAX_TREE_BYTES = 64 * 1024 * 1024
MAX_TREE_ENTRIES = 20_000
MAX_DOCUMENT_BYTES = 1024 * 1024
MAX_DOCUMENTS = 500
MAX_KNOWLEDGE_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".md", ".mdx", ".yaml", ".yml", ".toml", ".json"}
SECRET_PATTERNS = (
    re.compile(
        r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"
    ),
    re.compile(
        r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|glpat-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16})\b"
    ),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
)


@dataclass(frozen=True)
class SyncDocument:
    path: str
    sha256: str
    content: str


class GitRepositorySyncAdapter:
    def __init__(
        self,
        repository_root: Path,
        local_repository_root: Path,
        allow_local_repositories: bool = False,
        known_hosts_path: Path = Path("/etc/caliper/ssh/known_hosts"),
        timeout_seconds: int = 120,
    ):
        self.repository_root = repository_root
        self.local_repository_root = local_repository_root
        self.allow_local_repositories = allow_local_repositories
        self.known_hosts_path = known_hosts_path
        self.timeout_seconds = timeout_seconds
        self.repository_root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def sync(
        self,
        project_id: UUID,
        url: str,
        branch: str,
        username: str | None,
        token: bytes | None,
        redact_secrets: list[bytes],
    ) -> GitSyncResult:
        source_url = self._validated_url(url)
        if not self._valid_branch(branch):
            raise GitSyncError("invalid_branch")
        try:
            with tempfile.TemporaryDirectory(
                prefix=f".sync-{project_id.hex}-", dir=self.repository_root
            ) as temp_root:
                stage = Path(temp_root) / "checkout"
                environment = self._environment(temp_root, source_url, username, token)
                self._run(
                    [
                        "git",
                        "clone",
                        "--depth",
                        "1",
                        "--single-branch",
                        "--branch",
                        branch,
                        source_url,
                        str(stage),
                    ],
                    cwd=self.repository_root,
                    environment=environment,
                )
                revision = self._revision(stage, environment)
                documents = self._documents(stage, revision, redact_secrets, environment)
                synced_at = datetime.now(UTC)
                return GitSyncResult(
                    revision,
                    [
                        KnowledgeDocument(
                            path=document.path,
                            revision=revision,
                            sha256=document.sha256,
                            content=document.content,
                            synced_at=synced_at,
                        )
                        for document in documents
                    ],
                )
        except GitSyncError:
            raise
        except subprocess.TimeoutExpired as error:
            raise GitSyncError("timed_out") from error
        except (OSError, tarfile.TarError):
            raise GitSyncError("repository_unavailable") from None

    def _validated_url(self, url: str) -> str:
        if any(ord(character) < 32 for character in url):
            raise GitSyncError("invalid_repository_url")
        parsed = urlsplit(url)
        if parsed.scheme == "https":
            if (
                not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
            ):
                raise GitSyncError("invalid_repository_url")
            return url
        if parsed.scheme == "ssh":
            if (
                not parsed.hostname
                or parsed.username not in {None, "git"}
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
            ):
                raise GitSyncError("invalid_repository_url")
            return url
        if url.startswith("git@") and re.fullmatch(r"git@[A-Za-z0-9.-]+:[^?#]+", url):
            return url
        if parsed.scheme == "file" and not parsed.netloc and self.allow_local_repositories:
            local_path = Path(url2pathname(unquote(parsed.path))).resolve()
            root = self.local_repository_root.resolve()
            if local_path == root or root in local_path.parents:
                return os.fspath(local_path)
        raise GitSyncError("unsupported_repository_url")

    @staticmethod
    def _valid_branch(branch: str) -> bool:
        if not branch or branch.startswith("-") or any(ord(char) < 32 for char in branch):
            return False
        try:
            result = subprocess.run(
                ["git", "check-ref-format", "--branch", branch],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=3,
            )
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def _environment(
        self, temp_root: str, url: str, username: str | None, token: bytes | None
    ) -> dict[str, str]:
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", temp_root),
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TRACE": "0",
            "GIT_CURL_VERBOSE": "0",
            "GIT_CONFIG_GLOBAL": str(Path(temp_root) / "gitconfig"),
            "GIT_SSH_COMMAND": (
                f"ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "
                f"-o UserKnownHostsFile={self.known_hosts_path}"
            ),
        }
        if os.name == "nt":
            for name in ("SystemRoot", "WINDIR", "TEMP", "TMP", "PATHEXT"):
                if name in os.environ:
                    env[name] = os.environ[name]
        (Path(temp_root) / "gitconfig").touch(mode=0o600)
        if username and token:
            auth = base64.b64encode(username.encode() + b":" + token).decode("ascii")
            env.update(
                {
                    "GIT_CONFIG_COUNT": "2",
                    "GIT_CONFIG_KEY_0": "http.extraheader",
                    "GIT_CONFIG_VALUE_0": f"Authorization: Basic {auth}",
                    "GIT_CONFIG_KEY_1": "http.followRedirects",
                    "GIT_CONFIG_VALUE_1": "false",
                }
            )
        else:
            env.update(
                {
                    "GIT_CONFIG_COUNT": "1",
                    "GIT_CONFIG_KEY_0": "http.followRedirects",
                    "GIT_CONFIG_VALUE_0": "false",
                }
            )
        for name in ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY"):
            if name in os.environ:
                env[name] = os.environ[name]
        return env

    def _run(self, command: list[str], cwd: Path, environment: dict[str, str]) -> None:
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            raise GitSyncError("timed_out") from error
        if result.returncode != 0:
            raise GitSyncError("remote_unavailable")

    def _revision(self, checkout: Path, environment: dict[str, str]) -> str:
        result = subprocess.run(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"],
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
        if result.returncode != 0 or len(result.stdout) > 80:
            raise GitSyncError("revision_unavailable")
        try:
            revision = result.stdout.decode("ascii", errors="strict").strip()
        except UnicodeDecodeError:
            raise GitSyncError("revision_unavailable") from None
        if not re.fullmatch(r"[0-9a-f]{40,64}", revision):
            raise GitSyncError("revision_unavailable")
        return revision

    def _documents(
        self,
        checkout: Path,
        revision: str,
        secrets_to_redact: list[bytes],
        environment: dict[str, str],
    ) -> list[SyncDocument]:
        archive = subprocess.Popen(
            [
                "git",
                "-C",
                str(checkout),
                "archive",
                "--format=tar",
                revision,
            ],
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        documents: list[SyncDocument] = []
        total_size = 0
        tree_size = 0
        tree_entries = 0
        try:
            with tarfile.open(fileobj=archive.stdout, mode="r|") as tar:
                for member in tar:
                    tree_entries += 1
                    tree_size += max(member.size, 0)
                    if tree_entries > MAX_TREE_ENTRIES or tree_size > MAX_TREE_BYTES:
                        raise GitSyncError("repository_tree_too_large")
                    if not member.isfile() or not self._is_knowledge_path(member.name):
                        continue
                    if member.size > MAX_DOCUMENT_BYTES:
                        raise GitSyncError("knowledge_document_too_large")
                    if (
                        len(documents) >= MAX_DOCUMENTS
                        or total_size + member.size > MAX_KNOWLEDGE_BYTES
                    ):
                        raise GitSyncError("knowledge_snapshot_too_large")
                    content_stream = tar.extractfile(member)
                    if content_stream is None:
                        continue
                    raw = content_stream.read(MAX_DOCUMENT_BYTES + 1)
                    if len(raw) != member.size:
                        raise GitSyncError("knowledge_document_invalid")
                    total_size += len(raw)
                    try:
                        content = raw.decode("utf-8")
                    except UnicodeDecodeError:
                        continue
                    content = self._redact(content, secrets_to_redact)
                    encoded = content.encode("utf-8")
                    documents.append(
                        SyncDocument(
                            path=member.name.removeprefix("./"),
                            sha256=hashlib.sha256(encoded).hexdigest(),
                            content=content,
                        )
                    )
            if archive.wait(timeout=self.timeout_seconds) != 0:
                raise GitSyncError("knowledge_snapshot_unavailable")
        except Exception:
            archive.kill()
            archive.wait()
            raise
        finally:
            if archive.stdout:
                archive.stdout.close()
        return documents

    @staticmethod
    def _is_knowledge_path(path: str) -> bool:
        path = path.removeprefix("./")
        if path.startswith((".caliper/", "docs/")):
            pass
        elif path not in {"README.md", "AGENTS.md"}:
            return False
        if path.startswith("/") or ".." in Path(path).parts or "/secrets/" in f"/{path}/":
            return False
        return Path(path).suffix.lower() in ALLOWED_EXTENSIONS

    @staticmethod
    def _redact(content: str, secrets_to_redact: list[bytes]) -> str:
        for secret in secrets_to_redact:
            if secret:
                try:
                    content = content.replace(secret.decode("utf-8"), "[REDACTED]")
                except UnicodeDecodeError:
                    continue
        for pattern in SECRET_PATTERNS:
            content = pattern.sub("[REDACTED]", content)
        return content
