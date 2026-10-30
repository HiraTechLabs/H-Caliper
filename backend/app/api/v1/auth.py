from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import (
    AUTH_COOKIE,
    CSRF_COOKIE,
    get_current_user,
)
from app.core.enums import Role
from app.core.errors import conflict, unauthorized
from app.core.security import (
    create_access_token,
    hash_password,
    new_csrf_token,
    verify_password,
)
from app.models.user import User
from app.schemas import BootstrapRequest, LoginRequest, MeOut, UserOut
from app.services.audit import audit

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session(response: Response, user: User) -> str:
    token = create_access_token(user.id, user.role)
    csrf = new_csrf_token()
    max_age = settings.ACCESS_TOKEN_MINUTES * 60
    response.set_cookie(
        AUTH_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=max_age,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )
    return csrf


def _clear_session(response: Response) -> None:
    response.delete_cookie(AUTH_COOKIE, path="/", domain=settings.COOKIE_DOMAIN)
    response.delete_cookie(CSRF_COOKIE, path="/", domain=settings.COOKIE_DOMAIN)


@router.get("/bootstrap-status")
async def bootstrap_status(db: AsyncSession = Depends(get_db)) -> dict:
    count = (await db.execute(select(func.count(User.id)))).scalar_one()
    return {
        "bootstrap_required": count == 0,
        "app_name": settings.APP_NAME,
        "environment": settings.ENV,
    }


@router.post("/bootstrap", response_model=MeOut)
async def bootstrap(
    payload: BootstrapRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> MeOut:
    count = (await db.execute(select(func.count(User.id)))).scalar_one()
    if count > 0:
        raise conflict("System is already initialised", "already_initialised")
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=Role.ADMIN.value,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await audit(
        db,
        action="auth.bootstrap",
        entity_type="user",
        actor_type="user",
        actor_id=user.email,
        entity_id=user.id,
        detail={"email": user.email},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    csrf = _set_session(response, user)
    return MeOut(user=UserOut.model_validate(user), csrf_token=csrf)


@router.post("/login", response_model=MeOut)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> MeOut:
    user = (
        await db.execute(select(User).where(User.email == payload.email.lower()))
    ).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise unauthorized("Invalid email or password")
    if not user.is_active:
        raise unauthorized("Account is disabled")
    user.last_login_at = datetime.now(timezone.utc)
    await audit(
        db,
        action="auth.login",
        entity_type="user",
        actor_type="user",
        actor_id=user.email,
        entity_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    csrf = _set_session(response, user)
    return MeOut(user=UserOut.model_validate(user), csrf_token=csrf)


@router.post("/logout")
async def logout(response: Response, request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    _clear_session(response)
    token = request.cookies.get(AUTH_COOKIE)
    if token:
        from app.core.security import decode_access_token

        try:
            payload = decode_access_token(token)
            await audit(
                db,
                action="auth.logout",
                entity_type="user",
                actor_type="user",
                actor_id=payload.get("sub"),
                ip_address=request.client.host if request.client else None,
            )
            await db.commit()
        except Exception:
            pass
    return {"ok": True}


@router.get("/me", response_model=MeOut)
async def me(
    request: Request,
    user: User = Depends(get_current_user),
) -> MeOut:
    return MeOut(user=UserOut.model_validate(user), csrf_token=request.cookies.get(CSRF_COOKIE))
