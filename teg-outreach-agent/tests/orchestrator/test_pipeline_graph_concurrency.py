"""Proves Phase 6's actual point: research_company / research_person /
verify_relevant_teg_claims genuinely run CONCURRENTLY inside a real
Orchestrator.run_pipeline() call — not just that app/graph/'s runner works
in isolation (tests/graph/test_runner.py already proves that). Same
timing-based technique, applied end to end this time.
"""
import asyncio
import time

import pytest

from app.agents.analysis import AnalysisAgent, _CanonResult
from app.agents.persuasion import PersuasionAgent
from app.agents.research import ResearchAgent, _Synthesis
from app.domain.schemas import IntakePayload
from app.llm.fake import FakeLLMClient
from app.orchestrator import Orchestrator
from app.research.tools import ResearchResult, ResearchTool
from app.store.db import Base, engine
from tests.conftest import StubExplorer

pytestmark = pytest.mark.asyncio

_SLEEP_S = 0.2


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


async def test_research_layer_runs_concurrently_in_a_real_pipeline_run(monkeypatch):
    timestamps: dict[str, float] = {}

    class _TimedResearch(ResearchAgent):
        async def run_company_track(self, intake, *, budget=None):
            # Recorded at START, not completion — this is what actually
            # proves the graph SCHEDULED the three nodes concurrently. A
            # completion timestamp would be misleading here: verify_relevant_
            # teg_claims has no internal await point (it's a synchronous file
            # read), so it finishes near-instantly regardless of whether it
            # started alongside company/person or was queued after them.
            timestamps["company"] = time.monotonic()
            await asyncio.sleep(_SLEEP_S)
            return await super().run_company_track(intake, budget=budget)

        async def run_person_track(self, intake, *, budget=None):
            timestamps["person"] = time.monotonic()
            await asyncio.sleep(_SLEEP_S)
            return await super().run_person_track(intake, budget=budget)

    import app.orchestrator.graph_nodes as graph_nodes_mod

    real_read_flags = graph_nodes_mod.read_verification_flags

    def _timed_read_flags(intake):
        timestamps["verify"] = time.monotonic()
        return real_read_flags(intake)

    monkeypatch.setattr(graph_nodes_mod, "read_verification_flags", _timed_read_flags)

    analysis = AnalysisAgent(FakeLLMClient(structured=[
        _CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor"),
    ]))
    research = _TimedResearch(
        FakeLLMClient(structured=[_Synthesis(
            sector="AI Consulting", company_size="200", hq=None, founder=None,
            designation=None, seniority=None, is_technical=None, person_company_match=None,
        )]),
        explorer=StubExplorer(), tools=[_DeadWeb()],
    )
    persuasion = PersuasionAgent(FakeLLMClient(responses=["Welcome back, Third Rock Techkno."]))
    orch = Orchestrator(analysis=analysis, research=research, persuasion=persuasion)

    t0 = time.monotonic()
    res = await orch.run_pipeline(IntakePayload(person_name="Rohan B", company_name="Third Rock Techkno"))
    elapsed = time.monotonic() - t0

    assert res.opening_message  # the pipeline actually completed end to end
    assert set(timestamps) == {"company", "person", "verify"}
    # Concurrent: company/person (each sleeping _SLEEP_S) and verify (near-
    # instant) all land close together, not staggered by _SLEEP_S each.
    spread = max(timestamps.values()) - min(timestamps.values())
    assert spread < _SLEEP_S / 2, f"nodes did not run concurrently (spread={spread:.3f}s)"
    # And the whole pipeline (analyze_intake + the research layer +
    # persuasion_init + DB writes) took roughly one _SLEEP_S, not two —
    # proving research_company/research_person aren't serialized end to end.
    assert elapsed < _SLEEP_S * 1.75, f"pipeline took {elapsed:.3f}s — looks serialized, not concurrent"
