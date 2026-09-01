from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.api.inquiries import get_orchestrator
from app.orchestrator import Orchestrator
from app.store.db import SessionLocal
from app.store.repositories import ProposalRepo

router = APIRouter()


@router.get("/proposals/{proposal_id}.pdf")
async def get_pdf(proposal_id: uuid.UUID) -> FileResponse:
    async with SessionLocal() as s:
        row = await ProposalRepo(s).get(proposal_id)
    if row is None or not row.pdf_path or not Path(row.pdf_path).is_file():
        raise HTTPException(404)
    fname = f"TEG-2026-Proposal-v{row.version}.pdf"
    return FileResponse(
        row.pdf_path, media_type="application/pdf", filename=fname,
        content_disposition_type="inline",
    )


@router.get("/proposals/{proposal_id}/preview.png")
async def get_png(proposal_id: uuid.UUID) -> FileResponse:
    async with SessionLocal() as s:
        row = await ProposalRepo(s).get(proposal_id)
    if row is None or not row.png_path or not Path(row.png_path).is_file():
        raise HTTPException(404)
    return FileResponse(row.png_path, media_type="image/png")


@router.post("/sessions/{session_id}/proposal", status_code=status.HTTP_202_ACCEPTED)
async def make_proposal(
    session_id: uuid.UUID,
    payload: dict = Body(default={}),
    orch: Orchestrator = Depends(get_orchestrator),
) -> dict:
    card = await orch.generate_proposal(session_id, email=payload.get("email"))
    return card.model_dump()
