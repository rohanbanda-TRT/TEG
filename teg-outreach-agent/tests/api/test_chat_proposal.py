import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.agents.analysis import AnalysisAgent, _CanonResult
from app.agents.persuasion import PersuasionAgent, _Analysis, _PersonaChoice
from app.agents.proposal import ProposalAgent
from app.agents.research import ResearchAgent, _Synthesis
from app.api.inquiries import get_orchestrator
from app.domain.schemas import HandoffPacket, Proposal, ProposalPackage, ProposalPain
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


def _good_proposal():
    return Proposal(
        company="Third Rock Techkno", person="Tapan Patel", persona="it_tech_service",
        sector="Software Development", generated_on="__DATE__", session_ref="x", version=0,
        what_you_told_us="w",
        pains=[ProposalPain(pain="US-heavy revenue", teg_answer="15,000+ India buyers")],
        lead_generation="Pre-scheduled B2B meetings plus a live demo space.",
        proof=["TEG 2024 drew 8,000+ attendees."],
        recommended_package=ProposalPackage(name="3m x 3m stall",
            price_line="₹1,17,000 + GST (indicative, confirmed at booking)",
            includes=["2 exhibitor passes"], payment_plan="25% x 4"),
        peer_companies=["NeuraMonks"], next_steps=["Book at techexpogujarat.com"],
        contact="info@techexpogujarat.com",
    )


def _orch(proposal_llm):
    return Orchestrator(
        analysis=AnalysisAgent(FakeLLMClient(structured=[_CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor")])),
        research=ResearchAgent(FakeLLMClient(structured=[_Synthesis(
            sector="AI Consulting", company_size="200", hq=None, founder=None,
            designation=None, seniority=None, is_technical=None, person_company_match=None)]),
            explorer=StubExplorer(), tools=[_DeadWeb()]),
        persuasion=PersuasionAgent(FakeLLMClient(
            structured=[_PersonaChoice(persona="it_tech_service", reason="s"),
                        _Analysis(reply="Sure, one moment.", detected_cta=None, cta_status="offered",
                                  cta_type=None, cta_detail={}, should_handoff=False, learned_facts={},
                                  wants_proposal=True),
                        HandoffPacket(summary="s", recommended_next_step="n",
                                      suggested_followup_message="m", prospect_confidence="medium",
                                      key_facts={})],
            responses=["Welcome. A 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed at booking)."])),
        proposal=ProposalAgent(proposal_llm, explorer=StubExplorer()),
    )


def test_ws_proposal_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("PROPOSAL_DIR", str(tmp_path / "proposals"))
    from config.settings import get_settings
    get_settings.cache_clear()

    app = create_app()
    shared = _orch(FakeLLMClient(structured=[_good_proposal()]))
    app.dependency_overrides[get_orchestrator] = lambda: shared
    client = TestClient(app)

    posted = client.post("/inquiries", json={"person_name": "Tapan Patel", "company_name": "Third Rock Techkno"}).json()
    sid = posted["session_id"]

    with client.websocket_connect(f"/chat/{sid}") as ws:
        assert ws.receive_json()["type"] == "opening"
        ws.send_json({"type": "message", "text": "can you send me a proposal?"})
        assert ws.receive_json()["type"] == "reply"
        assert ws.receive_json()["type"] == "proposal_pending"
        att = ws.receive_json()
        assert att["type"] == "attachment"
        assert att["kind"] == "proposal" and att["version"] == 1
        assert att["pdf_url"].endswith(".pdf")
        ws.send_json({"type": "end"})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()

    pdf = client.get(att["pdf_url"])
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"
    get_settings.cache_clear()


def test_ws_proposal_failure_emits_failed(tmp_path, monkeypatch):
    monkeypatch.setenv("PROPOSAL_DIR", str(tmp_path / "proposals"))
    from config.settings import get_settings
    get_settings.cache_clear()

    class _BoomProposal(ProposalAgent):
        async def build(self, **kw):
            raise RuntimeError("render boom")

    app = create_app()
    shared = _orch(FakeLLMClient())
    shared.proposal = _BoomProposal(FakeLLMClient())
    app.dependency_overrides[get_orchestrator] = lambda: shared
    client = TestClient(app)

    posted = client.post("/inquiries", json={"person_name": "Tapan Patel", "company_name": "Third Rock Techkno"}).json()
    sid = posted["session_id"]
    with client.websocket_connect(f"/chat/{sid}") as ws:
        ws.receive_json()  # opening
        ws.send_json({"type": "message", "text": "proposal please"})
        ws.receive_json()  # reply
        ws.receive_json()  # proposal_pending
        assert ws.receive_json()["type"] == "proposal_failed"
        ws.send_json({"type": "end"})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
    get_settings.cache_clear()
