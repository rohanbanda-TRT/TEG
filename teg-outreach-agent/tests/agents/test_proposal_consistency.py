"""Cross-field self-consistency (§3.2 of docs/superpowers/specs/
2026-09-10-verification-harness-and-graph-design.md). FakeLLMClient-seeded,
no network — construct Proposal/ConversationSignals objects directly rather
than seeding a full generation, per the spec's testing section."""
from app.agents.guardrails import PROPOSAL_SAFE_SECTIONS
from app.agents.proposal import ProposalAgent, _select_tier, check_section_consistency
from app.domain.schemas import (
    ConversationSignals,
    Proposal,
    ProposalPackage,
)
from app.kb.explorer import ExploreResult, KBExplorer
from app.kb.pricing import load_pricing
from app.llm.fake import FakeLLMClient


class _FixedExplorer(KBExplorer):
    def __init__(self) -> None:  # no llm needed — explore() never calls it
        pass

    async def explore(self, goal: str) -> ExploreResult:
        return ExploreResult()


def _agent(llm=None) -> ProposalAgent:
    return ProposalAgent(llm or FakeLLMClient(structured=[]), explorer=_FixedExplorer())


def _base_proposal(**over) -> Proposal:
    base_pkg = load_pricing()["it_tech_service"][0]
    p = Proposal(
        company="Acme Co", person="Jane Doe", sector="Software Development",
        persona="it_tech_service", generated_on="X", session_ref="X", version=0,
        what_you_told_us="You run a tech company.",
        lead_generation="Access to 15,000+ visitors.",
        recommended_package=base_pkg.model_copy(),
        next_steps=["Book a stall"],
        contact="info@techexpogujarat.com",
        how_a_teg_plays_out=["Day 1: setup and meetings", "Day 2: demos", "Day 3: closing"],
        growth_journey=[],
    )
    return p.model_copy(update=over)


# ---- Rule A: package tier ----

async def test_rule_a_detects_explicit_tier_mismatch():
    """The exact motivating bug from §1.2: recommended_package stayed at the
    base tier while the transcript explicitly asked for a bigger one."""
    proposal = _base_proposal()  # base 3m x 3m stall
    signals = ConversationSignals(requested_tier="mid", signal_confidence="explicit")
    violations = check_section_consistency(proposal, signals, price_requested=False)
    codes = {v.code for v in violations}
    assert "SECTION_INCONSISTENCY::package_tier" in codes


async def test_rule_a_regression_guard_moves_package_up_not_next_steps():
    """Regression guard for the 'resolves the bug backwards' defect: on
    exhaustion, the package must move UP to match the signal — the fix must
    NOT scrub next_steps or otherwise protect the (wrong) base package."""
    expected = _select_tier(
        "it_tech_service", ConversationSignals(requested_tier="mid", signal_confidence="explicit"),
    )
    proposal = _base_proposal(next_steps=["Book the corner stall we discussed"])
    signals = ConversationSignals(requested_tier="mid", signal_confidence="explicit")
    violations = check_section_consistency(proposal, signals, price_requested=False)
    assert violations, "expected the package_tier violation to fire"

    agent = _agent()
    resolved = agent._resolve_by_safety_order(proposal, violations, signals, "it_tech_service")

    assert resolved.recommended_package.name == expected.name
    assert resolved.recommended_package.name != "3m x 3m stall"
    # next_steps — the field that was TELLING THE TRUTH — must be untouched.
    assert resolved.next_steps == ["Book the corner stall we discussed"]


async def test_rule_a_no_signal_case_raises_no_violation():
    proposal = _base_proposal()
    signals = ConversationSignals()  # requested_tier is None
    violations = check_section_consistency(proposal, signals, price_requested=False)
    assert not any(v.code == "SECTION_INCONSISTENCY::package_tier" for v in violations)


async def test_rule_a_inferred_only_case_no_violation_but_flag_available():
    """An inferred (not explicit) signal must not fire the actionable
    package_tier violation — Never Guess. The separate low-severity
    'inferred_only' note is a distinct code, checked in its own test."""
    from app.agents.proposal import _inferred_tier_note

    proposal = _base_proposal()
    signals = ConversationSignals(requested_tier="mid", signal_confidence="inferred")
    violations = check_section_consistency(proposal, signals, price_requested=False)
    assert not any(v.code == "SECTION_INCONSISTENCY::package_tier" for v in violations)

    note = _inferred_tier_note("it_tech_service", signals)
    assert note == "SECTION_INCONSISTENCY::package_tier_inferred_only"
    # distinguishable from the explicit-signal code
    assert note != "SECTION_INCONSISTENCY::package_tier"


