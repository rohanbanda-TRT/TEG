from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text

from app.jobs.retention import purge_expired
from app.store.db import Base, SessionLocal, engine
from app.store.models import ChatSession, Inquiry, ProposalRow, ResearchDossierRow


@pytest.fixture(autouse=True)
async def _schema():
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)
        await c.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)


async def test_purge_removes_old_proposals_and_files(tmp_path):
    pdf = tmp_path / "old" / "v1.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-old")
    async with SessionLocal() as s:
        inq = Inquiry(person_name="X", company_name_raw="Y", company_name_canonical="Y",
                      consent_status="unknown", intent_hint="exhibitor", source="t")
        s.add(inq); await s.flush()
        d = ResearchDossierRow(inquiry_id=inq.id, company_profile={}, person_profile={},
                               relationship="cold", peer_companies=[], field_confidence={},
                               sources=[], review_flags=[], ask_prospect=[], research_cost={})
        s.add(d); await s.flush()
        cs = ChatSession(inquiry_id=inq.id, dossier_id=d.id, cta_status="none")
        s.add(cs); await s.flush()
        s.add(ProposalRow(session_id=cs.id, version=1, proposal_json={},
                          pdf_path=str(pdf), png_path=str(pdf.with_suffix(".png")), bytes=8,
                          guardrail_flags=[]))
        await s.flush()
        await s.execute(text("UPDATE inquiries SET created_at = :ts WHERE id = :id"),
                        {"ts": datetime.now(timezone.utc) - timedelta(days=400), "id": inq.id})
        await s.commit()

    counts = await purge_expired()
    assert counts["proposals"] >= 1
    assert not pdf.exists()
    async with SessionLocal() as s:
        assert (await s.execute(select(ProposalRow))).scalars().first() is None
