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

import pytest  # noqa: E402


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
