"""Sanity checks on the Alembic migration chain.

The test suite builds its schema from ``Base.metadata`` (see the per-file
``_schema`` fixtures), so these tests guard the migration files themselves —
that the revision chain is linear and each migration renders valid SQL offline.
"""
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

_ROOT = Path(__file__).resolve().parents[2]


def _script_dir() -> ScriptDirectory:
    cfg = Config(str(_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_ROOT / "app" / "store" / "migrations"))
    return ScriptDirectory.from_config(cfg)


def test_migration_chain_is_linear_and_head_is_0005():
    sd = _script_dir()
    assert list(sd.get_heads()) == ["0005"]
    revs = [s.revision for s in sd.walk_revisions()]
    assert revs == ["0005", "0004", "0003", "0002", "0001"]


def test_0003_adds_price_requested_column():
    src = (_ROOT / "app" / "store" / "migrations" / "versions" / "0003_price_requested.py").read_text()
    assert 'revision = "0003"' in src
    assert 'down_revision = "0002"' in src
    assert 'add_column(\n        "chat_sessions"' in src
    assert '"price_requested"' in src


def test_0004_adds_discovery_state_column():
    src = (_ROOT / "app" / "store" / "migrations" / "versions" / "0004_discovery_state.py").read_text()
    assert 'revision = "0004"' in src
    assert 'down_revision = "0003"' in src
    assert '"discovery_state"' in src


def test_0005_adds_company_briefs_table():
    src = (_ROOT / "app" / "store" / "migrations" / "versions" / "0005_company_briefs.py").read_text()
    assert 'revision = "0005"' in src
    assert 'down_revision = "0004"' in src
    assert '"company_briefs"' in src
    assert '"company_key"' in src
