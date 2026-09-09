import asyncio
import os

# Tests use a local userspace Postgres 16 instance (no root needed).
# See teg-outreach-agent/scripts/pg.sh for start/stop; the instance lives in
# the session scratchpad and listens on 127.0.0.1:5433 with trust auth, user "teg".
# Override with DATABASE_URL in the environment to point elsewhere.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://teg@127.0.0.1:5433/teg_outreach_test",
)

# The suite must never spawn a real `claude` process, whatever the developer's
# .env says. Tests that exercise the CLI backend inject a fake ClaudeCli
# explicitly; this only stops agents self-constructing a real one. Set before
# any app import, so get_settings() caches the overridden value.
os.environ["CLAUDE_CLI_ENABLED"] = "false"
# Orchestrator.run_deep_research is itself gated on claude_cli_enabled (it
# has no fallback backend), so the line above already covers it — this is
# defense-in-depth so the background deep-research task never fires a real
# subprocess via POST /inquiries even if that gate is ever loosened.
os.environ["DEEP_RESEARCH_ENABLED"] = "false"

# Settings.discovery_v2_enabled defaults to False, but that default is only
# as real as nobody's local .env overriding it — pydantic-settings reads
# .env unconditionally, so a developer who has DISCOVERY_V2_ENABLED=true
# in their own .env (to test that path manually) would otherwise silently
# flip every test in this suite onto the discovery-v2 path, breaking tests
# that were written against (and whose whole point is proving) the legacy
# path — tests/orchestrator/test_run_turn_discovery.py's own docstring
# calls the rest of this suite "the flag-off suite," a claim that should be
# true by construction, not by accident of whoever's .env happens to run
# it. Tests that need v2 on (test_run_turn_discovery.py) already
# monkeypatch.setenv + get_settings.cache_clear() per-test to opt in, so
# forcing the default off here doesn't take anything away from them.
os.environ["DISCOVERY_V2_ENABLED"] = "false"

from typing import ClassVar

import pytest


class StubExplorer:
    """A KBExplorer stand-in for tests: canned results, no LLM and no file reads.

    Defaults describe the KB-known fixtures the suite uses (Third Rock Techkno /
    Tapan Patel). Anything else comes back as a miss, which is what an unknown
    company or person should produce.
    """

    _COMPANY: ClassVar[dict] = {
        "sector": "AI & Machine Learning",
        "website": "https://www.thirdrocktechkno.com/",
        "teg_history": "TEG 2024 exhibitor; TEG 2026 exhibitor",
        "sector_peers": "ViitorCloud, Green Apex, NeuraMonks, ZeroThreat",
    }
    _PERSON: ClassVar[dict] = {"designation": "CMO", "teg_role": "organizer"}
    _GOALS: ClassVar[dict] = {
        "goals": "Connect Gujarat's businesses with AI and tech providers.",
        "mechanism": "Pre-scheduled 1:1 B2B meetings, a networking app, live demo space.",
        "evidence": "TEG 2024 drew 8,000+ attendees and 125+ exhibitors.",
        "pains": '[["Reaching the right buyers", "15,000+ cross-industry decision-makers"], '
                 '["Long sales cycles", "Pre-scheduled B2B meetings compress evaluation"]]',
        "sector_peers": "NeuraMonks, ViitorCloud, Perigeon",
    }

    def __init__(self, known: dict | None = None) -> None:
        from app.kb.explorer import ExploreResult

        self._ExploreResult = ExploreResult
        self._known = known if known is not None else {
            "third rock techkno": self._COMPANY,
            "tapan patel": self._PERSON,
        }
        self.goals: list[str] = []

    async def explore(self, goal: str):
        self.goals.append(goal)
        g = goal.lower()
        # proposal goal: asks for goals / mechanism / pain library
        if "event_goals_and_problem.md" in g or "pain library" in g:
            return self._ExploreResult(
                found=True, confidence=0.9, facts=dict(self._GOALS),
                sources=["event_goals_and_problem.md"],
            )
        for key, facts in self._known.items():
            if key in g:
                return self._ExploreResult(
                    found=True, confidence=0.9, facts=dict(facts),
                    summary=f"KB profile for {key}", sources=[f"stub/{key}.md"],
                )
        return self._ExploreResult()


@pytest.fixture
def stub_explorer():
    return StubExplorer()


@pytest.fixture
def db_schema():
    """Sync fixture: create all tables, drop after.

    Use in SYNC tests (TestClient / websocket_connect) via the `db_schema`
    argument or `@pytest.mark.usefixtures("db_schema")`. Async tests define
    their own local async `_schema` autouse fixture instead.
    """
    from app.store.db import Base, engine

    async def _create():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    async def _drop():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    asyncio.run(_create())
    yield
    asyncio.run(_drop())
