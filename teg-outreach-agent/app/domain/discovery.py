"""Structured discovery state for the TEG conversation.

The transcript stays the source of truth; this is a *structured view* the
conversation policy reasons over so it never has to re-derive everything from
an undifferentiated wall of text.

Design rules (do not weaken without a spec change):

* **Evidence precedence** — ``prospect_stated > verified_company > verified_teg
  > inference > hypothesis``. A stronger signal is never overwritten by a
  weaker one; the weaker one is recorded as a conflict instead.
* **History is kept** — superseded signals stay on the field; a change of mind
  is recorded, not erased.
* **Research ≠ prospect** — industries the prospect names live in
  ``target_industries``; industries research merely *suggests* live in
  ``research_opportunity_industries``. They never merge.
* **objective_type may be inferred** but carries its evidence + confidence, is
  never rendered as prospect-stated, and never overwrites the prospect's
  actual objective *text*. Ambiguous ⇒ stays ambiguous, discovery continues.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# --- evidence -----------------------------------------------------------------

EvidenceType = Literal[
    "prospect_stated", "verified_company", "verified_teg", "inference", "hypothesis"
]

# lower rank == stronger evidence
_EVIDENCE_RANK: dict[str, int] = {
    "prospect_stated": 0,
    "verified_company": 1,
    "verified_teg": 2,
    "inference": 3,
    "hypothesis": 4,
}


def evidence_rank(e: EvidenceType) -> int:
    return _EVIDENCE_RANK[e]


FieldStatus = Literal["known", "unknown", "not_applicable", "inferred", "hypothesized"]

_STATUS_FOR_EVIDENCE: dict[str, FieldStatus] = {
    "prospect_stated": "known",
    "verified_company": "known",
    "verified_teg": "known",
    "inference": "inferred",
    "hypothesis": "hypothesized",
}


class Signal(BaseModel):
    value: str
    verbatim: str | None = None        # the prospect's own words, when this came from them
    evidence: EvidenceType
    source_turn: int | None = None
    confidence: float = 0.7
    superseded: bool = False


class DiscoveryField(BaseModel):
    key: str
    status: FieldStatus = "unknown"
    signals: list[Signal] = Field(default_factory=list)

    def current(self) -> Signal | None:
        for s in reversed(self.signals):
            if not s.superseded:
                return s
        return None

    def _recompute_status(self) -> None:
        cur = self.current()
        self.status = "unknown" if cur is None else _STATUS_FOR_EVIDENCE[cur.evidence]


class ChangedMind(BaseModel):
    key: str
    from_value: str
    to_value: str
    turn: int | None = None


class Conflict(BaseModel):
    key: str
    kept: str
    kept_evidence: EvidenceType
    ignored: str
    ignored_evidence: EvidenceType
    turn: int | None = None


class DiscoveryState(BaseModel):
    fields: dict[str, DiscoveryField] = Field(default_factory=dict)
    stage: str = "objective"                      # authoritative stage, owned by completeness
    open_questions: list[str] = Field(default_factory=list)   # things the prospect asked us, unanswered
    objections: list[Signal] = Field(default_factory=list)
    concerns: list[Signal] = Field(default_factory=list)
    changed_mind: list[ChangedMind] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    validated: bool = False                       # prospect confirmed the playback
    soft_defer_count: int = 0                     # times we've asked them to hold on for a proposal
    pending_brief: str = ""                       # policy instruction for the NEXT turn
    last_completeness: dict = Field(default_factory=dict)     # cached, informational

    def get(self, key: str) -> DiscoveryField | None:
        return self.fields.get(key)

    def field(self, key: str) -> DiscoveryField:
        return self.fields.setdefault(key, DiscoveryField(key=key))


# --- what the model reports each turn ---------------------------------------

class IncomingSignal(BaseModel):
    value: str
    verbatim: str | None = None
    evidence: EvidenceType = "prospect_stated"
    confidence: float = 0.7


class TurnSignals(BaseModel):
    """Model-reported signals for one prospect turn."""
    fields: dict[str, IncomingSignal] = Field(default_factory=dict)
    stage: str | None = None            # the model's guess — telemetry only, never authoritative
    intents: list[str] = Field(default_factory=list)   # requested_proposal | insists_proposal |
                                                       # confirmed_understanding | just_researching
    asked_about_price: bool = False
    open_questions: list[str] = Field(default_factory=list)
    objection: str | None = None
    concern: str | None = None


# --- the field registry (data, not conditionals) --------------------------

DiscoveryStage = Literal[
    "objective", "business_offer", "target_customer", "current_acquisition",
    "growth_intent", "event_readiness", "commercial", "validation", "transition",
]

STAGE_ORDER: tuple[str, ...] = (
    "objective", "business_offer", "target_customer", "current_acquisition",
    "growth_intent", "event_readiness", "commercial", "validation", "transition",
)


class FieldSpec(BaseModel):
    key: str
    stage: DiscoveryStage
    # evidence types that let this field count as satisfied
    satisfied_by: tuple[EvidenceType, ...] = (
        "prospect_stated", "verified_company", "verified_teg", "inference",
    )
    min_confidence: float = 0.0        # a satisfying signal must clear this


def _spec(key: str, stage: DiscoveryStage, **kw) -> tuple[str, FieldSpec]:
    return key, FieldSpec(key=key, stage=stage, **kw)


DISCOVERY_FIELDS: dict[str, FieldSpec] = dict([
    # objective
    _spec("objective", "objective", satisfied_by=("prospect_stated",)),
    _spec("objective_type", "objective", min_confidence=0.6),
    _spec("desired_outcome", "objective"),
    _spec("success_criteria", "objective"),
    _spec("commercial_importance", "objective"),
    _spec("growth_posture", "objective"),   # committed_push | market_test | exploratory
    # business / offer
    _spec("what_they_sell", "business_offer",
          satisfied_by=("prospect_stated", "verified_company", "verified_teg"),
          min_confidence=0.7),
    _spec("high_value_offering", "business_offer"),
    _spec("promote_at_teg", "business_offer"),
    _spec("typical_engagement", "business_offer"),
    _spec("differentiator", "business_offer"),
    # target customer / audience / partner / investor — objective-dependent
    _spec("target_industries", "target_customer", satisfied_by=("prospect_stated",)),
    _spec("target_company_type", "target_customer"),
    _spec("target_geography", "target_customer"),
    _spec("target_buyer_role", "target_customer"),
    _spec("icp", "target_customer"),
    _spec("target_market", "target_customer"),
    _spec("target_audience", "target_customer"),
    _spec("partner_type", "target_customer"),
    _spec("investor_type", "target_customer"),
    _spec("distributor_profile", "target_customer"),
    _spec("talent_profile", "target_customer"),
    _spec("launch_audience", "target_customer"),
    # current acquisition
    _spec("acquisition_channels", "current_acquisition"),
    _spec("acquisition_constraints", "current_acquisition"),
    # growth intent
    _spec("growth_direction", "growth_intent"),
    _spec("partnership_objective", "growth_intent"),
    _spec("desired_relationship", "growth_intent"),
    _spec("funding_objective", "growth_intent"),
    _spec("funding_stage", "growth_intent"),
    _spec("funding_amount", "growth_intent"),
    _spec("traction_signal", "growth_intent"),
    _spec("visibility_objective", "growth_intent"),
    _spec("desired_exposure", "growth_intent"),
    _spec("test_hypothesis", "growth_intent"),
    _spec("distribution_objective", "growth_intent"),
    _spec("hiring_objective", "growth_intent"),
    _spec("hiring_requirements", "growth_intent"),
    _spec("what_is_launching", "growth_intent"),
    _spec("launch_objective", "growth_intent"),
    # event readiness
    _spec("event_experience", "event_readiness"),
    _spec("team_attending", "event_readiness"),
    _spec("attendee_roles", "event_readiness"),
    _spec("readiness_concerns", "event_readiness"),
    _spec("setup_need", "event_readiness"),
    # commercial
    _spec("budget_signal", "commercial"),
    _spec("stall_preference", "commercial"),
    _spec("meeting_need", "commercial"),
    _spec("demo_need", "commercial"),
    # research-only — NEVER a prospect target
    _spec("research_opportunity_industries", "target_customer",
          satisfied_by=("inference", "hypothesis", "verified_company")),
])

# fields the model must NOT write into via a prospect_stated signal — these are
# owned by research seeding / policy, and a prospect industry mention must be
# routed to `target_industries`, not here.
RESEARCH_OWNED_FIELDS: frozenset[str] = frozenset({"research_opportunity_industries"})

# an internal marker field for the validation gate
VALIDATED_FIELD = "_validated"


# --- objective-type requirement profiles (data, not conditionals) ---------

class ObjectiveProfile(BaseModel):
    label: str
    required: tuple[str, ...] = ()       # field keys that block readiness for this objective
    recommended: tuple[str, ...] = ()    # probe when cheap, never block


# fields required for EVERY objective, before any objective-specific ones
ALWAYS_REQUIRED: tuple[str, ...] = (
    "objective",
    "objective_type",
    "what_they_sell",
    "growth_posture",
)

OBJECTIVE_REQUIREMENTS: dict[str, ObjectiveProfile] = {
    "sales": ObjectiveProfile(
        label="Sales / client acquisition",
        required=("desired_outcome", "target_industries", "target_company_type",
                  "target_buyer_role", "acquisition_channels"),
        recommended=("differentiator", "typical_engagement", "high_value_offering",
                     "team_attending", "event_experience", "setup_need"),
    ),
    "partnership": ObjectiveProfile(
        label="Partnership",
        required=("partner_type", "partnership_objective", "desired_relationship"),
        recommended=("target_geography", "high_value_offering", "team_attending",
                     "event_experience"),
    ),
    "investment": ObjectiveProfile(
        label="Investment / fundraising",
        required=("funding_objective", "investor_type", "funding_stage"),
        recommended=("funding_amount", "traction_signal", "team_attending"),
    ),
    "visibility": ObjectiveProfile(
        label="Visibility / brand",
        required=("target_audience", "visibility_objective", "desired_exposure"),
        recommended=("promote_at_teg", "team_attending", "setup_need", "event_experience"),
    ),
    "market_test": ObjectiveProfile(
        label="Market test",
        required=("target_market", "test_hypothesis", "success_criteria"),
        recommended=("target_industries", "target_company_type", "acquisition_channels",
                     "team_attending", "event_experience", "setup_need"),
    ),
    "distribution": ObjectiveProfile(
        label="Distribution / channel",
        required=("distributor_profile", "target_geography", "distribution_objective"),
        recommended=("high_value_offering", "team_attending", "event_experience"),
    ),
    "hiring": ObjectiveProfile(
        label="Hiring / talent",
        required=("talent_profile", "hiring_objective", "hiring_requirements"),
        recommended=("team_attending", "setup_need"),
    ),
    "launch": ObjectiveProfile(
        label="Product launch",
        required=("what_is_launching", "launch_audience", "launch_objective"),
        recommended=("promote_at_teg", "demo_need", "team_attending", "setup_need"),
    ),
    "other": ObjectiveProfile(
        label="Other",
        required=("desired_outcome",),
        recommended=("target_market", "team_attending"),
    ),
}

# objective types where TEG participation means exhibiting — for these,
# event-readiness fields (team, experience, setup) become required.
EXHIBITING_OBJECTIVE_TYPES: frozenset[str] = frozenset({
    "sales", "visibility", "launch", "distribution", "market_test",
})

# growth_posture values that must NOT be inferred — only the prospect can put
# us into a "committed push" reading; a test must never become "expansion".
POSTURE_REQUIRES_PROSPECT: frozenset[str] = frozenset({
    "committed_push", "expansion", "aggressive_expansion",
})

# objective_type values that mean "we could not classify" — treated as unknown
AMBIGUOUS_OBJECTIVE_TYPES: frozenset[str] = frozenset({"ambiguous", "unclear", "unknown", ""})
