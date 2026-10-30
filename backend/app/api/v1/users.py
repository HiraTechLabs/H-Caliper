from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.core.errors import conflict, not_found
from app.core.security import hash_password
from app.models.user import ProjectMember, User
from app.schemas import UserCreate, UserOut, UserUpdate
from app.services.audit import audit

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)
) -> list[User]:
    rows = await db.execute(select(User).order_by(User.created_at))
    return list(rows.scalars().all())


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    payload: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> User:
    existing = (
        await db.execute(select(User).where(User.email == payload.email.lower()))
    ).scalar_one_or_none()
    if existing:
        raise conflict("A user with this email already exists", "email_exists")
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role.value,
    )
    db.add(user)
    await db.flush()
    await audit(
        db,
        action="user.create",
        entity_type="user",
        actor_type="user",
        actor_id=admin.email,
        entity_id=user.id,
        detail={"email": user.email, "role": user.role},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> User:
    user = await db.get(User, user_id)
    if not user:
        raise not_found("User")
    data = payload.model_dump(exclude_unset=True)
    if "password" in data:
        user.password_hash = hash_password(data.pop("password"))
    if "role" in data and data["role"] is not None:
        data["role"] = data["role"].value
    for key, value in data.items():
        setattr(user, key, value)
    await audit(
        db,
        action="user.update",
        entity_type="user",
        actor_type="user",
        actor_id=admin.email,
        entity_id=user.id,
        detail={k: v for k, v in data.items() if k != "password"},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204, response_class=Response, response_model=None)
async def deactivate_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> None:
    user = await db.get(User, user_id)
    if not user:
        raise not_found("User")
    if user.id == admin.id:
        raise conflict("You cannot deactivate your own account", "self_deactivate")
    user.is_active = False
    await db.execute(
        ProjectMember.__table__.delete().where(ProjectMember.user_id == user.id)
    )
    await audit(
        db,
        action="user.deactivate",
        entity_type="user",
        actor_type="user",
        actor_id=admin.email,
        entity_id=user.id,
    )
    await db.commit()
