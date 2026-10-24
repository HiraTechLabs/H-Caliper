from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from caliper.adapters.postgres.models import OllamaSettingsRow
from caliper.application.ollama_provider import (
    OllamaConfigurationChanged,
    OllamaModelNotAvailable,
    OllamaSettings,
)


class SqlOllamaSettingsRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self) -> OllamaSettings:
        row = await self._session.get(OllamaSettingsRow, 1)
        if row is None:
            settings = OllamaSettings("", None, "not_configured", None, None, [])
        else:
            settings = self._as_settings(row)
        await self._session.rollback()
        return settings

    async def configure(self, endpoint_url: str) -> OllamaSettings:
        row = await self._session.get(OllamaSettingsRow, 1)
        now = datetime.now(UTC)
        if row is None:
            row = OllamaSettingsRow(
                id=1,
                endpoint_url=endpoint_url,
                selected_model_id=None,
                status="configured",
                models=[],
                checked_at=None,
                error_code=None,
                updated_at=now,
            )
            self._session.add(row)
        else:
            if row.endpoint_url != endpoint_url:
                row.selected_model_id = None
                row.models = []
                row.checked_at = None
            row.endpoint_url = endpoint_url
            row.status = "configured"
            row.error_code = None
            row.updated_at = now
        await self._commit()
        return await self.get()

    async def save_discovery(
        self,
        expected_endpoint: str,
        status: str,
        models: list[str],
        error_code: str | None,
        checked_at: datetime,
    ) -> OllamaSettings:
        row = await self._session.scalar(
            select(OllamaSettingsRow)
            .where(OllamaSettingsRow.id == 1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise ValueError("Ollama endpoint configuration disappeared")
        if row.endpoint_url != expected_endpoint:
            await self._session.rollback()
            raise OllamaConfigurationChanged("Ollama endpoint changed during validation")
        row.status = status
        row.models = models
        row.checked_at = checked_at
        row.error_code = error_code
        if row.selected_model_id not in models:
            row.selected_model_id = None
        row.updated_at = checked_at
        await self._commit()
        return await self.get()

    async def select_model(self, model_id: str) -> OllamaSettings:
        row = await self._session.get(OllamaSettingsRow, 1)
        if row is None or row.status != "reachable" or model_id not in row.models:
            raise OllamaModelNotAvailable(model_id)
        row.selected_model_id = model_id
        row.updated_at = datetime.now(UTC)
        await self._commit()
        return await self.get()

    async def _commit(self) -> None:
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

    @staticmethod
    def _as_settings(row: OllamaSettingsRow) -> OllamaSettings:
        return OllamaSettings(
            row.endpoint_url,
            row.selected_model_id,
            row.status,
            row.checked_at,
            row.error_code,
            list(row.models),
        )
