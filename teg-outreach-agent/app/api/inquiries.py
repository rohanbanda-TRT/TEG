from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.domain.schemas import IntakePayload
from app.orchestrator import Orchestrator
from app.store.db import SessionLocal
from app.store.repositories import InquiryRepo

router = APIRouter()
_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator


@router.post("/inquiries", status_code=status.HTTP_202_ACCEPTED)
async def create_inquiry(
    payload: IntakePayload, orch: Orchestrator = Depends(get_orchestrator)
) -> dict:
    result = await orch.run_pipeline(payload)
    return {
        "session_id": str(result.session_id),
        "opening_message": result.opening_message,
        "persona": result.persona,
    }


@router.get("/inquiries/{inquiry_id}")
async def get_inquiry(inquiry_id: uuid.UUID) -> dict:
    async with SessionLocal() as s:
        row = await InquiryRepo(s).get(inquiry_id)
        if row is None:
            raise HTTPException(404)
        return {
            "id": str(row.id), "person_name": row.person_name,
            "company_name_canonical": row.company_name_canonical,
            "intent_hint": row.intent_hint, "consent_status": row.consent_status,
        }
