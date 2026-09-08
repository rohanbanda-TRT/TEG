"""Decide whether discovery has gathered enough to build a credible,
prospect-specific business case.

This is a **pure function** — no LLM, no turn counting. Readiness is a boolean
AND of concrete conditions, driven by the objective-type requirement profiles
in ``app/domain/discovery.py`` (data, not conditionals). ``score`` is computed
for telemetry only and appears in no ``ready`` decision.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.discovery import (
    ALWAYS_REQUIRED,
    AMBIGUOUS_OBJECTIVE_TYPES,
    DISCOVERY_FIELDS,
    EXHIBITING_OBJECTIVE_TYPES,
    OBJECTIVE_REQUIREMENTS,
    POSTURE_REQUIRES_PROSPECT,
    STAGE_ORDER,
    VALIDATED_FIELD,
    DiscoveryState,
)

# event-readiness fields that become required when the objective means exhibiting
_EXHIBITING_EXTRA: tuple[str, ...] = ("team_attending", "event_experience", "setup_need")

_MIN_OBJECTIVE_TYPE_CONF = 0.6


class Completeness(BaseModel):
    ready: bool
    score: float                       # 0..1, informational only
    stage: str                         # authoritative discovery stage
    objective_type: str | None         # resolved; None while ambiguous / unknown
    have: list[str] = Field(default_factory=list)
    missing_required: list[str] = Field(default_factory=list)
    missing_optional: list[str] = Field(default_factory=list)
    reasons: dict[str, str] = Field(default_factory=dict)   # field -> why it's missing
    validated: bool = False


def resolve_objective_type(state: DiscoveryState) -> str | None:
    """The prospect's objective type, or None if we can't classify it yet.

    Ambiguity stays ambiguity — the conversation continues rather than forcing
    a label. An inferred type is accepted only above a confidence floor.
    """
    f = state.get("objective_type")
    cur = f.current() if f else None
    if cur is None:
        return None
    v = " ".join(cur.value.lower().split())
    if v in AMBIGUOUS_OBJECTIVE_TYPES:
        return None
    if cur.evidence in ("prospect_stated", "verified_company", "verified_teg"):
        return v
    return v if cur.confidence >= _MIN_OBJECTIVE_TYPE_CONF else None


def _satisfied(state: DiscoveryState, key: str) -> tuple[bool, str]:
    """(ok, reason_if_not). Reason is '' when ok."""
    if key == VALIDATED_FIELD:
        return (state.validated, "" if state.validated else "not_validated")

    if key == "objective_type":
        return (resolve_objective_type(state) is not None, "ambiguous")

    spec = DISCOVERY_FIELDS.get(key)
    f = state.get(key)
    cur = f.current() if f else None

    if f is not None and f.status == "not_applicable":
        return (True, "")
    if cur is None:
        return (False, "not_stated")

    # the anti-expansion rule: a "committed push" reading must come from the
    # prospect, never from an inference. A test/exploration may be inferred.
    if key == "growth_posture":
        v = " ".join(cur.value.lower().split())
        if v in POSTURE_REQUIRES_PROSPECT and cur.evidence != "prospect_stated":
            return (False, "posture_requires_prospect")

    if spec is None:                       # unregistered field — any signal counts
        return (True, "")
    if cur.evidence not in spec.satisfied_by:
        return (False, "wrong_evidence_type")
    if cur.evidence == "prospect_stated":  # they said it — confidence bar doesn't apply
        return (True, "")
    if cur.confidence < spec.min_confidence:
        return (False, "low_confidence_research")
    return (True, "")


def _required_fields(state: DiscoveryState, objective_type: str | None) -> list[str]:
    """Business facts that must be established. Validation is tracked separately
    (``state.validated``) and is NOT in this list — ``ready`` means "we have
    enough to draft"; the mandatory playback happens between ready and propose.
    """
    req: list[str] = list(ALWAYS_REQUIRED)
    if objective_type and objective_type in OBJECTIVE_REQUIREMENTS:
        req += list(OBJECTIVE_REQUIREMENTS[objective_type].required)
        if objective_type in EXHIBITING_OBJECTIVE_TYPES:
            req += list(_EXHIBITING_EXTRA)
    seen: set[str] = set()
    out: list[str] = []
    for k in req:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _optional_fields(objective_type: str | None) -> list[str]:
    if not objective_type or objective_type not in OBJECTIVE_REQUIREMENTS:
        return []
    return list(OBJECTIVE_REQUIREMENTS[objective_type].recommended)


def _stage_for(missing_required: list[str], validated: bool) -> str:
    """Lowest-ordered stage with a blocking gap."""
    blocking = list(missing_required)
    if blocking:
        stages = {DISCOVERY_FIELDS[k].stage for k in blocking if k in DISCOVERY_FIELDS}
        # objective_type has no spec entry stage-wise but belongs to "objective"
        if "objective_type" in blocking or "objective" in blocking:
            stages.add("objective")
        for s in STAGE_ORDER:
            if s in stages:
                return s
        return "objective"
    if not validated:
        return "validation"
    return "transition"


def assess(state: DiscoveryState) -> Completeness:
    ot = resolve_objective_type(state)
    required = _required_fields(state, ot)
    optional = _optional_fields(ot)

    have: list[str] = []
    missing_required: list[str] = []
    reasons: dict[str, str] = {}
    for key in required:
        ok, why = _satisfied(state, key)
        if ok:
            have.append(key)
        else:
            missing_required.append(key)
            reasons[key] = why

    if not state.validated:
        reasons[VALIDATED_FIELD] = "not_validated"

    missing_optional = [k for k in optional if not _satisfied(state, k)[0]]

    # score: 0.8 * required coverage + 0.2 * optional coverage
    req_frac = len(have) / max(1, len(required))
    opt_total = len(optional)
    opt_have = opt_total - len(missing_optional)
    opt_frac = (opt_have / opt_total) if opt_total else 1.0
    score = round(0.8 * req_frac + 0.2 * opt_frac, 3)

    ready = not missing_required
    stage = _stage_for(missing_required, state.validated)

    return Completeness(
        ready=ready,
        score=score,
        stage=stage,
        objective_type=ot,
        have=have,
        missing_required=missing_required,
        missing_optional=missing_optional,
        reasons=reasons,
        validated=state.validated,
    )
