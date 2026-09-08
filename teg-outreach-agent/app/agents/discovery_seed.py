"""Seed a DiscoveryState from the pre-conversation research dossier.

Research facts enter as ``verified_company`` / ``verified_teg`` signals at the
dossier's own confidence. The conversation then *upgrades* them to
``prospect_stated`` on confirmation, or *conflicts* them on contradiction.

Only fields research can genuinely establish are seeded — chiefly
``what_they_sell``. This is what lets a well-researched company skip the
"so what do you do?" question (adjustment #2), while a thinly-researched one
(low confidence) still gets asked.
"""
from __future__ import annotations

from app.domain.discovery import DiscoveryState, Signal
from app.domain.schemas import IntakeResult, ResearchDossier

_DEFAULT_CONF = 0.5


def seed_from_dossier(dossier: ResearchDossier, intake: IntakeResult) -> DiscoveryState:
    st = DiscoveryState()
    cp = dossier.company_profile or {}
    fc = dossier.field_confidence or {}

    # what_they_sell — the sector is the cleanest signal; the overview is often
    # a "no KB file for this company" note, so only use it if it looks like a
    # real description.
    sector = (cp.get("sector") or dossier.sector or "").strip()
    overview = (cp.get("overview") or "").strip()
    if sector:
        st.field("what_they_sell").signals.append(Signal(
            value=sector,
            evidence="verified_company",
            source_turn=0,
            confidence=float(fc.get("sector", _DEFAULT_CONF)),
        ))
        st.field("what_they_sell")._recompute_status()
    elif overview and not overview.lower().startswith(("no file", "no dedicated", "not found")):
        st.field("what_they_sell").signals.append(Signal(
            value=overview[:300],
            evidence="verified_company",
            source_turn=0,
            confidence=float(fc.get("overview", _DEFAULT_CONF)),
        ))
        st.field("what_they_sell")._recompute_status()

    return st
