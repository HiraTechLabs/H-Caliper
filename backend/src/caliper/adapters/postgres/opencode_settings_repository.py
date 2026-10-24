from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliper.adapters.postgres.models import OpenCodeSettingsRow


@dataclass(frozen=True)
class OpenCodeSettings:
    auth_secret_ref: UUID | None
    selected_provider_id: str | None
    selected_model_id: str | None
    status: str
    checked_at: datetime | None
    error_code: str | None
    updated_at: datetime


class SqlOpenCodeSettingsRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self) -> OpenCodeSettings:
        row = await self._session.get(OpenCodeSettingsRow, 1)
        if row is None:
            result = OpenCodeSettings(
                None, None, None, "not_configured", None, None, datetime.now(UTC)
            )
        else:
            result = self._from_row(row)
        await self._session.rollback()
        return result

    async def save_profile(self, secret_ref: UUID | None) -> OpenCodeSettings:
        row = await self._row()
        row.auth_secret_ref = secret_ref
        row.status = "configured" if secret_ref else "not_configured"
        row.error_code = None
        row.updated_at = datetime.now(UTC)
        await self._commit()
        return await self.get()

    async def record_status(self, status: str, error_code: str | None) -> OpenCodeSettings:
        row = await self._row()
        row.status = status
        row.error_code = error_code
        row.checked_at = datetime.now(UTC)
        row.updated_at = row.checked_at
        await self._commit()
        return await self.get()

    async def select_model(self, provider_id: str, model_id: str) -> OpenCodeSettings:
        row = await self._row()
        row.selected_provider_id = provider_id
        row.selected_model_id = model_id
        row.updated_at = datetime.now(UTC)
        await self._commit()
        return await self.get()

    async def clear_selection(self) -> OpenCodeSettings:
        row = await self._row()
        row.selected_provider_id = None
        row.selected_model_id = None
        row.updated_at = datetime.now(UTC)
        await self._commit()
        return await self.get()

    async def _row(self) -> OpenCodeSettingsRow:
        row = await self._session.get(OpenCodeSettingsRow, 1)
        if row is None:
            row = OpenCodeSettingsRow(
                id=1,
                auth_secret_ref=None,
                selected_provider_id=None,
                selected_model_id=None,
                status="not_configured",
                checked_at=None,
                error_code=None,
                updated_at=datetime.now(UTC),
            )
            self._session.add(row)
            await self._session.flush()
        return row

    async def _commit(self) -> None:
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

    @staticmethod
    def _from_row(row: OpenCodeSettingsRow) -> OpenCodeSettings:
        return OpenCodeSettings(
            row.auth_secret_ref,
            row.selected_provider_id,
            row.selected_model_id,
            row.status,
            row.checked_at,
            row.error_code,
            row.updated_at,
        )
