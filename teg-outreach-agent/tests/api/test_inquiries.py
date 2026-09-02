# tests/api/test_inquiries.py
import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.analysis import AnalysisAgent, _CanonResult
from app.agents.persuasion import PersuasionAgent, _PersonaChoice
from app.agents.research import ResearchAgent, _Synthesis
from app.api.inquiries import get_orchestrator
from app.llm.fake import FakeLLMClient
from app.main import create_app
from app.orchestrator import Orchestrator
from tests.conftest import StubExplorer
from app.research.tools import ResearchResult, ResearchTool
from app.store.db import Base, engine


@pytest.fixture(autouse=True)
async def _schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


class _DeadWeb(ResearchTool):
    name = "web"
    async def lookup(self, q):
        return ResearchResult(available=False, tool_name="web")


# "Tapan Patel" (a TEG core organizer and Third Rock Techkno co-founder) and
# "Third Rock Techkno" both resolve in the read-only KB at full confidence, so the
# research person-track produces no `ask_prospect` gap and persona maps to a real
# sector persona (Third Rock Techkno's KB category contains "Software Development").
def _fake_orchestrator() -> Orchestrator:
    return Orchestrator(
        analysis=AnalysisAgent(FakeLLMClient(structured=[_CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor")])),
        research=ResearchAgent(
            FakeLLMClient(structured=[_Synthesis(
                sector="AI Consulting", company_size="200", hq=None, founder=None,
                designation=None, seniority=None, is_technical=None, person_company_match=None,
            )]),
            explorer=StubExplorer(), tools=[_DeadWeb()],
        ),
        persuasion=PersuasionAgent(FakeLLMClient(
            structured=[_PersonaChoice(persona="it_tech_service", reason="software services")],
            responses=[
                "Welcome back. A 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed at booking). Want details?"
            ],
        )),
    )


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_orchestrator] = _fake_orchestrator
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def test_post_inquiry_returns_session_and_opening(client):
    async with client as c:
        r = await c.post("/inquiries", json={"person_name": "Tapan Patel", "company_name": "Third Rock Techkno"})
    assert r.status_code == 202
    body = r.json()
    assert body["session_id"]
    assert "1,17,000" in body["opening_message"]
    assert body["persona"] in {"it_tech_service", "ai_startup"}


async def test_post_inquiry_requires_company(client):
    async with client as c:
        r = await c.post("/inquiries", json={"person_name": "Tapan Patel"})
    assert r.status_code == 422


async def test_get_session_returns_transcript(client):
    async with client as c:
        posted = (await c.post("/inquiries", json={"person_name": "Tapan Patel", "company_name": "Third Rock Techkno"})).json()
        r = await c.get(f"/sessions/{posted['session_id']}")
    assert r.status_code == 200
    data = r.json()
    assert data["transcript"][0]["role"] == "agent"
    assert data["dossier"]["sector"]
