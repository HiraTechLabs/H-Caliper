"""Domain enumerations shared by models, services, and API schemas."""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


class Role(StrEnum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"


class ProjectStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class AgentRole(StrEnum):
    PLANNING = "PLANNING"
    EXECUTION = "EXECUTION"
    REVIEW = "REVIEW"
    DOCUMENTATION = "DOCUMENTATION"


class ProviderType(StrEnum):
    OPENAI_COMPATIBLE = "openai_compatible"
    FREELLMAPI = "freellmapi"
    LMSTUDIO = "lmstudio"
    OLLAMA = "ollama"
    OPENCODE = "opencode"
    CODEX = "codex"
    ANTIGRAVITY = "antigravity"
    MOCK = "mock"


class ProviderStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNREACHABLE = "UNREACHABLE"
    AUTH_FAILED = "AUTH_FAILED"
    DISABLED = "DISABLED"


class Capability(StrEnum):
    CHAT = "chat"
    AGENT = "agent"
    TOOLS = "tools"
    FILE_EDITING = "file_editing"
    TERMINAL = "terminal"
    STREAMING = "streaming"
    MODEL_DISCOVERY = "model_discovery"


class TaskStatus(StrEnum):
    CREATED = "CREATED"
    CONTEXT_COLLECTION = "CONTEXT_COLLECTION"
    PLANNING = "PLANNING"
    PLAN_REVIEW = "PLAN_REVIEW"
    READY_FOR_EXECUTION = "READY_FOR_EXECUTION"
    EXECUTING = "EXECUTING"
    AUTOMATED_VALIDATION = "AUTOMATED_VALIDATION"
    AI_REVIEW = "AI_REVIEW"
    REJECTED = "REJECTED"
    REPLANNING = "REPLANNING"
    DOCUMENTATION = "DOCUMENTATION"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    RELEASE_READY = "RELEASE_READY"
    DEPLOYING = "DEPLOYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"


TERMINAL_TASK_STATES = {
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
}

RUNNABLE_TASK_STATES = {
    TaskStatus.CREATED,
    TaskStatus.CONTEXT_COLLECTION,
    TaskStatus.PLANNING,
    TaskStatus.PLAN_REVIEW,
    TaskStatus.READY_FOR_EXECUTION,
    TaskStatus.EXECUTING,
    TaskStatus.AUTOMATED_VALIDATION,
    TaskStatus.AI_REVIEW,
    TaskStatus.REPLANNING,
    TaskStatus.DOCUMENTATION,
}


class StageStatus(StrEnum):
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class GateStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    WARNING = "WARNING"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    SKIPPED = "SKIPPED"


class ReviewDecision(StrEnum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    NEEDS_HUMAN_APPROVAL = "NEEDS_HUMAN_APPROVAL"
    BLOCKED = "BLOCKED"


class ApprovalKind(StrEnum):
    MERGE = "MERGE"
    DEPLOY = "DEPLOY"
    CALIPER = "CALIPER"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class EnvironmentKind(StrEnum):
    DEVELOPMENT = "DEVELOPMENT"
    PRODUCTION = "PRODUCTION"


class ConnectionType(StrEnum):
    LOCAL = "LOCAL"
    DOCKER = "DOCKER"
    SSH = "SSH"
    WEBHOOK = "WEBHOOK"


class DeploymentStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
