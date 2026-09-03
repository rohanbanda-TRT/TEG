from app.agents.proposal import _PRICING_BY_PERSONA, ProposalAgent
from app.domain.schemas import (
    IntakeResult,
    Proposal,
    ProposalPackage,
    ProposalPain,
    ResearchDossier,
    SectorFitRow,
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
        "sector_peer_count": "12",
        "scale_note": "125+ exhibitors and 8,000+ visitors at TEG 2024; 250+ exhibitors and "
                      "15,000+ visitors targeted for TEG 2026.",
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
        executive_summary="DataZen Analytics builds BI dashboards and is exploring TEG 2026 for India buyers.",
        how_a_teg_plays_out=["Pre-event matchmaking", "Day 1 demos", "Day 2 buyer meetings"],
        roi_framing="If one India-market engagement covers the cost several times over, it pays for itself.",
        sector_fit=[SectorFitRow(lever="Buyer access", weight=5), SectorFitRow(lever="Demos", weight=4),
                    SectorFitRow(lever="Meetings", weight=5), SectorFitRow(lever="Visibility", weight=3)],
        hero_headline="Turn TEG 2026 into your India-market pipeline",
        hero_subline="Three focused days from cold outreach to booked buyer meetings.",
        section_ctas={"priorities": "See the plan", "charts": "Explore the numbers", "investment": "Get your quote"},
        closing_cta_headline="Let's make TEG 2026 count for DataZen Analytics",
        closing_cta_body="Reply in the chat, or reach the team directly — we'll take it from here.",
        peers_in_sector_total=12,
        peer_context_line="12 companies in Software Development exhibited at TEG 2024 — including the names below.",
        target_industries=["Manufacturing", "Finance"],
        target_industries_note="Your BI dashboards sell into operations and finance teams.",
    )
    return base.model_copy(update=over)


async def test_build_returns_clean_proposal():
    llm = FakeLLMClient(structured=[_good_proposal()])
    p, flags = await ProposalAgent(llm, explorer=_explorer()).build(
        intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[{"role": "prospect", "content": "we want India-market clients"}],
        learned_facts={"target_market": "India"}, session_ref="ab12cd34", version=2,
        price_requested=True,
    )
    assert flags == []
    assert p.version == 2 and p.session_ref == "ab12cd34"
    assert p.company == "DataZen Analytics" and p.persona == "it_tech_service"
    assert "DataZen Analytics" not in p.peer_companies


async def test_build_populates_new_fields():
    llm = FakeLLMClient(structured=[_good_proposal()])
    p, flags = await ProposalAgent(llm, explorer=_explorer()).build(
        intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[], learned_facts={"goal": "India clients"}, session_ref="x", version=1,
        price_requested=True,
    )
    assert p.executive_summary
    assert len(p.how_a_teg_plays_out) >= 3
    assert p.roi_framing
    assert 4 <= len(p.sector_fit) <= 6
    assert p.peers_in_sector_total == 12
    assert p.scale_note.startswith("125+ exhibitors")
    assert "Software Development" in p.peer_context_line
    assert all(1 <= r.weight <= 5 for r in p.sector_fit)


async def test_build_omits_price_when_not_requested():
    llm = FakeLLMClient(structured=[_good_proposal()])
    p, _ = await ProposalAgent(llm, explorer=_explorer()).build(
        intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[], learned_facts={}, session_ref="x", version=1, price_requested=False,
    )
    assert p.recommended_package.price_line == ""
    assert p.recommended_package.payment_plan == ""


async def test_build_flags_overpromising_roi():
    bad = _good_proposal(roi_framing="You will close 5 deals and see a guaranteed ROI of 400%.")
    llm = FakeLLMClient(structured=[bad, bad])
    p, flags = await ProposalAgent(llm, explorer=_explorer()).build(
        intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[], learned_facts={}, session_ref="x", version=1, price_requested=True,
    )
    assert "overpromise" in flags
    assert "guaranteed" not in p.roi_framing.lower()


async def test_build_falls_back_on_repeated_violation():
    bad = _good_proposal(
        lead_generation="Unlike other expos in Gujarat, TEG has the best footfall.",
    )
    llm = FakeLLMClient(structured=[bad, bad])
    p, flags = await ProposalAgent(llm, explorer=_explorer()).build(
        intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[], learned_facts={}, session_ref="x", version=1, price_requested=True,
    )
    assert "competitor_mention" in flags
    assert "other expos" not in p.lead_generation.lower()


async def test_build_survives_explorer_miss():
    """No KB goals/pains -> proposal still builds from dossier + persona fallbacks."""
    explorer = _FixedExplorer(ExploreResult())  # found=False, empty facts
    llm = FakeLLMClient(structured=[_good_proposal()])
    p, flags = await ProposalAgent(llm, explorer=explorer).build(
        intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[], learned_facts={}, session_ref="x", version=1, price_requested=True,
    )
    assert p.company == "DataZen Analytics"
    assert p.peer_companies  # falls back to the dossier's peers


