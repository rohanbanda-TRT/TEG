"""Merge one turn's model-reported signals into the DiscoveryState.

The single rule that must never break: a **prospect-stated** fact is never
silently overwritten by a weaker (inferred / researched) one. When a weaker
signal disagrees with a stronger one, it is recorded in ``conflicts`` and
dropped. When a same-strength signal disagrees, that's a change of mind — the
new value becomes current, the old one is kept (superseded) and logged.
"""
from __future__ import annotations

from app.domain.discovery import (
    RESEARCH_OWNED_FIELDS,
    ChangedMind,
    Conflict,
    DiscoveryState,
    Signal,
    TurnSignals,
    evidence_rank,
)
from app.obs import get_logger

_log = get_logger("discovery.merge")

# a prospect naming an industry that research merely suggested must land here,
# never in the prospect-owned `target_industries`
_INDUSTRY_REDIRECT = {"target_industries": "research_opportunity_industries"}


def merge_turn(
    state: DiscoveryState, signals: TurnSignals | None, turn_index: int
) -> DiscoveryState:
    """Return the state with this turn's signals folded in (mutates and returns)."""
    if signals is None:
        return state

    for key, incoming in signals.fields.items():
        target_key = key

        # research-only fields can't be written by a prospect_stated signal, and
        # a non-prospect industry signal is redirected off the prospect field
        if key in _INDUSTRY_REDIRECT and incoming.evidence != "prospect_stated":
            target_key = _INDUSTRY_REDIRECT[key]
        if target_key in RESEARCH_OWNED_FIELDS and incoming.evidence == "prospect_stated":
            # a prospect can't "state" a research-opportunity — treat as a real target
            target_key = key if key not in _INDUSTRY_REDIRECT.values() else "target_industries"

        new_sig = Signal(
            value=incoming.value.strip(),
            verbatim=(incoming.verbatim or None),
            evidence=incoming.evidence,
            source_turn=turn_index,
            confidence=max(0.0, min(1.0, incoming.confidence)),
        )
        _apply(state, target_key, new_sig, turn_index)

    if signals.objection:
        state.objections.append(
            Signal(value=signals.objection, evidence="prospect_stated", source_turn=turn_index)
        )
    if signals.concern:
        state.concerns.append(
            Signal(value=signals.concern, evidence="prospect_stated", source_turn=turn_index)
        )
    for q in signals.open_questions:
        if q and q not in state.open_questions:
            state.open_questions.append(q)

    if "confirmed_understanding" in signals.intents:
        state.validated = True

    return state


def _apply(state: DiscoveryState, key: str, incoming: Signal, turn_index: int) -> None:
    field = state.field(key)
    current = field.current()

    if current is None:
        field.signals.append(incoming)
        field._recompute_status()
        return

    r_new, r_cur = evidence_rank(incoming.evidence), evidence_rank(current.evidence)

    if r_new > r_cur:
        # incoming is WEAKER — never overwrite a stronger fact
        if _norm(incoming.value) != _norm(current.value):
            state.conflicts.append(Conflict(
                key=key, kept=current.value, kept_evidence=current.evidence,
                ignored=incoming.value, ignored_evidence=incoming.evidence, turn=turn_index,
            ))
            _log.info("discovery conflict on %s: kept %r (%s) over %r (%s)",
                      key, current.value, current.evidence, incoming.value, incoming.evidence)
        return

    if r_new < r_cur:
        # incoming is STRONGER — supersede, keep history
        current.superseded = True
        field.signals.append(incoming)
        field._recompute_status()
        return

    # same evidence strength
    if _norm(incoming.value) == _norm(current.value):
        current.confidence = max(current.confidence, incoming.confidence)
        if incoming.verbatim and not current.verbatim:
            current.verbatim = incoming.verbatim
        return

    # same strength, different value -> change of mind
    current.superseded = True
    field.signals.append(incoming)
    field._recompute_status()
    state.changed_mind.append(ChangedMind(
        key=key, from_value=current.value, to_value=incoming.value, turn=turn_index,
    ))
    _log.info("discovery change-of-mind on %s: %r -> %r (turn %d)",
              key, current.value, incoming.value, turn_index)


def _norm(s: str) -> str:
    return " ".join(s.lower().split())
