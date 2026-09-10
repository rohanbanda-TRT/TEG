"""Orchestrator.run_deep_research and the run_turn mid-chat pickup — unit
level, no network (app.orchestrator.deep_research.deep_research is
monkeypatched)."""
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

import app.orchestrator.deep_research as orch_mod
from app.orchestrator import Orchestrator
from app.research.deep import DeepFindings
from app.store.db import Base, SessionLocal, engine
from app.store.models import CompanyBriefRow
from app.store.repositories import CompanyBriefRepo

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@dataclass
class _FakeSettings:
    deep_research_enabled: bool = True
    claude_cli_enabled: bool = True
    deep_research_staleness_days: int = 90


def _findings(**over) -> DeepFindings:
    base = dict(funding_status="bootstrapped", growth_trend="flat")
    base.update(over)
    return DeepFindings(**base)


async def test_gated_off_by_deep_research_enabled(monkeypatch):
    monkeypatch.setattr(orch_mod, "get_settings",
                        lambda: _FakeSettings(deep_research_enabled=False))
    calls = {"n": 0}

    async def _fake_deep(*a, **kw):
        calls["n"] += 1
        return _findings()

    monkeypatch.setattr(orch_mod, "deep_research", _fake_deep)
    await Orchestrator().run_deep_research(company_name="Acme Co", person_name="X")
    assert calls["n"] == 0


async def test_gated_off_by_claude_cli_enabled(monkeypatch):
    monkeypatch.setattr(orch_mod, "get_settings",
                        lambda: _FakeSettings(claude_cli_enabled=False))
    calls = {"n": 0}

    async def _fake_deep(*a, **kw):
        calls["n"] += 1
        return _findings()

    monkeypatch.setattr(orch_mod, "deep_research", _fake_deep)
    await Orchestrator().run_deep_research(company_name="Acme Co", person_name="X")
    assert calls["n"] == 0


async def test_runs_and_upserts_when_no_prior_deep_row(monkeypatch):
    monkeypatch.setattr(orch_mod, "get_settings", lambda: _FakeSettings())
    calls = {"n": 0}

    async def _fake_deep(company_name, person_name, *, cli=None):
        calls["n"] += 1
        return _findings(funding_status="Series A, $5M (2022)")

    monkeypatch.setattr(orch_mod, "deep_research", _fake_deep)
    await Orchestrator().run_deep_research(company_name="Acme Co", person_name="X")
    assert calls["n"] == 1

    async with SessionLocal() as s:
        row = await CompanyBriefRepo(s).get_by_company("Acme Co")
    assert row is not None
    assert row.depth == "deep"
    assert row.deep_findings_json["funding_status"] == "Series A, $5M (2022)"
    assert row.deep_researched_at is not None


async def test_skips_when_a_fresh_deep_row_already_exists(monkeypatch):
    monkeypatch.setattr(orch_mod, "get_settings", lambda: _FakeSettings())
    async with SessionLocal() as s:
        await CompanyBriefRepo(s).upsert_deep_findings("Acme Co", _findings())
        await s.commit()

    calls = {"n": 0}

    async def _fake_deep(*a, **kw):
        calls["n"] += 1
        return _findings()

    monkeypatch.setattr(orch_mod, "deep_research", _fake_deep)
    await Orchestrator().run_deep_research(company_name="Acme Co", person_name="X")
    assert calls["n"] == 0, "a fresh deep row should not trigger another pass"


async def test_stale_deep_row_triggers_another_pass(monkeypatch):
    monkeypatch.setattr(orch_mod, "get_settings", lambda: _FakeSettings())
    async with SessionLocal() as s:
        row = await CompanyBriefRepo(s).upsert_deep_findings("Acme Co", _findings())
        await s.flush()
        row.deep_researched_at = datetime.now(UTC) - timedelta(days=91)
        await s.commit()

    calls = {"n": 0}

    async def _fake_deep(*a, **kw):
        calls["n"] += 1
        return _findings()

    monkeypatch.setattr(orch_mod, "deep_research", _fake_deep)
    await Orchestrator().run_deep_research(company_name="Acme Co", person_name="X")
    assert calls["n"] == 1


async def test_never_raises_when_deep_research_itself_fails(monkeypatch):
    monkeypatch.setattr(orch_mod, "get_settings", lambda: _FakeSettings())

    async def _boom(*a, **kw):
        raise RuntimeError("network exploded")

    monkeypatch.setattr(orch_mod, "deep_research", _boom)
    await Orchestrator().run_deep_research(company_name="Acme Co", person_name="X")  # must not raise

    async with SessionLocal() as s:
        row = await CompanyBriefRepo(s).get_by_company("Acme Co")
    assert row is None  # nothing was saved, but nothing broke either


async def test_run_turn_folds_in_a_fresh_deep_brief():
    orch = Orchestrator()
    session_started = datetime.now(UTC) - timedelta(minutes=5)
    async with SessionLocal() as s:
        await CompanyBriefRepo(s).upsert_deep_findings(
            "Acme Co", _findings(funding_status="bootstrapped"),
        )
        await s.commit()

    picked_up = await orch_mod.pickup_deep_research("Acme Co", session_started)
    assert picked_up is not None
    assert picked_up["funding_status"] == "bootstrapped"


async def test_run_turn_ignores_a_deep_brief_older_than_the_session():
    orch = Orchestrator()
    async with SessionLocal() as s:
        row = await CompanyBriefRepo(s).upsert_deep_findings("Acme Co", _findings())
        await s.flush()
        row.deep_researched_at = datetime.now(UTC) - timedelta(days=1)
        await s.commit()

    session_started = datetime.now(UTC)  # session started AFTER the deep pass
    picked_up = await orch_mod.pickup_deep_research("Acme Co", session_started)
    assert picked_up is None


async def test_run_turn_pickup_returns_none_for_a_light_only_company():
    orch = Orchestrator()
    picked_up = await orch_mod.pickup_deep_research("Never Researched Co", datetime.now(UTC))
    assert picked_up is None
