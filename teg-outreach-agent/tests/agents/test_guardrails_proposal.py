from app.agents.guardrails import PROPOSAL_SAFE_SECTIONS, check_message


def test_flags_competitor_mention():
    for txt in (
        "Unlike EFY Expo, TEG focuses on AI.",
        "TEG is bigger than Tech Vapi 2026.",
        "Compared to other expos in Gujarat, TEG has more footfall.",
    ):
        v = check_message(txt, allowed_peers=[], persona="it_tech_service")
        assert any(x.code == "competitor_mention" for x in v), txt


def test_does_not_flag_generic_industry_language():
    v = check_message(
        "TEG brings together technology providers from across the region.",
        allowed_peers=[], persona="it_tech_service",
    )
    assert not any(x.code == "competitor_mention" for x in v)


def test_flags_commitment_language():
    for txt in (
        "By signing below, you agree to the stall terms.",
        "This proposal constitutes a binding offer.",
        "Authorised signatory: ____________",
    ):
        v = check_message(txt, allowed_peers=[], persona="non_tech_sponsor")
        assert any(x.code == "commitment_language" for x in v), txt


def test_does_not_flag_soft_cta():
    v = check_message(
        "When you're ready, you can book your stall at techexpogujarat.com.",
        allowed_peers=[], persona="it_tech_service",
    )
    assert not any(x.code == "commitment_language" for x in v)


def test_proposal_safe_sections_cover_all_fields_and_personas():
    for field in ("what_you_told_us", "lead_generation", "pain_answer", "proof_bullet", "next_step"):
        assert field in PROPOSAL_SAFE_SECTIONS
        for p in ("it_tech_service", "ai_startup", "non_tech_sponsor", "visitor"):
            assert PROPOSAL_SAFE_SECTIONS[field][p].strip()
