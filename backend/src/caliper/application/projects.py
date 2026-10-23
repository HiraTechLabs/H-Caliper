from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from caliper.domain.project import Project, normalize_project_name


class ProjectRepository(Protocol):
    async def list(self) -> list[Project]: ...
    async def get(self, project_id: UUID) -> Project | None: ...
    async def add(self, project: Project) -> Project: ...
    async def save(self, project: Project) -> Project: ...
    async def delete(self, project_id: UUID) -> bool: ...


class ProjectNotFound(LookupError):
    pass


class ProjectHasCredentials(RuntimeError):
    pass


class ProjectHasRunningSync(RuntimeError):
    pass


class Projects:
    def __init__(self, repository: ProjectRepository):
        self._repository = repository

    async def list(self) -> list[Project]:
        return await self._repository.list()

    async def get(self, project_id: UUID) -> Project:
        project = await self._repository.get(project_id)
        if project is None:
            raise ProjectNotFound(str(project_id))
        return project

    async def create(
        self,
        *,
        name: str,
        description: str = "",
        repository_url: str | None = None,
        default_branch: str = "main",
    ) -> Project:
        now = datetime.now(UTC)
        return await self._repository.add(
            Project(
                id=uuid4(),
                name=normalize_project_name(name),
                description=description.strip(),
                repository_url=repository_url,
                default_branch=default_branch.strip() or "main",
                created_at=now,
                updated_at=now,
            )
        )

    async def update(
        self,
        project_id: UUID,
        *,
        name: str,
        description: str,
        repository_url: str | None,
        default_branch: str,
    ) -> Project:
        existing = await self.get(project_id)
        updated = Project(
            id=existing.id,
            name=normalize_project_name(name),
            description=description.strip(),
            repository_url=repository_url,
            default_branch=default_branch.strip() or "main",
            created_at=existing.created_at,
            updated_at=datetime.now(UTC),
        )
        try:
            return await self._repository.save(updated)
        except LookupError as error:
            raise ProjectNotFound(str(project_id)) from error

    async def delete(self, project_id: UUID) -> None:
        if not await self._repository.delete(project_id):
            raise ProjectNotFound(str(project_id))
