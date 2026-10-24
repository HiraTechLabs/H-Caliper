from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from caliper.adapters.postgres.models import CredentialRow, ProjectRow, ProjectSyncRow
from caliper.application.projects import ProjectHasCredentials, ProjectHasRunningSync
from caliper.domain.project import Project


def to_domain(row: ProjectRow) -> Project:
    return Project(
        row.id,
        row.name,
        row.description,
        row.repository_url,
        row.default_branch,
        row.created_at,
        row.updated_at,
    )


class SqlProjectRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list(self) -> list[Project]:
        rows = (
            await self._session.scalars(select(ProjectRow).order_by(ProjectRow.created_at.desc()))
        ).all()
        return [to_domain(row) for row in rows]

    async def get(self, project_id: UUID) -> Project | None:
        row = await self._session.get(ProjectRow, project_id)
        return to_domain(row) if row else None

    async def add(self, project: Project) -> Project:
        self._session.add(
            ProjectRow(
                id=project.id,
                name=project.name,
                description=project.description,
                repository_url=project.repository_url,
                default_branch=project.default_branch,
                created_at=project.created_at,
                updated_at=project.updated_at,
            )
        )
        await self._session.commit()
        return project

    async def save(self, project: Project) -> Project:
        row = await self._session.get(ProjectRow, project.id)
        if row is None:
            raise LookupError(str(project.id))
        row.name = project.name
        row.description = project.description
        row.repository_url = project.repository_url
        row.default_branch = project.default_branch
        row.updated_at = project.updated_at
        await self._session.commit()
        return to_domain(row)

    async def delete(self, project_id: UUID) -> bool:
        row = await self._session.scalar(
            select(ProjectRow).where(ProjectRow.id == project_id).with_for_update()
        )
        if row is None:
            return False
        has_credentials = await self._session.scalar(
            select(CredentialRow.id).where(CredentialRow.project_id == project_id).limit(1)
        )
        if has_credentials is not None:
            raise ProjectHasCredentials("Delete project credentials before deleting the project")
        running_sync = await self._session.scalar(
            select(ProjectSyncRow.project_id).where(
                ProjectSyncRow.project_id == project_id,
                ProjectSyncRow.status.in_(("queued", "running")),
            )
        )
        if running_sync is not None:
            raise ProjectHasRunningSync(
                "Wait for repository synchronization to finish before deleting the project"
            )
        await self._session.delete(row)
        try:
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            raise ProjectHasCredentials(
                "Remove related credentials before deleting the project"
            ) from error
        return True
