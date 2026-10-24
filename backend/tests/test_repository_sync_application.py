import asyncio
from datetime import UTC, datetime
from uuid import UUID

import pytest

from caliper.application.repository_sync import (
    GitCredential,
    KnowledgeDocument,
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
        self.snapshot = None

    async def project_source(self, project_id):
        return RepositorySource(PROJECT_ID, "https://example.test/repo.git", "main")

    async def credential(self, project_id, credential_id):
        if credential_id != CREDENTIAL_ID:
            return None
        return GitCredential("x-access-token", UUID(int=1), True, False)

    async def enqueue(self, project_id, url, branch, credential_id, at):
        self.enqueued = (project_id, url, branch, credential_id)
        return SyncState(project_id, "queued", url, branch, None, at, None, None, 0, TASK_ID)

    async def workspace_snapshot(self, project_id):
        return self.snapshot


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


def test_workspace_returns_sync_state_and_documents_from_one_snapshot():
    repository = QueueRepository()
    source = RepositorySource(PROJECT_ID, "https://example.test/repo.git", "main")
    now = datetime.now(UTC)
    state = SyncState(
        PROJECT_ID, "synchronized", source.url, source.branch, "a" * 40, now, now, None, 1
    )
    document = KnowledgeDocument(
        ".caliper/graph.yaml", "a" * 40, "b" * 64, "nodes: []\nedges: []", now
    )
    repository.snapshot = (source, state, [document])
    sync = RepositorySync(repository, SecretStoreMustNotBeRead(), git=object())

    fresh_state, documents = asyncio.run(sync.workspace(PROJECT_ID))

    assert fresh_state.revision == document.revision
    assert documents == [document]
