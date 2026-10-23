import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from caliper.adapters.postgres.models import AdminCredentialRow, AdminSessionRow
from caliper.application.auth import verify_password

SESSION_LIFETIME = timedelta(hours=12)


async def admin_is_configured(session: AsyncSession) -> bool:
    result = await session.execute(select(AdminCredentialRow.id).where(AdminCredentialRow.id == 1))
    return result.scalar_one_or_none() is not None


async def set_admin_password(session: AsyncSession, encoded_hash: str) -> None:
    now = datetime.now(UTC)
    credential = await session.get(AdminCredentialRow, 1)
    if credential is None:
        session.add(AdminCredentialRow(id=1, password_hash=encoded_hash, updated_at=now))
    else:
        credential.password_hash = encoded_hash
        credential.updated_at = now
    await session.execute(delete(AdminSessionRow))
    await session.commit()


async def authenticate(session: AsyncSession, password: str) -> str | None:
    credential = await session.get(AdminCredentialRow, 1)
    if credential is None or not verify_password(password, credential.password_hash):
        return None
    token = secrets.token_urlsafe(48)
    now = datetime.now(UTC)
    session.add(
        AdminSessionRow(
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            created_at=now,
            expires_at=now + SESSION_LIFETIME,
        )
    )
    await session.commit()
    return token


async def valid_session(session: AsyncSession, token: str | None) -> bool:
    if not token:
        return False
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    result = await session.execute(
        select(AdminSessionRow.token_hash).where(
            AdminSessionRow.token_hash == token_hash,
            AdminSessionRow.expires_at > datetime.now(UTC),
        )
    )
    return result.scalar_one_or_none() is not None


async def revoke_session(session: AsyncSession, token: str | None) -> None:
    if token:
        await session.execute(
            delete(AdminSessionRow).where(
                AdminSessionRow.token_hash == hashlib.sha256(token.encode()).hexdigest()
            )
        )
        await session.commit()
