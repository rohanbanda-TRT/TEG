"""Background deep-research pass — scheduling, freshness checks, and lookup.

See docs/superpowers/specs/2026-09-09-background-deep-research-design.md.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.obs import get_logger
from app.research.deep import DeepFindings, deep_research
from app.store.db import SessionLocal
from app.store.repositories import CompanyBriefRepo
from config.settings import get_settings

_log = get_logger("orchestrator")


async def run_deep_research_task(*, company_name: str, person_name: str) -> None:
    """Background-task entrypoint — app/api/inquiries.py schedules this via
    FastAPI BackgroundTasks AFTER the response (the opening message) is
    already computed, so it can never delay anything the prospect sees.
    Never raises: a background task that raises has nowhere useful to send
    that exception. See
    docs/superpowers/specs/2026-09-09-background-deep-research-design.md §3.2/§3.4.
    """
    settings = get_settings()
    # deep_research() has no fallback backend the way ResearchAgent does
    # (Tavily/Brave) — it's Claude-only by design (§3.1 of the spec), so
    # claude_cli_enabled=False means "can't run at all," not just "prefer a
    # different tool." This is also what makes the suite safe: tests force
    # CLAUDE_CLI_ENABLED=false (see tests/conftest.py) the same way they
    # already do for every other ClaudeCli-backed caller, so a test hitting
    # POST /inquiries never spawns a real subprocess via this background task.
    if not settings.deep_research_enabled or not settings.claude_cli_enabled:
        return
    try:
        async with SessionLocal() as s:
            row = await CompanyBriefRepo(s).get_by_company(company_name)
        if row is not None and row.deep_researched_at is not None:
            age = datetime.now(UTC) - row.deep_researched_at
            staleness = timedelta(days=settings.deep_research_staleness_days)
            if age <= staleness:
                _log.info("deep brief for %r is fresh (age=%s) -> skipping", company_name, age)
                return
        _log.info("deep research starting for %r", company_name)
        findings = await deep_research(company_name, person_name)
        if findings is None:
            _log.warning("deep research produced nothing for %r", company_name)
            return
        async with SessionLocal() as s:
            await CompanyBriefRepo(s).upsert_deep_findings(company_name, findings)
            await s.commit()
        _log.info("deep research done for %r", company_name)
    except Exception as exc:  # noqa: BLE001 — a background task must never raise
        _log.warning("deep research failed for %r: %s", company_name, exc)


async def pickup_deep_research(company_name: str, session_started_at: datetime) -> dict | None:
    """Read-only, cheap: has a deep brief landed for this company SINCE
    this conversation started? Never blocks, never awaited-for — just a
    lookup. Returns the raw findings dict for the caller to fold into
    learned_facts, or None if nothing fresher than the session exists."""
    try:
        async with SessionLocal() as s:
            row = await CompanyBriefRepo(s).get_by_company(company_name)
    except Exception as exc:  # noqa: BLE001
        _log.warning("deep-research pickup lookup failed for %r: %s", company_name, exc)
        return None
    if row is None or row.deep_researched_at is None:
        return None
    if row.deep_researched_at <= session_started_at:
        return None
    return row.deep_findings_json


async def fetch_deep_findings(company_name: str) -> DeepFindings | None:
    """Used by generate_proposal — unlike pickup_deep_research (which only
    counts a deep brief NEWER than the session start), a proposal should use
    whatever deep research exists at all, however old, since using it is
    strictly better than not — staleness only governs whether
    run_deep_research_task decides to RE-research, never whether existing
    findings are worth using once they exist."""
    try:
        async with SessionLocal() as s:
            row = await CompanyBriefRepo(s).get_by_company(company_name)
    except Exception as exc:  # noqa: BLE001
        _log.warning("deep-findings lookup failed for %r: %s", company_name, exc)
        return None
    if row is None or row.deep_findings_json is None:
        return None
    return DeepFindings.model_validate(row.deep_findings_json)
