# tests/orchestrator/test_run_pipeline.py
import pytest

from app.agents.analysis import AnalysisAgent, _CanonResult
from app.agents.persuasion import PersuasionAgent
from app.agents.research import ResearchAgent, _Synthesis
from app.domain.schemas import IntakePayload
from app.llm.fake import FakeLLMClient
from app.orchestrator import Orchestrator
from tests.conftest import StubExplorer
from app.research.tools import ResearchResult, ResearchTool
from app.store.db import Base, SessionLocal, engine
from app.store.models import ChatMessage, ChatSession, Inquiry
from sqlalchemy import select


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
    async def lookup(self, query):
        return ResearchResult(available=False, tool_name="web")


async def test_run_pipeline_persists_and_returns_opening():
    analysis = AnalysisAgent(FakeLLMClient(structured=[
        _CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor"),
    ]))
    research = ResearchAgent(
        FakeLLMClient(structured=[_Synthesis(
            sector="AI Consulting", company_size="200", hq=None, founder=None,
            designation=None, seniority=None, is_technical=None, person_company_match=None,
        )]),
        explorer=StubExplorer(), tools=[_DeadWeb()],
    )
    persuasion = PersuasionAgent(FakeLLMClient(responses=[
        "Welcome back, Third Rock Techkno. Companies like NeuraMonks and ViitorCloud are "
        "exhibiting. A 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed at booking). "
        "Want the stall options?"
    ]))
    orch = Orchestrator(analysis=analysis, research=research, persuasion=persuasion)
    res = await orch.run_pipeline(IntakePayload(person_name="Rohan B", company_name="TRT"))

    assert res.opening_message
    async with SessionLocal() as s:
        assert (await s.execute(select(Inquiry))).scalars().first().company_name_canonical == "Third Rock Techkno"
        cs = (await s.execute(select(ChatSession))).scalars().first()
        assert cs.id == res.session_id
        msgs = (await s.execute(select(ChatMessage))).scalars().all()
        assert len(msgs) == 1 and msgs[0].role == "agent"


async def test_run_pipeline_research_timeout_uses_empty_dossier(monkeypatch):
    monkeypatch.setenv("PIPELINE_HARD_TIMEOUT_S", "0")
    from config.settings import get_settings
    get_settings.cache_clear()

    class _SlowResearch(ResearchAgent):
        async def run(self, intake):
            import asyncio
            await asyncio.sleep(1)
            raise AssertionError("should have timed out")

    analysis = AnalysisAgent(FakeLLMClient(structured=[_CanonResult(canonical="Acme", intent_hint="unknown")]))
    research = _SlowResearch(FakeLLMClient(), explorer=StubExplorer(), tools=[_DeadWeb()])
    persuasion = PersuasionAgent(FakeLLMClient(responses=["What does your company do, and what's your role?"]))
    orch = Orchestrator(analysis=analysis, research=research, persuasion=persuasion)
    res = await orch.run_pipeline(IntakePayload(person_name="X", company_name="Acme"))
    assert "?" in res.opening_message
    get_settings.cache_clear()
