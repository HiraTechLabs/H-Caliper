from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from caliper.adapters.postgres.models import CredentialRow, ProjectRow
from caliper.application.credentials import Credential


def to_domain(row: CredentialRow) -> Credential:
    return Credential(
        id=row.id,
        project_id=row.project_id,
        name=row.name,
        kind=row.kind,
        username=row.username,
        enabled=row.enabled,
        status=row.status,
        deletion_pending=row.deletion_pending,
        created_at=row.created_at,
        updated_at=row.updated_at,
        last_checked_at=row.last_checked_at,
        cleanup_pending=row.cleanup_secret_ref is not None,
    )


class SqlCredentialRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def project_exists(self, project_id: UUID) -> bool:
        return await self._session.get(ProjectRow, project_id) is not None

    async def list(self, project_id: UUID) -> list[Credential]:
        rows = (
            await self._session.scalars(
                select(CredentialRow)
                .where(CredentialRow.project_id == project_id)
                .order_by(CredentialRow.created_at.desc())
            )
        ).all()
        return [to_domain(row) for row in rows]

    async def get(self, project_id: UUID, credential_id: UUID) -> Credential | None:
        row = await self._session.scalar(
            select(CredentialRow).where(
                CredentialRow.id == credential_id,
                CredentialRow.project_id == project_id,
            )
        )
        return to_domain(row) if row else None

    async def get_cleanup_ref(self, credential_id: UUID) -> UUID | None:
        row = await self._session.get(CredentialRow, credential_id)
        return row.cleanup_secret_ref if row else None

    async def get_secret_ref(self, credential_id: UUID) -> UUID | None:
        row = await self._session.get(CredentialRow, credential_id)
        return row.secret_ref if row else None

    async def get_project_repository_url(self, project_id: UUID) -> str | None:
        project = await self._session.get(ProjectRow, project_id)
        return project.repository_url if project else None

    async def set_validation(
        self, credential_id: UUID, result: str, checked_at: datetime
    ) -> Credential:
        row = await self._session.get(CredentialRow, credential_id)
        if row is None:
            raise LookupError(str(credential_id))
        row.status = result
        row.last_checked_at = checked_at
        row.updated_at = checked_at
        await self._session.commit()
        return to_domain(row)

    async def add(self, credential: Credential, secret_ref: UUID) -> None:
        self._session.add(
            CredentialRow(
                id=credential.id,
                project_id=credential.project_id,
                name=credential.name,
                kind=credential.kind,
                username=credential.username,
                secret_ref=secret_ref,
                enabled=credential.enabled,
                status=credential.status,
                deletion_pending=credential.deletion_pending,
                created_at=credential.created_at,
                updated_at=credential.updated_at,
            )
        )
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

    async def replace(
        self, credential_id: UUID, name: str, username: str, secret_ref: UUID
    ) -> Credential:
        row = await self._session.get(CredentialRow, credential_id)
        if row is None:
            raise LookupError(str(credential_id))
        row.cleanup_secret_ref = row.secret_ref
        row.secret_ref = secret_ref
        row.name = name
        row.username = username
        row.status = "configured"
        row.last_checked_at = None
        row.updated_at = datetime.now(UTC)
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return to_domain(row)

    async def set_enabled(self, credential_id: UUID, enabled: bool) -> Credential:
        row = await self._session.get(CredentialRow, credential_id)
        if row is None:
            raise LookupError(str(credential_id))
        if row.deletion_pending:
            raise ValueError("Credential deletion is pending")
        row.enabled = enabled
        row.updated_at = datetime.now(UTC)
        await self._session.commit()
        return to_domain(row)

    async def prepare_delete(self, credential_id: UUID) -> tuple[UUID, UUID | None]:
        row = await self._session.get(CredentialRow, credential_id)
        if row is None:
            raise LookupError(str(credential_id))
        row.deletion_pending = True
        row.enabled = False
        row.status = "deleting"
        row.updated_at = datetime.now(UTC)
        await self._session.commit()
        return row.secret_ref, row.cleanup_secret_ref

    async def finish_delete(self, credential_id: UUID) -> None:
        row = await self._session.get(CredentialRow, credential_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.commit()

    async def finish_cleanup(self, credential_id: UUID) -> None:
        row = await self._session.get(CredentialRow, credential_id)
        if row is not None:
            row.cleanup_secret_ref = None
            await self._session.commit()
