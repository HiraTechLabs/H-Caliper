from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from caliper.adapters.postgres.models import (
    CredentialRow,
    KnowledgeFileRow,
    ProjectRow,
    ProjectSyncRow,
)
from caliper.application.repository_sync import (
    GitCredential,
    KnowledgeDocument,
    ProjectNotFound,
    RepositorySource,
    RepositorySourceChanged,
    SyncAlreadyRunning,
    SyncState,
)


class SqlRepositorySyncRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def project_source(self, project_id: UUID) -> RepositorySource | None:
        project = await self._session.get(ProjectRow, project_id)
        if project is None:
            return None
        return RepositorySource(project_id, project.repository_url, project.default_branch)

    async def credential(self, project_id: UUID, credential_id: UUID) -> GitCredential | None:
        row = await self._session.scalar(
            select(CredentialRow).where(
                CredentialRow.id == credential_id,
                CredentialRow.project_id == project_id,
            )
        )
        if row is None:
            return None
        return GitCredential(row.username, row.secret_ref, row.enabled, row.deletion_pending)

    async def credential_secret_refs(self, project_id: UUID) -> list[UUID]:
        rows = (
            await self._session.execute(
                select(CredentialRow.secret_ref, CredentialRow.cleanup_secret_ref).where(
                    CredentialRow.project_id == project_id
                )
            )
        ).all()
        return [secret_ref for row in rows for secret_ref in row if secret_ref is not None]

    async def begin(self, project_id: UUID, url: str, branch: str, at: datetime) -> None:
        project = await self._session.scalar(
            select(ProjectRow)
            .where(ProjectRow.id == project_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if project is None:
            raise ProjectNotFound(str(project_id))
        if project.repository_url != url or project.default_branch != branch:
            raise RepositorySourceChanged("Repository settings changed; reload and retry")
        row = await self._session.get(ProjectSyncRow, project_id)
        if row is not None and row.status == "running":
            raise SyncAlreadyRunning("A synchronization is already running for this project")
        if row is None:
            row = ProjectSyncRow(
                project_id=project_id,
                status="running",
                source_url=url,
                branch=branch,
                revision=None,
                attempted_at=at,
                last_success_at=None,
                error_code=None,
            )
            self._session.add(row)
        else:
            row.status = "running"
            row.source_url = url
            row.branch = branch
            row.attempted_at = at
            row.error_code = None
        await self._session.commit()

    async def succeed(
        self,
        project_id: UUID,
        url: str,
        branch: str,
        revision: str,
        documents: list[KnowledgeDocument],
        at: datetime,
    ) -> SyncState:
        try:
            await self._session.execute(
                delete(KnowledgeFileRow).where(KnowledgeFileRow.project_id == project_id)
            )
            self._session.add_all(
                [
                    KnowledgeFileRow(
                        id=uuid4(),
                        project_id=project_id,
                        path=document.path,
                        revision=revision,
                        sha256=document.sha256,
                        content=document.content,
                        synced_at=at,
                    )
                    for document in documents
                ]
            )
            row = await self._session.get(ProjectSyncRow, project_id)
            if row is None:
                raise RuntimeError("Sync state disappeared during synchronization")
            row.status = "synchronized"
            row.source_url = url
            row.branch = branch
            row.revision = revision
            row.attempted_at = at
            row.last_success_at = at
            row.error_code = None
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return await self.state(project_id)  # type: ignore[return-value]

    async def fail(self, project_id: UUID, error_code: str, at: datetime) -> SyncState:
        row = await self._session.get(ProjectSyncRow, project_id)
        if row is None:
            raise RuntimeError("Sync state disappeared during synchronization")
        prior_success = row.last_success_at is not None
        row.status = "stale" if prior_success else "failed"
        row.error_code = error_code
        row.attempted_at = at
        await self._session.commit()
        return await self.state(project_id)  # type: ignore[return-value]

    async def state(self, project_id: UUID) -> SyncState | None:
        row = await self._session.get(ProjectSyncRow, project_id)
        if row is None:
            return None
        count = await self._session.scalar(
            select(func.count())
            .select_from(KnowledgeFileRow)
            .where(KnowledgeFileRow.project_id == project_id)
        )
        return SyncState(
            project_id,
            row.status,
            row.source_url,
            row.branch,
            row.revision,
            row.attempted_at,
            row.last_success_at,
            row.error_code,
            count or 0,
        )

    async def documents(self, project_id: UUID) -> list[KnowledgeDocument]:
        rows = (
            await self._session.scalars(
                select(KnowledgeFileRow)
                .where(KnowledgeFileRow.project_id == project_id)
                .order_by(KnowledgeFileRow.path)
            )
        ).all()
        return [
            KnowledgeDocument(row.path, row.revision, row.sha256, row.content, row.synced_at)
            for row in rows
        ]
