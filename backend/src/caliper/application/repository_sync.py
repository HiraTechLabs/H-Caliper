import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from caliper.application.secret_store import SecretStore

MAX_REDACTION_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class RepositorySource:
    project_id: UUID
    url: str | None
    branch: str


@dataclass(frozen=True)
class SyncState:
    project_id: UUID
    status: str
    source_url: str
    branch: str
    revision: str | None
    attempted_at: datetime
    last_success_at: datetime | None
    error_code: str | None
    document_count: int
    task_id: UUID | None = None


@dataclass(frozen=True)
class KnowledgeDocument:
    path: str
    revision: str
    sha256: str
    content: str
    synced_at: datetime


@dataclass(frozen=True)
class GitSyncResult:
    revision: str
    documents: list[KnowledgeDocument]


@dataclass(frozen=True)
class GitCredential:
    username: str
    secret_ref: UUID
    enabled: bool
    deletion_pending: bool


class RepositorySyncRepository(Protocol):
    async def project_source(self, project_id: UUID) -> RepositorySource | None: ...
    async def credential(self, project_id: UUID, credential_id: UUID) -> GitCredential | None: ...
    async def credential_secret_refs(self, project_id: UUID) -> list[UUID]: ...
    async def enqueue(
        self, project_id: UUID, url: str, branch: str, credential_id: UUID | None, at: datetime
    ) -> SyncState: ...
    async def begin(self, project_id: UUID, url: str, branch: str, at: datetime) -> None: ...
    async def succeed(
        self,
        project_id: UUID,
        url: str,
        branch: str,
        revision: str,
        documents: list[KnowledgeDocument],
        at: datetime,
    ) -> SyncState: ...
    async def fail(self, project_id: UUID, error_code: str, at: datetime) -> SyncState: ...
    async def state(self, project_id: UUID) -> SyncState | None: ...
    async def documents(self, project_id: UUID) -> list[KnowledgeDocument]: ...


class GitSyncAdapter(Protocol):
    def sync(
        self,
        project_id: UUID,
        url: str,
        branch: str,
        username: str | None,
        token: bytes | None,
        redact_secrets: list[bytes],
    ) -> GitSyncResult: ...


class GitSyncError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ProjectNotFound(LookupError):
    pass


class CredentialNotFound(LookupError):
    pass


class SyncAlreadyRunning(RuntimeError):
    pass


class RepositorySourceChanged(RuntimeError):
    pass


class TaskQueueFull(RuntimeError):
    pass


class RepositorySyncFailed(RuntimeError):
    def __init__(self, state: SyncState):
        super().__init__(state.error_code or "Repository sync failed")
        self.state = state


class RepositorySync:
    def __init__(
        self,
        repository: RepositorySyncRepository,
        secret_store: SecretStore,
        git: GitSyncAdapter,
    ):
        self._repository = repository
        self._secret_store = secret_store
        self._git = git

    async def state(self, project_id: UUID) -> SyncState:
        source = await self._repository.project_source(project_id)
        if source is None:
            raise ProjectNotFound(str(project_id))
        current = await self._repository.state(project_id)
        if current is None:
            now = datetime.now(UTC)
            return SyncState(
                project_id,
                "configured" if source.url else "not_configured",
                source.url or "",
                source.branch,
                None,
                now,
                None,
                None,
                0,
            )
        if (
            current.status == "synchronized"
            and current.last_success_at
            and (current.source_url != source.url or current.branch != source.branch)
        ):
            return SyncState(
                current.project_id,
                "stale",
                current.source_url,
                current.branch,
                current.revision,
                current.attempted_at,
                current.last_success_at,
                "source_changed",
                current.document_count,
            )
        return current

    async def documents(self, project_id: UUID) -> list[KnowledgeDocument]:
        if await self._repository.project_source(project_id) is None:
            raise ProjectNotFound(str(project_id))
        return await self._repository.documents(project_id)

    async def enqueue(self, project_id: UUID, credential_id: UUID | None = None) -> SyncState:
        source = await self._repository.project_source(project_id)
        if source is None:
            raise ProjectNotFound(str(project_id))
        if not source.url:
            raise ValueError("Set a repository URL before synchronizing")
        if credential_id:
            credential = await self._repository.credential(project_id, credential_id)
            if credential is None:
                raise CredentialNotFound(str(credential_id))
            if not credential.enabled or credential.deletion_pending:
                raise ValueError("Enable the credential before synchronizing")
        return await self._repository.enqueue(
            project_id, source.url, source.branch, credential_id, datetime.now(UTC)
        )

    async def sync(self, project_id: UUID, credential_id: UUID | None = None) -> SyncState:
        source = await self._repository.project_source(project_id)
        if source is None:
            raise ProjectNotFound(str(project_id))
        if not source.url:
            raise ValueError("Set a repository URL before synchronizing")

        username = None
        token = None
        if credential_id:
            credential = await self._repository.credential(project_id, credential_id)
            if credential is None:
                raise CredentialNotFound(str(credential_id))
            if not credential.enabled or credential.deletion_pending:
                raise ValueError("Enable the credential before synchronizing")
            username = credential.username
            token = await asyncio.to_thread(self._secret_store.get, credential.secret_ref)

        secrets_to_redact = []
        redaction_bytes = 0
        for secret_ref in await self._repository.credential_secret_refs(project_id):
            secret = await asyncio.to_thread(self._secret_store.get, secret_ref)
            redaction_bytes += len(secret)
            if redaction_bytes > MAX_REDACTION_BYTES:
                raise ValueError("Credential set is too large to redact safely")
            secrets_to_redact.append(secret)

        attempted_at = datetime.now(UTC)
        await self._repository.begin(project_id, source.url, source.branch, attempted_at)
        try:
            result = await asyncio.to_thread(
                self._git.sync,
                project_id,
                source.url,
                source.branch,
                username,
                token,
                secrets_to_redact,
            )
            return await self._repository.succeed(
                project_id,
                source.url,
                source.branch,
                result.revision,
                result.documents,
                datetime.now(UTC),
            )
        except GitSyncError as error:
            state = await self._repository.fail(project_id, error.code, datetime.now(UTC))
            raise RepositorySyncFailed(state) from None
