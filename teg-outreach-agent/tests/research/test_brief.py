from app.domain.schemas import ResearchDossier, SourceRef
from app.research.brief import render_company_brief


def test_all_sections_present_even_on_a_near_empty_dossier():
    md = render_company_brief(ResearchDossier())
    for heading in (
        "# Company Research Brief", "## Executive Summary", "## Company Overview",
        "## Growth Signals", "## How They Currently Win Business", "## Strengths",
        "## Weaknesses / Pain Points", "## Opportunity Fit for TEG", "## Sources",
    ):
        assert heading in md
    # every section on an empty dossier should say so plainly, not go silent
    assert md.count("Not enough public signal to assess") >= 5


def test_populated_dossier_surfaces_real_fields_not_generic_text():
    d = ResearchDossier(
        company_profile={
            "sector": "AI & Machine Learning", "company_size": "30-50", "hq": "Ahmedabad",
            "founder": "Jane Doe", "website": "https://example.com",
            "teg_history": "TEG 2024 exhibitor", "overview": "Builds BI dashboards for SMEs.",
        },
        person_profile={"designation": "CTO", "seniority": "c_level", "teg_role": "none"},
        relationship="returning",
        sector="AI & Machine Learning",
        peer_companies=["NeuraMonks", "ViitorCloud"],
        sources=[SourceRef(field="sector", url="https://example.com/about", tool="web", confidence=0.8)],
        research_cost={"web_calls": 1, "scrape_calls": 1, "llm_calls": 1},
    )
    md = render_company_brief(d)
    assert "AI & Machine Learning" in md
    assert "Ahmedabad" in md
    assert "Builds BI dashboards for SMEs." in md
    assert "NeuraMonks" in md and "ViitorCloud" in md
    assert "TEG 2024 exhibitor" in md
    assert "returning" not in md.lower() or "prior TEG history" in md  # phrased in prose, not the raw enum
    assert "example.com/about" in md
    assert "web_calls" not in md  # rendered as prose, not the raw dict key
    assert "1 web call" in md


def test_never_invents_a_business_weakness_from_nothing():
    """The dossier has no source for actual business weaknesses — the
    section must frame itself as research gaps, never fabricate one."""
    d = ResearchDossier(sector="Fintech")  # no ask_prospect, no review_flags
    md = render_company_brief(d)
    weaknesses_section = md.split("## Weaknesses / Pain Points", 1)[1].split("## Opportunity", 1)[0]
    assert "Not enough public signal to assess" in weaknesses_section


def test_ask_prospect_and_review_flags_surface_as_research_gaps():
    d = ResearchDossier(
        sector="Fintech", ask_prospect=["company_description", "role"],
        review_flags=["person_company_mismatch"],
    )
    md = render_company_brief(d)
    weaknesses_section = md.split("## Weaknesses / Pain Points", 1)[1].split("## Opportunity", 1)[0]
    assert "could not be confirmed" in weaknesses_section
