export type Role = "ADMIN" | "OPERATOR" | "VIEWER";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface Me {
  user: User;
  csrf_token?: string | null;
}

export interface BootstrapStatus {
  bootstrap_required: boolean;
  app_name: string;
  environment: string;
}

export interface Repository {
  id: string;
  provider: string;
  url: string;
  auth_type: string;
  default_branch: string;
  github_owner: string | null;
  github_repo: string | null;
}

export interface Workspace {
  id: string;
  name: string;
  storage_path: string;
  storage_backend: string;
  status: string;
}

export interface Project {
  id: string;
  slug: string;
  name: string;
  description: string;
  status: "ACTIVE" | "ARCHIVED";
  owner_id: string | null;
  default_branch: string;
  max_retries: number;
  quality_gates: QualityGateConfig[];
  settings: Record<string, unknown>;
  default_planning_provider_id: string | null;
  default_planning_model: string | null;
  default_execution_provider_id: string | null;
  default_execution_model: string | null;
  default_review_provider_id: string | null;
  default_review_model: string | null;
  default_documentation_provider_id: string | null;
  default_documentation_model: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectDetail extends Project {
  repository: Repository | null;
  workspaces: Workspace[];
}

export interface QualityGateConfig {
  name: string;
  command: string;
  required?: boolean;
  timeout?: number;
  type?: string;
}

export interface ProjectMember {
  id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: Role;
}

export interface Environment {
  id: string;
  project_id: string;
  kind: "DEVELOPMENT" | "PRODUCTION";
  name: string;
  connection_type: "LOCAL" | "DOCKER" | "SSH" | "WEBHOOK";
  config: Record<string, unknown>;
  is_active: boolean;
  deployment_enabled: boolean;
  requires_approval: boolean;
  health_status: string;
  last_checked_at: string | null;
  created_at: string;
}

export interface ProviderModel {
  id: string;
  model_id: string;
  display_name: string;
  capabilities: Record<string, unknown>;
  enabled: boolean;
  discovered: boolean;
}

export type ProviderType =
  | "openai_compatible"
  | "freellmapi"
  | "lmstudio"
  | "ollama"
  | "opencode"
  | "codex"
  | "antigravity"
  | "mock";

export interface Provider {
  id: string;
  name: string;
  type: ProviderType;
  base_url: string | null;
  enabled: boolean;
  status: string;
  capabilities: Record<string, boolean>;
  config: Record<string, unknown>;
  has_api_key: boolean;
  last_error: string | null;
  last_checked_at: string | null;
  created_at: string;
  models: ProviderModel[];
}

export interface ProviderTypeInfo {
  type: ProviderType;
  label: string;
  capabilities: Record<string, boolean>;
  requires_base_url: boolean;
}

export interface CaliperDocument {
  id: string;
  project_id: string;
  slug: string;
  title: string;
  slot: number;
  is_protected: boolean;
  is_active: boolean;
  current_version: number;
  created_at: string;
  updated_at: string;
}

export interface CaliperVersion {
  id: string;
  version: number;
  change_summary: string;
  reason: string;
  author: string;
  status: string;
  approved_by: string | null;
  created_at: string;
}

export interface CaliperDocumentDetail extends CaliperDocument {
  content: string;
  versions: CaliperVersion[];
}

export interface CaliperProposal {
  id: string;
  document_id: string;
  base_version: number;
  proposed_content: string;
  change_summary: string;
  reason: string;
  related_task_id: string | null;
  author: string;
  status: "PENDING" | "APPROVED" | "REJECTED";
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
  created_at: string;
}

export interface TaskSummary {
  id: string;
  project_id: string;
  title: string;
  description: string;
  status: TaskStatus;
  current_stage: string;
  branch: string | null;
  base_commit: string | null;
  head_commit: string | null;
  max_retries: number;
  retry_count: number;
  error: string | null;
  cancel_requested: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  project_name: string;
  project_slug: string;
}

export type TaskStatus =
  | "CREATED"
  | "CONTEXT_COLLECTION"
  | "PLANNING"
  | "PLAN_REVIEW"
  | "READY_FOR_EXECUTION"
  | "EXECUTING"
  | "AUTOMATED_VALIDATION"
  | "AI_REVIEW"
  | "REJECTED"
  | "REPLANNING"
  | "DOCUMENTATION"
  | "AWAITING_APPROVAL"
  | "RELEASE_READY"
  | "DEPLOYING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED"
  | "BLOCKED";

export interface Plan {
  id: string;
  version: number;
  content_md: string;
  structured: Record<string, unknown>;
  status: string;
  created_at: string;
}

export interface Review {
  id: string;
  attempt: number;
  decision: "ACCEPTED" | "REJECTED" | "NEEDS_HUMAN_APPROVAL" | "BLOCKED";
  reason: string;
  evidence: Record<string, unknown>;
  violated_principles: string[];
  required_corrections: string[];
  severity: string;
  created_at: string;
}

export interface DocumentationRecord {
  id: string;
  summary: string;
  content_md: string;
  files: string[];
  commit_sha: string | null;
  created_at: string;
}

export interface PipelineStage {
  id: string;
  stage: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  detail: Record<string, unknown>;
}

export interface AgentExecution {
  id: string;
  stage: string;
  role: string;
  provider_name: string;
  provider_type: string;
  model: string;
  status: string;
  duration_ms: number | null;
  error: string | null;
  output: Record<string, unknown>;
  created_at: string;
}

export interface GateResult {
  id: string;
  attempt: number;
  name: string;
  status: "PASSED" | "FAILED" | "WARNING" | "NOT_CONFIGURED" | "SKIPPED";
  required: boolean;
  command: string;
  output: string;
  duration_ms: number | null;
  created_at: string;
}

export interface Artifact {
  id: string;
  kind: string;
  name: string;
  path: string | null;
  content_type: string;
  size: number;
  created_at: string;
}

export interface ArtifactDetail extends Artifact {
  content: string;
}

export interface TaskDetail extends TaskSummary {
  plan: Plan | null;
  review: Review | null;
  documentation: DocumentationRecord | null;
  stages: PipelineStage[];
  agent_executions: AgentExecution[];
  gates: GateResult[];
  artifacts: Artifact[];
  diff: string | null;
}

export interface TaskEvent {
  id: string;
  event_type: string;
  severity: string;
  message: string;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Approval {
  id: string;
  task_id: string | null;
  kind: "MERGE" | "DEPLOY" | "CALIPER";
  requested_by: string | null;
  status: "PENDING" | "APPROVED" | "REJECTED";
  decided_by: string | null;
  notes: string | null;
  created_at: string;
  decided_at: string | null;
}

export interface Deployment {
  id: string;
  environment_id: string;
  task_id: string | null;
  status: "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED" | "BLOCKED";
  approved_by: string | null;
  detail: Record<string, unknown>;
  output: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface AuditLog {
  id: string;
  actor_type: string;
  actor_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  detail: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
}

export interface Notification {
  id: string;
  title: string;
  body: string;
  level: string;
  is_read: boolean;
  task_id: string | null;
  created_at: string;
}

export interface DashboardData {
  projects: { total: number; active: number };
  tasks: {
    total: number;
    active: number;
    completed: number;
    failed: number;
    blocked: number;
    awaiting_approval: number;
    by_status: Record<string, number>;
  };
  providers: {
    total: number;
    healthy: number;
    items: Array<{
      id: string;
      name: string;
      type: string;
      status: string;
      enabled: boolean;
      last_checked_at: string | null;
    }>;
  };
  gates: {
    by_status: Record<string, number>;
    passed: number;
    failed: number;
    warning: number;
    not_configured: number;
  };
  recent_activity: Array<{
    id: string;
    task_id: string;
    event_type: string;
    severity: string;
    message: string;
    created_at: string;
  }>;
  awaiting_approval: Array<{
    id: string;
    title: string;
    project_id: string;
    updated_at: string;
  }>;
  activity_7d: Array<{ date: string; count: number }>;
}

export interface HealthReport {
  status: string;
  components: Record<
    string,
    { status: string; message?: string; [key: string]: unknown }
  >;
  timestamp: string;
}

export interface ModelSelection {
  provider_id: string | null;
  model: string | null;
}
