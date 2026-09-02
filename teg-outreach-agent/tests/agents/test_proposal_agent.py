from app.agents.proposal import _PRICING_BY_PERSONA, ProposalAgent
from app.domain.schemas import (
    IntakeResult,
    Proposal,
    ProposalPackage,
    ProposalPain,
    ResearchDossier,
)
from app.kb.explorer import ExploreResult, KBExplorer
from app.llm.fake import FakeLLMClient


class _FixedExplorer(KBExplorer):
    def __init__(self, result: ExploreResult) -> None:
        self._result = result
        self.goals: list[str] = []

    async def explore(self, goal: str) -> ExploreResult:
        self.goals.append(goal)
        return self._result


def _explorer(**facts_over):
    facts = {
        "goals": "Connect Gujarat's businesses with AI and tech providers.",
        "mechanism": "Pre-scheduled 1:1 B2B meetings, a networking app, live demo space.",
        "evidence": "TEG 2024 drew 8,000+ attendees and 125+ exhibitors.",
        "pains": '[["Revenue concentrated in US clients", "15,000+ India-market decision-makers"], '
                 '["Long sales cycles", "Pre-scheduled B2B meetings compress evaluation"]]',
        "sector_peers": "NeuraMonks, ViitorCloud, Perigeon",
    }
    facts.update(facts_over)
    return _FixedExplorer(ExploreResult(found=True, confidence=0.9, facts=facts,
                                        sources=["event_goals_and_problem.md"]))


def _intake(company="DataZen Analytics"):
    return IntakeResult(
        person_name="Rohan B", company_name_raw=company, company_name_canonical=company,
        provided_fields=[], intent_hint="exhibitor", consent_status="unknown",
    )


def _dossier(sector="Software Development"):
    return ResearchDossier(
        sector=sector, relationship="cold",
        company_profile={"company_size": "30", "hq": "Ahmedabad"},
        person_profile={"designation": "CTO"},
        peer_companies=["NeuraMonks", "ViitorCloud", "Perigeon"],
    )


def _good_proposal(**over):
    base = Proposal(
        company="DataZen Analytics", person="Rohan B", person_role="CTO",
        sector="Software Development", persona="it_tech_service",
        generated_on="X", session_ref="X", version=0,
        what_you_told_us="You build BI dashboards for SMEs and want India-market clients.",
        pains=[ProposalPain(pain="Revenue concentrated in US clients",
                            teg_answer="15,000+ India-market decision-makers plus pre-scheduled B2B meetings")],
        lead_generation="Pre-scheduled B2B meetings with India-market buyers across manufacturing and BFSI, plus a live demo space.",
        proof=["TEG 2024 drew 8,000+ attendees and 125+ exhibitors."],
        recommended_package=ProposalPackage(
            name="3m x 6m stall", price_line="₹2,34,000 + GST (indicative, confirmed at booking)",
            includes=["4 exhibitor passes", "10 visitor passes"], payment_plan="25% x 4 instalments",
        ),
        peer_companies=["NeuraMonks", "ViitorCloud"],
        next_steps=["Book at techexpogujarat.com/become-an-exhibitor"],
        contact="info@techexpogujarat.com",
    )
    return base.model_copy(update=over)


async def test_build_returns_clean_proposal():
    llm = FakeLLMClient(structured=[_good_proposal()])
    p, flags = await ProposalAgent(llm, explorer=_explorer()).build(
        intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[{"role": "prospect", "content": "we want India-market clients"}],
        learned_facts={"target_market": "India"}, session_ref="ab12cd34", version=2,
    )
    assert flags == []
    assert p.version == 2 and p.session_ref == "ab12cd34"
    assert p.company == "DataZen Analytics" and p.persona == "it_tech_service"
    assert "DataZen Analytics" not in p.peer_companies


async def test_build_falls_back_on_repeated_violation():
    bad = _good_proposal(
        proof=["As Jane Doe said, \"This event completely transformed our pipeline and closed ten deals in a week.\""],
        lead_generation="Unlike other expos in Gujarat, TEG has the best footfall.",
    )
    llm = FakeLLMClient(structured=[bad, bad])
    p, flags = await ProposalAgent(llm, explorer=_explorer()).build(
        intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[], learned_facts={}, session_ref="x", version=1,
    )
    assert "uncleared_testimonial" in flags
    assert "competitor_mention" in flags
    assert "Jane Doe" not in " ".join(p.proof)
    assert "other expos" not in p.lead_generation.lower()


async def test_build_survives_explorer_miss():
    """No KB goals/pains -> proposal still builds from dossier + persona fallbacks."""
    explorer = _FixedExplorer(ExploreResult())  # found=False, empty facts
    llm = FakeLLMClient(structured=[_good_proposal()])
    p, flags = await ProposalAgent(llm, explorer=explorer).build(
        intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[], learned_facts={}, session_ref="x", version=1,
    )
    assert p.company == "DataZen Analytics"
    assert p.peer_companies  # falls back to the dossier's peers


async def test_pricing_fallback_table_has_all_personas():
    for k in ("it_tech_service", "ai_startup", "non_tech_sponsor", "visitor"):
        pkg = _PRICING_BY_PERSONA[k]
        assert "+ GST" in pkg.price_line or k == "visitor"
