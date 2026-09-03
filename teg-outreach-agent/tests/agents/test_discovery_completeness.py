"""Discovery completeness + research seed (Phase 2)."""
from app.agents.discovery_completeness import assess, resolve_objective_type
from app.agents.discovery_merge import merge_turn
from app.agents.discovery_seed import seed_from_dossier
from app.domain.discovery import DiscoveryState, IncomingSignal, TurnSignals
from app.domain.schemas import IntakeResult, ResearchDossier


def _sig(**pairs) -> TurnSignals:
    ts = TurnSignals()
    for k, v in pairs.items():
        if isinstance(v, tuple):
            value, evidence = v
            ts.fields[k] = IncomingSignal(value=value, evidence=evidence)
        else:
            ts.fields[k] = IncomingSignal(value=v, evidence="prospect_stated")
    return ts


def _intake():
    return IntakeResult(person_name="P", company_name_raw="C", company_name_canonical="C",
                        provided_fields=[], intent_hint="exhibitor", consent_status="unknown")


# --- objective_type resolution -------------------------------------------

def test_objective_type_ambiguous_stays_unresolved():
    st = merge_turn(DiscoveryState(), _sig(objective_type=("ambiguous", "inference")), 1)
    assert resolve_objective_type(st) is None
    assert assess(st).objective_type is None


def test_low_confidence_inferred_objective_type_is_not_resolved():
    st = DiscoveryState()
    st.field("objective_type").signals.append(
        __import__("app.domain.discovery", fromlist=["Signal"]).Signal(
            value="sales", evidence="inference", confidence=0.4))
    st.field("objective_type")._recompute_status()
    assert resolve_objective_type(st) is None


def test_high_confidence_inferred_objective_type_resolves():
    st = DiscoveryState()
    from app.domain.discovery import Signal
    st.field("objective_type").signals.append(
        Signal(value="sales", evidence="inference", confidence=0.85))
    st.field("objective_type")._recompute_status()
    assert resolve_objective_type(st) == "sales"


def test_prospect_stated_objective_type_resolves_regardless_of_confidence():
    st = merge_turn(DiscoveryState(), _sig(objective_type="partnership"), 1)
    assert resolve_objective_type(st) == "partnership"


# --- what_they_sell: verified research can satisfy it -------------------

def test_high_confidence_verified_research_satisfies_what_they_sell():
    d = ResearchDossier(sector="Enterprise SaaS", field_confidence={"sector": 0.9})
    st = seed_from_dossier(d, _intake())
    assert "what_they_sell" not in assess(st).missing_required


def test_low_confidence_verified_research_does_not_satisfy_what_they_sell():
    d = ResearchDossier(sector="Web Development", field_confidence={"sector": 0.6})
    st = seed_from_dossier(d, _intake())
    assert "what_they_sell" in assess(st).missing_required
    assert assess(st).reasons["what_they_sell"] == "low_confidence_research"


def test_prospect_confirming_upgrades_and_satisfies_what_they_sell():
    d = ResearchDossier(sector="Web Development", field_confidence={"sector": 0.6})
    st = seed_from_dossier(d, _intake())
    merge_turn(st, _sig(what_they_sell="digital transformation consulting for manufacturers"), 2)
    assert "what_they_sell" not in assess(st).missing_required


# --- the anti-expansion rule -------------------------------------------

def test_growth_posture_committed_push_must_be_prospect_stated():
    st = merge_turn(DiscoveryState(), _sig(growth_posture=("committed_push", "inference")), 1)
    ok = "growth_posture" not in assess(st).missing_required
    assert ok is False
    assert assess(st).reasons["growth_posture"] == "posture_requires_prospect"


def test_growth_posture_market_test_may_be_inferred():
    st = merge_turn(DiscoveryState(), _sig(growth_posture=("market_test", "inference")), 1)
    assert "growth_posture" not in assess(st).missing_required


# --- objective-type-dependent requirements ----------------------------

def _sales_state_missing_buyer_and_channels():
    st = DiscoveryState()
    merge_turn(st, _sig(
        objective="new client acquisition",
        objective_type=("sales", "inference"),
        desired_outcome="3-5 enterprise clients",
        target_industries="manufacturing, e-commerce",
        target_company_type="enterprise with transformation budgets",
        growth_posture="market_test",
        what_they_sell="web development and digital marketing",
    ), 1)
    return st


def test_sales_objective_still_needs_buyer_role_and_acquisition_channels():
    c = assess(_sales_state_missing_buyer_and_channels())
    assert c.ready is False
    assert "target_buyer_role" in c.missing_required
    assert "acquisition_channels" in c.missing_required
    assert c.validated is False and "_validated" in c.reasons


def test_investment_objective_needs_investor_fields_not_buyer_role():
    st = DiscoveryState()
    merge_turn(st, _sig(
        objective="raise a seed round",
        objective_type="investment",
        what_they_sell="an AI code-review tool",
        growth_posture="committed_push",
        funding_objective="close a seed round by Q3",
        investor_type="early-stage deep-tech VCs",
        funding_stage="seed",
    ), 1)
    c = assess(st)
    assert "target_buyer_role" not in c.missing_required   # not required for investment
    assert "acquisition_channels" not in c.missing_required
    assert c.missing_required == [] and c.ready is True    # business facts done; validation is separate


def test_partnership_objective_uses_partner_fields():
    st = DiscoveryState()
    merge_turn(st, _sig(
        objective="find implementation partners in Gujarat",
        objective_type="partnership",
        what_they_sell="a cloud ERP platform",
        growth_posture="exploratory",
        partner_type="regional system integrators",
        partnership_objective="a referral + co-delivery arrangement",
        desired_relationship="non-exclusive channel partners",
    ), 1)
    c = assess(st)
    assert c.missing_required == [] and c.ready is True
    assert c.objective_type == "partnership"


# --- stage ownership --------------------------------------------------

def test_stage_is_the_lowest_ordered_gap():
    st = _sales_state_missing_buyer_and_channels()   # missing target_buyer_role, acquisition_channels
    # target_customer comes before current_acquisition in STAGE_ORDER
    assert assess(st).stage == "target_customer"


def test_stage_is_validation_when_only_validation_is_missing():
    st = DiscoveryState()
    merge_turn(st, _sig(
        objective="raise a round", objective_type="investment",
        what_they_sell="x", growth_posture="committed_push",
        funding_objective="a", investor_type="b", funding_stage="seed",
    ), 1)
    assert assess(st).stage == "validation"


def test_stage_is_transition_when_validated_and_complete():
    st = DiscoveryState()
    merge_turn(st, _sig(
        objective="raise a round", objective_type="investment",
        what_they_sell="x", growth_posture="committed_push",
        funding_objective="a", investor_type="b", funding_stage="seed",
    ), 1)
    st.validated = True
    c = assess(st)
    assert c.ready is True
    assert c.stage == "transition"


# --- score is informational -----------------------------------------

def test_score_present_but_not_gating():
    st = _sales_state_missing_buyer_and_channels()
    c = assess(st)
    assert 0.0 < c.score < 1.0
    assert c.ready is False    # ready is driven by missing_required, not score
