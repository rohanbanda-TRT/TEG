import pytest
from fastapi.testclient import TestClient

from app.agents.analysis import AnalysisAgent, _CanonResult
from app.agents.persuasion import PersuasionAgent, _PersonaChoice
from app.agents.proposal import ProposalAgent
from app.agents.research import ResearchAgent, _Synthesis
from app.api.inquiries import get_orchestrator
from app.domain.schemas import Proposal, ProposalPackage, ProposalPain
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
        company="Third Rock Techkno", person="Tapan Patel", person_role="CMO",
        sector="Software Development", persona="it_tech_service",
        generated_on="__DATE__", session_ref="x", version=0,
        what_you_told_us="AI + software consulting firm exploring TEG.",
        pains=[ProposalPain(pain="US-heavy revenue", teg_answer="15,000+ India buyers + B2B meetings")],
        lead_generation="Pre-scheduled B2B meetings with India-market buyers plus a live demo space.",
        proof=["TEG 2024 drew 8,000+ attendees and 125+ exhibitors."],
        recommended_package=ProposalPackage(
            name="3m x 3m stall", price_line="₹1,17,000 + GST (indicative, confirmed at booking)",
            includes=["2 exhibitor passes"], payment_plan="25% x 4"),
        peer_companies=["NeuraMonks"], next_steps=["Book at techexpogujarat.com"],
        contact="info@techexpogujarat.com",
    )


def _orch():
    return Orchestrator(
        analysis=AnalysisAgent(FakeLLMClient(structured=[_CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor")])),
        research=ResearchAgent(FakeLLMClient(structured=[_Synthesis(
            sector="AI Consulting", company_size="200", hq="Ahmedabad", founder=None,
            designation=None, seniority=None, is_technical=None, person_company_match=None)]),
            explorer=StubExplorer(), tools=[_DeadWeb()]),
        persuasion=PersuasionAgent(FakeLLMClient(
            structured=[_PersonaChoice(persona="it_tech_service", reason="software services")],
            responses=["Welcome. A 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed at booking)."])),
        proposal=ProposalAgent(FakeLLMClient(structured=[_good_proposal()]), explorer=StubExplorer()),
    )


def test_post_proposal_then_get_page(tmp_path, monkeypatch):
    """Proposals are delivered as the live `/p/{id}` page only — no PDF/PNG."""
    monkeypatch.setenv("PROPOSAL_DIR", str(tmp_path / "proposals"))
    from config.settings import get_settings
    get_settings.cache_clear()

    app = create_app()
    shared = _orch()
    app.dependency_overrides[get_orchestrator] = lambda: shared
    client = TestClient(app)

    posted = client.post("/inquiries", json={"person_name": "Tapan Patel", "company_name": "Third Rock Techkno"}).json()
    sid = posted["session_id"]

    r = client.post(f"/sessions/{sid}/proposal", json={})
    assert r.status_code == 202
    card = r.json()
    assert card["version"] == 1
    assert card["kind"] == "proposal_link"
    assert card["page_url"] == f"/p/{card['proposal_id']}"
    assert card["pdf_url"] is None and card["png_url"] is None

    proposal_json = client.get(f"/proposals/{card['proposal_id']}.json")
    assert proposal_json.status_code == 200
    assert proposal_json.json()["proposal"]["company"] == "Third Rock Techkno"

    # no file was ever rendered, so both legacy file routes 404
    assert client.get(f"/proposals/{card['proposal_id']}.pdf").status_code == 404
    assert client.get(f"/proposals/{card['proposal_id']}/preview.png").status_code == 404

    sess = client.get(f"/sessions/{sid}").json()
    assert len(sess["proposals"]) == 1
    assert sess["proposals"][0]["version"] == 1
    get_settings.cache_clear()


def test_get_missing_proposal_404(tmp_path, monkeypatch):
    monkeypatch.setenv("PROPOSAL_DIR", str(tmp_path / "proposals"))
    from config.settings import get_settings
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_orchestrator] = lambda: _orch()
    client = TestClient(app)
    r = client.get("/proposals/00000000-0000-0000-0000-000000000000.pdf")
    assert r.status_code == 404
    get_settings.cache_clear()


@pytest.fixture
def built_proposal(tmp_path, monkeypatch):
    """A generated proposal: yields (proposal_id, TestClient)."""
    monkeypatch.setenv("PROPOSAL_DIR", str(tmp_path / "proposals"))
    from config.settings import get_settings
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_orchestrator] = lambda: _orch()
    client = TestClient(app)
    posted = client.post(
        "/inquiries", json={"person_name": "Tapan Patel", "company_name": "Third Rock Techkno"}
    ).json()
    card = client.post(f"/sessions/{posted['session_id']}/proposal", json={}).json()
    yield card["proposal_id"], client
    get_settings.cache_clear()


def test_get_proposal_json(built_proposal):
    pid, client = built_proposal
    r = client.get(f"/proposals/{pid}.json")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == str(pid)
    assert body["version"] >= 1
    assert body["pdf_url"] == f"/proposals/{pid}.pdf"
    assert body["proposal"]["company"]


def test_get_proposal_json_404(built_proposal):
    _, client = built_proposal
    import uuid
    r = client.get(f"/proposals/{uuid.uuid4()}.json")
    assert r.status_code == 404


def test_get_proposal_page(built_proposal):
    pid, client = built_proposal
    from pathlib import Path
    r = client.get(f"/p/{pid}")
    if Path("app/static/proposal/index.html").is_file():
        assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    else:
        assert r.status_code == 503
