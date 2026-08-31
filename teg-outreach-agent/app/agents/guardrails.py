from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.schemas import Persona
from app.kb.loader import get_kb

_RUPEE = re.compile(r"₹\s?[\d,]+(?:\.\d+)?\s*(?:crore|cr|lakh|lac|k)?", re.I)
_VISITOR_CTX = re.compile(r"\b(visitor|golden ticket)\b", re.I)
_TICKETY = re.compile(r"\b(ticket|pass|entry)\b", re.I)
_QUOTE = re.compile(r"[\"“]([^\"”]{20,})[\"”]")
_ATTRIB = re.compile(
    r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b(?=[^.]{0,40}(?:said|noted|shared|according to|remarked))|"
    r"(?:said|noted|according to|as)\s+([A-Z][a-z]+ [A-Z][a-z]+)",
    re.I,
)
_PEER_CTX = re.compile(
    r"(companies like|peers such as|alongside|exhibiting with|joined by)\s+(.+?)(?:\.|$)", re.I
)
_CAP_ORG = re.compile(r"\b([A-Z][A-Za-z0-9&.]+(?:\s+[A-Z][A-Za-z0-9&.]+){0,3})\b")
_AWAITING = re.compile(
    r"(the ticket price is|tickets cost ₹|confirmed sponsors include|the 2026 sponsors are)", re.I
)


@dataclass
class GuardrailViolation:
    code: str
    detail: str


def _cleared_names() -> set[str]:
    return {t["name"] for t in get_kb().cleared_testimonials()}


def _kb_company_names() -> set[str]:
    return {c.name for c in get_kb()._companies}  # noqa: SLF001


def check_message(text: str, *, allowed_peers: list[str], persona: Persona) -> list[GuardrailViolation]:
    out: list[GuardrailViolation] = []

    # visitor price
    for m in _RUPEE.finditer(text):
        window = text[max(0, m.start() - 40): m.end() + 40]
        wl = window.lower()
        if "stall" in wl or "sponsor" in wl:
            continue
        if _VISITOR_CTX.search(window) or _TICKETY.search(window):
            out.append(GuardrailViolation("visitor_price", window.strip()))
            break

    # missing GST on stall/sponsor price
    for m in _RUPEE.finditer(text):
        window = text[max(0, m.start() - 60): m.end() + 60]
        if re.search(r"\b(stall|sponsor|sponsorship|booth|title sponsor|partner)\b", window, re.I):
            if "gst" not in window.lower():
                out.append(GuardrailViolation("missing_gst", window.strip()))
                break

    # uncleared testimonial
    cleared = _cleared_names()
    for qm in _QUOTE.finditer(text):
        if len(qm.group(1).split()) < 12:
            continue
        span = text[max(0, qm.start() - 80): qm.end() + 80]
        names = [g for pair in _ATTRIB.findall(span) for g in pair if g]
        if names and not any(n in cleared for n in names):
            out.append(GuardrailViolation("uncleared_testimonial", qm.group(1)[:80]))
            break

    # invented peer
    kb_names_lower = {n.lower() for n in _kb_company_names()}
    allowed_lower = {p.lower() for p in allowed_peers}
    pm = _PEER_CTX.search(text)
    if pm:
        chunk = pm.group(2)
        stop = {"and", "the", "companies like", "peers such"}
        for om in _CAP_ORG.finditer(chunk):
            cand = om.group(1).strip()
            if cand.lower() in stop or len(cand) < 3:
                continue
            if cand.lower() in allowed_lower or cand.lower() in kb_names_lower:
                continue
            out.append(GuardrailViolation("invented_peer", cand))
            break

    # awaiting-as-confirmed
    am = _AWAITING.search(text)
    if am:
        out.append(GuardrailViolation("awaiting_as_confirmed", am.group(0)))

    return out


SAFE_TEMPLATES: dict[Persona, str] = {
    "it_tech_service": (
        "Tech Expo Gujarat 2026 runs 27–29 November 2026 at GUCEC, Ahmedabad, targeting "
        "250+ exhibitors and 15,000+ business visitors across manufacturing, healthcare, "
        "finance and more. Stall packages start at ₹1,17,000 + GST for a 3m x 3m stall "
        "(indicative, confirmed at booking), with pre-scheduled 1:1 buyer meetings and "
        "live demo space included. Would you like me to walk you through the stall options "
        "for your team?"
    ),
    "ai_startup": (
        "Tech Expo Gujarat 2026 (27–29 Nov 2026, GUCEC Ahmedabad) has a startup-focused "
        "Catalyst Zone at ₹35,000 + GST (indicative, confirmed at booking), plus an AI demo "
        "area and investor-matchmaking that came out of the TEG ecosystem. Want the Catalyst "
        "Zone details, or information on submitting a pitch?"
    ),
    "non_tech_sponsor": (
        "Tech Expo Gujarat 2026 (27–29 Nov 2026, GUCEC Ahmedabad) offers category-exclusive "
        "sponsorships — once a brand locks a category, direct competitors are excluded. "
        "Tiers run from the Title Sponsor at ₹35,00,000 + GST down to focused partner slots "
        "(all + GST, indicative and confirmed at booking). Shall I arrange a sponsorship call "
        "with the TEG team?"
    ),
    "visitor": (
        "Tech Expo Gujarat 2026 runs 27–29 November 2026 at GUCEC, Ahmedabad — three days of "
        "AI, SaaS, cloud, cybersecurity and industry tech with 250+ exhibitors. Entry is "
        "ticketed (there is no free entry); current pricing is on the official ticketing "
        "portal. Would you like the registration link?"
    ),
}
