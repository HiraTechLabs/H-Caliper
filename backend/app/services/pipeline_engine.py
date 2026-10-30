"""Persistent production pipeline engine.

State lives entirely in PostgreSQL.  ``run`` is idempotent per stage: a worker
crash leaves the task in its last committed state and the next worker resumes
from there.  No in-memory state is required for correctness.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import (
    AgentRole,
    ApprovalKind,
    ApprovalStatus,
    Capability,
    GateStatus,
    ReviewDecision,
    TaskStatus,
)
from app.models.caliper import CaliperDocument
from app.models.governance import Approval
from app.models.project import Project, RepositoryConnection
from app.models.provider import Provider, ProviderModel
from app.models.task import (
    Artifact,
    DocumentationRecord,
    PipelineStage,
    Plan,
    QualityGateResult,
    Review,
    Task,
    TaskEvent,
    TaskExecution,
)
from app.services import (
    agents,
    caliper_service,
    git_manager,
    quality_gates,
    workspace as workspace_service,
)
from app.services.audit import audit, notify
from app.services.providers.base import ProviderError, UnsupportedCapabilityError
from app.services.providers.registry import get_handle
from app.services.security_context import decrypt_repository_token

logger = logging.getLogger(__name__)


class Cancelled(Exception):
    pass


class StaleTask(Exception):
    pass


class PipelineEngine:
    def __init__(self, db: AsyncSession, task: Task, *, worker_id: str = "engine") -> None:
        self.db = db
        self.task = task
        self.worker_id = worker_id
        self.project: Optional[Project] = None
        self.repo: Optional[RepositoryConnection] = None
        self.execution: Optional[TaskExecution] = None
        self.worktree: Optional[workspace_service.TaskWorktree] = None

    # ---------------------------------------------------------------- helpers
    async def event(
        self,
        event_type: str,
        message: str,
        *,
        severity: str = "INFO",
        detail: Optional[Dict] = None,
    ) -> None:
        self.db.add(
            TaskEvent(
                task_id=self.task.id,
                event_type=event_type,
                severity=severity,
                message=message[:4000],
                detail=detail or {},
            )
        )
        await self.db.flush()

    async def transition(
        self,
        status: str,
        stage: str,
        *,
        detail: Optional[Dict] = None,
        message: Optional[str] = None,
    ) -> None:
        previous = self.task.status
        self.task.status = status
        self.task.current_stage = stage
        self.db.add(
            PipelineStage(
                task_id=self.task.id,
                execution_id=self.execution.id if self.execution else None,
                stage=stage,
                status="PASSED",
                finished_at=datetime.now(timezone.utc),
                detail={"from": previous, "to": status, **(detail or {})},
            )
        )
        await self.event(
            f"stage.{stage.lower()}",
            message or f"{previous} → {status}",
            detail={"from": previous, "to": status, **(detail or {})},
        )
        await self.db.commit()

    async def check_cancelled(self) -> None:
        await self.db.refresh(self.task, attribute_names=["cancel_requested"])
        if self.task.cancel_requested:
            raise Cancelled()

    async def _reload(self) -> None:
        await self.db.refresh(self.task)

    async def _current_execution(self, attempt: int) -> TaskExecution:
        row = await self.db.execute(
            select(TaskExecution)
            .where(TaskExecution.task_id == self.task.id, TaskExecution.attempt == attempt)
            .limit(1)
        )
        execution = row.scalar_one_or_none()
        if not execution:
            execution = TaskExecution(task_id=self.task.id, attempt=attempt, status="RUNNING")
            self.db.add(execution)
            await self.db.flush()
        self.execution = execution
        return execution

    async def _repository(self) -> RepositoryConnection:
        row = await self.db.execute(
            select(RepositoryConnection).where(
                RepositoryConnection.project_id == self.project.id
            )
        )
        repo = row.scalar_one_or_none()
        if not repo:
            raise agents.AgentFailure(
                "Project has no repository connection. Connect a repository before creating tasks."
            )
        return repo

    async def _resolve_model(self, role: AgentRole) -> Tuple[object, Provider, str, str, str]:
        config = self.task.config or {}
        selection = (config.get("agents") or {}).get(role.value.lower()) or {}
        provider_id = selection.get("provider_id")
        model = selection.get("model")
        if not provider_id:
            provider_id = getattr(self.project, f"default_{role.value.lower()}_provider_id", None)
            model = model or getattr(self.project, f"default_{role.value.lower()}_model", None)
        if not provider_id:
            raise agents.AgentFailure(
                f"No {role.value.lower()} model is configured for this project or task."
            )
        handle = await get_handle(self.db, provider_id)
        adapter = handle.adapter
        if role in {AgentRole.PLANNING, AgentRole.REVIEW, AgentRole.DOCUMENTATION} and not adapter.supports(
            Capability.CHAT
        ):
            raise agents.AgentFailure(
                f"Provider '{handle.record.name}' does not support chat completion required by "
                f"the {role.value.lower()} agent."
            )
        if role == AgentRole.EXECUTION and not (
            adapter.supports(Capability.AGENT) or adapter.supports(Capability.CHAT)
        ):
            raise agents.AgentFailure(
                f"Provider '{handle.record.name}' cannot execute tasks (no agent runtime or chat)."
            )
        if not model:
            row = await self.db.execute(
                select(ProviderModel)
                .where(
                    ProviderModel.provider_id == handle.record.id,
                    ProviderModel.enabled.is_(True),
                )
                .order_by(ProviderModel.model_id)
                .limit(1)
            )
            fallback = row.scalar_one_or_none()
            if fallback:
                model = fallback.model_id
        if not model:
            raise agents.AgentFailure(
                f"No model selected for the {role.value.lower()} agent on provider "
                f"'{handle.record.name}'."
            )
        return handle, handle.record, model, handle.record.name, handle.record.type

    def _runner(self, handle, provider: Provider, model: str) -> agents.AgentRunner:
        return agents.AgentRunner(
            self.db,
            task=self.task,
            project=self.project,
            provider=handle.adapter,
            provider_name=provider.name,
            provider_type=provider.type,
            model=model,
        )

    async def _principles(self) -> str:
        return await caliper_service.load_context(self.db, self.project.id)

    async def _prepare_attempt(self, attempt: int) -> str:
        repo = await self._repository()
        token = decrypt_repository_token(repo)
        project_root = await workspace_service.ensure_project_workspace(
            self.project.slug,
            repository_url=repo.url,
            token=token,
            default_branch=repo.default_branch or self.project.default_branch,
        )
        branch = (
            f"hcaliper/task-{self.task.id}"
            if attempt == 1
            else f"hcaliper/task-{self.task.id}-r{attempt}"
        )
        self.worktree = await workspace_service.prepare_task_worktree(
            slug=self.project.slug,
            task_id=self.task.id,
            attempt=attempt,
            branch=branch,
            repository_url=repo.url,
            token=token,
            default_branch=repo.default_branch or self.project.default_branch,
        )
        self.task.branch = branch
        self.task.base_commit = self.worktree.base_commit
        execution = await self._current_execution(attempt)
        execution.workspace_path = self.worktree.path
        execution.status = "RUNNING"
        await self.db.flush()
        docs = await caliper_service.list_documents(self.db, self.project.id)
        contents = {doc.id: await caliper_service.current_content(self.db, doc) for doc in docs}
        await caliper_service.render_workspace(self.project, project_root, docs, contents)
        return self.worktree.path

    async def _save_artifact(self, kind: str, name: str, content: str, *, path: str | None = None) -> None:
        self.db.add(
            Artifact(
                task_id=self.task.id,
                kind=kind,
                name=name,
                path=path,
                content=content[: settings.MAX_ARTIFACT_BYTES],
                size=len(content.encode("utf-8")),
            )
        )
        await self.db.flush()

    # ------------------------------------------------------------------ stages
    async def _plan(self, attempt: int, feedback: Optional[str] = None) -> Plan:
        handle, provider, model, pname, ptype = await self._resolve_model(AgentRole.PLANNING)
        runner = self._runner(handle, provider, model)
        principles = await self._principles()
        repo_path = self.worktree.path if self.worktree else (await self._prepare_attempt(attempt))
        context = agents.collect_repository_context(
            repo_path, max_chars=min(settings.MAX_CONTEXT_CHARS, 70_000)
        )
        plan = await agents.create_plan(
            db=self.db,
            task=self.task,
            project=self.project,
            runner=runner,
            principles=principles,
            context=context,
            version=attempt,
            feedback=feedback,
        )
        await self._save_artifact(
            "plan", f"plan-v{attempt}.md", plan.content_md
        )
        await self.event(
            "plan.created",
            f"Plan v{attempt} created by {pname} / {model}",
            detail={"provider": pname, "model": model, "plan_id": plan.id},
        )
        return plan

    async def _execute(self, attempt: int, plan: Plan) -> Tuple[git_manager.DiffSummary, List[QualityGateResult]]:
        handle, provider, model, pname, ptype = await self._resolve_model(AgentRole.EXECUTION)
        runner = self._runner(handle, provider, model)
        principles = await self._principles()
        summary, result = await agents.execute_plan(
            db=self.db,
            task=self.task,
            project=self.project,
            runner=runner,
            plan=plan,
            principles=principles,
            workspace=self.worktree.path,
        )
        await self._save_artifact("execution", f"execution-attempt-{attempt}.md", summary)

        changed = await git_manager.changed_files(self.worktree.path)
        diff = await git_manager.diff_against(self.worktree.path, self.task.base_commit)
        await self._save_artifact("diff", f"diff-attempt-{attempt}.patch", diff.diff)
        if not changed:
            await self.event(
                "execution.no_changes",
                "Execution agent made no repository changes",
                severity="WARNING",
            )

        gate_config = list(self.project.quality_gates or [])
        task_gates = ((self.task.config or {}).get("validation_requirements") or {}).get("gates")
        if isinstance(task_gates, list):
            gate_config += task_gates
        outcomes = await quality_gates.run_gates(
            workspace=self.worktree.path,
            configured=gate_config,
            changed_files=changed,
            protected_paths=["CALIPER/manifest.md", ".env"],
        )
        results: List[QualityGateResult] = []
        for outcome in outcomes:
            record = QualityGateResult(
                task_id=self.task.id,
                execution_id=self.execution.id if self.execution else None,
                attempt=attempt,
                name=outcome.name,
                status=outcome.status,
                required=outcome.required,
                command=outcome.command,
                output=outcome.output[:200_000],
                duration_ms=outcome.duration_ms,
            )
            self.db.add(record)
            results.append(record)
        await self.db.flush()
        await self._save_artifact(
            "quality_gates",
            f"gates-attempt-{attempt}.json",
            "\n\n".join(
                f"### {r.name}: {r.status}\n$ {r.command}\n{r.output}" for r in results
            ),
        )

        failed = [r for r in results if r.required and r.status == GateStatus.FAILED.value]
        if not failed and changed:
            commit_sha = await git_manager.commit_all(
                self.worktree.path,
                f"hcaliper: {self.task.title}\n\nTask: {self.task.id}\nAttempt: {attempt}",
            )
            if commit_sha:
                self.task.head_commit = commit_sha
                await self.event("git.commit", f"Committed {commit_sha[:12]}", detail={"sha": commit_sha})
        await self.db.commit()
        return diff, results

    async def _review(
        self, attempt: int, plan: Plan, diff: git_manager.DiffSummary, gates: List[QualityGateResult]
    ) -> Review:
        handle, provider, model, pname, ptype = await self._resolve_model(AgentRole.REVIEW)
        runner = self._runner(handle, provider, model)
        principles = await self._principles()
        review = await agents.run_review(
            db=self.db,
            task=self.task,
            project=self.project,
            runner=runner,
            plan=plan,
            principles=principles,
            diff=diff,
            gates=gates,
            changed=diff.files,
            attempt=attempt,
        )
        await self._save_artifact("review", f"review-attempt-{attempt}.json", review.reason)
        return review

    async def _document(self, attempt: int, plan: Plan, review: Review, diff, gates) -> DocumentationRecord:
        handle, provider, model, pname, ptype = await self._resolve_model(AgentRole.DOCUMENTATION)
        runner = self._runner(handle, provider, model)
        changed = diff.files
        doc_data = await agents.generate_documentation(
            db=self.db,
            task=self.task,
            project=self.project,
            runner=runner,
            plan=plan,
            review=review,
            diff=diff,
            changed=changed,
            commit_sha=self.task.head_commit,
        )
        content = str(doc_data.get("content_md", ""))
        rel_path = f"docs/tasks/{self.task.id}.md"
        written = agents.safe_write(self.worktree.path, rel_path, content)
        commit_sha = await git_manager.commit_all(
            self.worktree.path,
            f"docs: task {self.task.id} documentation\n\nTask: {self.task.id}",
        )
        if commit_sha:
            self.task.head_commit = commit_sha
        record = DocumentationRecord(
            task_id=self.task.id,
            summary=str(doc_data.get("summary", ""))[:20_000],
            content_md=content,
            files=doc_data.get("files", []),
            commit_sha=commit_sha or self.task.head_commit,
        )
        self.db.add(record)
        await self.db.flush()
        await self._save_artifact("documentation", "documentation.md", content, path=written)
        await self.event(
            "documentation.created",
            f"Documentation written to {written} by {doc_data.get('generated_by', pname)}",
            detail={"path": written, "generated_by": doc_data.get("generated_by")},
        )

        # CALIPER proposals may be suggested, never silently applied.
        proposal = doc_data.get("caliper_proposal")
        if isinstance(proposal, dict) and proposal.get("slug") and proposal.get("content"):
            row = await self.db.execute(
                select(CaliperDocument).where(
                    CaliperDocument.project_id == self.project.id,
                    CaliperDocument.slug == proposal["slug"],
                )
            )
            target = row.scalar_one_or_none()
            if target:
                try:
                    await caliper_service.create_proposal(
                        self.db,
                        target,
                        content=str(proposal["content"]),
                        change_summary=str(proposal.get("change_summary", "Agent proposal"))[:2000],
                        reason=str(proposal.get("reason", ""))[:4000],
                        author=f"agent:{pname}/{model}",
                        task_id=self.task.id,
                    )
                    await self.event(
                        "caliper.proposal",
                        f"Documentation agent proposed a change to {target.slug}.md (awaiting approval)",
                    )
                except Exception as exc:
                    await self.event(
                        "caliper.proposal_failed",
                        f"CALIPER proposal not created: {exc}",
                        severity="WARNING",
                    )
        return record

    # -------------------------------------------------------------------- run
    async def run(self) -> None:
        self.project = await self.db.get(Project, self.task.project_id)
        if not self.project:
            await self.fail("Project no longer exists")
            return
        self.repo = await self._repository()

        if not self.task.started_at:
            self.task.started_at = datetime.now(timezone.utc)

        # Resume from persisted state until a terminal or human-gated state.
        for _ in range(40):
            await self.check_cancelled()
            await self._reload()
            status = self.task.status
            if status in {
                TaskStatus.AWAITING_APPROVAL.value,
                TaskStatus.COMPLETED.value,
                TaskStatus.FAILED.value,
                TaskStatus.CANCELLED.value,
                TaskStatus.BLOCKED.value,
                TaskStatus.DEPLOYING.value,
                TaskStatus.RELEASE_READY.value,
            }:
                if self.execution:
                    self.execution.status = "FINISHED"
                    self.execution.finished_at = datetime.now(timezone.utc)
                    await self.db.commit()
                return

            attempt = max(1, self.task.retry_count + 1)
            await self._ensure_worktree(attempt)

            try:
                if status in {
                    TaskStatus.CREATED.value,
                    TaskStatus.CONTEXT_COLLECTION.value,
                    TaskStatus.PLANNING.value,
                    TaskStatus.REPLANNING.value,
                }:
                    await self._stage_plan(attempt)
                elif status in {TaskStatus.PLAN_REVIEW.value, TaskStatus.READY_FOR_EXECUTION.value}:
                    await self._stage_execute(attempt)
                elif status in {TaskStatus.EXECUTING.value, TaskStatus.AUTOMATED_VALIDATION.value}:
                    await self._stage_validate(attempt)
                elif status == TaskStatus.AI_REVIEW.value:
                    await self._stage_review(attempt)
                elif status == TaskStatus.DOCUMENTATION.value:
                    await self._stage_document(attempt)
                else:
                    await self.fail(f"Unhandled task state: {status}")
                    return
            except Cancelled:
                await self.cancel()
                return
            except (agents.AgentFailure, ProviderError, git_manager.GitError, UnsupportedCapabilityError) as exc:
                await self.fail(str(exc))
                return
            except Exception as exc:  # pragma: no cover - defensive boundary
                logger.exception("pipeline failure task=%s", self.task.id)
                await self.fail(f"Unexpected pipeline error: {type(exc).__name__}: {exc}")
                return
        await self.fail("Pipeline exceeded its stage budget; possible loop detected")

    async def _ensure_worktree(self, attempt: int) -> None:
        """Reuse a surviving worktree after a restart, or create a new attempt."""
        if self.worktree and os.path.isdir(self.worktree.path):
            return
        expected = os.path.join(
            self.project_path(), "tasks", self.task.id, f"attempt-{attempt}", "repository"
        )
        if os.path.isdir(os.path.join(expected, ".git")) or os.path.isfile(
            os.path.join(expected, ".git")
        ):
            branch = (
                f"hcaliper/task-{self.task.id}"
                if attempt == 1
                else f"hcaliper/task-{self.task.id}-r{attempt}"
            )
            base = self.task.base_commit or await git_manager.resolve_ref(expected, "HEAD")
            self.worktree = workspace_service.TaskWorktree(
                path=expected, branch=branch, base_commit=base
            )
            self.task.branch = branch
            self.task.base_commit = base
            execution = await self._current_execution(attempt)
            execution.workspace_path = expected
            await self.db.commit()
            return
        await self._prepare_attempt(attempt)

    def project_path(self) -> str:
        return workspace_service.project_path(self.project.slug)

    async def _stage_plan(self, attempt: int) -> None:
        await self._transition_simple(TaskStatus.CONTEXT_COLLECTION, "CONTEXT_COLLECTION")
        feedback = None
        if attempt > 1:
            row = await self.db.execute(
                select(Review)
                .where(Review.task_id == self.task.id)
                .order_by(Review.created_at.desc())
                .limit(1)
            )
            previous = row.scalar_one_or_none()
            if previous:
                feedback = (
                    f"Decision: {previous.decision}\nReason: {previous.reason}\n"
                    f"Required corrections:\n"
                    + "\n".join(f"- {c}" for c in (previous.required_corrections or []))
                )
        await self._transition_simple(
            TaskStatus.PLANNING, "PLANNING", message=f"Planning attempt {attempt}"
        )
        plan = await self._plan(attempt, feedback)
        await self._transition_simple(
            TaskStatus.PLAN_REVIEW, "PLAN_VALIDATION", detail={"plan_id": plan.id, "version": plan.version}
        )
        await self._transition_simple(
            TaskStatus.READY_FOR_EXECUTION, "PLAN_VALIDATION", detail={"plan_id": plan.id}
        )

    async def _stage_execute(self, attempt: int) -> None:
        plan = await self._latest_plan()
        await self._transition_simple(TaskStatus.EXECUTING, "EXECUTING", detail={"plan_id": plan.id})
        diff, gates = await self._execute(attempt, plan)
        await self._transition_simple(
            TaskStatus.AUTOMATED_VALIDATION,
            "AUTOMATED_VALIDATION",
            detail={"files": diff.files},
        )
        await self._transition_simple(TaskStatus.AI_REVIEW, "AI_REVIEW")

    async def _stage_validate(self, attempt: int) -> None:
        # Recovery path: if the process died after execution, re-run gates only if
        # results are incomplete; otherwise move to review.
        row = await self.db.execute(
            select(QualityGateResult).where(
                QualityGateResult.task_id == self.task.id,
                QualityGateResult.attempt == attempt,
            )
        )
        if not row.scalars().first():
            plan = await self._latest_plan()
            await self._execute(attempt, plan)
            await self._transition_simple(TaskStatus.AI_REVIEW, "AI_REVIEW")
        else:
            await self._transition_simple(TaskStatus.AI_REVIEW, "AI_REVIEW")

    async def _stage_review(self, attempt: int) -> None:
        plan = await self._latest_plan()
        diff = await git_manager.diff_against(self.worktree.path, self.task.base_commit)
        gates = list(
            (
                await self.db.execute(
                    select(QualityGateResult).where(
                        QualityGateResult.task_id == self.task.id,
                        QualityGateResult.attempt == attempt,
                    )
                )
            )
            .scalars()
            .all()
        )
        review = await self._review(attempt, plan, diff, gates)
        await self._save_artifact(
            "review_report",
            f"review-attempt-{attempt}.md",
            f"# Review\n\nDecision: **{review.decision}**\n\n{review.reason}\n\n"
            + "\n".join(f"- {c}" for c in review.required_corrections or []),
        )
        await self.event(
            "review.completed",
            f"Review decision: {review.decision}",
            severity="INFO" if review.decision == ReviewDecision.ACCEPTED.value else "WARNING",
            detail={"decision": review.decision, "review_id": review.id},
        )
        if review.decision == ReviewDecision.ACCEPTED.value:
            await self._transition_simple(
                TaskStatus.DOCUMENTATION, "DOCUMENTATION", detail={"review_id": review.id}
            )
            return
        if review.decision == ReviewDecision.NEEDS_HUMAN_APPROVAL.value:
            self.db.add(
                Approval(
                    task_id=self.task.id,
                    kind=ApprovalKind.MERGE.value,
                    requested_by="review-agent",
                    status=ApprovalStatus.PENDING.value,
                    notes="Review requires human approval: " + review.reason[:4000],
                )
            )
            await self._transition_simple(
                TaskStatus.DOCUMENTATION,
                "DOCUMENTATION",
                detail={"review_id": review.id, "human_approval_required": True},
            )
            return
        if review.decision == ReviewDecision.BLOCKED.value:
            await self._transition_simple(
                TaskStatus.BLOCKED, "BLOCKED", detail={"review_id": review.id, "reason": review.reason}
            )
            return
        # REJECTED
        self.task.retry_count = attempt
        if attempt > self.task.max_retries:
            await self.transition(
                TaskStatus.FAILED,
                "AI_REVIEW",
                message=f"Rejected after {attempt} attempt(s); retry limit reached",
                detail={"review_id": review.id},
            )
            await self.fail(
                f"Review rejected the implementation; retry limit "
                f"({self.task.max_retries}) reached. Last reason: {review.reason[:1000]}"
            )
            return
        await self.transition(
            TaskStatus.REPLANNING,
            "REPLANNING",
            message=f"Rejected; replanning for attempt {attempt + 1}",
            detail={"review_id": review.id, "required_corrections": review.required_corrections},
        )
        self.worktree = None

    async def _stage_document(self, attempt: int) -> None:
        plan = await self._latest_plan()
        row = await self.db.execute(
            select(Review)
            .where(Review.task_id == self.task.id)
            .order_by(Review.created_at.desc())
            .limit(1)
        )
        review = row.scalar_one_or_none()
        if not review:
            raise agents.AgentFailure("Cannot document without a review")
        diff = await git_manager.diff_against(self.worktree.path, self.task.base_commit)
        gates = list(
            (
                await self.db.execute(
                    select(QualityGateResult).where(
                        QualityGateResult.task_id == self.task.id,
                        QualityGateResult.attempt == attempt,
                    )
                )
            )
            .scalars()
            .all()
        )
        await self._document(attempt, plan, review, diff, gates)
        self.db.add(
            Approval(
                task_id=self.task.id,
                kind=ApprovalKind.MERGE.value,
                requested_by=str(self.task.created_by or "user"),
                status=ApprovalStatus.PENDING.value,
                notes="Awaiting human approval to merge the reviewed branch.",
            )
        )
        await notify(
            self.db,
            user_id=None,
            title=f"Task awaiting approval: {self.task.title}",
            body="Review accepted the change. Approve the merge to continue.",
            level="INFO",
            task_id=self.task.id,
        )
        await self._transition_simple(TaskStatus.AWAITING_APPROVAL, "AWAITING_APPROVAL")
        if self.execution:
            self.execution.status = "FINISHED"
            self.execution.finished_at = datetime.now(timezone.utc)
        await self.db.commit()

    # ------------------------------------------------------------ transitions
    async def _transition_simple(
        self, status: TaskStatus, stage: str, *, detail: Optional[Dict] = None, message: Optional[str] = None
    ) -> None:
        await self.transition(status.value, stage, detail=detail, message=message)

    async def _latest_plan(self) -> Plan:
        row = await self.db.execute(
            select(Plan)
            .where(Plan.task_id == self.task.id)
            .order_by(Plan.version.desc())
            .limit(1)
        )
        plan = row.scalar_one_or_none()
        if not plan:
            raise agents.AgentFailure("No approved plan exists for this task")
        return plan

    async def fail(self, message: str) -> None:
        self.task.status = TaskStatus.FAILED.value
        self.task.current_stage = "FAILED"
        self.task.error = message[:4000]
        self.task.completed_at = datetime.now(timezone.utc)
        if self.execution:
            self.execution.status = "FAILED"
            self.execution.finished_at = datetime.now(timezone.utc)
            self.execution.error = message[:4000]
        self.db.add(
            PipelineStage(
                task_id=self.task.id,
                execution_id=self.execution.id if self.execution else None,
                stage="FAILED",
                status="FAILED",
                finished_at=datetime.now(timezone.utc),
                detail={"error": message[:4000]},
            )
        )
        await self.event("task.failed", message, severity="ERROR")
        await notify(
            self.db,
            user_id=None,
            title=f"Task failed: {self.task.title}",
            body=message[:1000],
            level="ERROR",
            task_id=self.task.id,
        )
        await audit(
            self.db,
            action="task.failed",
            entity_type="task",
            entity_id=self.task.id,
            detail={"error": message[:2000]},
        )
        await self.db.commit()

    async def cancel(self) -> None:
        self.task.status = TaskStatus.CANCELLED.value
        self.task.current_stage = "CANCELLED"
        self.task.completed_at = datetime.now(timezone.utc)
        if self.execution:
            self.execution.status = "CANCELLED"
            self.execution.finished_at = datetime.now(timezone.utc)
        await self.event("task.cancelled", "Task cancelled by request", severity="WARNING")
        await self.db.commit()
