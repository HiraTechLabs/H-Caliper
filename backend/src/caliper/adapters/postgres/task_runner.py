import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import case, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from caliper.adapters.postgres.models import ProjectSyncRow, TaskRow

WORKER_LOCK_KEY = 7_524_910_182_331
MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class PersistedTask:
    id: UUID
    project_id: UUID
    kind: str
    payload: dict
    attempt_count: int


TaskHandler = Callable[[PersistedTask], Awaitable[str | None]]


class PostgresTaskRunner:
    """A single-process worker over a PostgreSQL queue with restart recovery."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        engine: AsyncEngine,
        handler: TaskHandler,
        poll_interval: float = 0.5,
    ):
        self._session_factory = session_factory
        self._engine = engine
        self._handler = handler
        self._poll_interval = poll_interval
        self._stop = asyncio.Event()
        self._runner: asyncio.Task[None] | None = None
        self._lock_connection = None

    async def start(self) -> None:
        self._runner = asyncio.create_task(self._run(), name="caliper-postgres-task-runner")

    async def stop(self) -> None:
        self._stop.set()
        if self._runner is not None:
            await self._runner

    async def _recover_interrupted(self) -> None:
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            committed_syncs = (
                select(TaskRow.id)
                .join(ProjectSyncRow, ProjectSyncRow.task_id == TaskRow.id)
                .where(
                    TaskRow.status == "running",
                    ProjectSyncRow.status == "synchronized",
                )
            )
            await session.execute(
                update(TaskRow)
                .where(TaskRow.id.in_(committed_syncs))
                .values(status="succeeded", finished_at=now, error_code=None)
            )
            await session.execute(
                update(TaskRow)
                .where(TaskRow.status == "running", TaskRow.attempt_count < MAX_ATTEMPTS)
                .values(status="queued", error_code="worker_interrupted")
            )
            await session.execute(
                update(TaskRow)
                .where(TaskRow.status == "running", TaskRow.attempt_count >= MAX_ATTEMPTS)
                .values(status="failed", finished_at=now, error_code="worker_interrupted")
            )
            queued_ids = select(TaskRow.id).where(TaskRow.status == "queued")
            await session.execute(
                update(ProjectSyncRow)
                .where(
                    ProjectSyncRow.status == "running",
                    ProjectSyncRow.task_id.in_(queued_ids),
                )
                .values(status="queued", attempted_at=now, error_code="worker_interrupted")
            )
            await session.execute(
                update(ProjectSyncRow)
                .where(ProjectSyncRow.status == "running", ProjectSyncRow.task_id.is_(None))
                .values(
                    status=case(
                        (ProjectSyncRow.last_success_at.is_not(None), "stale"),
                        else_="failed",
                    ),
                    error_code="worker_interrupted",
                )
            )
            failed_ids = select(TaskRow.id).where(
                TaskRow.status == "failed", TaskRow.error_code == "worker_interrupted"
            )
            await session.execute(
                update(ProjectSyncRow)
                .where(ProjectSyncRow.task_id.in_(failed_ids))
                .values(
                    status=case(
                        (ProjectSyncRow.last_success_at.is_not(None), "stale"),
                        else_="failed",
                    ),
                    error_code="worker_interrupted",
                )
            )
            terminal_task_ids = select(TaskRow.id).where(
                TaskRow.status.in_(("succeeded", "failed"))
            )
            await session.execute(
                update(ProjectSyncRow)
                .where(
                    ProjectSyncRow.status == "running",
                    ProjectSyncRow.task_id.in_(terminal_task_ids),
                )
                .values(
                    status=case(
                        (ProjectSyncRow.last_success_at.is_not(None), "stale"),
                        else_="failed",
                    ),
                    error_code="task_interrupted",
                )
            )
            await session.commit()

    async def _run(self) -> None:
        try:
            while not self._stop.is_set():
                if self._lock_connection is None:
                    try:
                        acquired = await self._acquire_lock()
                    except SQLAlchemyError:
                        await self._wait_before_retry()
                        continue
                    if not acquired:
                        await self._wait_before_retry()
                        continue
                    try:
                        await self._recover_interrupted()
                    except SQLAlchemyError:
                        await self._release_lock()
                        await self._wait_before_retry()
                        continue
                try:
                    task = await self._claim_next()
                except SQLAlchemyError:
                    await self._release_lock()
                    await self._wait_before_retry()
                    continue
                if task is None:
                    await self._wait_before_retry(self._poll_interval)
                    continue
                error_code = "worker_error"
                try:
                    error_code = await self._handler(task)
                except asyncio.CancelledError:
                    raise
                except Exception:  # noqa: BLE001 - isolate one durable job and keep the worker alive
                    error_code = "worker_error"
                while True:
                    try:
                        await self._finish(task.id, error_code)
                        break
                    except SQLAlchemyError:
                        if self._stop.is_set():
                            break
                        await self._wait_before_retry()
        finally:
            await self._release_lock()

    async def _acquire_lock(self) -> bool:
        connection = await self._engine.connect()
        try:
            await connection.execution_options(isolation_level="AUTOCOMMIT")
            acquired = await connection.scalar(
                text("SELECT pg_try_advisory_lock(:lock_key)"),
                {"lock_key": WORKER_LOCK_KEY},
            )
        except SQLAlchemyError:
            await connection.close()
            raise
        if not acquired:
            await connection.close()
            return False
        self._lock_connection = connection
        return True

    async def _release_lock(self) -> None:
        connection = self._lock_connection
        self._lock_connection = None
        if connection is not None:
            try:
                await connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_key)"),
                    {"lock_key": WORKER_LOCK_KEY},
                )
            except SQLAlchemyError:
                pass
            try:
                await connection.close()
            except SQLAlchemyError:
                pass

    async def _wait_before_retry(self, interval: float = 1) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=interval)
        except TimeoutError:
            pass

    async def _claim_next(self) -> PersistedTask | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(TaskRow)
                .where(TaskRow.status == "queued")
                .order_by(TaskRow.created_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if row is None:
                await session.rollback()
                return None
            row.status = "running"
            row.started_at = datetime.now(UTC)
            row.finished_at = None
            row.attempt_count += 1
            await session.commit()
            return PersistedTask(
                row.id, row.project_id, row.kind, dict(row.payload), row.attempt_count
            )

    async def _finish(self, task_id: UUID, error_code: str | None) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(TaskRow)
                .where(TaskRow.id == task_id, TaskRow.status == "running")
                .values(
                    status="failed" if error_code else "succeeded",
                    error_code=error_code,
                    finished_at=datetime.now(UTC),
                )
            )
            await session.commit()
