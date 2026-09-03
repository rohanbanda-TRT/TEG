from app.claude.prompt_builder import build_proposal_prompt
from app.claude.skill_loader import SkillContent
from app.domain.schemas import IntakeResult, ResearchDossier


def _skill():
    return SkillContent(
        name="teg-proposal",
        instructions="SKILL BODY",
        references={"pain-library.md": "PAINS", "teg-mechanism.md": "MECHANISM"},
    )


def _intake(company="DataZen Analytics"):
    return IntakeResult(
        person_name="Rohan B", company_name_raw=company, company_name_canonical=company,
        provided_fields=[], intent_hint="exhibitor", consent_status="unknown",
    )


def _dossier():
    return ResearchDossier(
        sector="AI & Machine Learning", relationship="cold",
        company_profile={"hq": "Ahmedabad"}, person_profile={"designation": "CTO"},
        peer_companies=["ViitorCloud"],
    )


def _build(**over):
    kw = dict(
        skill=_skill(), intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[{"role": "prospect", "content": "we want India-market clients"}],
        learned_facts={"goal": "India clients"}, peers=["ViitorCloud", "NeuraMonks"],
        testimonials=[], industries=["Manufacturing", "Finance"], sector_peer_count=12,
        scale_note="125+ exhibitors at TEG 2024.", package_line="Package: 3m x 3m",
        session_ref="ab12", version=2, price_requested=True,
    )
    kw.update(over)
    return build_proposal_prompt(**kw)


def test_system_prompt_carries_the_skill_and_its_references():
    p = _build()
    assert "SKILL BODY" in p.system_prompt
    assert "PAINS" in p.system_prompt
    assert "MECHANISM" in p.system_prompt


def test_user_prompt_carries_the_conversation_and_the_prospect():
    p = _build()
    assert "DataZen Analytics" in p.user_prompt
    assert "Rohan B" in p.user_prompt
    assert "we want India-market clients" in p.user_prompt
    assert "AI & Machine Learning" in p.user_prompt


def test_user_prompt_lists_the_allowed_peers_and_industries():
    p = _build()
    assert "ViitorCloud" in p.user_prompt
    assert "NeuraMonks" in p.user_prompt
    assert "Manufacturing" in p.user_prompt


def test_price_requested_passes_the_package_line_through():
    p = _build(price_requested=True, package_line="Package: 3m x 3m at ₹1,17,000 + GST")
    assert "₹1,17,000" in p.user_prompt


def test_no_price_requested_states_the_no_figures_rule():
    p = _build(price_requested=False, package_line="Name only, no price.")
    assert "NO figures" in p.user_prompt or "no figures" in p.user_prompt.lower()


def test_echo_fields_are_pinned_in_the_prompt():
    p = _build(session_ref="zz99", version=7)
    assert "zz99" in p.user_prompt
    assert "7" in p.user_prompt


def test_empty_transcript_does_not_break_the_prompt():
    p = _build(transcript=[])
    assert "no messages yet" in p.user_prompt.lower()


def test_testimonials_are_rendered_verbatim_when_present():
    p = _build(testimonials=[{"name": "Sonu Sharma", "role": "Speaker", "quote": "Great scale."}])
    assert "Sonu Sharma" in p.user_prompt
    assert "Great scale." in p.user_prompt
