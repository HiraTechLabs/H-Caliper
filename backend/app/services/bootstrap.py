"""Initial administrator provisioning.

No password is hardcoded.  If BOOTSTRAP_ADMIN_EMAIL is set and the database has
no users, a random password is generated and printed exactly once to the server
log.  The /auth/bootstrap endpoint is the normal first-run path.
"""

from __future__ import annotations

import logging
import secrets

from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.enums import Role
from app.core.security import hash_password
from app.models.user import User
from app.services.audit import audit

logger = logging.getLogger(__name__)


async def ensure_bootstrap_admin() -> None:
    if not settings.BOOTSTRAP_ADMIN_EMAIL:
        return
    async with SessionLocal() as db:
        count = (await db.execute(select(func.count(User.id)))).scalar_one()
        if count:
            return
        password = secrets.token_urlsafe(24)
        user = User(
            email=settings.BOOTSTRAP_ADMIN_EMAIL.lower(),
            password_hash=hash_password(password),
            full_name="Initial Administrator",
            role=Role.ADMIN.value,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        await audit(
            db,
            action="auth.bootstrap",
            entity_type="user",
            actor_type="system",
            actor_id="startup",
            entity_id=user.id,
            detail={"email": user.email, "method": "env_bootstrap"},
        )
        await db.commit()
        # Printed once; not stored in the database or returned by any endpoint.
        logger.warning(
            "BOOTSTRAP ADMIN CREATED\n  email: %s\n  password: %s\nChange this password after login.",
            user.email,
            password,
        )