async def test_pricing_fallback_table_has_all_personas():
    for k in ("it_tech_service", "ai_startup", "non_tech_sponsor", "visitor"):
        pkg = _PRICING_BY_PERSONA[k]
        assert "+ GST" in pkg.price_line or k == "visitor"


async def test_build_writes_landing_page_fields():
    llm = FakeLLMClient(structured=[_good_proposal()])
    p, flags = await ProposalAgent(llm, explorer=_explorer()).build(
        intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[], learned_facts={"goal": "leads"}, session_ref="x", version=1,
        price_requested=True,
    )
    assert p.hero_headline and p.hero_subline
    assert p.closing_cta_headline and p.closing_cta_body


async def test_build_flags_overpromising_hero():
    bad = _good_proposal(hero_headline="You will 10x your pipeline, guaranteed.")
    llm = FakeLLMClient(structured=[bad, bad])
    p, flags = await ProposalAgent(llm, explorer=_explorer()).build(
        intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[], learned_facts={}, session_ref="x", version=1, price_requested=True,
    )
    assert "overpromise" in flags
    assert "guaranteed" not in p.hero_headline.lower()


async def test_build_clamps_section_ctas():
    bad = _good_proposal(section_ctas={
        "priorities": "x" * 80, "charts": "ok", "investment": "ok", "bogus": "drop me",
    })
    llm = FakeLLMClient(structured=[bad])
    p, _ = await ProposalAgent(llm, explorer=_explorer()).build(
        intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[], learned_facts={}, session_ref="x", version=1, price_requested=True,
    )
    assert set(p.section_ctas) <= {"priorities", "charts", "investment"}
    assert all(len(v) <= 40 for v in p.section_ctas.values())


async def test_build_clamps_target_industries_to_the_official_list():
    bad = _good_proposal(target_industries=[
        "manufacturing",          # wrong case -> canonicalized
        "Blockchain Consulting",  # not a TEG industry -> dropped
        "Textile", "Textile",     # duplicate -> deduped
        "Finance", "Retail", "Logistics", "Healthcare", "Agriculture",  # -> capped at 6
    ])
    llm = FakeLLMClient(structured=[bad])
    p, _ = await ProposalAgent(llm, explorer=_explorer()).build(
        intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[], learned_facts={}, session_ref="x", version=1, price_requested=True,
    )
    assert "Blockchain Consulting" not in p.target_industries
    assert p.target_industries[0] == "Manufacturing"  # canonical casing
    assert len(p.target_industries) == len(set(p.target_industries)) <= 6


async def test_build_drops_the_industry_note_when_no_industries_survive():
    bad = _good_proposal(
        target_industries=["Blockchain Consulting"],
        target_industries_note="These are your buyers.",
    )
    llm = FakeLLMClient(structured=[bad])
    p, _ = await ProposalAgent(llm, explorer=_explorer()).build(
        intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[], learned_facts={}, session_ref="x", version=1, price_requested=True,
    )
    assert p.target_industries == []
    assert p.target_industries_note == ""


