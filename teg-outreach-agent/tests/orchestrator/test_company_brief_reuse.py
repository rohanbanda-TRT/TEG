"""Company Research Brief reuse — a second inquiry from the same company
should skip research entirely and reuse the stored brief; a stale entry
should trigger fresh research and overwrite it."""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.agents.analysis import AnalysisAgent, _CanonResult
from app.agents.persuasion import PersuasionAgent
from app.agents.research import ResearchAgent, _Synthesis
from app.domain.schemas import IntakePayload
from app.llm.fake import FakeLLMClient
from app.orchestrator import Orchestrator
from app.research.tools import ResearchResult, ResearchTool
from app.store.db import Base, SessionLocal, engine
from app.store.models import CompanyBriefRow
from app.store.repositories import CompanyBriefRepo
from tests.conftest import StubExplorer

pytestmark = pytest.mark.asyncio


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


class _CountingResearch(ResearchAgent):
    """Counts real research-track calls so tests can assert whether
    research actually ran, not just whether the pipeline finished."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.company_track_calls = 0
        self.person_track_calls = 0

    async def run_company_track(self, intake, *, budget=None):
        self.company_track_calls += 1
        return await super().run_company_track(intake, budget=budget)

    async def run_person_track(self, intake, *, budget=None):
        self.person_track_calls += 1
        return await super().run_person_track(intake, budget=budget)


def _orch(research: ResearchAgent) -> Orchestrator:
    # Both tests call run_pipeline() twice — queue two of everything the
    # non-research agents need per call.
    analysis = AnalysisAgent(FakeLLMClient(structured=[
        _CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor"),
        _CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor"),
    ]))
    persuasion = PersuasionAgent(FakeLLMClient(responses=[
        "Welcome back, Third Rock Techkno.",
        "Welcome back, Third Rock Techkno.",
    ]))
    return Orchestrator(analysis=analysis, research=research, persuasion=persuasion)


def _payload() -> IntakePayload:
    return IntakePayload(person_name="Rohan B", company_name="Third Rock Techkno")


async def test_second_inquiry_reuses_stored_brief_without_reresearching():
    research = _CountingResearch(
        FakeLLMClient(structured=[_Synthesis(
            sector="AI Consulting", company_size="200", hq=None, founder=None,
            designation=None, seniority=None, is_technical=None, person_company_match=None,
        )]),
        explorer=StubExplorer(), tools=[_DeadWeb()],
    )
    orch = _orch(research)

    res1 = await orch.run_pipeline(_payload())
    assert research.company_track_calls == 1
    assert research.person_track_calls == 1

    # A stored brief now exists — confirm it landed before the second call.
    async with SessionLocal() as s:
        row = await CompanyBriefRepo(s).get_by_company("Third Rock Techkno")
    assert row is not None
    assert "Company Research Brief" in row.brief_markdown

    res2 = await orch.run_pipeline(_payload())
    assert research.company_track_calls == 1, "research ran again on a fresh cache hit"
    assert research.person_track_calls == 1
    assert res2.opening_message  # the pipeline still completed end to end
    assert res1.inquiry_id != res2.inquiry_id  # two distinct inquiries, one reused brief


async def test_stale_brief_triggers_fresh_research_and_overwrites():
    research = _CountingResearch(
        FakeLLMClient(structured=[
            _Synthesis(sector="AI Consulting", company_size="200", hq=None, founder=None,
                       designation=None, seniority=None, is_technical=None, person_company_match=None),
            _Synthesis(sector="Fintech", company_size="500", hq="Mumbai", founder=None,
                       designation=None, seniority=None, is_technical=None, person_company_match=None),
        ]),
        explorer=StubExplorer(), tools=[_DeadWeb()],
    )
    orch = _orch(research)

    await orch.run_pipeline(_payload())
    assert research.company_track_calls == 1

    # Backdate the stored row past the staleness window directly — the
    # public surface for "how a brief goes stale" is time passing, not a
    # setting this test should have to fake through monkeypatching.
    async with SessionLocal() as s:
        row = (await s.execute(
            select(CompanyBriefRow).where(CompanyBriefRow.company_key == "third rock techkno")
        )).scalars().first()
        row.updated_at = datetime.now(UTC) - timedelta(days=31)
        await s.commit()

    await orch.run_pipeline(_payload())
    assert research.company_track_calls == 2, "a stale brief did not trigger fresh research"
    assert research.person_track_calls == 2

    async with SessionLocal() as s:
        row = await CompanyBriefRepo(s).get_by_company("Third Rock Techkno")
        count = len((await s.execute(
            select(CompanyBriefRow).where(CompanyBriefRow.company_key == "third rock techkno")
        )).scalars().all())
    # Overwritten IN PLACE — still exactly one row for this company (an
    # upsert, not a second row), and its updated_at proves the write is
    # from just now, not the original run.
    assert row is not None
    assert count == 1
    assert row.updated_at > datetime.now(UTC) - timedelta(minutes=1)
