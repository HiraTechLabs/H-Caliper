"""CALIPER governance: seeding, versioning, proposals, rendering and context."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Role
from app.core.errors import bad_request, conflict, forbidden, not_found
from app.models.caliper import CaliperDocument, CaliperProposal, CaliperVersion
from app.models.project import Project
from app.services.caliper_templates import CALIPER_DOCUMENTS, RESERVED_SLOT

MAX_PRINCIPLE_CHARS = 12_000


async def seed_project_caliper(
    db: AsyncSession, project_id: str, *, author: str = "system"
) -> List[CaliperDocument]:
    existing = await db.execute(
        select(CaliperDocument.slug).where(CaliperDocument.project_id == project_id)
    )
    present = set(existing.scalars().all())
    created: List[CaliperDocument] = []
    for index, template in enumerate(CALIPER_DOCUMENTS, start=1):
        if template["slug"] in present:
            continue
        doc = CaliperDocument(
            project_id=project_id,
            slug=template["slug"],
            title=template["title"],
            slot=index,
            is_protected=True,
            is_active=True,
            current_version=1,
        )
        db.add(doc)
        await db.flush()
        db.add(
            CaliperVersion(
                document_id=doc.id,
                version=1,
                content=template["content"],
                change_summary="Initial constitutional version",
                reason="Seeded from the H-Caliper CALIPER template",
                author=author,
                status="APPROVED",
                approved_by=author,
                approved_at=datetime.now(timezone.utc),
            )
        )
        created.append(doc)
    await db.flush()
    return created


async def list_documents(db: AsyncSession, project_id: str) -> List[CaliperDocument]:
    rows = await db.execute(
        select(CaliperDocument)
        .where(CaliperDocument.project_id == project_id)
        .order_by(CaliperDocument.slot, CaliperDocument.slug)
    )
    return list(rows.scalars().all())


async def get_document(db: AsyncSession, project_id: str, document_id: str) -> CaliperDocument:
    doc = await db.get(CaliperDocument, document_id)
    if not doc or doc.project_id != project_id:
        raise not_found("CALIPER document")
    return doc


async def current_content(db: AsyncSession, doc: CaliperDocument) -> str:
    row = await db.execute(
        select(CaliperVersion)
        .where(
            CaliperVersion.document_id == doc.id,
            CaliperVersion.version == doc.current_version,
        )
        .limit(1)
    )
    version = row.scalar_one_or_none()
    if not version:
        raise conflict("CALIPER document has no current version", "caliper_version_missing")
    return version.content


async def versions(db: AsyncSession, doc: CaliperDocument) -> List[CaliperVersion]:
    rows = await db.execute(
        select(CaliperVersion)
        .where(CaliperVersion.document_id == doc.id)
        .order_by(CaliperVersion.version.desc())
    )
    return list(rows.scalars().all())


async def _new_version(
    db: AsyncSession,
    doc: CaliperDocument,
    *,
    content: str,
    change_summary: str,
    reason: str,
    author: str,
    approved_by: Optional[str],
    task_id: Optional[str] = None,
) -> CaliperVersion:
    next_version = doc.current_version + 1
    version = CaliperVersion(
        document_id=doc.id,
        version=next_version,
        content=content,
        change_summary=change_summary,
        reason=reason,
        author=author,
        status="APPROVED" if approved_by else "PENDING",
        approved_by=approved_by,
        approved_at=datetime.now(timezone.utc) if approved_by else None,
        related_task_id=task_id,
    )
    db.add(version)
    doc.current_version = next_version
    await db.flush()
    return version


async def update_document(
    db: AsyncSession,
    doc: CaliperDocument,
    *,
    content: str,
    change_summary: str,
    reason: str,
    author: str,
    role: str,
) -> CaliperVersion:
    if not content.strip():
        raise bad_request("Content must not be empty", "empty_caliper_content")
    if doc.is_protected and role != Role.ADMIN.value:
        raise forbidden(
            "Protected principles can only be changed by an administrator; submit a proposal instead",
            "caliper_approval_required",
        )
    return await _new_version(
        db,
        doc,
        content=content,
        change_summary=change_summary,
        reason=reason,
        author=author,
        approved_by=author if role == Role.ADMIN.value else None,
    )


async def create_proposal(
    db: AsyncSession,
    doc: CaliperDocument,
    *,
    content: str,
    change_summary: str,
    reason: str,
    author: str,
    task_id: Optional[str] = None,
) -> CaliperProposal:
    pending = await db.execute(
        select(CaliperProposal).where(
            CaliperProposal.document_id == doc.id,
            CaliperProposal.status == "PENDING",
        )
    )
    if pending.scalars().first():
        raise conflict(
            "A pending proposal already exists for this principle",
            "proposal_already_pending",
        )
    proposal = CaliperProposal(
        document_id=doc.id,
        base_version=doc.current_version,
        proposed_content=content,
        change_summary=change_summary,
        reason=reason,
        related_task_id=task_id,
        author=author,
        status="PENDING",
    )
    db.add(proposal)
    await db.flush()
    return proposal


async def decide_proposal(
    db: AsyncSession,
    proposal: CaliperProposal,
    *,
    approve: bool,
    reviewer: str,
    notes: str,
) -> CaliperVersion | None:
    if proposal.status != "PENDING":
        raise conflict("Proposal has already been decided", "proposal_already_decided")
    proposal.status = "APPROVED" if approve else "REJECTED"
    proposal.reviewed_by = reviewer
    proposal.reviewed_at = datetime.now(timezone.utc)
    proposal.review_notes = notes
    if not approve:
        await db.flush()
        return None
    doc = await db.get(CaliperDocument, proposal.document_id)
    if not doc:
        raise not_found("CALIPER document")
    if doc.current_version != proposal.base_version:
        proposal.status = "REJECTED"
        proposal.review_notes = (
            (notes + "\n" if notes else "")
            + "Proposal is stale: the document changed after the proposal was created."
        )
        await db.flush()
        raise conflict(
            "Proposal is stale because the document changed; reject and resubmit",
            "proposal_stale",
        )
    return await _new_version(
        db,
        doc,
        content=proposal.proposed_content,
        change_summary=proposal.change_summary,
        reason=proposal.reason,
        author=proposal.author,
        approved_by=reviewer,
        task_id=proposal.related_task_id,
    )


async def create_reserved_slot(
    db: AsyncSession,
    project: Project,
    *,
    slug: str,
    title: str,
    content: str,
    author: str,
) -> CaliperDocument:
    existing = await db.execute(
        select(CaliperDocument).where(
            CaliperDocument.project_id == project.id,
            CaliperDocument.slot == RESERVED_SLOT["slot"],
        )
    )
    if existing.scalars().first():
        raise conflict("The reserved thirteenth slot is already defined", "slot_already_used")
    doc = CaliperDocument(
        project_id=project.id,
        slug=slug,
        title=title,
        slot=RESERVED_SLOT["slot"],
        is_protected=True,
        is_active=True,
        current_version=1,
    )
    db.add(doc)
    await db.flush()
    db.add(
        CaliperVersion(
            document_id=doc.id,
            version=1,
            content=content,
            change_summary="Administrator defined the reserved thirteenth principle",
            reason="Reserved slot activated",
            author=author,
            status="APPROVED",
            approved_by=author,
            approved_at=datetime.now(timezone.utc),
        )
    )
    await db.flush()
    return doc


async def render_workspace(project: Project, root: str, docs: Sequence[CaliperDocument], contents: Dict[str, str]) -> None:
    caliper_dir = os.path.join(root, "CALIPER")
    os.makedirs(caliper_dir, exist_ok=True)
    manifest_lines = [f"# CALIPER manifest for {project.name}", ""]
    for doc in docs:
        if not doc.is_active:
            continue
        filename = f"{doc.slug}.md"
        content = contents.get(doc.id, "")
        with open(os.path.join(caliper_dir, filename), "w", encoding="utf-8") as handle:
            handle.write(content)
        manifest_lines.append(
            f"- `{filename}` — {doc.title} (v{doc.current_version}, slot {doc.slot})"
        )
    with open(os.path.join(caliper_dir, "manifest.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(manifest_lines) + "\n")


async def load_context(
    db: AsyncSession, project_id: str, *, max_chars: int = 40_000
) -> str:
    docs = await list_documents(db, project_id)
    parts: List[str] = []
    used = 0
    for doc in docs:
        if not doc.is_active:
            continue
        content = await current_content(db, doc)
        section = f"\n\n===== {doc.slug}.md — {doc.title} =====\n{content}"
        if used + len(section) > max_chars:
            parts.append(
                f"\n\n===== {doc.slug}.md — {doc.title} =====\n[Truncated: context budget reached]"
            )
            break
        parts.append(section)
        used += len(section)
    return "".join(parts)
