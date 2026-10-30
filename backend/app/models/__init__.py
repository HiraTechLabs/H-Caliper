"""Import every model so SQLAlchemy metadata is complete."""

from app.models.base import Base
from app.models.caliper import CaliperDocument, CaliperProposal, CaliperVersion
from app.models.governance import AuditLog, Approval, Deployment, Notification
from app.models.project import (
    Environment,
    EnvironmentVariable,
    Project,
    RepositoryConnection,
    Workspace,
)
from app.models.provider import AgentConfiguration, Provider, ProviderModel
from app.models.task import (
    AgentExecution,
    Artifact,
    DocumentationRecord,
    GitOperation,
    PipelineStage,
    Plan,
    QualityGateResult,
    Review,
    Task,
    TaskEvent,
    TaskExecution,
)
from app.models.user import ProjectMember, User

__all__ = [
    "Base",
    "User",
    "ProjectMember",
    "Project",
    "Workspace",
    "RepositoryConnection",
    "Environment",
    "EnvironmentVariable",
    "Provider",
    "ProviderModel",
    "AgentConfiguration",
    "CaliperDocument",
    "CaliperVersion",
    "CaliperProposal",
    "Task",
    "TaskExecution",
    "PipelineStage",
    "TaskEvent",
    "AgentExecution",
    "Plan",
    "Review",
    "QualityGateResult",
    "GitOperation",
    "Artifact",
    "DocumentationRecord",
    "Approval",
    "AuditLog",
    "Notification",
    "Deployment",
]
