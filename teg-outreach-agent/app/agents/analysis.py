from __future__ import annotations

import re

from pydantic import BaseModel

from app.agents.base import Agent
from app.domain.schemas import IntakePayload, IntakeResult, IntentHint
from app.kb._names import _token_set_ratio
from app.kb.loader import get_kb
from app.obs import get_logger

_log = get_logger("agent.analysis")

_HONORIFICS = re.compile(r"^\s*(mr|mrs|ms|dr|shri|smt|prof)\.?\s+", re.I)

_PARTICIPATION_MAP = {
    "visitor": "visitor", "exhibitor": "exhibitor", "sponsor": "sponsor",
    "startup_pitch": "startup_pitch", "startup pitch": "startup_pitch",
    "speaker": "speaker",
}

_MESSAGE_HINTS = [
    (re.compile(r"\b(exhibit|stall|booth)\b", re.I), "exhibitor"),
    (re.compile(r"\b(sponsor|partner)\b", re.I), "sponsor"),
    (re.compile(r"\b(pitch|funding|investor)\b", re.I), "startup_pitch"),
    (re.compile(r"\b(visit|attend|ticket|pass)\b", re.I), "visitor"),
]


class _CanonResult(BaseModel):
    canonical: str
    intent_hint: IntentHint


def _clean_name(raw: str) -> str:
    name = _HONORIFICS.sub("", raw or "").strip()
    name = " ".join(name.split())
    return name.title()


def _guess_intent(payload: IntakePayload) -> IntentHint:
    pt = (payload.participation_type or "").strip().lower()
    if pt in _PARTICIPATION_MAP:
        return _PARTICIPATION_MAP[pt]  # type: ignore[return-value]
    msg = payload.message or ""
    for rx, hint in _MESSAGE_HINTS:
        if rx.search(msg):
            return hint  # type: ignore[return-value]
    return "unknown"


class AnalysisAgent(Agent):
    async def run(self, payload: IntakePayload) -> IntakeResult:
        person = _clean_name(payload.person_name)
        raw_company = payload.company_name.strip()

        kb = get_kb()
        kb_names = [c.name for c in kb._companies]  # noqa: SLF001
        system = (
            "You normalise a company name for an event CRM. Only expand an abbreviation "
            "or partial name if it clearly matches one of the known companies provided. "
            "Otherwise return the input unchanged. Also give a best-guess intent_hint."
        )
        user = (
            f"Company as entered: {raw_company!r}\n"
            f"Message (may be empty): {payload.message or ''!r}\n"
            f"Known companies: {', '.join(kb_names[:400])}"
        )
        canon = await self.llm.generate_structured(
            system=system,
            messages=[{"role": "user", "content": user}],
            schema=_CanonResult,
        )

        canonical = canon.canonical.strip() or raw_company
        matches_input = _token_set_ratio(canonical, raw_company) >= 0.5
        matches_kb = any(_token_set_ratio(canonical, n) >= 0.9 for n in kb_names)
        if not (matches_input or matches_kb):
            canonical = raw_company

        provided = [
            f for f in (
                "email", "phone", "city", "designation", "participation_type",
                "tech_category", "message", "preferred_contact_time",
            )
            if getattr(payload, f) not in (None, "")
        ]

        if payload.consent is True:
            consent = "given"
        elif payload.consent is False:
            consent = "not_given"
        else:
            consent = "unknown"

        explicit_intent = _guess_intent(payload)
        intent = explicit_intent if explicit_intent != "unknown" else canon.intent_hint

        _log.info(
            "intake  person=%r  company=%r -> %r  intent=%s  consent=%s  provided=%s",
            person, raw_company, canonical, intent, consent, provided or "-",
        )
        return IntakeResult(
            person_name=person,
            company_name_raw=raw_company,
            company_name_canonical=canonical,
            provided_fields=provided,
            intent_hint=intent,
            consent_status=consent,
        )
