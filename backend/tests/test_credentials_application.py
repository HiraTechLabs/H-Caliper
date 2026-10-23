import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from caliper.adapters.secret_store.fernet_store import FernetFileSecretStore
from caliper.application.credentials import Credential, Credentials
from caliper.application.secret_store import SecretUnavailable


class MemoryCredentialRepository:
    def __init__(self, project_id: UUID):
        self.project_id = project_id
        self.rows: dict[UUID, Credential] = {}
        self.secrets: dict[UUID, UUID] = {}
        self.cleanup_refs: dict[UUID, UUID] = {}
        self.repository_url = "https://example.test/org/repo.git"

    async def project_exists(self, project_id: UUID) -> bool:
        return project_id == self.project_id

    async def list(self, project_id: UUID) -> list[Credential]:
        return list(self.rows.values())

    async def get(self, project_id: UUID, credential_id: UUID) -> Credential | None:
        return self.rows.get(credential_id)

    async def get_cleanup_ref(self, credential_id: UUID) -> UUID | None:
        return self.cleanup_refs.get(credential_id)

    async def get_secret_ref(self, credential_id: UUID) -> UUID | None:
        return self.secrets.get(credential_id)

    async def get_project_repository_url(self, project_id: UUID) -> str | None:
        return self.repository_url if project_id == self.project_id else None

    async def set_validation(
        self, credential_id: UUID, result: str, checked_at: datetime
    ) -> Credential:
        updated = replace(self.rows[credential_id], status=result, last_checked_at=checked_at)
        self.rows[credential_id] = updated
        return updated

    async def add(self, credential: Credential, secret_ref: UUID) -> None:
        self.rows[credential.id] = credential
        self.secrets[credential.id] = secret_ref

    async def replace(
        self, credential_id: UUID, name: str, username: str, secret_ref: UUID
    ) -> Credential:
        existing = self.rows[credential_id]
        self.cleanup_refs[credential_id] = self.secrets[credential_id]
        self.secrets[credential_id] = secret_ref
        updated = replace(
            existing,
            name=name,
            username=username,
            status="configured",
            last_checked_at=None,
            updated_at=datetime.now(UTC),
            cleanup_pending=True,
        )
        self.rows[credential_id] = updated
        return updated

    async def set_enabled(self, credential_id: UUID, enabled: bool) -> Credential:
        updated = replace(self.rows[credential_id], enabled=enabled)
        self.rows[credential_id] = updated
        return updated

    async def prepare_delete(self, credential_id: UUID) -> tuple[UUID, UUID | None]:
        existing = self.rows[credential_id]
        self.rows[credential_id] = replace(existing, deletion_pending=True, enabled=False)
        return self.secrets[credential_id], self.cleanup_refs.get(credential_id)

    async def finish_delete(self, credential_id: UUID) -> None:
        self.rows.pop(credential_id, None)
        self.secrets.pop(credential_id, None)
        self.cleanup_refs.pop(credential_id, None)

    async def finish_cleanup(self, credential_id: UUID) -> None:
        self.cleanup_refs.pop(credential_id, None)
        self.rows[credential_id] = replace(self.rows[credential_id], cleanup_pending=False)


def test_credential_create_replace_disable_delete_lifecycle(tmp_path: Path):
    project_id = UUID("36f5814e-fc03-4855-b69b-0ae5c306d1c1")
    repository = MemoryCredentialRepository(project_id)
    remote = ReachableRemote()
    store = FernetFileSecretStore(tmp_path / "vault", tmp_path / "keys" / "keyring.json")
    store.initialize_keyring()
    service = Credentials(repository, store, remote)

    async def exercise():
        created = await service.create(
            project_id, "Git access", "x-access-token", b"old-token-value"
        )
        old_ref = repository.secrets[created.id]
        assert store.get(old_ref) == b"old-token-value"
        assert not hasattr(created, "secret")

        validated = await service.validate(project_id, created.id)
        assert validated.status == "reachable"
        assert remote.checked == (
            "https://example.test/org/repo.git",
            "x-access-token",
            b"old-token-value",
        )

        replaced = await service.replace(
            project_id, created.id, "Git access", "x-access-token", b"new-token-value"
        )
        assert replaced.status == "configured"
        assert not replaced.cleanup_pending
        assert store.get(repository.secrets[created.id]) == b"new-token-value"
        with pytest.raises(SecretUnavailable):
            store.get(old_ref)

        disabled = await service.set_enabled(project_id, created.id, False)
        assert not disabled.enabled
        assert store.get(repository.secrets[created.id]) == b"new-token-value"

        await service.delete(project_id, created.id)
        assert await service.list(project_id) == []
        assert list((tmp_path / "vault").glob("*.secret")) == []

    asyncio.run(exercise())


class ReachableRemote:
    def __init__(self):
        self.checked = None

    def validate(self, url: str, username: str, token: bytes) -> bool:
        self.checked = (url, username, token)
        return True
