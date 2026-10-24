import asyncio
from uuid import UUID

import pytest

from caliper.application.repository_sync import (
    GitCredential,
    RepositorySource,
    RepositorySync,
    SyncState,
)

PROJECT_ID = UUID("09e1e92a-e2d0-4a25-98a6-1d95f7b8ae21")
CREDENTIAL_ID = UUID("bdf05286-8544-40de-89e5-6cc3b5ac2255")
TASK_ID = UUID("0366363c-6e06-4177-804e-a9fdc71ac0f2")


class QueueRepository:
    def __init__(self):
        self.enqueued = None

    async def project_source(self, project_id):
        return RepositorySource(PROJECT_ID, "https://example.test/repo.git", "main")

    async def credential(self, project_id, credential_id):
        if credential_id != CREDENTIAL_ID:
            return None
        return GitCredential("x-access-token", UUID(int=1), True, False)

    async def enqueue(self, project_id, url, branch, credential_id, at):
        self.enqueued = (project_id, url, branch, credential_id)
        return SyncState(project_id, "queued", url, branch, None, at, None, None, 0, TASK_ID)


class SecretStoreMustNotBeRead:
    def get(self, _secret_ref):
        raise AssertionError("queueing a task must not decrypt its credential")


@pytest.mark.parametrize("credential_id", [None, CREDENTIAL_ID])
def test_enqueue_persists_only_project_and_credential_references(credential_id):
    repository = QueueRepository()
    sync = RepositorySync(repository, SecretStoreMustNotBeRead(), git=object())

    state = asyncio.run(sync.enqueue(PROJECT_ID, credential_id))

    assert state.status == "queued"
    assert state.task_id == TASK_ID
    assert repository.enqueued == (
        PROJECT_ID,
        "https://example.test/repo.git",
        "main",
        credential_id,
    )
