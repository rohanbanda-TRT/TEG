import pytest
from sqlalchemy import select

from app.agents.analysis import AnalysisAgent, _CanonResult
from app.agents.persuasion import PersuasionAgent, _Analysis, _PersonaChoice
from app.agents.research import ResearchAgent, _Synthesis
from app.domain.schemas import IntakePayload
from app.llm.fake import FakeLLMClient
from app.orchestrator import Orchestrator
from tests.conftest import StubExplorer
from app.research.tools import ResearchResult, ResearchTool
from app.store.db import Base, SessionLocal, engine
from app.store.models import ProposalRow


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


async def test_run_turn_populates_wants_proposal_without_generating():
    orch = Orchestrator(
        analysis=AnalysisAgent(FakeLLMClient(structured=[_CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor")])),
        research=ResearchAgent(FakeLLMClient(structured=[_Synthesis(
            sector="AI Consulting", company_size="200", hq=None, founder=None,
            designation=None, seniority=None, is_technical=None, person_company_match=None)]),
            explorer=StubExplorer(), tools=[_DeadWeb()]),
        persuasion=PersuasionAgent(FakeLLMClient(
            structured=[_PersonaChoice(persona="it_tech_service", reason="s"),
                        _Analysis(reply="Sure.", detected_cta=None, cta_status="offered", cta_type=None,
                                  cta_detail={}, should_handoff=False, learned_facts={}, wants_proposal=True)],
            responses=["Welcome. A 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed at booking)."])),
    )
    res = await orch.run_pipeline(IntakePayload(person_name="Tapan Patel", company_name="Third Rock Techkno"))
    turn = await orch.run_turn(res.session_id, "send me a proposal please")
    assert turn.wants_proposal is True
    async with SessionLocal() as s:
        assert (await s.execute(select(ProposalRow))).scalars().first() is None
