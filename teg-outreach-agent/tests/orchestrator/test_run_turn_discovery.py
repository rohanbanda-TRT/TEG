"""discovery v2 wired through run_turn (Phase 5).

These flip DISCOVERY_V2_ENABLED on. The flag-off suite (everything else) proves
the legacy path is untouched.
"""
import pytest
from sqlalchemy import select

from app.agents.analysis import AnalysisAgent, _CanonResult
from app.agents.persuasion import PersuasionAgent, _Analysis, _PersonaChoice
from app.agents.research import ResearchAgent, _Synthesis
from app.domain.discovery import DiscoveryState, IncomingSignal, TurnSignals
from app.domain.schemas import IntakePayload
from app.llm.fake import FakeLLMClient
from app.orchestrator import Orchestrator
from app.research.tools import ResearchResult, ResearchTool
from app.store.db import Base, SessionLocal, engine
from app.store.models import ChatSession, ProposalRow
from tests.conftest import StubExplorer


@pytest.fixture(autouse=True)
async def _schema():
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)
        await c.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
def _v2(monkeypatch):
    monkeypatch.setenv("DISCOVERY_V2_ENABLED", "true")
    from config.settings import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _DeadWeb(ResearchTool):
    name = "web"
    async def lookup(self, q):
        return ResearchResult(available=False, tool_name="web")


def _analysis(reply="ok", *, ts: TurnSignals | None = None, wants_proposal=False):
    return _Analysis(
        reply=reply, detected_cta=None, cta_status="none", cta_type=None,
        cta_detail={}, should_handoff=False, learned_facts={},
        wants_proposal=wants_proposal, turn_signals=ts,
    )


def _ts(intents=None, **fields):
    t = TurnSignals(intents=intents or [])
    for k, v in fields.items():
        ev = "prospect_stated"
        if isinstance(v, tuple):
            v, ev = v
        t.fields[k] = IncomingSignal(value=v, evidence=ev)
    return t


def _orch(*analyses, canon="Acme Corp"):
    return Orchestrator(
        analysis=AnalysisAgent(FakeLLMClient(structured=[
            _CanonResult(canonical=canon, intent_hint="exhibitor")])),
        research=ResearchAgent(
            FakeLLMClient(structured=[_Synthesis(
                sector="Web Development", company_size="20", hq=None, founder=None,
                designation=None, seniority=None, is_technical=None, person_company_match=None)]),
            explorer=StubExplorer(), tools=[_DeadWeb()]),
        persuasion=PersuasionAgent(FakeLLMClient(
            structured=[_PersonaChoice(persona="it_tech_service", reason="s"), *analyses],
            responses=["Good to hear from you. What are you hoping to get out of TEG?"])),
    )


async def _pipeline(orch):
    return await orch.run_pipeline(
        IntakePayload(person_name="Rohan B", company_name="Acme Corp"))


# --- state gets seeded + persisted ------------------------------------

