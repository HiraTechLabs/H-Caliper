from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AvailableProjectModel:
    provider_type: str
    provider_id: str
    provider_name: str
    model_id: str
    model_name: str


@dataclass(frozen=True, slots=True)
class ProjectModelSelection:
    provider_type: str
    provider_id: str
    model_id: str
    updated_at: datetime


class ProjectModelRepository(Protocol):
    async def get(self, project_id: UUID) -> ProjectModelSelection | None: ...
    async def select(
        self, project_id: UUID, provider_type: str, provider_id: str, model_id: str
    ) -> ProjectModelSelection: ...
    async def clear(self, project_id: UUID) -> None: ...


class ProjectModelUnavailable(LookupError):
    pass


class ProjectModels:
    def __init__(self, repository: ProjectModelRepository):
        self._repository = repository

    async def get(
        self, project_id: UUID, options: Sequence[AvailableProjectModel]
    ) -> tuple[ProjectModelSelection | None, list[AvailableProjectModel]]:
        return await self._repository.get(project_id), list(options)

    async def select(
        self,
        project_id: UUID,
        *,
        provider_type: str,
        provider_id: str,
        model_id: str,
        options: Sequence[AvailableProjectModel],
    ) -> tuple[ProjectModelSelection, list[AvailableProjectModel]]:
        if not any(
            item.provider_type == provider_type
            and item.provider_id == provider_id
            and item.model_id == model_id
            for item in options
        ):
            raise ProjectModelUnavailable("Choose a model from the current provider catalog")
        await self._repository.select(project_id, provider_type, provider_id, model_id)
        fresh = await self._repository.get(project_id)
        if fresh is None:
            raise RuntimeError("Committed project model selection was not found on fresh read")
        return fresh, list(options)

    async def clear(self, project_id: UUID) -> None:
        await self._repository.clear(project_id)
