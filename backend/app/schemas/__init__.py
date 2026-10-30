from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.enums import Role


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- auth
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class BootstrapRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=200)
    full_name: str = Field(default="Administrator", max_length=200)

    @field_validator("password")
    @classmethod
    def strong_enough(cls, value: str) -> str:
        if not any(c.isdigit() for c in value) or not any(c.isalpha() for c in value):
            raise ValueError("password must contain letters and numbers")
        return value


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=200)
    full_name: str = Field(default="", max_length=200)
    role: Role = Role.VIEWER


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=200)
    role: Optional[Role] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=12, max_length=200)


class UserOut(ORMModel):
    id: str
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    last_login_at: Optional[datetime]
    created_at: datetime


class MeOut(BaseModel):
    user: UserOut
    csrf_token: Optional[str] = None


# ------------------------------------------------------------- projects
class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: Optional[str] = Field(default=None, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str = Field(default="", max_length=20_000)
    repository_url: Optional[str] = Field(default=None, max_length=1024)
    repository_auth_type: str = Field(default="none", pattern=r"^(none|token|github_app)$")
    repository_token: Optional[str] = Field(default=None, max_length=4096)
    default_branch: str = Field(default="main", max_length=200)
    max_retries: int = Field(default=2, ge=0, le=10)
    quality_gates: List[Dict[str, Any]] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    description: Optional[str] = Field(default=None, max_length=20_000)
    status: Optional[str] = Field(default=None, pattern=r"^(ACTIVE|ARCHIVED)$")
    default_branch: Optional[str] = Field(default=None, max_length=200)
    max_retries: Optional[int] = Field(default=None, ge=0, le=10)
    quality_gates: Optional[List[Dict[str, Any]]] = None
    settings: Optional[Dict[str, Any]] = None
    default_planning_provider_id: Optional[str] = None
    default_planning_model: Optional[str] = None
    default_execution_provider_id: Optional[str] = None
    default_execution_model: Optional[str] = None
    default_review_provider_id: Optional[str] = None
    default_review_model: Optional[str] = None
    default_documentation_provider_id: Optional[str] = None
    default_documentation_model: Optional[str] = None


class RepositoryOut(ORMModel):
    id: str
    provider: str
    url: str
    auth_type: str
    default_branch: str
    github_owner: Optional[str]
    github_repo: Optional[str]


class WorkspaceOut(ORMModel):
    id: str
    name: str
    storage_path: str
    storage_backend: str
    status: str


class ProjectOut(ORMModel):
    id: str
    slug: str
    name: str
    description: str
    status: str
    owner_id: Optional[str]
    default_branch: str
    max_retries: int
    quality_gates: List[Dict[str, Any]]
    settings: Dict[str, Any]
    default_planning_provider_id: Optional[str] = None
    default_planning_model: Optional[str] = None
    default_execution_provider_id: Optional[str] = None
    default_execution_model: Optional[str] = None
    default_review_provider_id: Optional[str] = None
    default_review_model: Optional[str] = None
    default_documentation_provider_id: Optional[str] = None
    default_documentation_model: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ProjectDetail(ProjectOut):
    repository: Optional[RepositoryOut] = None
    workspaces: List[WorkspaceOut] = Field(default_factory=list)


class ProjectMemberOut(BaseModel):
    id: str
    user_id: str
    email: str
    full_name: str
    role: str


class MemberCreate(BaseModel):
    user_id: str
    role: Role = Role.OPERATOR


# ---------------------------------------------------------- environments
class EnvironmentCreate(BaseModel):
    kind: str = Field(pattern=r"^(DEVELOPMENT|PRODUCTION)$")
    name: str = Field(min_length=2, max_length=120)
    connection_type: str = Field(
        default="LOCAL", pattern=r"^(LOCAL|DOCKER|SSH|WEBHOOK)$"
    )
    config: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    deployment_enabled: bool = False
    requires_approval: bool = True


class EnvironmentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    connection_type: Optional[str] = Field(default=None, pattern=r"^(LOCAL|DOCKER|SSH|WEBHOOK)$")
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    deployment_enabled: Optional[bool] = None
    requires_approval: Optional[bool] = None


class EnvironmentOut(ORMModel):
    id: str
    project_id: str
    kind: str
    name: str
    connection_type: str
    config: Dict[str, Any]
    is_active: bool
    deployment_enabled: bool
    requires_approval: bool
    health_status: str
    last_checked_at: Optional[datetime]
    created_at: datetime


# ------------------------------------------------------------- providers
class ProviderCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    type: str
    base_url: Optional[str] = Field(default=None, max_length=1024)
    api_key: Optional[str] = Field(default=None, max_length=4096)
    enabled: bool = True
    config: Dict[str, Any] = Field(default_factory=dict)


class ProviderUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    base_url: Optional[str] = Field(default=None, max_length=1024)
    api_key: Optional[str] = Field(default=None, max_length=4096)
    enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None


class ProviderModelOut(ORMModel):
    id: str
    model_id: str
    display_name: str
    capabilities: Dict[str, Any]
    enabled: bool
    discovered: bool


class ProviderOut(ORMModel):
    id: str
    name: str
    type: str
    base_url: Optional[str]
    enabled: bool
    status: str
    capabilities: Dict[str, Any]
    config: Dict[str, Any]
    has_api_key: bool
    last_error: Optional[str]
    last_checked_at: Optional[datetime]
    created_at: datetime
    models: List[ProviderModelOut] = Field(default_factory=list)


class ModelAssign(BaseModel):
    provider_id: Optional[str] = None
    model: Optional[str] = None


class AgentDefaults(BaseModel):
    planning: Optional[ModelAssign] = None
    execution: Optional[ModelAssign] = None
    review: Optional[ModelAssign] = None
    documentation: Optional[ModelAssign] = None


# --------------------------------------------------------------- caliper
class CaliperDocumentOut(ORMModel):
    id: str
    project_id: str
    slug: str
    title: str
    slot: int
    is_protected: bool
    is_active: bool
    current_version: int
    created_at: datetime
    updated_at: datetime


class CaliperDocumentDetail(CaliperDocumentOut):
    content: str
    versions: List[Dict[str, Any]] = Field(default_factory=list)


class CaliperUpdate(BaseModel):
    content: str = Field(min_length=1)
    change_summary: str = Field(min_length=3, max_length=2000)
    reason: str = Field(default="", max_length=4000)


class CaliperProposalCreate(BaseModel):
    content: str = Field(min_length=1)
    change_summary: str = Field(min_length=3, max_length=2000)
    reason: str = Field(default="", max_length=4000)
    task_id: Optional[str] = None


class CaliperProposalOut(ORMModel):
    id: str
    document_id: str
    base_version: int
    proposed_content: str
    change_summary: str
    reason: str
    related_task_id: Optional[str]
    author: str
    status: str
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    review_notes: Optional[str]
    created_at: datetime


class ProposalDecision(BaseModel):
    approve: bool
    notes: str = Field(default="", max_length=4000)


class CaliperSlotCreate(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$", max_length=60)
    title: str = Field(min_length=2, max_length=200)
    content: str = Field(min_length=1)


# ----------------------------------------------------------------- tasks
class ModelSelection(BaseModel):
    provider_id: Optional[str] = None
    model: Optional[str] = Field(default=None, max_length=250)


class TaskCreate(BaseModel):
    project_id: str
    title: str = Field(min_length=3, max_length=250)
    description: str = Field(min_length=10, max_length=50_000)
    planning: Optional[ModelSelection] = None
    execution: Optional[ModelSelection] = None
    review: Optional[ModelSelection] = None
    documentation: Optional[ModelSelection] = None
    max_retries: Optional[int] = Field(default=None, ge=0, le=10)
    validation_requirements: Optional[Dict[str, Any]] = None


class TaskOut(ORMModel):
    id: str
    project_id: str
    title: str
    description: str
    status: str
    current_stage: str
    branch: Optional[str]
    base_commit: Optional[str]
    head_commit: Optional[str]
    max_retries: int
    retry_count: int
    error: Optional[str]
    cancel_requested: bool
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


class TaskSummary(TaskOut):
    project_name: str = ""
    project_slug: str = ""


class StageOut(ORMModel):
    id: str
    stage: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime]
    detail: Dict[str, Any]


class AgentExecutionOut(ORMModel):
    id: str
    stage: str
    role: str
    provider_name: str
    provider_type: str
    model: str
    status: str
    duration_ms: Optional[int]
    error: Optional[str]
    output: Dict[str, Any]
    created_at: datetime


class GateOut(ORMModel):
    id: str
    attempt: int
    name: str
    status: str
    required: bool
    command: str
    output: str
    duration_ms: Optional[int]
    created_at: datetime


class ArtifactOut(ORMModel):
    id: str
    kind: str
    name: str
    path: Optional[str]
    content_type: str
    size: int
    created_at: datetime


class ArtifactDetail(ArtifactOut):
    content: str


class PlanOut(ORMModel):
    id: str
    version: int
    content_md: str
    structured: Dict[str, Any]
    status: str
    created_at: datetime


class ReviewOut(ORMModel):
    id: str
    attempt: int
    decision: str
    reason: str
    evidence: Dict[str, Any]
    violated_principles: Any
    required_corrections: Any
    severity: str
    created_at: datetime


class DocumentationOut(ORMModel):
    id: str
    summary: str
    content_md: str
    files: Any
    commit_sha: Optional[str]
    created_at: datetime


class TaskDetail(TaskSummary):
    plan: Optional[PlanOut] = None
    review: Optional[ReviewOut] = None
    documentation: Optional[DocumentationOut] = None
    stages: List[StageOut] = Field(default_factory=list)
    agent_executions: List[AgentExecutionOut] = Field(default_factory=list)
    gates: List[GateOut] = Field(default_factory=list)
    artifacts: List[ArtifactOut] = Field(default_factory=list)
    diff: Optional[str] = None


class TaskEventOut(ORMModel):
    id: str
    event_type: str
    severity: str
    message: str
    detail: Dict[str, Any]
    created_at: datetime


class TaskCancel(BaseModel):
    reason: str = Field(default="", max_length=2000)


# ------------------------------------------------------------- approvals
class ApprovalOut(ORMModel):
    id: str
    task_id: Optional[str]
    kind: str
    requested_by: Optional[str]
    status: str
    decided_by: Optional[str]
    notes: Optional[str]
    created_at: datetime
    decided_at: Optional[datetime]


class ApprovalDecision(BaseModel):
    approve: bool
    notes: str = Field(default="", max_length=4000)


class DeploymentCreate(BaseModel):
    environment_id: str
    approval_id: Optional[str] = None


class DeploymentOut(ORMModel):
    id: str
    environment_id: str
    task_id: Optional[str]
    status: str
    approved_by: Optional[str]
    detail: Dict[str, Any]
    output: Optional[str]
    created_at: datetime
    finished_at: Optional[datetime]


# ----------------------------------------------------------------- audit
class AuditOut(ORMModel):
    id: str
    actor_type: str
    actor_id: Optional[str]
    action: str
    entity_type: str
    entity_id: Optional[str]
    detail: Dict[str, Any]
    ip_address: Optional[str]
    created_at: datetime


class NotificationOut(ORMModel):
    id: str
    title: str
    body: str
    level: str
    is_read: bool
    task_id: Optional[str]
    created_at: datetime


class Page(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
