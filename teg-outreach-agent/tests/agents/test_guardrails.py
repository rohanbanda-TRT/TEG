from app.agents.guardrails import check_message, SAFE_TEMPLATES


def test_flags_visitor_price():
    v = check_message(
        "A visitor pass costs around ₹500 for early birds.",
        allowed_peers=[], persona="visitor",
    )
    assert any(x.code == "visitor_price" for x in v)


def test_allows_stall_price_with_gst():
    v = check_message(
        "A 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed at booking).",
        allowed_peers=[], persona="it_tech_service",
    )
    assert v == []


def test_flags_stall_price_missing_gst():
    v = check_message(
        "A 3m x 3m stall is ₹1,17,000.",
        allowed_peers=[], persona="it_tech_service",
    )
    assert any(x.code == "missing_gst" for x in v)


def test_flags_uncleared_testimonial():
    v = check_message(
        'As Jane Doe said, "This event completely transformed our pipeline and we closed ten deals in a week."',
        allowed_peers=[], persona="it_tech_service",
    )
    assert any(x.code == "uncleared_testimonial" for x in v)


def test_allows_cleared_testimonial():
    # Sonu Sharma is one of the 4 cleared names
    v = check_message(
        'Sonu Sharma noted that Gujarat "has an amazing force of tech people" after visiting.',
        allowed_peers=[], persona="visitor",
    )
    assert not any(x.code == "uncleared_testimonial" for x in v)


def test_flags_invented_peer():
    v = check_message(
        "Companies like Globex Corp and Initech are already exhibiting alongside you.",
        allowed_peers=["Third Rock Techkno", "NeuraMonks"], persona="ai_startup",
    )
    assert any(x.code == "invented_peer" for x in v)


def test_allows_listed_peer():
    v = check_message(
        "Companies like Third Rock Techkno and NeuraMonks are already exhibiting.",
        allowed_peers=["Third Rock Techkno", "NeuraMonks"], persona="ai_startup",
    )
    assert not any(x.code == "invented_peer" for x in v)


def test_safe_templates_cover_all_personas():
    for p in ("it_tech_service", "ai_startup", "non_tech_sponsor", "visitor"):
        assert p in SAFE_TEMPLATES and SAFE_TEMPLATES[p].strip()
