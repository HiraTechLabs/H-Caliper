from __future__ import annotations


from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.enums import ProviderType
from app.core.errors import bad_request, conflict, not_found
from app.core.security import encrypt_secret
from app.models.provider import Provider, ProviderModel
from app.models.user import User
from app.schemas import ProviderCreate, ProviderModelOut, ProviderOut, ProviderUpdate
from app.services.audit import audit
from app.services.providers.registry import (
    REGISTRY,
    capability_snapshot,
    check_health,
    sync_models,
)

router = APIRouter(prefix="/providers", tags=["providers"])


def _serialize(provider: Provider) -> ProviderOut:
    return ProviderOut(
        id=provider.id,
        name=provider.name,
        type=provider.type,
        base_url=provider.base_url,
        enabled=provider.enabled,
        status=provider.status,
        capabilities=provider.capabilities or {},
        config=provider.config or {},
        has_api_key=bool(provider.api_key_encrypted),
        last_error=provider.last_error,
        last_checked_at=provider.last_checked_at,
        created_at=provider.created_at,
        models=[ProviderModelOut.model_validate(m) for m in (provider.models or [])],
    )


@router.get("/types")
async def provider_types(_: User = Depends(get_current_user)) -> list[dict]:
    return [
        {
            "type": provider_type,
            "label": provider_type.replace("_", " ").title(),
            "capabilities": await capability_snapshot(provider_type),
            "requires_base_url": provider_type
            in {
                ProviderType.OPENAI_COMPATIBLE.value,
                ProviderType.FREELLMAPI.value,
                ProviderType.LMSTUDIO.value,
                ProviderType.OLLAMA.value,
            },
        }
        for provider_type in REGISTRY
    ]


@router.get("", response_model=list[ProviderOut])
async def list_providers(
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)
) -> list[ProviderOut]:
    providers = (
        (await db.execute(select(Provider).options(selectinload(Provider.models)).order_by(Provider.name))).scalars().all()
    )
    return [_serialize(p) for p in providers]


@router.post("", response_model=ProviderOut, status_code=201)
async def create_provider(
    payload: ProviderCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> ProviderOut:
    if payload.type not in REGISTRY:
        raise bad_request(f"Unknown provider type '{payload.type}'", "unknown_provider_type")
    existing = (
        await db.execute(select(Provider).where(Provider.name == payload.name))
    ).scalar_one_or_none()
    if existing:
        raise conflict("A provider with this name already exists", "provider_name_exists")
    if payload.type in {
        ProviderType.OPENAI_COMPATIBLE.value,
        ProviderType.FREELLMAPI.value,
        ProviderType.LMSTUDIO.value,
        ProviderType.OLLAMA.value,
    } and not payload.base_url:
        raise bad_request("This provider type requires a base URL", "base_url_required")
    provider = Provider(
        name=payload.name,
        type=payload.type,
        base_url=payload.base_url,
        api_key_encrypted=encrypt_secret(payload.api_key),
        enabled=payload.enabled,
        capabilities=await capability_snapshot(payload.type),
        config=payload.config,
    )
    db.add(provider)
    await db.flush()
    await audit(
        db,
        action="provider.create",
        entity_type="provider",
        actor_type="user",
        actor_id=admin.email,
        entity_id=provider.id,
        detail={"name": provider.name, "type": provider.type},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    provider = (
        await db.execute(
            select(Provider).options(selectinload(Provider.models)).where(Provider.id == provider.id)
        )
    ).scalar_one()
    return _serialize(provider)


@router.patch("/{provider_id}", response_model=ProviderOut)
async def update_provider(
    provider_id: str,
    payload: ProviderUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> ProviderOut:
    provider = await db.get(Provider, provider_id)
    if not provider:
        raise not_found("Provider")
    data = payload.model_dump(exclude_unset=True)
    if "api_key" in data:
        provider.api_key_encrypted = encrypt_secret(data.pop("api_key"))
    for key, value in data.items():
        setattr(provider, key, value)
    await audit(
        db,
        action="provider.update",
        entity_type="provider",
        actor_type="user",
        actor_id=admin.email,
        entity_id=provider.id,
        detail={k: v for k, v in data.items()},
    )
    await db.commit()
    provider = (
        await db.execute(
            select(Provider).options(selectinload(Provider.models)).where(Provider.id == provider.id)
        )
    ).scalar_one()
    return _serialize(provider)


@router.delete("/{provider_id}", status_code=204, response_class=Response, response_model=None)
async def delete_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> None:
    provider = await db.get(Provider, provider_id)
    if not provider:
        raise not_found("Provider")
    await db.delete(provider)
    await audit(
        db,
        action="provider.delete",
        entity_type="provider",
        actor_type="user",
        actor_id=admin.email,
        entity_id=provider_id,
        detail={"name": provider.name, "type": provider.type},
    )
    await db.commit()


@router.post("/{provider_id}/test")
async def test_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    provider = await db.get(Provider, provider_id)
    if not provider:
        raise not_found("Provider")
    health = await check_health(db, provider)
    await audit(
        db,
        action="provider.test",
        entity_type="provider",
        actor_type="user",
        actor_id=admin.email,
        entity_id=provider.id,
        detail={"connected": health["connected"], "status": health["status"]},
    )
    await db.commit()
    return health


@router.post("/{provider_id}/sync-models", response_model=list[ProviderModelOut])
async def sync_provider_models(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> list[ProviderModel]:
    provider = await db.get(Provider, provider_id)
    if not provider:
        raise not_found("Provider")
    try:
        models = await sync_models(db, provider)
    except Exception as exc:
        raise bad_request(
            f"Model discovery failed: {exc}", "model_discovery_failed"
        ) from exc
    await audit(
        db,
        action="provider.sync_models",
        entity_type="provider",
        actor_type="user",
        actor_id=admin.email,
        entity_id=provider.id,
        detail={"count": len(models)},
    )
    return models


@router.post("/{provider_id}/models", response_model=ProviderModelOut, status_code=201)
async def add_manual_model(
    provider_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> ProviderModel:
    provider = await db.get(Provider, provider_id)
    if not provider:
        raise not_found("Provider")
    model_id = str(payload.get("model_id", "")).strip()
    if not model_id or len(model_id) > 250:
        raise bad_request("A valid model_id is required", "invalid_model_id")
    existing = (
        await db.execute(
            select(ProviderModel).where(
                ProviderModel.provider_id == provider.id,
                ProviderModel.model_id == model_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.enabled = True
        existing.discovered = False
        model = existing
    else:
        model = ProviderModel(
            provider_id=provider.id,
            model_id=model_id,
            display_name=str(payload.get("display_name", model_id))[:250],
            discovered=False,
            enabled=True,
        )
        db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


@router.patch("/{provider_id}/models/{model_db_id}", response_model=ProviderModelOut)
async def toggle_model(
    provider_id: str,
    model_db_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> ProviderModel:
    model = await db.get(ProviderModel, model_db_id)
    if not model or model.provider_id != provider_id:
        raise not_found("Provider model")
    if "enabled" in payload:
        model.enabled = bool(payload["enabled"])
    await db.commit()
    await db.refresh(model)
    return model
