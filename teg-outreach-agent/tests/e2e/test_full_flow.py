"""End-to-end coverage for spec §11 success criteria 1, 2, 3, 5.

Both tests drive the whole app through ``TestClient`` (sync) with a scripted
``FakeLLMClient`` per agent -- no real Gemini / Tavily calls. They exercise:

* happy path -- a KB-resolvable person + company gets a persona-correct opening
  with real peer names and the indicative stall price, then a two-turn chat
  advances the CTA to ``completed`` and the session record is ``qualified``
  with no handoff packet.
* handoff path -- an unknown person + company gets a qualifying question, the
  prospect reveals a sector then deflects ("just researching"), and the session
  ends with a low-confidence handoff packet.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.agents.analysis import AnalysisAgent, _CanonResult
from app.agents.persuasion import PersuasionAgent, _Analysis, _PersonaChoice
from app.agents.research import ResearchAgent, _Synthesis
from app.api.inquiries import get_orchestrator
from app.domain.schemas import HandoffPacket
from app.llm.fake import FakeLLMClient
from app.main import create_app
from app.orchestrator import Orchestrator
from app.research.tools import ResearchResult, ResearchTool
from app.store.db import SessionLocal
from app.store.models import ChatSession, HandoffPacketRow
from tests.conftest import StubExplorer

pytestmark = pytest.mark.usefixtures("db_schema")


class _DeadWeb(ResearchTool):
    name = "web"

    async def lookup(self, q):
        return ResearchResult(available=False, tool_name="web")


def test_happy_path_kb_company_completes_cta():
    """Criteria 1, 2, 5: name+company -> persona-correct opening w/ real peers
    -> CTA completed -> qualified record, no handoff."""
    orch = Orchestrator(
        analysis=AnalysisAgent(
            FakeLLMClient(structured=[_CanonResult(canonical="Codemech Solutions", intent_hint="exhibitor")])
        ),
        research=ResearchAgent(
            FakeLLMClient(structured=[_Synthesis(
                sector="Software Development", company_size="200", hq="Ahmedabad", founder=None,
                designation=None, seniority=None, is_technical=None, person_company_match=None,
            )]),
            explorer=StubExplorer({"codemech": {
                "sector": "Software Development & IT Services",
                "teg_history": "TEG 2024 exhibitor",
                "sector_peers": "Techalmas, TechEniac, AppsRow",
            }}),
            tools=[_DeadWeb()],
        ),
        persuasion=PersuasionAgent(FakeLLMClient(
            responses=[
                (
                    "Welcome back, Codemech. Companies like Techalmas and TechEniac are "
                    "exhibiting again this year. What would make TEG 2026 worth it for your team?"
                )
            ],
            structured=[
                _PersonaChoice(persona="it_tech_service", reason="software services company"),
                _Analysis(
                    reply="A larger stall would give a team of 4 room to run live demos. "
                          "Shall I get a stall reserved for you?",
                    detected_cta="book_stall", cta_status="in_progress", cta_type="stall",
                    cta_detail={"stall_size": "3x6"}, should_handoff=False,
                ),
                _Analysis(
                    reply="Done -- I've noted a stall booking. The team will confirm the details.",
                    detected_cta="book_stall", cta_status="completed", cta_type="stall",
                    cta_detail={"stall_size": "3x6"}, should_handoff=False,
                ),
            ],
        )),
    )
    app = create_app()
    app.dependency_overrides[get_orchestrator] = lambda: orch
    client = TestClient(app)

    posted = client.post(
        "/inquiries", json={"person_name": "Tapan Patel", "company_name": "Codemech Solutions"}
    ).json()
    assert posted["persona"] in {"it_tech_service", "ai_startup"}
    assert "Techalmas" in posted["opening_message"]
    assert "₹" not in posted["opening_message"]

    sid = posted["session_id"]
    with client.websocket_connect(f"/chat/{sid}") as ws:
        assert ws.receive_json()["type"] == "opening"
        ws.send_json({"type": "message", "text": "we're a team of 4"})
        assert ws.receive_json()["cta_status"] == "in_progress"
        ws.send_json({"type": "message", "text": "yes book it"})
        assert ws.receive_json()["cta_status"] == "completed"
        ws.send_json({"type": "end"})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()

    async def _check():
        async with SessionLocal() as s:
            cs = (await s.execute(select(ChatSession))).scalars().first()
            assert cs.cta_status == "completed"
            assert cs.outcome_status == "qualified"
            assert cs.cta_detail.get("stall_size") == "3x6"
            assert (await s.execute(select(HandoffPacketRow))).scalars().first() is None

    asyncio.run(_check())


def test_handoff_path_unknown_company_deflect():
    """Criteria 3, 5: unknown identity -> qualifying question -> deflection ->
    low-confidence handoff packet."""
    orch = Orchestrator(
        analysis=AnalysisAgent(
            FakeLLMClient(structured=[_CanonResult(canonical="Obscure Local Co", intent_hint="unknown")])
        ),
        research=ResearchAgent(
            FakeLLMClient(structured=[]), explorer=StubExplorer(), tools=[_DeadWeb()]
        ),
        persuasion=PersuasionAgent(FakeLLMClient(
            responses=["So I can tailor this -- what does your company do, and what's your role there?"],
            structured=[
                _PersonaChoice(persona="it_tech_service", reason="IT services firm"),
                _Analysis(
                    reply="Thanks! TEG has a lot for services firms. Are you thinking of exhibiting or visiting?",
                    detected_cta=None, cta_status="none", cta_type=None, cta_detail={},
                    should_handoff=False, learned_facts={"sector": "IT services"},
                ),
                _Analysis(
                    reply="No problem -- I'll have the team send details when you're ready.",
                    detected_cta=None, cta_status="none", cta_type=None, cta_detail={},
                    should_handoff=True, learned_facts={},
                ),
                HandoffPacket(
                    summary="Person from Obscure Local Co, an IT services firm, just researching.",
                    recommended_next_step="Email the exhibitor brochure.",
                    suggested_followup_message="Hi, thanks for your interest in TEG 2026...",
                    prospect_confidence="low", key_facts={},
                ),
            ],
        )),
    )
    app = create_app()
    app.dependency_overrides[get_orchestrator] = lambda: orch
    client = TestClient(app)

    posted = client.post(
        "/inquiries", json={"person_name": "Someone New", "company_name": "Obscure Local Co"}
    ).json()
    assert posted["opening_message"].endswith("?")

    sid = posted["session_id"]
    with client.websocket_connect(f"/chat/{sid}") as ws:
        ws.receive_json()
        ws.send_json({"type": "message", "text": "we do IT staffing, I'm the founder"})
        ws.receive_json()
        ws.send_json({"type": "message", "text": "just researching for now"})
        r = ws.receive_json()
        assert r["should_handoff"] is True
        assert ws.receive_json()["type"] == "handoff"
        ws.send_json({"type": "end"})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()

    r2 = client.get(f"/sessions/{sid}").json()
    assert r2["handoff"] is not None
    assert r2["handoff"]["prospect_confidence"] == "low"
    assert r2["session"]["outcome_status"] in {"contacted", "lost"}
