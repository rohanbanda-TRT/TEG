import pytest

from app.agents.guardrails import (
    SAFE_TEMPLATES,
    _TestimonialCheck,
    check_message,
    check_overpromise,
    check_testimonial,
)
from app.llm.fake import FakeLLMClient


async def test_no_quote_means_no_llm_call():
    fake = FakeLLMClient()
    assert await check_testimonial("TEG has 250+ exhibitors and great matchmaking.", fake) is None
    assert fake.calls == []


async def test_cleared_quote_passes():
    fake = FakeLLMClient(structured=[_TestimonialCheck(quotes_testimonial=True, all_cleared=True)])
    v = await check_testimonial(
        'As Sonu Sharma said, "I used to think tech talent was mostly in Bangalore, but not any more."',
        fake,
    )
    assert v is None


async def test_fabricated_quote_flagged():
    fake = FakeLLMClient(structured=[
        _TestimonialCheck(quotes_testimonial=True, all_cleared=False, problem="unknown name Jane Doe")
    ])
    v = await check_testimonial('As Jane Doe said, "TEG tripled our revenue in a week."', fake)
    assert v is not None and v.code == "uncleared_testimonial"


async def test_llm_error_fails_safe():
    class _Boom:
        async def generate_structured(self, **kw):
            raise RuntimeError("down")

    v = await check_testimonial('Someone said, "a long enough quote to trip the prefilter here."', _Boom())
    assert v is not None and v.code == "uncleared_testimonial"


def test_unsolicited_price_flagged_when_not_price_ok():
    v = check_message(
        "A 3m x 3m stall is around ₹1,17,000 for you.",
        allowed_peers=[], persona="it_tech_service", price_ok=False,
    )
    assert "unsolicited_price" in {x.code for x in v}


@pytest.mark.parametrize("text", [
    "Stalls start at just ₹1,17,000 + GST — shall I book you in?",
    "Our booths are ₹1,17,000 + GST.",
    "Sponsorships begin at ₹6,00,000 + GST.",
    "Packages start from ₹35,000 + GST.",
    "Pricing is ₹1,17,000 + GST.",
])
def test_unsolicited_price_catches_plurals_and_synonyms(text):
    """Regression: `\\bstall\\b` never matched "Stalls", so a plural-worded
    unprompted price sailed through the guardrail."""
    v = check_message(text, allowed_peers=[], persona="it_tech_service", price_ok=False)
    assert "unsolicited_price" in {x.code for x in v}, text


def test_unsolicited_price_ignores_a_non_offer_rupee_figure():
    """The Retreat fundraising figure is evidence, not a price offer."""
    v = check_message(
        "The TEG Business Retreat 2025 helped facilitate ₹1.5 crore raised in one day.",
        allowed_peers=[], persona="it_tech_service", price_ok=False,
    )
    assert "unsolicited_price" not in {x.code for x in v}


def test_price_allowed_when_price_ok_but_gst_still_enforced():
    ok = check_message(
        "A 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed at booking).",
        allowed_peers=[], persona="it_tech_service", price_ok=True,
    )
    assert "unsolicited_price" not in {x.code for x in ok}
    assert ok == []
    bad = check_message(
        "A 3m x 3m stall is ₹1,17,000 for you.",
        allowed_peers=[], persona="it_tech_service", price_ok=True,
    )
    assert "missing_gst" in {x.code for x in bad}
    assert "unsolicited_price" not in {x.code for x in bad}


def test_overpromise_patterns():
    assert check_overpromise("You will close 5 deals at TEG.") is not None
    assert check_overpromise("A guaranteed ROI of 300%.") is not None
    assert check_overpromise("Expect a return of ₹50,00,000.") is not None
    assert check_overpromise(
        "If a single partnership covers the investment several times over, it pays for itself."
    ) is None


@pytest.mark.parametrize("text", [
    # TEG promising a count — must flag
    "You will get 3 enterprise clients.",
    "We deliver 10 qualified leads.",
    "Expect to close 5 deals at TEG.",
    "The programme generates 20 qualified leads for you.",
    "That produces 4 strategic partnerships.",
])
def test_overpromise_flags_a_teg_delivered_count(text):
    assert check_overpromise(text) is not None, text


@pytest.mark.parametrize("text", [
    # the PROSPECT's own stated goal, echoed back — must NOT flag
    "A good outcome for you is 3 to 5 high-value, qualified enterprise leads.",
    "You told us you want 3-5 leads with active digital transformation budgets.",
    "The leads focus for your channel team is front and centre.",
    "Your goal is qualified leads from B2B manufacturing.",
])
def test_overpromise_ignores_the_prospects_own_goal(text):
    """Regression: `\\d+ leads` flagged 'a good outcome for you is 3-5 leads' —
    the prospect's own words echoed back — and every regenerate re-tripped it,
    so the proposal never sent."""
    assert check_overpromise(text) is None, text


def test_flags_visitor_price():
    v = check_message(
        "A visitor pass costs around ₹500 for early birds.",
        allowed_peers=[], persona="visitor",
    )
    assert any(x.code == "visitor_price" for x in v)


def test_allows_stall_price_with_gst_when_asked():
    v = check_message(
        "A 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed at booking).",
        allowed_peers=[], persona="it_tech_service", price_ok=True,
    )
    assert v == []


def test_flags_stall_price_missing_gst():
    v = check_message(
        "A 3m x 3m stall is ₹1,17,000.",
        allowed_peers=[], persona="it_tech_service",
    )
    assert any(x.code == "missing_gst" for x in v)


# testimonial verification moved to check_testimonial() (async, LLM-backed) —
# see the tests near the top of this file. check_message no longer inspects quotes.
def test_check_message_ignores_quotes():
    v = check_message(
        'As Jane Doe said, "This event completely transformed our pipeline and we closed ten deals."',
        allowed_peers=[], persona="it_tech_service",
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
