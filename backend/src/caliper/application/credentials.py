import asyncio
from dataclasses import dataclass
from dataclasses import replace as dataclass_replace
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from caliper.application.secret_store import SecretStore, SecretStoreError


@dataclass(frozen=True)
class Credential:
    id: UUID
    project_id: UUID
    name: str
    kind: str
    username: str
    enabled: bool
    status: str
    deletion_pending: bool
    created_at: datetime
    updated_at: datetime
    last_checked_at: datetime | None
    cleanup_pending: bool = False


class CredentialRepository(Protocol):
    async def project_exists(self, project_id: UUID) -> bool: ...
    async def list(self, project_id: UUID) -> list[Credential]: ...
    async def get(self, project_id: UUID, credential_id: UUID) -> Credential | None: ...
    async def get_cleanup_ref(self, credential_id: UUID) -> UUID | None: ...
    async def get_secret_ref(self, credential_id: UUID) -> UUID | None: ...
    async def get_project_repository_url(self, project_id: UUID) -> str | None: ...
    async def set_validation(
        self, credential_id: UUID, result: str, checked_at: datetime
    ) -> Credential: ...
    async def add(self, credential: Credential, secret_ref: UUID) -> None: ...
    async def replace(
        self, credential_id: UUID, name: str, username: str, secret_ref: UUID
    ) -> Credential: ...
    async def set_enabled(self, credential_id: UUID, enabled: bool) -> Credential: ...
    async def prepare_delete(self, credential_id: UUID) -> tuple[UUID, UUID | None]: ...
    async def finish_delete(self, credential_id: UUID) -> None: ...
    async def finish_cleanup(self, credential_id: UUID) -> None: ...


class RemoteCredentialValidator(Protocol):
    def validate(self, url: str, username: str, token: bytes) -> bool: ...


class ProjectNotFound(LookupError):
    pass


class CredentialNotFound(LookupError):
    pass


class CredentialNameRequired(ValueError):
    pass


class Credentials:
    def __init__(
        self,
        repository: CredentialRepository,
        secret_store: SecretStore,
        validator: RemoteCredentialValidator,
    ):
        self._repository = repository
        self._secret_store = secret_store
        self._validator = validator

    async def list(self, project_id: UUID) -> list[Credential]:
        if not await self._repository.project_exists(project_id):
            raise ProjectNotFound(str(project_id))
        return await self._repository.list(project_id)

    async def create(self, project_id: UUID, name: str, username: str, secret: bytes) -> Credential:
        if not await self._repository.project_exists(project_id):
            raise ProjectNotFound(str(project_id))
        normalized_name = name.strip()
        normalized_username = username.strip()
        if not normalized_name:
            raise CredentialNameRequired("Credential name cannot be blank")
        if not normalized_username:
            raise CredentialNameRequired("Credential username cannot be blank")
        secret_ref = await asyncio.to_thread(self._secret_store.put, secret)
        now = datetime.now(UTC)
        credential = Credential(
            id=uuid4(),
            project_id=project_id,
            name=normalized_name,
            kind="https_token",
            username=normalized_username,
            enabled=True,
            status="configured",
            deletion_pending=False,
            created_at=now,
            updated_at=now,
            last_checked_at=None,
        )
        try:
            await self._repository.add(credential, secret_ref)
        except Exception:
            await asyncio.to_thread(self._secret_store.delete, secret_ref)
            raise
        return credential

    async def replace(
        self, project_id: UUID, credential_id: UUID, name: str, username: str, secret: bytes
    ) -> Credential:
        existing = await self._required(project_id, credential_id)
        if existing.deletion_pending:
            raise ValueError("Credential deletion is pending; retry deletion first")
        if existing.cleanup_pending:
            try:
                await self._delete_pending_cleanup(credential_id)
            except SecretStoreError:
                raise SecretStoreError("Previous secret cleanup is pending") from None
        normalized_name = name.strip()
        normalized_username = username.strip()
        if not normalized_name:
            raise CredentialNameRequired("Credential name cannot be blank")
        if not normalized_username:
            raise CredentialNameRequired("Credential username cannot be blank")
        new_ref = await asyncio.to_thread(self._secret_store.put, secret)
        try:
            updated = await self._repository.replace(
                credential_id, normalized_name, normalized_username, new_ref
            )
        except Exception:
            await asyncio.to_thread(self._secret_store.delete, new_ref)
            raise
        try:
            cleanup_ref = await self._pending_cleanup_ref(credential_id)
            await asyncio.to_thread(self._secret_store.delete, cleanup_ref)
            await self._repository.finish_cleanup(credential_id)
            return dataclass_replace(updated, cleanup_pending=False)
        except SecretStoreError:
            return dataclass_replace(updated, cleanup_pending=True)

    async def set_enabled(self, project_id: UUID, credential_id: UUID, enabled: bool) -> Credential:
        await self._required(project_id, credential_id)
        return await self._repository.set_enabled(credential_id, enabled)

    async def validate(self, project_id: UUID, credential_id: UUID) -> Credential:
        credential = await self._required(project_id, credential_id)
        if not credential.enabled or credential.deletion_pending:
            raise ValueError("Enable the credential before validation")
        repository_url = await self._repository.get_project_repository_url(project_id)
        if not repository_url or not repository_url.startswith("https://"):
            raise ValueError("Set an HTTPS repository URL before validating this token")
        secret_ref = await self._repository.get_secret_ref(credential_id)
        if secret_ref is None:
            raise CredentialNotFound(str(credential_id))
        token = await asyncio.to_thread(self._secret_store.get, secret_ref)
        reachable = await asyncio.to_thread(
            self._validator.validate, repository_url, credential.username, token
        )
        checked_at = datetime.now(UTC)
        return await self._repository.set_validation(
            credential_id, "reachable" if reachable else "failed", checked_at
        )

    async def delete(self, project_id: UUID, credential_id: UUID) -> None:
        existing = await self._required(project_id, credential_id)
        if existing.cleanup_pending:
            try:
                await self._delete_pending_cleanup(credential_id)
            except SecretStoreError:
                raise SecretStoreError("Previous secret cleanup is pending") from None
        secret_ref, cleanup_ref = await self._repository.prepare_delete(credential_id)
        try:
            await asyncio.to_thread(self._secret_store.delete, secret_ref)
            if cleanup_ref:
                await asyncio.to_thread(self._secret_store.delete, cleanup_ref)
        except SecretStoreError:
            raise SecretStoreError("Credential deletion is pending; retry to finish") from None
        await self._repository.finish_delete(credential_id)

    async def _required(self, project_id: UUID, credential_id: UUID) -> Credential:
        credential = await self._repository.get(project_id, credential_id)
        if credential is None:
            raise CredentialNotFound(str(credential_id))
        return credential

    async def _pending_cleanup_ref(self, credential_id: UUID) -> UUID:
        cleanup_ref = await self._repository.get_cleanup_ref(credential_id)
        if cleanup_ref is None:
            raise CredentialNotFound(str(credential_id))
        return cleanup_ref

    async def _delete_pending_cleanup(self, credential_id: UUID) -> None:
        ref = await self._pending_cleanup_ref(credential_id)
        await asyncio.to_thread(self._secret_store.delete, ref)
        await self._repository.finish_cleanup(credential_id)
