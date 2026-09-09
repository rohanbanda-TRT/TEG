"""POST /inquiries schedules Orchestrator.run_deep_research as a FastAPI
background task, AFTER the response is already computed. See
docs/superpowers/specs/2026-09-09-background-deep-research-design.md §3.2.
"""
import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.analysis import AnalysisAgent, _CanonResult
from app.agents.persuasion import PersuasionAgent, _PersonaChoice
from app.agents.research import ResearchAgent, _Synthesis
from app.api.inquiries import get_orchestrator
from app.llm.fake import FakeLLMClient
from app.main import create_app
from app.orchestrator import Orchestrator
from app.research.tools import ResearchResult, ResearchTool
from app.store.db import Base, engine
from tests.conftest import StubExplorer


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


def _orch() -> Orchestrator:
    return Orchestrator(
        analysis=AnalysisAgent(FakeLLMClient(structured=[
            _CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor"),
        ])),
        research=ResearchAgent(
            FakeLLMClient(structured=[_Synthesis(
                sector="AI Consulting", company_size="200", hq=None, founder=None,
                designation=None, seniority=None, is_technical=None, person_company_match=None,
            )]),
            explorer=StubExplorer(), tools=[_DeadWeb()],
        ),
        persuasion=PersuasionAgent(FakeLLMClient(
            structured=[_PersonaChoice(persona="it_tech_service", reason="software services")],
            responses=["Welcome back to Tech Expo Gujarat!"],
        )),
    )


async def test_inquiry_schedules_deep_research_with_the_right_identity():
    orch = _orch()
    calls: list[dict] = []

    async def _spy(*, company_name: str, person_name: str) -> None:
        calls.append({"company_name": company_name, "person_name": person_name})

    orch.run_deep_research = _spy  # replace the bound method with a spy

    app = create_app()
    app.dependency_overrides[get_orchestrator] = lambda: orch
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/inquiries", json={"person_name": "Rohan B", "company_name": "Third Rock Techkno"})

    assert r.status_code == 202
    assert len(calls) == 1
    assert calls[0]["company_name"] == "Third Rock Techkno"
    assert calls[0]["person_name"] == "Rohan B"


async def test_deep_research_gated_off_never_touches_claude_cli(monkeypatch):
    """Real safety net, not just a unit-level assumption: with the settings
    this suite runs under (CLAUDE_CLI_ENABLED=false, DEEP_RESEARCH_ENABLED=false
    — see tests/conftest.py), the REAL Orchestrator.run_deep_research must
    return immediately without ever constructing a ClaudeCli."""
    import app.orchestrator as orch_mod

    def _boom(*a, **kw):
        raise AssertionError("ClaudeCli should never be constructed here")

    monkeypatch.setattr(orch_mod, "deep_research", _boom)

    orch = _orch()
    app = create_app()
    app.dependency_overrides[get_orchestrator] = lambda: orch
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/inquiries", json={"person_name": "Rohan B", "company_name": "Third Rock Techkno"})

    assert r.status_code == 202  # the background task ran (and no-opped) without raising
