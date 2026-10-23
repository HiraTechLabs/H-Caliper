from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Project:
    id: UUID
    name: str
    description: str
    repository_url: str | None
    default_branch: str
    created_at: datetime
    updated_at: datetime


class ProjectNameRequired(ValueError):
    pass


def normalize_project_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise ProjectNameRequired("Project name cannot be blank")
    if len(normalized) > 120:
        raise ProjectNameRequired("Project name must be 120 characters or fewer")
    return normalized
