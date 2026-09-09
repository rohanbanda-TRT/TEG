import pytest
from sqlalchemy import select

from app.agents.analysis import AnalysisAgent, _CanonResult
from app.agents.persuasion import PersuasionAgent, _PersonaChoice
from app.agents.proposal import ProposalAgent
from app.agents.research import ResearchAgent, _Synthesis
from app.domain.schemas import IntakePayload, Proposal, ProposalPackage, ProposalPain
from app.llm.fake import FakeLLMClient
from app.orchestrator import Orchestrator
from app.research.deep import DeepFindings
from app.research.tools import ResearchResult, ResearchTool
from app.store.db import Base, SessionLocal, engine
from app.store.models import ChatMessage, ProposalRow
from app.store.repositories import CompanyBriefRepo
from tests.conftest import StubExplorer


@pytest.fixture(autouse=True)
async def _schema():
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)
        await c.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)


class _DeadWeb(ResearchTool):
    name = "web"
    async def lookup(self, q):
        return ResearchResult(available=False, tool_name="web")


def _good_proposal():
    return Proposal(
        company="Third Rock Techkno", person="Tapan Patel", person_role="CMO",
        sector="Software Development", persona="it_tech_service",
        generated_on="__DATE__", session_ref="x", version=0,
        what_you_told_us="You are an AI + software consulting firm exploring TEG.",
        pains=[ProposalPain(pain="Revenue concentrated in US clients",
                            teg_answer="15,000+ India-market decision-makers plus B2B meetings")],
        lead_generation="Pre-scheduled B2B meetings with India-market buyers plus a live demo space.",
        proof=["TEG 2024 drew 8,000+ attendees and 125+ exhibitors."],
        recommended_package=ProposalPackage(
            name="3m x 3m stall", price_line="₹1,17,000 + GST (indicative, confirmed at booking)",
            includes=["2 exhibitor passes"], payment_plan="25% x 4"),
        peer_companies=["NeuraMonks", "ViitorCloud"],
        next_steps=["Book at techexpogujarat.com/become-an-exhibitor"],
        contact="info@techexpogujarat.com",
    )


async def _seed_session():
    orch = Orchestrator(
        analysis=AnalysisAgent(FakeLLMClient(structured=[_CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor")])),
        research=ResearchAgent(FakeLLMClient(structured=[_Synthesis(
            sector="AI Consulting", company_size="200", hq="Ahmedabad", founder=None,
            designation=None, seniority=None, is_technical=None, person_company_match=None,
        )]), explorer=StubExplorer(), tools=[_DeadWeb()]),
        persuasion=PersuasionAgent(FakeLLMClient(
            structured=[_PersonaChoice(persona="it_tech_service", reason="software services")],
            responses=["Welcome back. A 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed at booking). Want details?"],
        )),
        proposal=ProposalAgent(FakeLLMClient(structured=[_good_proposal()]), explorer=StubExplorer()),
    )
    res = await orch.run_pipeline(IntakePayload(person_name="Tapan Patel", company_name="Third Rock Techkno"))
    return orch, res.session_id


async def test_generate_proposal_writes_files_row_and_message(tmp_path, monkeypatch):
    monkeypatch.setenv("PROPOSAL_DIR", str(tmp_path / "proposals"))
    from config.settings import get_settings
    get_settings.cache_clear()
    orch, sid = await _seed_session()
    card = await orch.generate_proposal(sid)

    assert card.version == 1
    assert card.filename.startswith("TEG-2026-Proposal-Third-Rock-Techkno-v1")
    assert card.kind == "proposal_link"
    assert card.page_url == f"/p/{card.proposal_id}"
    # link-only delivery: no PDF/PNG render pass, no files on disk.
    assert card.pdf_url is None and card.png_url is None
    assert not (tmp_path / "proposals").exists()

    async with SessionLocal() as s:
        pr = (await s.execute(select(ProposalRow))).scalars().one()
        assert pr.version == 1
        assert pr.proposal_json["generated_on"] != "__DATE__"
        msgs = (await s.execute(select(ChatMessage).order_by(ChatMessage.turn_index))).scalars().all()
        assert msgs[-1].attachment["kind"] == "proposal_link"
        assert msgs[-1].attachment["page_url"] == f"/p/{card.proposal_id}"
        assert "/p/" in msgs[-1].content
    get_settings.cache_clear()


async def test_generate_proposal_picks_up_a_stored_deep_research_brief(tmp_path, monkeypatch):
    monkeypatch.setenv("PROPOSAL_DIR", str(tmp_path / "proposals"))
    from config.settings import get_settings
    get_settings.cache_clear()

    async with SessionLocal() as s:
        await CompanyBriefRepo(s).upsert_deep_findings(
            "Third Rock Techkno",
            DeepFindings(
                market_positioning="AI + cloud engineering consultancy",
                teg_fit_reasons=["Their AI/cloud practice maps to TEG's tech-cluster visitors"],
            ),
        )
        await s.commit()

    orch, sid = await _seed_session()
    await orch.generate_proposal(sid)

    async with SessionLocal() as s:
        pr = (await s.execute(select(ProposalRow))).scalars().one()
        assert "AI + cloud engineering consultancy" in pr.proposal_json["company_standing"]
        assert pr.proposal_json["teg_fit_points"] == [
            "Their AI/cloud practice maps to TEG's tech-cluster visitors"
        ]


async def test_generate_proposal_bumps_version(tmp_path, monkeypatch):
    monkeypatch.setenv("PROPOSAL_DIR", str(tmp_path / "proposals"))
    from config.settings import get_settings
    get_settings.cache_clear()
    orch, sid = await _seed_session()
    orch.proposal.llm._structured.append(_good_proposal())
    c1 = await orch.generate_proposal(sid)
    c2 = await orch.generate_proposal(sid)
    assert (c1.version, c2.version) == (1, 2)
    get_settings.cache_clear()
