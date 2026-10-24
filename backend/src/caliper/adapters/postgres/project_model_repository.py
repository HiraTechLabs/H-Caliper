from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliper.adapters.postgres.models import ProjectModelRow, ProjectRow
from caliper.application.project_models import ProjectModelSelection


class SqlProjectModelRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, project_id: UUID) -> ProjectModelSelection | None:
        if await self._session.get(ProjectRow, project_id) is None:
            raise LookupError(str(project_id))
        row = await self._session.get(ProjectModelRow, project_id)
        await self._session.rollback()
        return self._selection(row) if row else None

    async def select(
        self, project_id: UUID, provider_type: str, provider_id: str, model_id: str
    ) -> ProjectModelSelection:
        if await self._session.get(ProjectRow, project_id) is None:
            raise LookupError(str(project_id))
        row = await self._session.get(ProjectModelRow, project_id)
        now = datetime.now(UTC)
        if row is None:
            row = ProjectModelRow(
                project_id=project_id,
                provider_type=provider_type,
                provider_id=provider_id,
                model_id=model_id,
                updated_at=now,
            )
            self._session.add(row)
        else:
            row.provider_type = provider_type
            row.provider_id = provider_id
            row.model_id = model_id
            row.updated_at = now
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return self._selection(row)

    async def clear(self, project_id: UUID) -> None:
        if await self._session.get(ProjectRow, project_id) is None:
            raise LookupError(str(project_id))
        row = await self._session.get(ProjectModelRow, project_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.commit()
        else:
            await self._session.rollback()

    @staticmethod
    def _selection(row: ProjectModelRow) -> ProjectModelSelection:
        return ProjectModelSelection(
            row.provider_type, row.provider_id, row.model_id, row.updated_at
        )
