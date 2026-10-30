from __future__ import annotations


from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    get_current_user,
    get_owned_project,
    require_admin,
    require_operator,
)
from app.core.errors import not_found
from app.models.caliper import CaliperDocument, CaliperProposal, CaliperVersion
from app.models.project import Project
from app.models.user import User
from app.schemas import (
    CaliperDocumentDetail,
    CaliperDocumentOut,
    CaliperProposalCreate,
    CaliperProposalOut,
    CaliperSlotCreate,
    CaliperUpdate,
    ProposalDecision,
)
from app.services import caliper_service
from app.services.audit import audit

router = APIRouter(tags=["caliper"])


@router.get("/projects/{project_id}/caliper", response_model=list[CaliperDocumentOut])
async def list_caliper(
    project: Project = Depends(get_owned_project),
    db: AsyncSession = Depends(get_db),
) -> list[CaliperDocument]:
    return await caliper_service.list_documents(db, project.id)


@router.get("/caliper/{document_id}", response_model=CaliperDocumentDetail)
async def get_caliper_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CaliperDocumentDetail:
    doc = await db.get(CaliperDocument, document_id)
    if not doc:
        raise not_found("CALIPER document")
    await get_owned_project(doc.project_id, user, db, write=False)
    content = await caliper_service.current_content(db, doc)
    versions = await caliper_service.versions(db, doc)
    return CaliperDocumentDetail(
        **CaliperDocumentOut.model_validate(doc).model_dump(),
        content=content,
        versions=[
            {
                "id": v.id,
                "version": v.version,
                "change_summary": v.change_summary,
                "reason": v.reason,
                "author": v.author,
                "status": v.status,
                "approved_by": v.approved_by,
                "created_at": v.created_at,
            }
            for v in versions
        ],
    )


@router.get("/caliper/{document_id}/versions/{version}")
async def get_caliper_version(
    document_id: str,
    version: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    doc = await db.get(CaliperDocument, document_id)
    if not doc:
        raise not_found("CALIPER document")
    await get_owned_project(doc.project_id, user, db, write=False)
    row = (
        await db.execute(
            select(CaliperVersion).where(
                CaliperVersion.document_id == document_id,
                CaliperVersion.version == version,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise not_found("CALIPER version")
    return {
        "version": row.version,
        "content": row.content,
        "change_summary": row.change_summary,
        "reason": row.reason,
        "author": row.author,
        "status": row.status,
        "created_at": row.created_at,
    }


@router.patch("/caliper/{document_id}", response_model=CaliperDocumentOut)
async def update_caliper(
    document_id: str,
    payload: CaliperUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_operator),
) -> CaliperDocument:
    doc = await db.get(CaliperDocument, document_id)
    if not doc:
        raise not_found("CALIPER document")
    await get_owned_project(doc.project_id, user, db, write=True)
    await caliper_service.update_document(
        db,
        doc,
        content=payload.content,
        change_summary=payload.change_summary,
        reason=payload.reason,
        author=user.email,
        role=user.role,
    )
    await audit(
        db,
        action="caliper.update",
        entity_type="caliper_document",
        actor_type="user",
        actor_id=user.email,
        entity_id=doc.id,
        detail={"slug": doc.slug, "summary": payload.change_summary},
    )
    await db.commit()
    await db.refresh(doc)
    return doc


@router.post("/caliper/{document_id}/proposals", response_model=CaliperProposalOut, status_code=201)
async def propose_caliper_change(
    document_id: str,
    payload: CaliperProposalCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_operator),
) -> CaliperProposal:
    doc = await db.get(CaliperDocument, document_id)
    if not doc:
        raise not_found("CALIPER document")
    await get_owned_project(doc.project_id, user, db, write=True)
    proposal = await caliper_service.create_proposal(
        db,
        doc,
        content=payload.content,
        change_summary=payload.change_summary,
        reason=payload.reason,
        author=user.email,
        task_id=payload.task_id,
    )
    await audit(
        db,
        action="caliper.propose",
        entity_type="caliper_proposal",
        actor_type="user",
        actor_id=user.email,
        entity_id=proposal.id,
        detail={"document": doc.slug, "summary": payload.change_summary},
    )
    await db.commit()
    await db.refresh(proposal)
    return proposal


@router.get("/projects/{project_id}/caliper/proposals", response_model=list[CaliperProposalOut])
async def list_proposals(
    project: Project = Depends(get_owned_project),
    db: AsyncSession = Depends(get_db),
    pending_only: bool = Query(default=False),
) -> list[CaliperProposal]:
    query = (
        select(CaliperProposal)
        .join(CaliperDocument, CaliperDocument.id == CaliperProposal.document_id)
        .where(CaliperDocument.project_id == project.id)
        .order_by(CaliperProposal.created_at.desc())
    )
    if pending_only:
        query = query.where(CaliperProposal.status == "PENDING")
    return list((await db.execute(query)).scalars().all())


@router.post("/caliper/proposals/{proposal_id}/decision", response_model=CaliperProposalOut)
async def decide_proposal(
    proposal_id: str,
    payload: ProposalDecision,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> CaliperProposal:
    proposal = await db.get(CaliperProposal, proposal_id)
    if not proposal:
        raise not_found("CALIPER proposal")
    doc = await db.get(CaliperDocument, proposal.document_id)
    await get_owned_project(doc.project_id, admin, db, write=True)
    await caliper_service.decide_proposal(
        db,
        proposal,
        approve=payload.approve,
        reviewer=admin.email,
        notes=payload.notes,
    )
    await audit(
        db,
        action="caliper.proposal_decision",
        entity_type="caliper_proposal",
        actor_type="user",
        actor_id=admin.email,
        entity_id=proposal.id,
        detail={"approve": payload.approve, "document": doc.slug},
    )
    await db.commit()
    await db.refresh(proposal)
    return proposal


@router.post("/projects/{project_id}/caliper/slot", response_model=CaliperDocumentOut, status_code=201)
async def create_slot(
    payload: CaliperSlotCreate,
    project: Project = Depends(get_owned_project),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> CaliperDocument:
    doc = await caliper_service.create_reserved_slot(
        db,
        project,
        slug=payload.slug,
        title=payload.title,
        content=payload.content,
        author=admin.email,
    )
    await audit(
        db,
        action="caliper.create_slot",
        entity_type="caliper_document",
        actor_type="user",
        actor_id=admin.email,
        entity_id=doc.id,
        detail={"slug": doc.slug},
    )
    await db.commit()
    await db.refresh(doc)
    return doc
