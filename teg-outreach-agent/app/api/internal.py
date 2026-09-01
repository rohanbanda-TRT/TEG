from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.store.db import SessionLocal
from app.store.repositories import (
    DossierRepo,
    HandoffRepo,
    MessageRepo,
    ProposalRepo,
    SessionRepo,
)

router = APIRouter()


@router.get("/sessions/{session_id}")
async def get_session(session_id: uuid.UUID) -> dict:
    async with SessionLocal() as s:
        cs = await SessionRepo(s).get(session_id)
        if cs is None:
            raise HTTPException(404)
        drow = await DossierRepo(s).get(cs.dossier_id)
        transcript = await MessageRepo(s).history(session_id)
        h = await HandoffRepo(s).get_by_session(session_id)
        prows = await ProposalRepo(s).list_for_session(session_id)
        return {
            "session": {
                "id": str(cs.id), "persona": cs.persona, "target_cta": cs.target_cta,
                "cta_status": cs.cta_status, "outcome_status": cs.outcome_status,
                "needs_review": cs.needs_review, "learned_facts": cs.learned_facts,
            },
            "dossier": {
                "company_profile": drow.company_profile, "person_profile": drow.person_profile,
                "relationship": drow.relationship, "sector": drow.sector,
                "peer_companies": drow.peer_companies, "review_flags": drow.review_flags,
                "ask_prospect": drow.ask_prospect,
            },
            "transcript": transcript,
            "handoff": None if h is None else {
                "summary": h.summary, "recommended_next_step": h.recommended_next_step,
                "suggested_followup_message": h.suggested_followup_message,
                "prospect_confidence": h.prospect_confidence, "key_facts": h.key_facts,
            },
            "proposals": [
                {
                    "version": p.version,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "pdf_url": f"/proposals/{p.id}.pdf",
                    "png_url": f"/proposals/{p.id}/preview.png",
                    "guardrail_flags": p.guardrail_flags or [],
                    "emailed_to": p.emailed_to,
                }
                for p in prows
            ],
        }
