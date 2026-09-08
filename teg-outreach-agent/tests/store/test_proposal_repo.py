import pytest
from sqlalchemy import select

from app.domain.schemas import Proposal, ProposalPackage, ProposalPain
from app.store.db import Base, SessionLocal, engine
from app.store.models import ChatMessage, ChatSession, Inquiry, ResearchDossierRow
from app.store.repositories import MessageRepo, ProposalRepo


@pytest.fixture(autouse=True)
async def _schema():
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)
        await c.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)


def _proposal():
    return Proposal(
        company="Y", person="X", persona="it_tech_service", generated_on="2026-09-01",
        session_ref="r", version=1, what_you_told_us="w",
        pains=[ProposalPain(pain="a", teg_answer="b")], lead_generation="l", proof=["p"],
        recommended_package=ProposalPackage(name="n", price_line="₹1 + GST", includes=[], payment_plan="x"),
        peer_companies=[], next_steps=["s"], contact="c",
    )


async def _seed(s):
    inq = Inquiry(person_name="X", company_name_raw="Y", company_name_canonical="Y",
                  consent_status="unknown", intent_hint="exhibitor", source="t")
    s.add(inq); await s.flush()
    d = ResearchDossierRow(inquiry_id=inq.id, company_profile={}, person_profile={},
                           relationship="cold", peer_companies=[], field_confidence={},
                           sources=[], review_flags=[], ask_prospect=[], research_cost={})
    s.add(d); await s.flush()
    cs = ChatSession(inquiry_id=inq.id, dossier_id=d.id, cta_status="none")
    s.add(cs); await s.flush()
    return cs


async def test_proposal_repo_versioning_and_attachment():
    async with SessionLocal() as s:
        cs = await _seed(s)
        pr = ProposalRepo(s)
        assert await pr.next_version(cs.id) == 1
        row1 = await pr.create(cs.id, proposal=_proposal(), version=1,
                               pdf_path="a/v1.pdf", png_path="a/v1.png", bytes_=10,
                               guardrail_flags=[])
        await s.flush()
        assert await pr.next_version(cs.id) == 2
        await MessageRepo(s).append(cs.id, "agent", "here", turn_index=0,
                                    attachment={"kind": "proposal", "proposal_id": str(row1.id)})
        await s.commit()

        rows = await ProposalRepo(s).list_for_session(cs.id)
        assert [r.version for r in rows] == [1]
        m = (await s.execute(select(ChatMessage))).scalars().one()
        assert m.attachment["kind"] == "proposal"
        got = await ProposalRepo(s).get(row1.id)
        assert got.pdf_path == "a/v1.pdf"
