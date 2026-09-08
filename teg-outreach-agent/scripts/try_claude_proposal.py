"""Generate one real proposal through the `claude` CLI and print the result.

Makes a real, billed model call. Manual smoke check for the CLI backend:

    .venv/bin/python scripts/try_claude_proposal.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.proposal import ProposalAgent  # noqa: E402
from app.claude.cli import ClaudeCli  # noqa: E402
from app.domain.schemas import IntakeResult, ResearchDossier  # noqa: E402
from app.kb.explorer import ExploreResult, KBExplorer  # noqa: E402
from app.llm.fake import FakeLLMClient  # noqa: E402


class _StubExplorer(KBExplorer):
    """KB facts, pre-baked — this script exercises the CLI path, not the KB."""

    def __init__(self) -> None:
        pass

    async def explore(self, goal: str) -> ExploreResult:
        return ExploreResult(
            found=True, confidence=0.9,
            facts={
                "goals": "Position Gujarat at the forefront of India's technological future; "
                         "converge techpreneurs, investors and industry across sectors.",
                "mechanism": "15,000+ cross-industry decision-makers, pre-scheduled 1:1 B2B "
                             "meetings, a live demo space and the TEG networking app.",
                "evidence": "TEG 2024: 8,000+ attendees, 125+ exhibitors, 50+ sponsors. "
                            "TEG 2026 targets 15,000+ and 250+.",
                "pains": '[["Revenue concentrated in US clients", "15,000+ India-market '
                         'decision-makers plus pre-scheduled B2B matchmaking"], '
                         '["Leads are casual footfall, low intent", "Curated 1:1 meetings '
                         'with pre-qualified prospects"]]',
                "sector_peers": "ViitorCloud, NeuraMonks, Perigeon, Green Apex",
                "sector_peer_count": "12",
                "scale_note": "125+ exhibitors and 8,000+ visitors at TEG 2024; 250+ "
                              "exhibitors and 15,000+ visitors targeted for TEG 2026.",
            },
            sources=["event_goals_and_problem.md"],
        )


async def main() -> int:
    agent = ProposalAgent(
        FakeLLMClient(structured=[]),
        explorer=_StubExplorer(),
        claude_cli=ClaudeCli(),
    )

    print("calling claude ... (this makes a real, billed call)\n")
    proposal, flags = await agent.build(
        intake=IntakeResult(
            person_name="Tapan Patel", company_name_raw="Third Rock Techkno",
            company_name_canonical="Third Rock Techkno", provided_fields=[],
            intent_hint="exhibitor", consent_status="unknown",
        ),
        dossier=ResearchDossier(
            sector="AI & Machine Learning", relationship="insider",
            company_profile={"hq": "Ahmedabad", "company_size": "120",
                             "focus": "custom software and AI product engineering"},
            person_profile={"designation": "CTO"},
            peer_companies=["ViitorCloud", "NeuraMonks"],
        ),
        persona="it_tech_service",
        transcript=[
            {"role": "prospect", "content": "We mostly serve US clients and want to build an "
                                            "India-market pipeline, especially manufacturing "
                                            "and BFSI buyers."},
            {"role": "agent", "content": "What would make TEG worth it for you?"},
            {"role": "prospect", "content": "Real conversations with buyers who can sign, not "
                                            "just badge scans. We'd send 3-4 people."},
        ],
        learned_facts={"goal": "India-market pipeline",
                       "target_market": "manufacturing and BFSI",
                       "scale": "3-4 people"},
        session_ref="smoke01", version=1,
        price_requested=False,
    )

    print(f"flags: {flags or '-'}\n")
    print(f"hero_headline      : {proposal.hero_headline}")
    print(f"hero_subline       : {proposal.hero_subline}")
    print(f"\nexecutive_summary  : {proposal.executive_summary}")
    print(f"\nwhat_you_told_us   : {proposal.what_you_told_us}")
    print(f"\npains ({len(proposal.pains)}):")
    for p in proposal.pains:
        print(f"  - {p.pain}\n    -> {p.teg_answer}")
    print(f"\nsector_fit         : {[(r.lever, r.weight) for r in proposal.sector_fit]}")
    print(f"target_industries  : {proposal.target_industries}")
    print(f"industries note    : {proposal.target_industries_note}")
    print(f"peers              : {proposal.peer_companies}")
    print(f"peers_in_sector    : {proposal.peers_in_sector_total}")
    print(f"peer_context_line  : {proposal.peer_context_line}")
    print(f"\nroi_framing        : {proposal.roi_framing}")
    print(f"\npackage            : {proposal.recommended_package.name}")
    print(f"price_line         : {proposal.recommended_package.price_line!r} "
          f"(price_requested=False, so this MUST be empty)")
    print(f"\nclosing            : {proposal.closing_cta_headline}")
    print(f"                     {proposal.closing_cta_body}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
