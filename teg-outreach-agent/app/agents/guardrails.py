from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.schemas import Persona
from app.kb.facts import load as _load_facts

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

# Names of other Gujarat / India tech expos and generic competitor phrasing.
_COMPETITOR = re.compile(
    r"\b(EFY\s*Expo|Tech\s*Vapi|Vibrant\s*Gujarat|"
    r"other\s+(?:expos?|events?|shows?)|compared\s+to\s+other|unlike\s+(?:other|the\s+other|EFY|Tech))\b",
    re.I,
)
_COMMITMENT = re.compile(
    r"\b(by\s+signing|you\s+(?:hereby\s+)?agree\s+to|this\s+(?:proposal|document)\s+constitutes|"
    r"binding\s+(?:offer|agreement|quote)|authoris?ed\s+signator|signature\s*[:_]|signatory\s*[:_])",
    re.I,
)


@dataclass
class GuardrailViolation:
    code: str
    detail: str


def _cleared_names() -> set[str]:
    return {t.name for t in _load_facts().cleared_testimonials}


def _kb_company_names() -> set[str]:
    return set(_load_facts().exhibitor_names)


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

    # competitor mention (proposals must not name / compare against other events)
    cm = _COMPETITOR.search(text)
    if cm:
        out.append(GuardrailViolation("competitor_mention", cm.group(0)))

    # commitment / signature language (a proposal is an information document, not a contract)
    lm = _COMMITMENT.search(text)
    if lm:
        out.append(GuardrailViolation("commitment_language", lm.group(0)))

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


PROPOSAL_SAFE_SECTIONS: dict[str, dict[Persona, str]] = {
    "what_you_told_us": {
        "it_tech_service": "You run a technology services company and are exploring how Tech Expo Gujarat 2026 could support your business development.",
        "ai_startup": "You run an early-stage AI/technology company and are exploring an affordable way to showcase it and meet investors and buyers at Tech Expo Gujarat 2026.",
        "non_tech_sponsor": "Your company is exploring a sponsorship association with Tech Expo Gujarat 2026 to build brand presence around the region's innovation story.",
        "visitor": "You are considering attending Tech Expo Gujarat 2026 to discover technology solutions relevant to your work.",
    },
    "lead_generation": {
        "it_tech_service": "Tech Expo Gujarat runs pre-scheduled 1:1 B2B meetings and a networking app, so you engage qualified decision-makers rather than waiting for casual footfall, with a live demo space to show your product working.",
        "ai_startup": "The event's pre-scheduled B2B meetings, Experience Zone demos and investor track put you in front of enterprise buyers and a 15+ VC pool in a few days.",
        "non_tech_sponsor": "A category-exclusive sponsorship gives you omnichannel visibility (venue, digital, print, regional media) and C-suite networking alongside keynote speakers.",
        "visitor": "In three days you can meet 250+ exhibitors across 18 industries and follow up through the TEG app, compressing months of vendor evaluation.",
    },
    "pain_answer": {
        "it_tech_service": "Tech Expo Gujarat connects you with 15,000+ cross-industry decision-makers and pre-scheduled meetings tuned to your target sectors.",
        "ai_startup": "The Catalyst Zone (₹35,000 + GST, indicative and confirmed at booking) plus the investor track give a small team an affordable route to buyers and VCs.",
        "non_tech_sponsor": "Category exclusivity means once you lock a category, direct competitors are excluded, and your brand is tied to the region's innovation narrative.",
        "visitor": "All the relevant providers are in one place, demonstrating live, so you can shortlist and meet founders directly.",
    },
    "proof_bullet": {
        "it_tech_service": "TEG 2024 drew 8,000+ attendees and 125+ exhibitors; TEG 2026 targets 15,000+ and 250+.",
        "ai_startup": "The TEG Business Retreat 2025 helped facilitate ₹1.5 crore in funding raised in one day (organizer-stated).",
        "non_tech_sponsor": "TEG 2024 had 50+ sponsors and 8,000+ attendees; it is Gujarat's largest tech expo.",
        "visitor": "TEG 2024 brought 8,000+ attendees and 125+ exhibitors together over two days.",
    },
    "next_step": {
        "it_tech_service": "Review the stall options and book at techexpogujarat.com/become-an-exhibitor, or reply here to have the team walk you through it.",
        "ai_startup": "Ask about the Catalyst Zone or the startup pitch track at techexpogujarat.com, or reply here.",
        "non_tech_sponsor": "Request a sponsorship call via techexpogujarat.com/become-a-sponsor.",
        "visitor": "Register at events.techexpogujarat.com when you're ready.",
    },
}