async def test_visitor_persona_never_produces_a_package_tier_violation():
    """A visitor persona has no tier-ladder concept — an upsized signal
    (e.g. a misclassified group/bulk-ticket ask) must never fire a
    package_tier violation, explicit guard, not relying on the single-entry
    ladder to collapse the mismatch away silently."""
    visitor_pkg = load_pricing()["visitor"][0]
    proposal = _base_proposal(persona="visitor", recommended_package=visitor_pkg.model_copy())
    signals = ConversationSignals(requested_tier="upsized", signal_confidence="explicit")
    violations = check_section_consistency(proposal, signals, price_requested=False)
    assert not any(v.code == "SECTION_INCONSISTENCY::package_tier" for v in violations)


# ---- Rule B: price without request ----

async def test_rule_b_price_without_request_detected_and_scrubbed():
    pkg = load_pricing()["it_tech_service"][0].model_copy()
    proposal = _base_proposal(recommended_package=pkg)
    signals = ConversationSignals()
    violations = check_section_consistency(proposal, signals, price_requested=False)
    codes = {v.code for v in violations}
    assert "SECTION_INCONSISTENCY::price_without_request" in codes

    agent = _agent()
    resolved = agent._resolve_by_safety_order(proposal, violations, signals, "it_tech_service")
    assert resolved.recommended_package.price_line == ""
    assert resolved.recommended_package.payment_plan == ""


async def test_rule_b_price_requested_does_not_trigger():
    pkg = load_pricing()["it_tech_service"][0].model_copy()
    proposal = _base_proposal(recommended_package=pkg)
    signals = ConversationSignals()
    violations = check_section_consistency(proposal, signals, price_requested=True)
    assert not any(v.code == "SECTION_INCONSISTENCY::price_without_request" for v in violations)


# ---- Rule B: journey / playout mismatch ----

async def test_rule_b_journey_playout_mismatch_detected_and_scrubbed():
    from app.domain.schemas import JourneyStage

    proposal = _base_proposal(
        growth_journey=[
            JourneyStage(stage="today", title="Today", points=["x"]),
            JourneyStage(stage="growth_move", title="Growth", points=["x"]),
            JourneyStage(stage="barrier", title="Barrier", points=["x"]),
            JourneyStage(stage="teg_opportunity", title="Opportunity", points=["x"]),
            JourneyStage(stage="action", title="Action",
                         points=["On Day 1 you set up meetings"]),
            JourneyStage(stage="potential", title="Potential", points=["x"]),
        ],
        how_a_teg_plays_out=["On Day 3 you close deals instead"],
    )
    signals = ConversationSignals()
    violations = check_section_consistency(proposal, signals, price_requested=False)
    codes = {v.code for v in violations}
    assert "SECTION_INCONSISTENCY::journey_playout_mismatch" in codes

    agent = _agent()
    resolved = agent._resolve_by_safety_order(proposal, violations, signals, "it_tech_service")
    assert resolved.how_a_teg_plays_out == [
        PROPOSAL_SAFE_SECTIONS["how_a_teg_plays_out"]["it_tech_service"]
    ]
    # growth_journey (the six-stage section) must be preserved, not dropped.
    assert len(resolved.growth_journey) == 6


async def test_regenerate_sections_names_the_specific_tier_in_the_prompt():
    expected = _select_tier(
        "it_tech_service", ConversationSignals(requested_tier="mid", signal_confidence="explicit"),
    )
    regenerated = _base_proposal(recommended_package=expected.model_copy())
    llm = FakeLLMClient(structured=[regenerated])
    agent = _agent(llm)
    proposal = _base_proposal()
    signals = ConversationSignals(requested_tier="mid", signal_confidence="explicit")
    violations = check_section_consistency(proposal, signals, price_requested=False)

    result = await agent._regenerate_sections(
        proposal, violations, signals, system="SYS", user="USER", persona="it_tech_service",
    )

    assert result.recommended_package.name == expected.name
    call = llm.calls[-1]
    assert expected.name in call["system"]
    assert "executive_summary" not in call["system"]  # scoped, not a generic "fix it"
