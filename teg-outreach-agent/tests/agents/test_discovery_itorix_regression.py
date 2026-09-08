"""Itorix regression — the conversation must NOT end after the '7 facts' turn.

Replays the fixture through merge -> completeness -> policy and asserts the
behaviour the redesign is for.
"""
from app.agents.discovery_completeness import assess
from app.agents.discovery_merge import merge_turn
from app.agents.discovery_policy import decide
from app.agents.discovery_seed import seed_from_dossier
from app.domain.discovery import DiscoveryState
from app.domain.schemas import IntakeResult, ResearchDossier
from tests.fixtures.itorix_transcript import ITORIX_TURNS


def _intake():
    return IntakeResult(person_name="Tushar Mandale", company_name_raw="Itorix Infotech LLP",
                        company_name_canonical="Itorix Infotech LLP", provided_fields=[],
                        intent_hint="exhibitor", consent_status="unknown")


def _seeded_state() -> DiscoveryState:
    # research (from the real DB row): sector guess at 0.6 confidence, no KB hit
    d = ResearchDossier(
        sector="Web Development & Digital Marketing",
        company_profile={"sector": "Web Development & Digital Marketing", "hq": "Pune, India",
                         "founder": "Tushar Mandale", "company_size": "11-50"},
        field_confidence={"sector": 0.6},
    )
    return seed_from_dossier(d, _intake())


def _replay(upto: int) -> tuple[DiscoveryState, list]:
    """Replay the first `upto` prospect turns. Returns (state, [decision per turn])."""
    st = _seeded_state()
    decisions = []
    for i, (_msg, ts, model_wants) in enumerate(ITORIX_TURNS[:upto], start=1):
        turn_index = i * 2 - 1
        merge_turn(st, ts, turn_index)
        comp = assess(st)
        d = decide(comp, ts, st, agent_turns=i, model_wants_proposal=model_wants)
        if d.bump_soft_defer:
            st.soft_defer_count += 1
        st.pending_brief = d.brief
        st.stage = comp.stage
        decisions.append((comp, d))
    return st, decisions


# --- the core regression: no early proposal ---------------------------

def test_after_the_seven_facts_turn_no_proposal_is_offered():
    st, decisions = _replay(2)   # turns 1 (7 facts) + 2 (team)
    comp, d = decisions[-1]
    assert comp.ready is False
    assert d.effective_wants_proposal is False
    assert d.action == "continue_discovery"
    # the gaps that make it not-ready are the business-context ones
    assert "target_buyer_role" in comp.missing_required
    assert "acquisition_channels" in comp.missing_required
    # what_they_sell is still only research at 0.6 -> not satisfied
    assert "what_they_sell" in comp.missing_required


def test_explicit_request_at_turn_3_soft_defers_not_generates():
    st, decisions = _replay(3)
    comp, d = decisions[-1]
    assert d.action == "soft_defer"
    assert d.effective_wants_proposal is False
    assert st.soft_defer_count == 1


# --- stated targets are preserved -----------------------------------

def test_manufacturing_and_ecommerce_stay_prospect_stated_and_verbatim():
    st, _ = _replay(len(ITORIX_TURNS))
    ti = st.get("target_industries").current()
    assert ti.value == "manufacturing, e-commerce"
    assert ti.evidence == "prospect_stated"
    assert "manufacturing" in (ti.verbatim or "").lower()
    # nothing merged research industries into it
    assert st.get("research_opportunity_industries") is None


def test_growth_posture_is_market_test_not_expansion():
    st, _ = _replay(len(ITORIX_TURNS))
    gp = st.get("growth_posture").current()
    assert gp.value == "market_test"
    assert gp.evidence == "prospect_stated"


def test_what_they_sell_upgrades_from_research_to_prospect_stated():
    st, _ = _replay(4)   # turn 4 is where they describe the actual offering
    ws = st.get("what_they_sell")
    assert ws.current().evidence == "prospect_stated"
    assert "transformation" in ws.current().value.lower()
    # research seed is kept as history, superseded
    assert any(s.superseded and s.evidence == "verified_company" for s in ws.signals)


# --- the path completes correctly --------------------------------

def test_discovery_becomes_ready_then_validates_then_proposes():
    st = _seeded_state()
    seq = []
    for i, (_m, ts, mw) in enumerate(ITORIX_TURNS, start=1):
        merge_turn(st, ts, i * 2 - 1)
        comp = assess(st)
        d = decide(comp, ts, st, agent_turns=i, model_wants_proposal=mw)
        if d.bump_soft_defer:
            st.soft_defer_count += 1
        st.pending_brief = d.brief
        seq.append(d.action)

    # turn 5 completes the business picture -> validate
    assert "validate" in seq
    # turn 6 the prospect confirms -> propose
    assert seq[-1] == "propose"
    # a validate always precedes the first propose
    assert seq.index("validate") < seq.index("propose")


def test_itorix_reaches_the_proposal_only_well_past_the_old_fourth_turn():
    """Regression expectation (not a product rule): a genuine discovery for
    Itorix reaches the proposal transition several turns later than the old
    system, which offered at turn 4."""
    st = _seeded_state()
    first_propose = None
    for i, (_m, ts, mw) in enumerate(ITORIX_TURNS, start=1):
        merge_turn(st, ts, i * 2 - 1)
        comp = assess(st)
        d = decide(comp, ts, st, agent_turns=i, model_wants_proposal=mw)
        if d.bump_soft_defer:
            st.soft_defer_count += 1
        st.pending_brief = d.brief
        # up to and including turn 4 the system must still be discovering / deferring
        if i <= 4:
            assert d.action in ("continue_discovery", "answer_then_continue", "soft_defer")
            assert d.effective_wants_proposal is False
        if d.action == "propose" and first_propose is None:
            first_propose = i
    assert first_propose is not None and first_propose >= 6
