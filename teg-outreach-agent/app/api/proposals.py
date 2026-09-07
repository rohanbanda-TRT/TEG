from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app.api.inquiries import get_orchestrator
from app.orchestrator import Orchestrator
from app.store.db import SessionLocal
from app.store.repositories import ProposalRepo

router = APIRouter()

_SPA_INDEX = Path(__file__).resolve().parents[2] / "app" / "static" / "proposal" / "index.html"


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


@router.get("/proposals/{proposal_id}.json")
async def get_proposal_json(proposal_id: uuid.UUID) -> JSONResponse:
    async with SessionLocal() as s:
        row = await ProposalRepo(s).get(proposal_id)
    if row is None:
        raise HTTPException(status_code=404, detail="not found")
    return JSONResponse({
        "id": str(row.id),
        "version": row.version,
        "generated_on": row.proposal_json.get("generated_on"),
        # unset unless this proposal predates the link-only delivery path
        "pdf_url": f"/proposals/{row.id}.pdf" if row.pdf_path else None,
        "proposal": row.proposal_json,
    })


@router.get("/p/{proposal_id}")
async def get_proposal_page(proposal_id: uuid.UUID) -> HTMLResponse:
    if not _SPA_INDEX.is_file():
        raise HTTPException(status_code=503, detail="proposal page not built")
    return HTMLResponse(_SPA_INDEX.read_text("utf-8"))


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