async def test_itorix_infotech_business_focused_proposal():
    """Test proposal generation for Itorix Infotech LLP following the new business-focused framework."""
    # Itorix-specific intake and dossier based on research
    intake = IntakeResult(
        person_name="Rohan Banda",
        company_name_raw="Itorix Infotech LLP",
        company_name_canonical="Itorix Infotech LLP",
        provided_fields=[],
        intent_hint="exhibitor",
        consent_status="unknown",
    )
    
    dossier = ResearchDossier(
        sector="Digital Marketing",
        relationship="cold",
        company_profile={
            "company_size": "10-50",
            "hq": "Pune",
            "services": "SEO, PPC, SMM, Web Development, Web Design, Custom Software, Email Marketing, Creative Design, Influencer Marketing, Local SEO",
            "industries_served": "Real Estate, Healthcare, Education, Manufacturing, B2B, Small Business, Startups, Jewellery, Visa/Immigration, Hotels, HR Consultancy, Interior Designers, Cleaning Services",
            "experience": "10+ years",
            "clients": "500+ brands claimed",
        },
        person_profile={"designation": "Founder/Director"},
        peer_companies=["Eternal Soft Solutions", "TechnoBrains", "Advait Energy Transitions"],
    )
    
    # Itorix-specific KB facts
    explorer = _explorer(
        pains='[["Access to SME/MSME decision-makers at scale", "TEG expects 15,000+ visitors and is designed to bring together SME/MSME decision-makers"], '
              '["Building relationships in new geography", "Concentrated 3-day environment for business conversations"]]',
        sector_peers="Eternal Soft Solutions, TechnoBrains",
        sector_peer_count="8",
    )
    
    # Expected proposal structure for Itorix
    expected = _good_proposal(
        company="Itorix Infotech LLP",
        person="Rohan Banda",
        person_role="Founder/Director",
        sector="Digital Marketing",
        what_you_told_us="You run a Pune-based digital marketing agency with 10+ years of experience serving 500+ brands across multiple industries.",
        pains=[
            ProposalPain(
                pain="Access to SME/MSME decision-makers at scale may be challenging from a remote location",
                teg_answer="TEG expects 15,000+ visitors and is designed to bring together SME/MSME decision-makers, entrepreneurs and business leaders across multiple industries"
            ),
        ],
        lead_generation="Tech Expo Gujarat expects 15,000+ visitors and is designed to bring together SME/MSME decision-makers across manufacturing, healthcare, education and other industries. The event offers pre-scheduled 1:1 B2B meetings and a networking app, which could help you engage qualified decision-makers.",
        proof=["TEG 2024 had 125+ exhibitors and 8,000+ visitors; TEG 2026 targets 250+ exhibitors and 15,000+ visitors."],
        executive_summary="Itorix Infotech LLP is a Pune-based digital marketing agency with 10+ years of experience exploring whether Tech Expo Gujarat 2026 could become a growth channel by providing access to SME/MSME decision-makers in Gujarat.",
        roi_framing="Tech Expo Gujarat expects 15,000+ visitors and is designed to bring together SME/MSME decision-makers across multiple industries. If a single engagement that starts here covers the cost of taking part many times over, participation could pay for itself.",
        hero_headline="Could Tech Expo Gujarat become your next growth channel?",
        hero_subline="The event expects 15,000+ visitors and is designed to bring together SME/MSME decision-makers across manufacturing, healthcare, education and other industries.",
        closing_cta_headline="Should we explore this opportunity further?",
        closing_cta_body="Reply in the chat to discuss whether this aligns with your growth goals, or reach the team directly.",
        target_industries=["Manufacturing", "Healthcare", "Educational Institute", "Real Estate"],
        target_industries_note="Your digital marketing services are relevant to these industries based on your stated experience.",
        peer_context_line="8 companies in Digital Marketing exhibited at TEG 2024 — including the names below.",
        peers_in_sector_total=8,
    )
    
    llm = FakeLLMClient(structured=[expected, expected])  # Provide two responses for potential regeneration
    p, flags = await ProposalAgent(llm, explorer=explorer).build(
        intake=intake,
        dossier=dossier,
        persona="it_tech_service",
        transcript=[{"role": "prospect", "content": "we're exploring geographic expansion opportunities"}],
        learned_facts={"growth_interest": "geographic expansion"},
        session_ref="itorix-test-001",
        version=1,
        price_requested=False,  # Test without pricing first
    )
    
    # Verify proposal structure
    assert flags == []
    assert p.company == "Itorix Infotech LLP"
    assert p.person == "Rohan Banda"
    assert p.sector == "Digital Marketing"
    assert p.persona == "it_tech_service"
    
    # Verify business-focused language (no definitive claims)
    assert "could" in p.hero_headline.lower() or "could" in p.hero_subline.lower()
    assert "will" not in p.hero_headline.lower()
    assert "guaranteed" not in p.roi_framing.lower()
    
    # Verify no pricing when not requested
    assert p.recommended_package.price_line == ""
    assert p.recommended_package.payment_plan == ""
    
    # Verify target industries are relevant to Itorix
    assert len(p.target_industries) >= 3
    assert "Manufacturing" in p.target_industries or "manufacturing" in p.target_industries
    assert "Healthcare" in p.target_industries or "healthcare" in p.target_industries
    
    # Verify evidence-based claims (no invented metrics)
    assert "15,000+" in p.lead_generation or "15000+" in p.lead_generation
    assert "decision-makers" not in p.lead_generation.lower() or "visitors" in p.lead_generation.lower()
    
    print("\n=== ITORIX PROPOSAL TEST RESULTS ===")
    print(f"Company: {p.company}")
    print(f"Hero Headline: {p.hero_headline}")
    print(f"Hero Subline: {p.hero_subline}")
    print(f"Executive Summary: {p.executive_summary}")
    print(f"What You Told Us: {p.what_you_told_us}")
    print(f"Lead Generation: {p.lead_generation}")
    print(f"ROI Framing: {p.roi_framing}")
    print(f"Target Industries: {p.target_industries}")
    print(f"Target Industries Note: {p.target_industries_note}")
    print(f"Closing CTA Headline: {p.closing_cta_headline}")
    print(f"Closing CTA Body: {p.closing_cta_body}")
    print(f"Flags: {flags}")
    print("=== END TEST RESULTS ===\n")
