from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from caliper.adapters.postgres.database import SessionLocal
from caliper.adapters.postgres.repository_sync_repository import SqlRepositorySyncRepository
from caliper.adapters.postgres.task_runner import PersistedTask
from caliper.adapters.repository_sync_factory import build_repository_sync
from caliper.application.repository_sync import RepositorySyncFailed


async def handle_persisted_task(task: PersistedTask) -> str | None:
    if task.kind != "repository_sync":
        return "unsupported_task"
    credential_value = task.payload.get("credential_id")
    try:
        credential_id = UUID(credential_value) if credential_value else None
    except (ValueError, TypeError):
        credential_id = None
        payload_error = True
    else:
        payload_error = False

    async with SessionLocal() as session:
        repository = SqlRepositorySyncRepository(session)
        if payload_error:
            try:
                await repository.fail(task.project_id, "invalid_task_payload", _utc_now())
            except (SQLAlchemyError, RuntimeError):
                await session.rollback()
            return "invalid_task_payload"
        sync = build_repository_sync(session)
        try:
            await sync.sync(task.project_id, credential_id)
        except RepositorySyncFailed as error:
            return error.state.error_code or "repository_sync_failed"
        except Exception:  # noqa: BLE001 - convert unexpected job errors to a non-sensitive state code
            try:
                await repository.fail(task.project_id, "worker_error", _utc_now())
            except (SQLAlchemyError, RuntimeError):
                await session.rollback()
            return "worker_error"
    return None


def _utc_now():
    return datetime.now(UTC)
