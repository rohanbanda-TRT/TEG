"""The v1 verification claim list — short and explicit, not KB-wide. See
docs/superpowers/specs/2026-09-10-verification-harness-and-graph-design.md
§3.1.3. Values re-confirmed against the current KB (September 9, 2026 pass)
before writing this file — not carried forward from the spec unchecked."""
from __future__ import annotations

from app.verify.schemas import Claim

CLAIMS: dict[str, Claim] = {
    "dates_venue": Claim(
        id="dates_venue",
        text="Tech Expo Gujarat 2026 is on 27-29 November 2026 at GUCEC, Ahmedabad.",
        kb_source_file="event_overview/event_info.md",
    ),
    "scale_targets": Claim(
        id="scale_targets",
        text="TEG 2026 targets 15,000+ visitors, 250+ exhibitors, and 25+ speakers.",
        kb_source_file="event_overview/event_info.md",
    ),
    "visitor_pricing_published": Claim(
        id="visitor_pricing_published",
        text=(
            "TEG 2026 visitor ticket pricing (rupee amounts for the 'Regular Visitor' / "
            "'Golden Ticket' tiers) has not yet been published anywhere."
        ),
        kb_source_file="registration/registration_and_passes.md",
        check_hint=(
            "Check events.techexpogujarat.com directly with a real browser render, not just "
            "search snippets — this page renders pricing dynamically if/when it goes live."
        ),
    ),
    "payment_plan_dates": Claim(
        id="payment_plan_dates",
        text=(
            "The TEG 2026 exhibitor/sponsor payment plan is 25% each on "
            "9 Apr / 30 Jun / 31 Jul / 31 Aug 2026."
        ),
        kb_source_file="pricing/pricing_and_packages.md",
    ),
}
