"""The four production agents: Planning, Execution, Review, Documentation.

Every agent runs through a shared runner that persists a normalized
``AgentExecution`` row (provider, model, duration, status, redacted output).
Structured outputs are validated before they can influence the pipeline.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import (
    AgentRole,
    Capability,
    GateStatus,
    ReviewDecision,
)
from app.models.project import Project
from app.models.task import AgentExecution, Plan, QualityGateResult, Review, Task
from app.services.providers.base import (
    AgentRunResult,
    BaseProvider,
    ProviderError,
)
from app.services import git_manager

logger = logging.getLogger(__name__)

PLAN_REQUIRED_FIELDS = [
    "task_understanding",
    "business_objective",
    "technical_objective",
    "relevant_principles",
    "existing_analysis",
    "files_to_create",
    "files_to_modify",
    "files_not_to_modify",
    "steps",
    "required_tests",
    "security_considerations",
    "performance_considerations",
    "breaking_changes",
    "dependencies",
    "acceptance_criteria",
    "rollback",
]


class AgentFailure(Exception):
    pass


class PlanValidationError(AgentFailure):
    pass


def parse_json_object(text: str) -> Dict[str, Any]:
    """Extract the first JSON object from an LLM response, tolerating fences."""
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    decoder = json.JSONDecoder()
    for index, char in enumerate(cleaned):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(cleaned[index:])
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    raise AgentFailure("Agent response did not contain a valid JSON object")


def _truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[:limit] + "\n… truncated"


def _text_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v)[:2000] for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [line.strip("-• ").strip() for line in value.splitlines() if line.strip()]
    return []


@dataclass
class RepositoryContext:
    tree: str
    files: str
    git_log: str
    status: str


def collect_repository_context(
    repo_path: str, *, max_files: int = 240, max_chars: int = 60_000
) -> RepositoryContext:
    skip_dirs = {
        ".git", "node_modules", ".venv", "venv", "__pycache__", ".next", "dist",
        "build", "target", ".mypy_cache", ".pytest_cache", "coverage", ".idea",
    }
    paths: List[str] = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = sorted(d for d in dirs if d not in skip_dirs and not d.startswith(".git"))
        for name in sorted(files):
            rel = os.path.relpath(os.path.join(root, name), repo_path)
            paths.append(rel)
            if len(paths) >= max_files * 4:
                break
        if len(paths) >= max_files * 4:
            break
    tree = "\n".join(paths[:max_files])

    priority = [
        "README.md", "README.rst", "package.json", "pyproject.toml", "requirements.txt",
        "go.mod", "Cargo.toml", "composer.json", "Makefile", "docker-compose.yml",
        "docker-compose.yaml", "Dockerfile", ".env.example", "tsconfig.json",
    ]
    code_extensions = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".rb", ".php", ".java", ".cs", ".sql", ".md"}
    selected: List[str] = []
    for name in priority:
        if name in paths and name not in selected:
            selected.append(name)
    for rel in paths[:max_files]:
        if len(selected) >= 40:
            break
        if rel in selected:
            continue
        if os.path.splitext(rel)[1].lower() in code_extensions:
            selected.append(rel)

    chunks: List[str] = []
    used = 0
    for rel in selected:
        full = os.path.realpath(os.path.join(repo_path, rel))
        if not full.startswith(os.path.realpath(repo_path) + os.sep):
            continue
        try:
            if os.path.getsize(full) > 120_000:
                continue
            content = open(full, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        header = f"\n\n----- FILE: {rel} -----\n"
        piece = header + content
        if used + len(piece) > max_chars:
            chunks.append(f"\n\n----- FILE: {rel} -----\n[omitted: context budget]")
            break
        chunks.append(piece)
        used += len(piece)

    git_log = ""
    status = ""
    try:
        import subprocess

        proc = subprocess.run(
            ["git", "log", "-8", "--pretty=format:%h %s"],
            cwd=repo_path, capture_output=True, text=True, timeout=20,
        )
        git_log = proc.stdout if proc.returncode == 0 else ""
        proc = subprocess.run(
            ["git", "status", "--short"],
            cwd=repo_path, capture_output=True, text=True, timeout=20,
        )
        status = proc.stdout if proc.returncode == 0 else ""
    except Exception:
        pass
    return RepositoryContext(tree=tree, files="".join(chunks), git_log=git_log, status=status)


class AgentRunner:
    """Shared provider invocation + persistence for all agent roles."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        task: Task,
        project: Project,
        provider: BaseProvider,
        provider_name: str,
        provider_type: str,
        model: str,
    ) -> None:
        self.db = db
        self.task = task
        self.project = project
        self.provider = provider
        self.provider_name = provider_name
        self.provider_type = provider_type
        self.model = model

    async def _record(
        self,
        *,
        role: str,
        stage: str,
        status: str,
        started: float,
        output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> AgentExecution:
        record = AgentExecution(
            task_id=self.task.id,
            stage=stage,
            role=role,
            provider_id=None,
            provider_name=self.provider_name,
            provider_type=self.provider_type,
            model=self.model,
            status=status,
            duration_ms=int((time.monotonic() - started) * 1000),
            error=error,
            output=output or {},
            finished_at=datetime.now(timezone.utc),
        )
        self.db.add(record)
        await self.db.flush()
        return record

    async def complete(
        self,
        *,
        role: str,
        stage: str,
        system: str,
        user: str,
        temperature: float = 0.2,
    ) -> str:
        started = time.monotonic()
        logger.info(
            "agent.start",
            extra={
                "task_id": self.task.id,
                "project_id": self.project.id,
                "agent_role": role,
                "provider": self.provider_name,
                "model": self.model,
                "stage": stage,
            },
        )
        last_exc: Optional[ProviderError] = None
        for attempt in range(2):
            try:
                text = await self.provider.complete(
                    [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    model=self.model,
                    temperature=temperature,
                )
                await self._record(
                    role=role,
                    stage=stage,
                    status="SUCCEEDED",
                    started=started,
                    output={"response": _truncate(text, 20_000)},
                )
                return text
            except ProviderError as exc:
                last_exc = exc
                if not exc.retryable or attempt == 1:
                    await self._record(
                        role=role, stage=stage, status="FAILED", started=started, error=exc.message
                    )
                    raise
                await asyncio.sleep(2)
        raise last_exc or ProviderError("Provider call failed")

    async def run_agent(
        self, *, role: str, stage: str, workspace: str, prompt: str, timeout: int
    ) -> AgentRunResult:
        started = time.monotonic()
        try:
            result = await self.provider.run_agent(
                workspace=workspace, prompt=prompt, model=self.model, timeout=timeout
            )
        except ProviderError as exc:
            await self._record(
                role=role, stage=stage, status="FAILED", started=started, error=exc.message
            )
            raise
        await self._record(
            role=role,
            stage=stage,
            status="SUCCEEDED" if result.exit_code == 0 else "FAILED",
            started=started,
            output={
                "response": _truncate(result.output, 20_000),
                "changed_files": result.changed_files,
                "exit_code": result.exit_code,
            },
            error=None if result.exit_code == 0 else f"Agent exited with {result.exit_code}",
        )
        return result


# ---------------------------------------------------------------- planning

PLANNING_SYSTEM = """You are the H-Caliper Planning Agent. You turn a development request
into an implementation plan that obeys the project's CALIPER constitution.

Rules:
- Study the provided repository context and principles before planning.
- Never propose secrets, destructive migrations, or edits to protected files.
- Keep scope minimal and consistent with the existing architecture.
- Output ONLY one JSON object. No prose outside the JSON.
- PLAN_SCHEMA begins below.
PLAN_SCHEMA:
{
  "task_understanding": "string",
  "business_objective": "string",
  "technical_objective": "string",
  "relevant_principles": ["file.md"],
  "existing_analysis": "string",
  "files_to_create": ["path"],
  "files_to_modify": ["path"],
  "files_not_to_modify": ["path"],
  "steps": ["ordered step"],
  "required_tests": ["test to add or run"],
  "security_considerations": ["string"],
  "performance_considerations": ["string"],
  "breaking_changes": ["string"],
  "dependencies": ["string"],
  "acceptance_criteria": ["testable criterion"],
  "rollback": "string",
  "summary": "one paragraph"
}"""


def validate_plan(plan: Dict[str, Any]) -> List[str]:
    problems = []
    for field in PLAN_REQUIRED_FIELDS:
        if field not in plan:
            problems.append(f"missing field: {field}")
        elif field in {
            "task_understanding", "business_objective", "technical_objective",
            "existing_analysis", "rollback",
        } and not str(plan.get(field) or "").strip():
            problems.append(f"empty field: {field}")
    for field in ("steps", "acceptance_criteria"):
        if not _text_list(plan.get(field)):
            problems.append(f"field must be a non-empty list: {field}")
    for field in ("files_to_create", "files_to_modify", "files_not_to_modify"):
        value = plan.get(field)
        if value is not None and not isinstance(value, list):
            problems.append(f"field must be a list: {field}")
    return problems


def plan_to_markdown(plan: Dict[str, Any], version: int) -> str:
    def bullets(key: str) -> str:
        values = _text_list(plan.get(key))
        return "\n".join(f"- {v}" for v in values) if values else "- (none)"

    return f"""# Implementation Plan (v{version})

## Task Understanding
{plan.get('task_understanding', '')}

## Business Objective
{plan.get('business_objective', '')}

## Technical Objective
{plan.get('technical_objective', '')}

## Relevant CALIPER Principles
{bullets('relevant_principles')}

## Existing Implementation Analysis
{plan.get('existing_analysis', '')}

## Files To Create
{bullets('files_to_create')}

## Files To Modify
{bullets('files_to_modify')}

## Files That Must Not Be Modified
{bullets('files_not_to_modify')}

## Implementation Steps
{bullets('steps')}

## Required Tests
{bullets('required_tests')}

## Security Considerations
{bullets('security_considerations')}

## Performance Considerations
{bullets('performance_considerations')}

## Potential Breaking Changes
{bullets('breaking_changes')}

## Dependencies
{bullets('dependencies')}

## Acceptance Criteria
{bullets('acceptance_criteria')}

## Rollback
{plan.get('rollback', '')}

## Summary
{plan.get('summary', '')}
"""


async def create_plan(
    *,
    db: AsyncSession,
    task: Task,
    project: Project,
    runner: AgentRunner,
    principles: str,
    context: RepositoryContext,
    version: int,
    feedback: Optional[str] = None,
) -> Plan:
    user = f"""TASK_TITLE: {task.title}
TASK_DESCRIPTION:
{task.description}

PROJECT: {project.name} ({project.slug})
TARGET_BRANCH: {project.default_branch}

CALIPER PRINCIPLES:
{principles}

REPOSITORY TREE (partial):
{context.tree}

RECENT GIT LOG:
{context.git_log}

REPOSITORY CONTEXT:
{context.files}
"""
    if feedback:
        user += f"\n\nPREVIOUS REVIEW FEEDBACK (the plan must correct these issues):\n{feedback}\n"

    last_error = ""
    for attempt in range(2):
        system = PLANNING_SYSTEM
        if attempt:
            system += f"\n\nYour previous output was invalid: {last_error}. Return valid JSON only."
        text = await runner.complete(
            role=AgentRole.PLANNING.value, stage="PLANNING", system=system, user=user
        )
        try:
            structured = parse_json_object(text)
            problems = validate_plan(structured)
            if problems:
                last_error = "; ".join(problems)
                continue
        except AgentFailure as exc:
            last_error = str(exc)
            continue
        markdown = plan_to_markdown(structured, version)
        plan = Plan(
            task_id=task.id,
            version=version,
            content_md=markdown,
            structured=structured,
            status="APPROVED",
            approved_at=datetime.now(timezone.utc),
        )
        db.add(plan)
        await db.flush()
        return plan
    raise PlanValidationError(f"Planning agent did not produce a valid plan: {last_error}")


# --------------------------------------------------------------- execution

EXECUTION_SYSTEM = """You are the H-Caliper Execution Agent. Implement the approved plan in the
current repository, respecting the CALIPER constitution.

Mandatory rules:
- Work only inside this repository. Never touch files outside it.
- Follow the approved plan; do not expand scope.
- Inspect existing code before changing it; reuse existing patterns.
- Never hardcode secrets, credentials or production endpoints.
- Add or update tests for changed behaviour.
- Do not commit, push, merge, deploy, or modify the CALIPER directory.
- When finished, reply with a concise change summary.
"""

PATCH_SYSTEM = """You are the H-Caliper Execution Agent operating in structured-patch mode.
Return ONLY a JSON object:
{
  "summary": "what changed and why",
  "files": [
    {"path": "relative/path.py", "content": "complete new file content"}
  ],
  "deleted_files": ["relative/path"]
}
Rules:
- Only relative paths inside the repository. Never absolute paths or '..'.
- Include the COMPLETE final content for each written file.
- Do not modify .git, CALIPER, .env or secrets.
- Keep the change minimal and add tests where the plan requires them.
"""


def safe_write(workspace: str, rel_path: str, content: str) -> str:
    if not rel_path or rel_path.startswith(("/", "\\")):
        raise AgentFailure(f"Unsafe absolute path: {rel_path}")
    rel = os.path.normpath(rel_path)
    if rel.startswith("..") or rel == ".git" or rel.startswith(".git" + os.sep):
        raise AgentFailure(f"Unsafe path: {rel_path}")
    if rel == "CALIPER" or rel.startswith("CALIPER" + os.sep) or rel == ".env":
        raise AgentFailure(f"Protected path: {rel_path}")
    target = os.path.realpath(os.path.join(workspace, rel))
    root = os.path.realpath(workspace)
    if target != root and not target.startswith(root + os.sep):
        raise AgentFailure(f"Path escapes workspace: {rel_path}")
    if len(content.encode("utf-8")) > 1_000_000:
        raise AgentFailure(f"File too large: {rel_path}")
    os.makedirs(os.path.dirname(target) or root, exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(content)
    return rel


async def execute_plan(
    *,
    db: AsyncSession,
    task: Task,
    project: Project,
    runner: AgentRunner,
    plan: Plan,
    principles: str,
    workspace: str,
) -> Tuple[str, AgentRunResult | None]:
    summary = ""
    result: Optional[AgentRunResult] = None
    prompt = f"""APPROVED PLAN:
{plan.content_md}

TASK:
{task.title}

{task.description}

CALIPER PRINCIPLES:
{principles}

Implement the plan now in the repository at {workspace}.
"""
    if runner.provider.supports(Capability.AGENT):
        result = await runner.run_agent(
            role=AgentRole.EXECUTION.value,
            stage="EXECUTING",
            workspace=workspace,
            prompt=prompt,
            timeout=settings.AGENT_TIMEOUT_SECONDS,
        )
        summary = result.output
        if result.exit_code != 0:
            raise AgentFailure(f"Execution agent failed with exit code {result.exit_code}")
    else:
        # Structured patch protocol for completion-only providers.  The factory,
        # not the model, performs file writes after validation.
        context = collect_repository_context(workspace, max_chars=45_000)
        user = f"""APPROVED PLAN:
{plan.content_md}

TASK:
{task.title}

{task.description}

CALIPER PRINCIPLES:
{principles}

REPOSITORY CONTEXT:
{context.files}
"""
        text = await runner.complete(
            role=AgentRole.EXECUTION.value, stage="EXECUTING", system=PATCH_SYSTEM, user=user
        )
        patch = parse_json_object(text)
        files = patch.get("files")
        if not isinstance(files, list) or not files:
            raise AgentFailure("Execution agent returned no file changes")
        if len(files) > 30:
            raise AgentFailure("Execution agent proposed too many files (>30)")
        written = []
        for item in files:
            if not isinstance(item, dict) or "path" not in item:
                continue
            written.append(safe_write(workspace, str(item["path"]), str(item.get("content", ""))))
        for rel in _text_list(patch.get("deleted_files")):
            target = os.path.realpath(os.path.join(workspace, rel))
            root = os.path.realpath(workspace)
            if target.startswith(root + os.sep) and os.path.isfile(target) and rel != ".env":
                os.remove(target)
                written.append(f"deleted:{rel}")
        summary = str(patch.get("summary", "")) or f"Patched {len(written)} file(s)"
        result = AgentRunResult(
            output=summary, exit_code=0, duration_ms=0, changed_files=written
        )
    return summary, result


# ------------------------------------------------------------------ review

REVIEW_SYSTEM = """You are the H-Caliper Review Agent. Independently audit the implementation.
Do not trust the execution summary: inspect the diff and deterministic gate results.
Reject when mandatory gates fail, the plan was not followed, CALIPER is violated,
or security/tests are insufficient. Compilation alone is not acceptance.

Output ONLY one JSON object.
REVIEW_SCHEMA:
{
  "decision": "ACCEPTED" | "REJECTED" | "NEEDS_HUMAN_APPROVAL" | "BLOCKED",
  "reason": "string",
  "evidence": {"files": ["..."], "notes": "..."},
  "violated_principles": ["clean-code.md: ..."],
  "required_corrections": ["specific correction"],
  "severity": "CRITICAL" | "MAJOR" | "MINOR" | "INFO"
}"""


async def run_review(
    *,
    db: AsyncSession,
    task: Task,
    project: Project,
    runner: AgentRunner,
    plan: Plan,
    principles: str,
    diff: git_manager.DiffSummary,
    gates: List[QualityGateResult],
    changed: List[str],
    attempt: int,
) -> Review:
    gate_text = "\n".join(
        f"- {g.name}: {g.status} (required={g.required})\n{_truncate(g.output, 4000)}"
        for g in gates
    )
    user = f"""TASK:
{task.title}

{task.description}

APPROVED PLAN:
{plan.content_md}

CHANGED FILES:
{chr(10).join(changed) or '(none)'}

DIFF:
{_truncate(diff.diff, 50_000) or '(no diff)'}

QUALITY GATE RESULTS:
{gate_text or '(none)'}

CALIPER PRINCIPLES:
{principles}
"""
    text = await runner.complete(
        role=AgentRole.REVIEW.value, stage="AI_REVIEW", system=REVIEW_SYSTEM, user=user
    )
    parsed = parse_json_object(text)
    decision = str(parsed.get("decision", "")).upper()
    if decision not in {d.value for d in ReviewDecision}:
        decision = ReviewDecision.REJECTED.value
        parsed["reason"] = (
            str(parsed.get("reason", "")) + " [invalid decision normalized to REJECTED]"
        ).strip()
    reason = str(parsed.get("reason", "No reason supplied"))[:20_000]
    violated = _text_list(parsed.get("violated_principles"))
    corrections = _text_list(parsed.get("required_corrections"))

    failed = [g for g in gates if g.required and g.status == GateStatus.FAILED.value]
    if failed and decision in {ReviewDecision.ACCEPTED.value, ReviewDecision.NEEDS_HUMAN_APPROVAL.value}:
        decision = ReviewDecision.REJECTED.value
        reason = (
            "Mandatory quality gate(s) failed: "
            + ", ".join(g.name for g in failed)
            + ". "
            + reason
        )
        corrections.append("Make all mandatory quality gates pass.")
    if not changed and decision == ReviewDecision.ACCEPTED.value:
        decision = ReviewDecision.REJECTED.value
        reason = "No file changes were produced. " + reason
        corrections.append("Implement the approved plan; the repository is unchanged.")

    review = Review(
        task_id=task.id,
        plan_id=plan.id,
        attempt=attempt,
        decision=decision,
        reason=reason,
        evidence={
            "files": changed,
            "diff_stat": diff.stat,
            "gate_summary": [
                {"name": g.name, "status": g.status, "required": g.required} for g in gates
            ],
        },
        violated_principles=violated,
        required_corrections=corrections,
        severity=str(parsed.get("severity", "MAJOR")).upper()[:20],
    )
    db.add(review)
    await db.flush()
    return review


# ----------------------------------------------------------- documentation

DOCUMENTATION_SYSTEM = """You are the H-Caliper Documentation Agent. Document the accepted change.
Be factual. Distinguish actual changes from proposals. Never alter CALIPER principles.

Output ONLY one JSON object.
DOCUMENTATION_SCHEMA:
{
  "summary": "string",
  "content_md": "complete markdown document",
  "files": [{"path": "changed/path", "change": "description"}],
  "decisions": ["decision made"],
  "dependencies": ["dependency change"],
  "caliper_proposal": null | {"slug": "principle-slug", "content": "proposed full content", "change_summary": "string", "reason": "string"}
}"""


async def generate_documentation(
    *,
    db: AsyncSession,
    task: Task,
    project: Project,
    runner: AgentRunner,
    plan: Plan,
    review: Review,
    diff: git_manager.DiffSummary,
    changed: List[str],
    commit_sha: Optional[str],
) -> Dict[str, Any]:
    user = f"""TASK: {task.title}
{task.description}

PLAN:
{plan.content_md}

REVIEW DECISION: {review.decision}
REVIEW REASON: {review.reason}

COMMIT: {commit_sha or '(not committed)'}

CHANGED FILES:
{chr(10).join(changed)}

DIFF:
{_truncate(diff.diff, 40_000)}
"""
    try:
        text = await runner.complete(
            role=AgentRole.DOCUMENTATION.value,
            stage="DOCUMENTATION",
            system=DOCUMENTATION_SYSTEM,
            user=user,
        )
        parsed = parse_json_object(text)
        if not str(parsed.get("content_md", "")).strip():
            raise AgentFailure("Documentation agent returned no content")
        parsed["generated_by"] = f"{runner.provider_name}/{runner.model}"
        return parsed
    except Exception as exc:
        # Honest deterministic fallback; never presented as an AI-generated document.
        logger.warning("documentation fallback: %s", exc)
        content = f"""# Task Documentation: {task.title}

> Generated by the factory fallback because the documentation model failed:
> `{type(exc).__name__}`. Review the diff and plan for authoritative detail.

## Summary
{task.description}

## Plan
{_truncate(plan.content_md, 12_000)}

## Changed Files
{chr(10).join(f'- `{f}`' for f in changed) or '- (none)'}

## Review
- Decision: {review.decision}
- Reason: {review.reason}

## Commit
`{commit_sha or 'not committed'}`

## Diff Stat
```
{diff.stat}
```
"""
        return {
            "summary": f"Fallback documentation for {task.title}",
            "content_md": content,
            "files": [{"path": f, "change": "changed"} for f in changed],
            "decisions": [],
            "dependencies": [],
            "generated_by": "factory-fallback",
        }
