"""Discovery state — evidence-aware merge (Phase 1).

Completeness and policy tests are added in later phases.
"""
from app.agents.discovery_merge import merge_turn
from app.domain.discovery import (
    DiscoveryState,
    IncomingSignal,
    Signal,
    TurnSignals,
)


def _sig(key, value, evidence="prospect_stated", verbatim=None, conf=0.8):
    return TurnSignals(fields={key: IncomingSignal(
        value=value, evidence=evidence, verbatim=verbatim, confidence=conf,
    )})


# --- first signal -----------------------------------------------------------

def test_first_signal_sets_field_and_status():
    st = merge_turn(DiscoveryState(), _sig("objective", "new client acquisition"), 1)
    f = st.get("objective")
    assert f.current().value == "new client acquisition"
    assert f.current().source_turn == 1
    assert f.status == "known"


def test_inference_signal_gives_inferred_status():
    st = merge_turn(DiscoveryState(), _sig("objective_type", "sales", evidence="inference"), 1)
    assert st.get("objective_type").status == "inferred"


def test_hypothesis_signal_gives_hypothesized_status():
    st = merge_turn(DiscoveryState(), _sig("growth_direction", "new geography", evidence="hypothesis"), 1)
    assert st.get("growth_direction").status == "hypothesized"


# --- THE CRITICAL RULE ----------------------------------------------------

def test_weaker_signal_never_overwrites_a_prospect_stated_fact():
    st = DiscoveryState()
    merge_turn(st, _sig("target_company_type", "mid-size enterprise",
                        verbatim="qualified enterprise clients"), 1)
    # a weaker signal later disagrees
    merge_turn(st, _sig("target_company_type", "SMEs", evidence="inference"), 3)

    cur = st.get("target_company_type").current()
    assert cur.value == "mid-size enterprise"
    assert cur.evidence == "prospect_stated"
    assert cur.verbatim == "qualified enterprise clients"
    # the disagreement is recorded, not lost
    assert any(c.key == "target_company_type" and "SMEs" in c.ignored for c in st.conflicts)


def test_weaker_signal_agreeing_is_a_silent_noop():
    st = DiscoveryState()
    merge_turn(st, _sig("what_they_sell", "web development", evidence="prospect_stated"), 1)
    merge_turn(st, _sig("what_they_sell", "web development", evidence="verified_company", conf=0.9), 2)
    assert st.get("what_they_sell").current().evidence == "prospect_stated"
    assert not st.conflicts


# --- stronger signal supersedes, history kept ---------------------------

def test_stronger_signal_supersedes_and_keeps_history():
    st = DiscoveryState()
    # research seed first
    merge_turn(st, _sig("what_they_sell", "software services", evidence="verified_company", conf=0.6), 0)
    # prospect confirms/corrects
    merge_turn(st, _sig("what_they_sell", "digital marketing and web dev", evidence="prospect_stated"), 2)

    f = st.get("what_they_sell")
    assert f.current().value == "digital marketing and web dev"
    assert f.current().evidence == "prospect_stated"
    assert len(f.signals) == 2
    assert f.signals[0].superseded is True
    assert f.signals[0].value == "software services"   # history preserved


# --- change of mind at the same evidence level ------------------------

def test_change_of_mind_is_recorded_and_history_kept():
    st = DiscoveryState()
    merge_turn(st, _sig("team_attending", "maybe 5 people"), 2)
    merge_turn(st, _sig("team_attending", "actually only 2 people"), 4)

    f = st.get("team_attending")
    assert f.current().value == "actually only 2 people"
    assert f.signals[0].superseded is True
    assert f.signals[0].value == "maybe 5 people"      # not deleted
    assert st.changed_mind and st.changed_mind[-1].from_value == "maybe 5 people"
    assert st.changed_mind[-1].to_value == "actually only 2 people"
    assert st.changed_mind[-1].turn == 4


# --- research vs prospect for industries -------------------------------

def test_inferred_industry_signal_is_redirected_off_the_prospect_field():
    st = DiscoveryState()
    merge_turn(st, _sig("target_industries", "manufacturing, e-commerce"), 1)
    # something emits an inferred industry set on the same key
    merge_turn(st, _sig("target_industries", "textile, ceramics", evidence="inference"), 2)

    assert st.get("target_industries").current().value == "manufacturing, e-commerce"
    opp = st.get("research_opportunity_industries")
    assert opp is not None and "textile" in opp.current().value
    assert opp.status == "inferred"


def test_prospect_industry_never_lands_in_the_research_field():
    st = DiscoveryState()
    merge_turn(st, _sig("target_industries", "logistics", evidence="prospect_stated"), 1)
    assert st.get("target_industries").current().value == "logistics"
    assert st.get("research_opportunity_industries") is None


# --- side channels ------------------------------------------------------

def test_objection_concern_open_questions_and_validation():
    st = DiscoveryState()
    ts = TurnSignals(
        objection="not sure the travel is worth it",
        concern="first out-of-state expo",
        open_questions=["what does a stall cost?"],
        intents=["confirmed_understanding"],
    )
    merge_turn(st, ts, 5)
    assert st.objections[-1].value == "not sure the travel is worth it"
    assert st.concerns[-1].value == "first out-of-state expo"
    assert "what does a stall cost?" in st.open_questions
    assert st.validated is True


def test_open_questions_are_deduped():
    st = DiscoveryState()
    merge_turn(st, TurnSignals(open_questions=["price?"]), 1)
    merge_turn(st, TurnSignals(open_questions=["price?", "matchmaking?"]), 2)
    assert st.open_questions == ["price?", "matchmaking?"]


def test_none_signals_is_a_noop():
    st = DiscoveryState()
    st.field("objective").signals.append(Signal(value="x", evidence="prospect_stated"))
    before = st.model_dump()
    merge_turn(st, None, 1)
    assert st.model_dump() == before


def test_state_roundtrips_through_json():
    st = DiscoveryState()
    merge_turn(st, _sig("objective", "new client acquisition", verbatim="strictly new client acquisition"), 1)
    merge_turn(st, _sig("team_attending", "5"), 2)
    merge_turn(st, _sig("team_attending", "2"), 4)
    dumped = st.model_dump()
    restored = DiscoveryState.model_validate(dumped)
    assert restored.get("objective").current().verbatim == "strictly new client acquisition"
    assert restored.changed_mind[-1].to_value == "2"
