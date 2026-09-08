import pytest
from sqlalchemy import select

from app.agents.analysis import AnalysisAgent, _CanonResult
from app.agents.persuasion import PersuasionAgent, _Analysis, _PersonaChoice
from app.agents.research import ResearchAgent, _Synthesis
from app.domain.schemas import HandoffPacket, IntakePayload
from app.llm.fake import FakeLLMClient
from app.orchestrator import Orchestrator
from app.research.tools import ResearchResult, ResearchTool
from app.store.db import Base, SessionLocal, engine
from app.store.models import ChatMessage, ChatSession, HandoffPacketRow
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


async def _seed_session(persuasion_llm) -> tuple[Orchestrator, "uuid.UUID"]:
    analysis = AnalysisAgent(FakeLLMClient(structured=[_CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor")]))
    research = ResearchAgent(FakeLLMClient(structured=[_Synthesis(
        sector="AI Consulting", company_size="200", hq=None, founder=None,
        designation=None, seniority=None, is_technical=None, person_company_match=None,
    )]), explorer=StubExplorer(), tools=[_DeadWeb()])
    persuasion = PersuasionAgent(persuasion_llm)
    orch = Orchestrator(analysis=analysis, research=research, persuasion=persuasion)
    res = await orch.run_pipeline(IntakePayload(person_name="Tapan Patel", company_name="Third Rock Techkno"))
    return orch, res.session_id


async def test_run_turn_persists_pair_and_state():
    persuasion_llm = FakeLLMClient(
        responses=["opening line ok"],
        structured=[
            _PersonaChoice(persona="it_tech_service", reason="software company"),
            _Analysis(
                reply="Shall I send the stall booking link?", detected_cta="book_stall",
                cta_status="offered", cta_type=None, cta_detail={}, should_handoff=False,
                discovery={"scale": "small"},
            ),
        ],
    )
    orch, sid = await _seed_session(persuasion_llm)
    turn = await orch.run_turn(sid, "tell me about stalls")
    assert turn.cta_status == "offered"
    async with SessionLocal() as s:
        msgs = (await s.execute(select(ChatMessage).order_by(ChatMessage.turn_index))).scalars().all()
        assert [m.role for m in msgs] == ["agent", "prospect", "agent"]
        cs = (await s.execute(select(ChatSession))).scalars().first()
        assert cs.cta_status == "offered"
        assert cs.learned_facts == {"scale": "small"}


async def test_end_session_generates_handoff_when_cta_incomplete():
    persuasion_llm = FakeLLMClient(
        responses=["opening line ok"],
        structured=[
            _PersonaChoice(persona="it_tech_service", reason="software company"),
            _Analysis(reply="No worries, I'll pass you to the team.", detected_cta=None,
                      cta_status="none", cta_type=None, cta_detail={}, should_handoff=True,
                      discovery={}),
            HandoffPacket(summary="Rohan from TRT, exploring exhibiting, not ready to commit.",
                          recommended_next_step="Sales rep to email stall deck.",
                          suggested_followup_message="Hi Rohan, following up on TEG 2026...",
                          prospect_confidence="high", key_facts={"company": "Third Rock Techkno"}),
        ],
    )
    orch, sid = await _seed_session(persuasion_llm)
    await orch.run_turn(sid, "just researching for now")
    packet = await orch.end_session(sid, reason="left")
    assert packet is not None
    async with SessionLocal() as s:
        cs = (await s.execute(select(ChatSession))).scalars().first()
        assert cs.outcome_status in {"contacted", "lost"}
        assert cs.handoff_generated is True
        h = (await s.execute(select(HandoffPacketRow))).scalars().first()
        assert "TRT" in h.summary
