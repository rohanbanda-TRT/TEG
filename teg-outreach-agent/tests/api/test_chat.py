# tests/api/test_chat.py
import asyncio

import pytest
from fastapi.testclient import TestClient

from app.agents.analysis import AnalysisAgent, _CanonResult
from app.agents.persuasion import PersuasionAgent, _Analysis, _PersonaChoice
from app.agents.research import ResearchAgent, _Synthesis
from app.api.inquiries import get_orchestrator
from app.llm.fake import FakeLLMClient
from app.main import create_app
from app.orchestrator import Orchestrator
from app.research.tools import ResearchResult, ResearchTool
from app.store.db import Base, engine
from tests.conftest import StubExplorer


@pytest.fixture
def db_schema():
    async def _reset(create: bool) -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            if create:
                await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_reset(create=True))
    yield
    asyncio.run(_reset(create=False))


pytestmark = pytest.mark.usefixtures("db_schema")


class _DeadWeb(ResearchTool):
    name = "web"

    async def lookup(self, q):
        return ResearchResult(available=False, tool_name="web")


# "Tapan Patel" and "Third Rock Techkno" both resolve in the read-only KB at full
# confidence, so the research person-track produces no `ask_prospect` gap and the
# persona maps to a real tech persona -> the opening carries the pricing line.
def _orch():
    return Orchestrator(
        analysis=AnalysisAgent(FakeLLMClient(structured=[_CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor")])),
        research=ResearchAgent(FakeLLMClient(structured=[_Synthesis(
            sector="AI Consulting", company_size="200", hq=None, founder=None,
            designation=None, seniority=None, is_technical=None, person_company_match=None,
        )]), explorer=StubExplorer(), tools=[_DeadWeb()]),
        persuasion=PersuasionAgent(FakeLLMClient(
            responses=["opening: a 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed at booking)."],
            structured=[
                _PersonaChoice(persona="it_tech_service", reason="software services"),
                _Analysis(
                    reply="Shall I send the booking link?", detected_cta="book_stall",
                    cta_status="offered", cta_type=None, cta_detail={}, should_handoff=False,
                    learned_facts={},
                ),
                _Analysis(
                    reply="Shall I send the booking link?", detected_cta="book_stall",
                    cta_status="offered", cta_type=None, cta_detail={}, should_handoff=False,
                    learned_facts={},
                ),
            ],
        )),
    )


def test_ws_chat_roundtrip():
    app = create_app()
    shared = _orch()
    app.dependency_overrides[get_orchestrator] = lambda: shared
    client = TestClient(app)

    posted = client.post("/inquiries", json={"person_name": "Tapan Patel", "company_name": "Third Rock Techkno"}).json()
    sid = posted["session_id"]

    with client.websocket_connect(f"/chat/{sid}") as ws:
        opening = ws.receive_json()
        assert opening["type"] == "opening"
        assert "1,17,000" in opening["text"]
        ws.send_json({"type": "message", "text": "tell me about stalls"})
        reply = ws.receive_json()
        assert reply["type"] == "reply"
        assert reply["cta_status"] == "offered"
        ws.send_json({"type": "end"})


def test_ws_unknown_session_closes():
    app = create_app()
    app.dependency_overrides[get_orchestrator] = lambda: _orch()
    client = TestClient(app)
    with pytest.raises(Exception):
        with client.websocket_connect("/chat/00000000-0000-0000-0000-000000000000") as ws:
            ws.receive_json()
