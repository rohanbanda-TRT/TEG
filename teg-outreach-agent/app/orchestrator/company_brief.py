"""Company Research Brief cache — reuse a saved dossier across inquiries
from the same company instead of re-researching every time.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.domain.schemas import IntakeResult, ResearchDossier
from app.obs import get_logger
from app.research.brief import render_company_brief
from app.store.db import SessionLocal
from app.store.repositories import CompanyBriefRepo
from config.settings import get_settings

_log = get_logger("orchestrator")


def dossier_is_thin(dossier: ResearchDossier) -> bool:
    """A dossier can complete a real research pass and still have found
    almost nothing about the company — an obscure company with little web
    footprint, the same class of case that trips deep_research's
    stop_sequence failure. That still gets cached by save_company_brief
    (it IS a real, completed pass, not a timeout fallback), but reusing a
    near-empty result forever is worse than re-researching: a later attempt
    may simply do better, and there is nothing worth protecting by keeping
    the sparse answer authoritative for company_brief_staleness_days."""
    return not dossier.company_profile and not dossier.sector


async def reuse_company_brief(intake: IntakeResult) -> ResearchDossier | None:
    """None on a miss, a stale hit, or a thin hit — either way, run_pipeline
    falls through to normal research. Never raises: a brief-lookup failure
    degrades to "do the research," not to a broken pipeline."""
    try:
        async with SessionLocal() as s:
            row = await CompanyBriefRepo(s).get_by_company(intake.company_name_canonical)
    except Exception as exc:  # noqa: BLE001 — a cache miss must never break the pipeline
        _log.warning("company brief lookup failed (%s); researching fresh", exc)
        return None
    if row is None or not row.dossier_json:
        # The empty-dossier_json case is real, not defensive filler: a
        # deep-only pass (upsert_deep_findings) can create a row before any
        # light pass ever has, with light_researched_at defaulted to "now"
        # at insert time even though no light research happened — without
        # this check that row would look like a fresh, valid light-research
        # hit and skip real research entirely.
        return None
    age = datetime.now(UTC) - row.light_researched_at
    staleness = timedelta(days=get_settings().company_brief_staleness_days)
    if age > staleness:
        _log.info("company brief for %r is stale (age=%s > %s) -> researching fresh",
                  intake.company_name_canonical, age, staleness)
        return None
    dossier = ResearchDossier.model_validate(row.dossier_json)
    if dossier_is_thin(dossier):
        _log.info("company brief for %r is fresh but empty -> researching fresh anyway",
                   intake.company_name_canonical)
        return None
    return dossier


async def save_company_brief(intake: IntakeResult, dossier: ResearchDossier) -> None:
    """Never raises out into run_pipeline — a failed save just means the
    NEXT inquiry for this company re-researches too, which is safe."""
    try:
        markdown = render_company_brief(dossier)
        async with SessionLocal() as s:
            await CompanyBriefRepo(s).upsert(intake.company_name_canonical, dossier, markdown)
            await s.commit()
        write_prospect_brief_file(intake.company_name_canonical, markdown)
    except Exception as exc:  # noqa: BLE001
        _log.warning("saving company brief for %r failed (%s)", intake.company_name_canonical, exc)


def write_prospect_brief_file(company_name: str, markdown: str) -> None:
    """teg-kb-agent/prospect_briefs/<slug>.md — a sibling of
    knowledge_base/, same "generated staging artifact, not sourced content"
    pattern _verification_log/ already established. Never written INTO
    knowledge_base/ — that directory is TEG's own sourced content, never
    prospect data."""
    from app.kb._names import _norm

    slug = _norm(company_name).replace(" ", "-") or "company"
    briefs_dir = Path(get_settings().kb_path).resolve().parent / "prospect_briefs"
    briefs_dir.mkdir(parents=True, exist_ok=True)
    (briefs_dir / f"{slug}.md").write_text(markdown, encoding="utf-8")
