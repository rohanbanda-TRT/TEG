import pytest
from sqlalchemy import select

from app.store.db import Base, SessionLocal, engine
from app.store.models import ChatMessage, ChatSession, Inquiry, ProposalRow, ResearchDossierRow


@pytest.fixture(autouse=True)
async def _schema():
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)
        await c.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)


async def test_proposal_row_and_attachment():
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
        s.add(ProposalRow(session_id=cs.id, version=1, proposal_json={"company": "Y"},
                          pdf_path="proposals/x/v1.pdf", png_path="proposals/x/v1.png",
                          bytes=12345, guardrail_flags=[]))
        s.add(ChatMessage(session_id=cs.id, turn_index=0, role="agent", content="here",
                          attachment={"kind": "proposal", "version": 1}))
        await s.commit()

        pr = (await s.execute(select(ProposalRow))).scalars().one()
        assert pr.version == 1 and pr.bytes == 12345
        m = (await s.execute(select(ChatMessage))).scalars().one()
        assert m.attachment["kind"] == "proposal"
