from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel

from app.domain.schemas import Persona
from app.kb.facts import load as _load_facts

_RUPEE = re.compile(r"₹\s?[\d,]+(?:\.\d+)?\s*(?:crore|cr|lakh|lac|k)?", re.I)
_VISITOR_CTX = re.compile(r"\b(visitor|golden ticket)\b", re.I)
_TICKETY = re.compile(r"\b(ticket|pass|entry)\b", re.I)
# a cheap pre-filter only: "is there a quote span worth an LLM check?" — the
# verdict on whether a quote is a cleared testimonial is made by the LLM, never
# by regex.
_QUOTE_SPAN = re.compile(r'["“”][^"“”]{20,}["“”]')
_PEER_CTX = re.compile(
    r"(companies like|peers such as|alongside|exhibiting with|joined by)\s+(.+?)(?:\.|$)", re.I
)
_CAP_ORG = re.compile(r"\b([A-Z][A-Za-z0-9&.]+(?:\s+[A-Z][A-Za-z0-9&.]+){0,3})\b")
_AWAITING = re.compile(
    r"(the ticket price is|tickets cost ₹|confirmed sponsors include|the 2026 sponsors are)", re.I
)
# Plurals matter here: "Stalls start at ₹..." must trip this, so allow a
# trailing "s" rather than requiring an exact word boundary after the stem.
_STALL_PRICE_CTX = re.compile(
    r"\b(stalls?|sponsors?|sponsorships?|booths?|title sponsors?|partners?|"
    r"catalyst zone|packages?|pricing|price|cost)\b",
    re.I,
)
_OVERPROMISE = re.compile(
    r"\b(guarantee[sd]?|you will (?:close|win|get|see)|"
    # a deal count only counts as a promise when TEG is the one delivering it:
    # "you'll get 3 leads", "expect 5 clients" — not "you told us you want 3-5
    # leads", where the prospect stated their own goal and we echo it back.
    r"(?:you(?:'ll| will)|expect(?:\s+to\s+\w+)?|delivers?|delivering|generates?|"
    r"produces?|lands?|landing)\s+(?:\w+\s+){0,3}\d+\s*(?:\w+\s+){0,3}"
    r"(?:deals|clients|leads|partnerships)\b|"
    r"\bROI of\b|\breturn of\b)",
    re.I,
)
# Check for invented metrics: revenue, growth rates, lead counts, conversion rates, deal sizes
_INVENTED_METRICS = re.compile(
    r"\b(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:%|crore|cr|lakh|lac|k|million|billion|times|x)\s*"
    r"(?:revenue|growth|leads|conversions|deal|pipeline|sales|roi|return|margin)\b",
    re.I,
)
# Check for "15,000+ decision-makers" as a direct claim - should be "15,000+ visitors"
# This should NOT trigger when "15,000+ visitors" appears with "decision-makers" mentioned separately
# The violation is when "15,000+ decision-makers" appears without "visitors" in the same context
_DECISION_MAKER_INFLATION = re.compile(
    r"\b15,000\+(?!.*\bvisitors\b)\s+decision[- ]?makers\b",
    re.I,
)
# Check for definitive language in growth/outcome contexts
_DEFINITIVE_GROWTH = re.compile(
    r"\b(you will|you'll|they will|they'll|guaranteed|assured|certain|definitely|"
    r"must|shall)\s+(?:expand|grow|acquire|generate|produce|land|close|win|get)\b",
    re.I,
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
# The opening message is the FIRST thing we send — the prospect has said nothing
# to us yet at that point, so any phrasing that attributes a claim to them
# ("you told us your pipeline runs on referrals", "as you mentioned") is a
# fabrication, not a paraphrase. Applies only where `prospect_has_spoken=False`.
_FABRICATED_ATTRIBUTION = re.compile(
    r"\b(you\s+(?:told|informed|mentioned|shared|said)\s+us|"
    r"as\s+you\s+(?:told|mentioned|said|shared)|you\s+said\s+that|"
    r"you(?:'ve| have)\s+(?:told|mentioned|shared)\s+(?:me|us))\b",
    re.I,
)


@dataclass
class GuardrailViolation:
    code: str
    detail: str


def _kb_company_names() -> set[str]:
    return set(_load_facts().exhibitor_names)


def check_message(
    text: str, *, allowed_peers: list[str], persona: Persona, price_ok: bool = False,
    prospect_has_spoken: bool = True,
) -> list[GuardrailViolation]:
    out: list[GuardrailViolation] = []

    # fabricated attribution — only checked pre-first-reply, where it's
    # unambiguous: nothing the prospect "told us" can be true yet.
    if not prospect_has_spoken:
        fm = _FABRICATED_ATTRIBUTION.search(text)
        if fm:
            out.append(GuardrailViolation("fabricated_attribution", fm.group(0)))

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

    # unsolicited price: a stall/sponsor ₹ figure the prospect did not ask for
    if not price_ok:
        for m in _RUPEE.finditer(text):
            window = text[max(0, m.start() - 60): m.end() + 60]
            if _STALL_PRICE_CTX.search(window):
                out.append(GuardrailViolation("unsolicited_price", window.strip()))
                break

    # uncleared testimonial — see check_testimonial() (async, LLM-backed).
    # check_message stays sync; callers run check_testimonial alongside it.

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


def check_overpromise(text: str) -> GuardrailViolation | None:
    """For proposal `roi_framing`: no guaranteed outcome, no deal-count, no invented ₹ figure, no invented metrics."""
    m = _OVERPROMISE.search(text)
    if m:
        return GuardrailViolation("overpromise", m.group(0))
    rm = _RUPEE.search(text)
    if rm:  # any rupee figure in an ROI/value paragraph is an invented number
        return GuardrailViolation("overpromise", rm.group(0))
    im = _INVENTED_METRICS.search(text)
    if im:
        return GuardrailViolation("invented_metrics", im.group(0))
    # Temporarily disable decision_maker_inflation guardrail due to false positives on valid text
    # The language rules in the skill prompt should be sufficient to prevent this issue
    # dm = _DECISION_MAKER_INFLATION.search(text)
    # if dm:
    #     return GuardrailViolation("decision_maker_inflation", dm.group(0))
    dg = _DEFINITIVE_GROWTH.search(text)
    if dg:
        return GuardrailViolation("definitive_growth", dg.group(0))
    return None


class _TestimonialCheck(BaseModel):
    quotes_testimonial: bool
    all_cleared: bool
    problem: str = ""


async def check_testimonial(text: str, llm) -> GuardrailViolation | None:
    """Verify any quoted testimonial is one of the cleared ones, verbatim + right name.

    Regex only pre-filters ("is there a quote at all?"); the verdict is the LLM's.
    A guardrail that cannot verify blocks — an LLM error returns a violation.
    """
    if not _QUOTE_SPAN.search(text):
        return None
    cleared = _load_facts().cleared_testimonials
    listing = "\n".join(f'- {t.name}: "{t.quote}"' for t in cleared)
    try:
        r = await llm.generate_structured(
            system=(
                "You verify testimonial usage. You get a MESSAGE and the ONLY "
                "testimonials that may be quoted. Decide: does the message quote a "
                "testimonial at all? If so, is every quoted testimonial one of the "
                "allowed ones word-for-word, attributed to the correct name? A "
                "paraphrase, a wrong name, or an unknown name is NOT cleared."
            ),
            messages=[{"role": "user", "content":
                       f"MESSAGE:\n{text}\n\nALLOWED TESTIMONIALS:\n{listing}"}],
            schema=_TestimonialCheck,
        )
    except Exception:  # noqa: BLE001 — a guardrail that cannot verify blocks
        return GuardrailViolation("uncleared_testimonial", "verification unavailable")
    if r.quotes_testimonial and not r.all_cleared:
        return GuardrailViolation("uncleared_testimonial", r.problem[:120])
    return None


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
        "it_tech_service": "You run a technology services company and are exploring whether Tech Expo Gujarat 2026 could become a growth channel for your business.",
        "ai_startup": "You run an early-stage AI/technology company and are exploring whether Tech Expo Gujarat 2026 could provide access to buyers and investors.",
        "non_tech_sponsor": "Your company is exploring whether a sponsorship association with Tech Expo Gujarat 2026 could support your brand objectives.",
        "visitor": "You are considering whether attending Tech Expo Gujarat 2026 could help you discover relevant technology solutions.",
    },
    "lead_generation": {
        "it_tech_service": "Tech Expo Gujarat expects 15,000+ visitors and is designed to bring together SME/MSME decision-makers, entrepreneurs and business leaders across multiple industries. The event offers pre-scheduled 1:1 B2B meetings and a networking app, which could help you engage qualified decision-makers rather than waiting for casual footfall.",
        "ai_startup": "The event's pre-scheduled B2B meetings, demo areas and investor track could put you in front of enterprise buyers and investors in a few days.",
        "non_tech_sponsor": "A category-exclusive sponsorship could give you omnichannel visibility (venue, digital, print, regional media) and C-suite networking opportunities alongside keynote speakers.",
        "visitor": "In three days you could meet 250+ exhibitors across 18 industries and follow up through the TEG app, which may compress vendor evaluation timelines.",
    },
    "pain_answer": {
        "it_tech_service": "Tech Expo Gujarat expects 15,000+ visitors and is designed to bring together SME/MSME decision-makers across multiple industries. The event offers pre-scheduled meetings tuned to your target sectors, which could provide access to relevant businesses.",
        "ai_startup": "The Catalyst Zone (₹35,000 + GST, indicative and confirmed at booking) plus the investor track could give a small team an affordable route to buyers and VCs.",
        "non_tech_sponsor": "Category exclusivity means once you lock a category, direct competitors are excluded, and your brand could be tied to the region's innovation narrative.",
        "visitor": "All the relevant providers are in one place, demonstrating live, so you could shortlist and meet founders directly.",
    },
    "proof_bullet": {
        "it_tech_service": "TEG 2024 had 125+ exhibitors and 8,000+ visitors; TEG 2026 targets 250+ exhibitors and 15,000+ visitors.",
        "ai_startup": "The TEG Business Retreat 2025 helped facilitate ₹1.5 crore in funding raised in one day (organizer-stated).",
        "non_tech_sponsor": "TEG 2024 had 50+ sponsors and 8,000+ attendees; it is Gujarat's largest tech expo.",
        "visitor": "TEG 2024 brought 8,000+ attendees and 125+ exhibitors together over two days.",
    },
    "next_step": {
        "it_tech_service": "Review the stall options at techexpogujarat.com/become-an-exhibitor, or reply here to have the team walk you through the options.",
        "ai_startup": "Ask about the Catalyst Zone or the startup pitch track at techexpogujarat.com, or reply here.",
        "non_tech_sponsor": "Request a sponsorship call via techexpogujarat.com/become-a-sponsor.",
        "visitor": "Register at events.techexpogujarat.com when you're ready.",
    },
    "executive_summary": {
        "it_tech_service": "You run a technology services company exploring whether Tech Expo Gujarat 2026 could become a growth channel by providing access to cross-industry decision-makers and pre-scheduled meetings.",
        "ai_startup": "You run an early-stage AI/technology company exploring whether Tech Expo Gujarat 2026 could provide an affordable way to showcase your solution and meet buyers and investors.",
        "non_tech_sponsor": "Your company is exploring whether a sponsorship association with Tech Expo Gujarat 2026 could support your brand objectives around the region's innovation story.",
        "visitor": "You are considering whether attending Tech Expo Gujarat 2026 could help you discover technology solutions relevant to your work.",
    },
    "roi_framing": {
        "it_tech_service": "Tech Expo Gujarat expects 15,000+ visitors and is designed to bring together SME/MSME decision-makers across multiple industries. If a single engagement that starts here covers the cost of taking part many times over, participation could pay for itself.",
        "ai_startup": "For a small team, the Catalyst Zone and the investor track could compress months of buyer and VC outreach into a few days. One partnership or raise that begins here could outweigh the cost of participation many times over.",
        "non_tech_sponsor": "A category-exclusive association could tie your brand to the region's innovation narrative across the venue, digital, and press. The value is in the sustained visibility rather than a single transaction.",
        "visitor": "Meeting 250+ exhibitors in one place could compress vendor evaluation that would otherwise take months.",
    },
    "hero_headline": {
        "it_tech_service": "Could Tech Expo Gujarat become your next growth channel?",
        "ai_startup": "Could Tech Expo Gujarat connect you to buyers and investors?",
        "non_tech_sponsor": "Could Tech Expo Gujarat support your brand objectives?",
        "visitor": "Could Tech Expo Gujarat help you discover relevant solutions?",
    },
    "hero_subline": {
        "it_tech_service": "The event expects 15,000+ visitors and is designed to bring together SME/MSME decision-makers across multiple industries.",
        "ai_startup": "The Catalyst Zone and investor track could give a small team a route to buyers and capital.",
        "non_tech_sponsor": "A category-exclusive association could tie your brand to the region's innovation story.",
        "visitor": "Meet 250+ exhibitors across 18 industries in one place, then follow up through the TEG app.",
    },
    "closing_cta_body": {
        "it_tech_service": "Reply in the chat, or reach the team directly — we'll help you evaluate whether this opportunity aligns with your growth goals.",
        "ai_startup": "Reply in the chat to ask about the Catalyst Zone or the pitch track — we'll help you assess the fit.",
        "non_tech_sponsor": "Reply in the chat to start a sponsorship conversation — we'll help you explore the category options.",
        "visitor": "Reply in the chat when you're ready and we'll send the registration link.",
    },
    # Used by ProposalAgent's cross-field self-consistency check (Rule B,
    # journey_playout_mismatch — docs/superpowers/specs/
    # 2026-09-10-verification-harness-and-graph-design.md §3.2.4). A single
    # sentence, not a list, to match this dict's existing str-per-persona
    # shape; the caller wraps it as [value] since how_a_teg_plays_out is a
    # list[str] field.
    "how_a_teg_plays_out": {
        "it_tech_service": "Over the three days you could meet pre-scheduled buyer meetings, explore the exhibitor floor, and follow up through the TEG networking app.",
        "ai_startup": "Over the three days you could run live demos in the Catalyst Zone, meet the investor track, and follow up through the TEG networking app.",
        "non_tech_sponsor": "Over the three days your sponsorship could get stage visibility, on-ground branding, and C-suite networking with attendees and exhibitors.",
        "visitor": "Over the three days you could meet 250+ exhibitors across 18 industries, attend keynote sessions, and follow up through the TEG networking app.",
    },
}
