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
