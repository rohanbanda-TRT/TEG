import asyncio

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.agents.analysis import AnalysisAgent, _CanonResult
from app.agents.persuasion import PersuasionAgent, _Analysis, _PersonaChoice
from app.agents.proposal import ProposalAgent
from app.agents.research import ResearchAgent, _Synthesis
from app.api.inquiries import get_orchestrator
from app.domain.schemas import (
    HandoffPacket,
    Proposal,
    ProposalPackage,
    ProposalPain,
    SectorFitRow,
)
from app.llm.fake import FakeLLMClient
from app.main import create_app
from app.orchestrator import Orchestrator
from app.research.tools import ResearchResult, ResearchTool
from tests.conftest import StubExplorer

pytestmark = pytest.mark.usefixtures("db_schema")


class _DeadWeb(ResearchTool):
    name = "web"
    async def lookup(self, q):
        return ResearchResult(available=False, tool_name="web")


def test_full_proposal_flow(tmp_path, monkeypatch):
    """Criteria 1-5: mid-chat proposal request -> personalized PDF card -> fetchable PDF."""
    monkeypatch.setenv("PROPOSAL_DIR", str(tmp_path / "proposals"))
    from config.settings import get_settings
    get_settings.cache_clear()

    proposal = Proposal(
        company="Third Rock Techkno", person="Tapan Patel", person_role="CMO",
        sector="Software Development", persona="it_tech_service",
        generated_on="__DATE__", session_ref="x", version=0,
        what_you_told_us="You're an AI + software consulting firm serving mostly US clients, "
                         "looking to build an India-market pipeline.",
        pains=[
            ProposalPain(pain="Revenue concentrated in US clients; thin India pipeline",
                         teg_answer="15,000+ India-market decision-makers plus pre-scheduled B2B "
                                    "meetings tuned to manufacturing, BFSI, pharma and retail"),
            ProposalPain(pain="Low brand visibility in the home market",
                         teg_answer="On-ground, website and regional PR presence at the state's largest tech expo"),
        ],
        lead_generation="Pre-scheduled B2B matchmaking with India-market buyers across your target "
                        "sectors, plus a live demo space to show your AI work.",
        proof=["TEG 2024 drew 8,000+ attendees and 125+ exhibitors; TEG 2026 targets 15,000+ and 250+.",
               "The TEG Business Retreat 2025 helped facilitate ₹1.5 crore raised in one day (organizer-stated)."],
        recommended_package=ProposalPackage(
            name="3m x 6m stall",
            price_line="₹2,34,000 + GST (indicative, confirmed at booking)",
            includes=["4 exhibitor passes", "10 visitor passes", "pre-scheduled 1:1 B2B meetings",
                      "live demo space"],
            payment_plan="4 instalments of 25% (9 Apr / 30 Jun / 31 Jul / 31 Aug 2026)"),
        peer_companies=["NeuraMonks", "ViitorCloud", "Perigeon"],
        next_steps=["Review stall options at techexpogujarat.com/become-an-exhibitor",
                    "Or reply here and the team will walk you through booking"],
        contact="info@techexpogujarat.com · +91 98989 23712",
        executive_summary="Third Rock Techkno, an AI + software services company, wants India-market "
                          "leads and is exploring a stall at TEG 2026.",
        how_a_teg_plays_out=["Pre-event: matchmaking with India buyers", "Day 1: live demos",
                             "Day 2: pre-scheduled meetings", "After: follow-up via the TEG app"],
        roi_framing="If a single India-market engagement that starts here covers the cost of taking "
                    "part several times over, participation pays for itself.",
        sector_fit=[SectorFitRow(lever="India-market buyer access", weight=5),
                    SectorFitRow(lever="Pre-scheduled B2B meetings", weight=5),
                    SectorFitRow(lever="Live demo space", weight=4),
                    SectorFitRow(lever="Brand visibility", weight=3)],
    )

    orch = Orchestrator(
        analysis=AnalysisAgent(FakeLLMClient(structured=[_CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor")])),
        research=ResearchAgent(FakeLLMClient(structured=[_Synthesis(
            sector="AI Consulting", company_size="200", hq="Ahmedabad", founder=None,
            designation=None, seniority=None, is_technical=None, person_company_match=None)]),
            explorer=StubExplorer(), tools=[_DeadWeb()]),
        persuasion=PersuasionAgent(FakeLLMClient(
            structured=[
                _PersonaChoice(persona="it_tech_service", reason="AI + software services"),
                _Analysis(reply="Absolutely — putting that together now.", detected_cta=None,
                          cta_status="offered", cta_type=None, cta_detail={}, should_handoff=False,
                          discovery={"target_market": "India", "goal": "leads", "scale": "200"},
                          asked_about_price=True, wants_proposal=True),
                HandoffPacket(summary="Tapan Patel, TRT, wants India-market leads, exploring a stall.",
                              recommended_next_step="Sales rep to follow up with stall options.",
                              suggested_followup_message="Hi Tapan, following up on TEG 2026...",
                              prospect_confidence="high", key_facts={}),
            ],
            responses=["Welcome back to Tech Expo Gujarat! What outcome would make taking part worthwhile for TRT this year?"])),
        proposal=ProposalAgent(FakeLLMClient(structured=[proposal]), explorer=StubExplorer()),
    )
    app = create_app()
    app.dependency_overrides[get_orchestrator] = lambda: orch
    client = TestClient(app)

    posted = client.post("/inquiries", json={
        "person_name": "Tapan Patel", "company_name": "Third Rock Techkno",
        "message": "how can Tech Expo help my company grow?",
    }).json()
    sid = posted["session_id"]

    with client.websocket_connect(f"/chat/{sid}") as ws:
        assert ws.receive_json()["type"] == "opening"
        ws.send_json({"type": "message",
                      "text": "we serve mostly US clients, want India-market clients. can you send a proposal?"})
        assert ws.receive_json()["type"] == "reply"
        assert ws.receive_json()["type"] == "proposal_pending"
        att = ws.receive_json()
        assert att["type"] == "attachment" and att["version"] == 1
        pdf_url = att["pdf_url"]
        ws.send_json({"type": "end"})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()

    pdf = client.get(pdf_url)
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"

    sess = client.get(f"/sessions/{sid}").json()
    assert sess["proposals"][0]["version"] == 1
    assert sess["proposals"][0]["guardrail_flags"] == []

    from sqlalchemy import select

    from app.store.db import SessionLocal
    from app.store.models import ProposalRow

    async def _check():
        async with SessionLocal() as s:
            pr = (await s.execute(select(ProposalRow))).scalars().one()
            j = pr.proposal_json
            assert "India" in j["what_you_told_us"]
            assert any("India" in p["teg_answer"] or "India" in p["pain"] for p in j["pains"])
            # the prospect asked about price -> the proposal keeps the figure
            assert "+ GST" in j["recommended_package"]["price_line"]
            assert j["executive_summary"]
            assert 4 <= len(j["sector_fit"]) <= 6
            assert j["generated_on"] != "__DATE__"
    asyncio.run(_check())
    get_settings.cache_clear()
