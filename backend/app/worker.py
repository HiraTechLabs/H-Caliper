"""Persistent pipeline worker.

Claims one runnable task at a time with ``SELECT … FOR UPDATE SKIP LOCKED`` so
multiple workers can be added without double execution.  A restart clears
unfinished locks; every stage resumes from committed database state.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select, update

from app.core.config import settings
from app.core.database import SessionLocal, dispose_engine
from app.core.enums import RUNNABLE_TASK_STATES
from app.core.logging import configure_logging
from app.models.task import Task
from app.services.audit import prune_audit_logs
from app.services.pipeline_engine import PipelineEngine, StaleTask

logger = logging.getLogger(__name__)
_stopping = False


def _handle_signal(signum, frame):  # pragma: no cover - signal path
    global _stopping
    _stopping = True
    logger.info("worker stopping on signal %s", signum)


async def reset_own_locks() -> None:
    async with SessionLocal() as db:
        await db.execute(
            update(Task)
            .where(Task.locked_by == settings.WORKER_ID)
            .values(locked_by=None, locked_at=None)
        )
        await db.commit()


async def recover_stale_locks() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.WORKER_LOCK_STALE_MINUTES)
    async with SessionLocal() as db:
        result = await db.execute(
            update(Task)
            .where(Task.locked_at.is_not(None), Task.locked_at < cutoff)
            .values(locked_by=None, locked_at=None)
        )
        await db.commit()
        if result.rowcount:
            logger.warning("recovered %s stale task lock(s)", result.rowcount)


async def claim_task() -> str | None:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.WORKER_LOCK_STALE_MINUTES)
    async with SessionLocal() as db:
        async with db.begin():
            row = await db.execute(
                select(Task)
                .where(
                    Task.status.in_([s.value for s in RUNNABLE_TASK_STATES]),
                    or_(Task.locked_by.is_(None), Task.locked_at < cutoff),
                    Task.cancel_requested.is_(False),
                )
                .order_by(Task.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            task = row.scalar_one_or_none()
            if not task:
                return None
            task.locked_by = settings.WORKER_ID
            task.locked_at = datetime.now(timezone.utc)
            return task.id


async def run_once() -> bool:
    task_id = await claim_task()
    if not task_id:
        return False
    async with SessionLocal() as db:
        task = await db.get(Task, task_id)
        if not task:
            return True
        engine = PipelineEngine(db, task, worker_id=settings.WORKER_ID)
        try:
            await engine.run()
        except StaleTask:
            logger.warning("task %s lost its lock", task_id)
        except Exception:
            logger.exception("unhandled worker error for task %s", task_id)
            await db.rollback()
            async with SessionLocal() as failure_db:
                failed = await failure_db.get(Task, task_id)
                if failed and failed.status not in {"COMPLETED", "CANCELLED"}:
                    engine.db = failure_db
                    engine.task = failed
                    engine.execution = None
                    await engine.fail("Worker crashed while processing the task; see server logs")
        finally:
            try:
                async with SessionLocal() as release_db:
                    await release_db.execute(
                        update(Task)
                        .where(Task.id == task_id, Task.locked_by == settings.WORKER_ID)
                        .values(locked_by=None, locked_at=None)
                    )
                    await release_db.commit()
            except Exception:
                logger.exception("failed to release task lock %s", task_id)
    return True


async def main() -> None:  # pragma: no cover - process entrypoint
    configure_logging()
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    await reset_own_locks()
    await recover_stale_locks()
    logger.info("H-Caliper worker %s started", settings.WORKER_ID)
    last_prune = 0.0
    while not _stopping:
        try:
            worked = await run_once()
        except Exception:
            logger.exception("worker loop error")
            worked = False
        if not worked:
            await asyncio.sleep(settings.WORKER_POLL_SECONDS)
        # Daily audit retention pass (cheap, idempotent).
        now = datetime.now(timezone.utc).timestamp()
        if now - last_prune > 86_400:
            last_prune = now
            try:
                async with SessionLocal() as db:
                    await prune_audit_logs(db)
            except Exception:
                logger.exception("audit retention failed")
    await dispose_engine()
    logger.info("worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
