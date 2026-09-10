"""Reads the scheduled TEG-claim verification harness's most recent output.

Read-only, no live call — this is what keeps the verification harness
(docs/superpowers/specs/2026-09-10-verification-harness-and-graph-design.md
§3.1) out of the per-inquiry latency budget entirely. Verification happens
on its own schedule (scripts/run_verification.py); the pipeline only ever
reads whatever the most recent scheduled pass wrote.
"""
from __future__ import annotations

from pathlib import Path

from app.domain.schemas import IntakeResult
from app.verify.claims import CLAIMS as _VERIFY_CLAIMS
from config.settings import get_settings

# Intent hints that don't cleanly map to a pricing-sensitive claim set fall
# back to "consider every v1 claim relevant" rather than guessing.
_INTENT_RELEVANT_CLAIMS: dict[str, tuple[str, ...]] = {
    "exhibitor": ("payment_plan_dates", "dates_venue", "scale_targets"),
    "sponsor": ("payment_plan_dates", "dates_venue", "scale_targets"),
    "startup_pitch": ("payment_plan_dates", "dates_venue", "scale_targets"),
    "visitor": ("visitor_pricing_published", "dates_venue"),
    "speaker": ("dates_venue", "scale_targets"),
}


def _latest_verification_log() -> Path | None:
    log_dir = Path(get_settings().kb_path).resolve() / "_verification_log"
    if not log_dir.is_dir():
        return None
    files = sorted(log_dir.glob("*.md"))
    return files[-1] if files else None


def read_verification_flags(intake: IntakeResult) -> list[str]:
    path = _latest_verification_log()
    if path is None:
        return []
    relevant = set(_INTENT_RELEVANT_CLAIMS.get(intake.intent_hint, tuple(_VERIFY_CLAIMS)))
    flags: list[str] = []
    for line in path.read_text("utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or set(cells[0]) <= set("- "):
            continue
        claim_id, status = cells[0], cells[3]
        if claim_id in relevant and status == "conflicting":
            flags.append(f"verification::{claim_id}")
    return flags
