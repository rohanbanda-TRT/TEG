"""Conversation policy (Phase 3)."""
from app.agents.discovery_completeness import assess
from app.agents.discovery_merge import merge_turn
from app.agents.discovery_policy import decide
from app.domain.discovery import DiscoveryState, IncomingSignal, TurnSignals


def _sig(intents=None, asked_price=False, open_questions=None, **fields) -> TurnSignals:
    ts = TurnSignals(
        intents=intents or [], asked_about_price=asked_price,
        open_questions=open_questions or [],
    )
    for k, v in fields.items():
        ev = "prospect_stated"
        if isinstance(v, tuple):
            v, ev = v
        ts.fields[k] = IncomingSignal(value=v, evidence=ev)
    return ts


def _thin_state() -> DiscoveryState:
    """objective known, nothing else."""
    return merge_turn(DiscoveryState(), _sig(objective="get more clients"), 1)


def _ready_unvalidated() -> DiscoveryState:
    st = DiscoveryState()
    merge_turn(st, _sig(
        objective="raise a seed round", objective_type="investment",
        what_they_sell="an AI tool", growth_posture="committed_push",
        funding_objective="close seed", investor_type="deep-tech VCs", funding_stage="seed",
    ), 1)
    return st


# --- keep discovering --------------------------------------------------

def test_thin_state_continues_discovery():
    st = _thin_state()
    d = decide(assess(st), _sig(), st, agent_turns=1, model_wants_proposal=False)
    assert d.action == "continue_discovery"
    assert d.effective_wants_proposal is False
    assert "Still unknown" in d.brief


def test_model_wanting_a_proposal_early_is_overruled():
    st = _thin_state()
    d = decide(assess(st), _sig(), st, agent_turns=2, model_wants_proposal=True)
    assert d.action == "continue_discovery"
    assert d.effective_wants_proposal is False


# --- explicit request -> soft defer -> allow --------------------------

def test_first_proposal_request_soft_defers():
    st = _thin_state()
    d = decide(assess(st), _sig(intents=["requested_proposal"]), st, 3, model_wants_proposal=True)
    assert d.action == "soft_defer"
    assert d.effective_wants_proposal is False
    assert d.bump_soft_defer is True


def test_second_request_after_two_defers_is_allowed_with_missing_marked():
    st = _thin_state()
    st.soft_defer_count = 2
    comp = assess(st)
    d = decide(comp, _sig(intents=["requested_proposal"]), st, 5, model_wants_proposal=True)
    assert d.action == "allow_on_insist"
    assert d.effective_wants_proposal is True
    assert d.mark_missing == [k for k in comp.missing_required if k != "_validated"]
    assert "do not invent" in d.brief.lower()


def test_insist_intent_allows_immediately():
    st = _thin_state()
    d = decide(assess(st), _sig(intents=["insists_proposal"]), st, 2, model_wants_proposal=False)
    assert d.action == "allow_on_insist"
    assert d.effective_wants_proposal is True


def test_turn_ceiling_allows_when_score_is_decent():
    # nearly-complete investment picture, one required field short
    st = DiscoveryState()
    merge_turn(st, _sig(objective="raise a round", objective_type="investment",
                        what_they_sell="an AI tool", growth_posture="committed_push",
                        funding_objective="close seed", investor_type="deep-tech VCs"), 1)
    comp = assess(st)                    # missing: funding_stage
    assert comp.ready is False and comp.score >= 0.5
    d = decide(comp, _sig(), st, agent_turns=11, model_wants_proposal=False)
    assert d.action == "allow_on_insist"
    assert "funding_stage" in d.mark_missing


# --- answer the prospect --------------------------------------------

def test_open_question_triggers_answer_then_continue():
    st = _thin_state()
    d = decide(assess(st), _sig(open_questions=["what does a stall cost?"], asked_price=True),
               st, 2, model_wants_proposal=False)
    assert d.action == "answer_then_continue"
    assert "indicative pricing line" in d.brief
    assert d.effective_wants_proposal is False


# --- mandatory validation -----------------------------------------

def test_ready_but_unvalidated_forces_playback():
    st = _ready_unvalidated()
    comp = assess(st)
    assert comp.ready is True and comp.validated is False
    d = decide(comp, _sig(), st, 6, model_wants_proposal=True)   # model wants it
    assert d.action == "validate"
    assert d.effective_wants_proposal is False    # not honoured until confirmed
    assert "playback" in d.brief.lower()


def test_validated_and_ready_proposes():
    st = _ready_unvalidated()
    st.validated = True
    d = decide(assess(st), _sig(), st, 7, model_wants_proposal=True)
    assert d.action == "propose"
    assert d.effective_wants_proposal is True


def test_validated_and_ready_but_model_silent_gets_an_offer_brief():
    st = _ready_unvalidated()
    st.validated = True
    d = decide(assess(st), _sig(), st, 7, model_wants_proposal=False)
    assert d.action == "propose"
    assert d.effective_wants_proposal is False
    assert "offer to build" in d.brief.lower()


def test_confirmed_understanding_intent_sets_validated_via_merge():
    st = _ready_unvalidated()
    merge_turn(st, TurnSignals(intents=["confirmed_understanding"]), 8)
    d = decide(assess(st), TurnSignals(), st, 8, model_wants_proposal=False)
    assert d.action == "propose"