async def test_discovery_state_is_seeded_from_research_when_the_sector_is_known():
    orch = Orchestrator(
        analysis=AnalysisAgent(FakeLLMClient(structured=[
            _CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor")])),
        research=ResearchAgent(
            FakeLLMClient(structured=[_Synthesis(
                sector=None, company_size=None, hq=None, founder=None, designation=None,
                seniority=None, is_technical=None, person_company_match=None)]),
            explorer=StubExplorer(), tools=[_DeadWeb()]),
        persuasion=PersuasionAgent(FakeLLMClient(
            structured=[_PersonaChoice(persona="it_tech_service", reason="s"), _analysis()],
            responses=["Hi."])),
    )
    await orch.run_pipeline(
        IntakePayload(person_name="Tapan Patel", company_name="Third Rock Techkno"))
    async with SessionLocal() as s:
        cs = (await s.execute(select(ChatSession))).scalars().first()
    ds = DiscoveryState.model_validate(cs.discovery_state)
    assert ds.get("what_they_sell") is not None
    assert ds.get("what_they_sell").current().evidence == "verified_company"


async def test_discovery_state_seed_is_empty_when_research_found_nothing():
    res = await _pipeline(_orch(_analysis()))
    async with SessionLocal() as s:
        cs = (await s.execute(select(ChatSession))).scalars().first()
    ds = DiscoveryState.model_validate(cs.discovery_state)
    assert ds.get("what_they_sell") is None   # nothing to seed, no crash


async def test_turn_persists_discovery_state_and_derives_learned_facts():
    orch = _orch(_analysis(
        "Got it — which industries are your buyers in?",
        ts=_ts(objective="new client acquisition",
               objective_type=("sales", "inference"),
               desired_outcome="3-5 enterprise clients"),
    ))
    res = await _pipeline(orch)
    await orch.run_turn(res.session_id, "we want new clients, 3-5 enterprise ones")

    async with SessionLocal() as s:
        cs = (await s.execute(select(ChatSession).where(ChatSession.id == res.session_id))).scalar_one()
    ds = DiscoveryState.model_validate(cs.discovery_state)
    assert ds.get("objective").current().value == "new client acquisition"
    # learned_facts is the flattened view ProposalAgent still reads
    assert cs.learned_facts.get("objective") == "new client acquisition"
    assert cs.learned_facts.get("desired_outcome") == "3-5 enterprise clients"


# --- the proposal trigger is now policy-gated -----------------------

async def test_model_wants_proposal_but_discovery_thin_is_overruled():
    orch = _orch(_analysis(
        "Sure, one moment.",
        ts=_ts(objective="some exposure"),
        wants_proposal=True,
    ))
    res = await _pipeline(orch)
    turn = await orch.run_turn(res.session_id, "just send me a proposal")

    assert turn.wants_proposal is False   # policy said no — discovery is thin
    async with SessionLocal() as s:
        assert (await s.execute(select(ProposalRow))).scalars().first() is None


async def test_explicit_request_soft_defers_then_pending_brief_reflects_it():
    orch = _orch(_analysis(
        "Happy to — one or two more details first.",
        ts=_ts(intents=["requested_proposal"], objective="win clients"),
        wants_proposal=True,
    ))
    res = await _pipeline(orch)
    await orch.run_turn(res.session_id, "can you send me a proposal?")

    async with SessionLocal() as s:
        cs = (await s.execute(select(ChatSession).where(ChatSession.id == res.session_id))).scalar_one()
    ds = DiscoveryState.model_validate(cs.discovery_state)
    assert ds.soft_defer_count == 1
    assert "more details" in ds.pending_brief.lower() or "tailored" in ds.pending_brief.lower()


async def test_insist_allows_proposal_and_marks_missing_context():
    orch = _orch(_analysis(
        "Of course — sending it now.",
        ts=_ts(intents=["insists_proposal"], objective="exposure"),
        wants_proposal=True,
    ))
    res = await _pipeline(orch)
    # NOTE: run_turn will try to generate the proposal via chat.py, but run_turn
    # itself only sets wants_proposal; generation is triggered by the WS handler.
    turn = await orch.run_turn(res.session_id, "no, just send it, I'm short on time")

    assert turn.wants_proposal is True
    async with SessionLocal() as s:
        cs = (await s.execute(select(ChatSession).where(ChatSession.id == res.session_id))).scalar_one()
    assert "_missing_context" in cs.learned_facts
    assert isinstance(cs.learned_facts["_missing_context"], list)


# --- flag-off is untouched ----------------------------------------

async def test_flag_off_leaves_discovery_state_empty(monkeypatch):
    monkeypatch.setenv("DISCOVERY_V2_ENABLED", "false")
    from config.settings import get_settings
    get_settings.cache_clear()

    orch = _orch(_analysis("hi", wants_proposal=False))
    res = await _pipeline(orch)
    await orch.run_turn(res.session_id, "tell me more")

    async with SessionLocal() as s:
        cs = (await s.execute(select(ChatSession).where(ChatSession.id == res.session_id))).scalar_one()
    assert cs.discovery_state == {}
    get_settings.cache_clear()
