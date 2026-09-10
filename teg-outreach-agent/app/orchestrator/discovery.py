"""discovery_v2 turn processing — merges a turn's signals into the stored
DiscoveryState, re-assesses completeness, and runs the readiness policy.
"""
from __future__ import annotations

from app.domain.schemas import PersuasionTurn
from app.obs import get_logger

_log = get_logger("orchestrator")


def derive_learned_facts(ds) -> dict:
    """Flatten the DiscoveryState's current signals into the dict ProposalAgent
    already consumes. Keeps the proposal pipeline unchanged while the extraction
    underneath it gets richer and evidence-safe."""
    out: dict[str, str] = {}
    for key, field in ds.fields.items():
        if key.startswith("_"):
            continue
        cur = field.current()
        if cur is not None and field.status in ("known", "inferred"):
            out[key] = cur.value
    return out


def apply_discovery_v2(
    cs, turn: PersuasionTurn, history: list[dict], prospect_turn_index: int,
) -> tuple[dict, dict, PersuasionTurn]:
    """Merge this turn's signals, re-assess completeness, run the policy.

    Returns (learned_facts, discovery_state_dump, turn) — `turn` is copied
    with its `wants_proposal` replaced by the policy-gated value.
    """
    from app.agents.discovery_completeness import assess
    from app.agents.discovery_merge import merge_turn
    from app.agents.discovery_policy import decide
    from app.domain.discovery import DiscoveryState, TurnSignals

    ds = DiscoveryState.model_validate(cs.discovery_state or {})
    ts = TurnSignals.model_validate(turn.turn_signals) if turn.turn_signals else None

    ds = merge_turn(ds, ts, prospect_turn_index)
    comp = assess(ds)
    agent_turns = sum(1 for m in history if m.get("role") == "agent") + 1
    decision = decide(
        comp, ts, ds, agent_turns, model_wants_proposal=turn.wants_proposal,
    )
    if decision.bump_soft_defer:
        ds.soft_defer_count += 1
    ds.pending_brief = decision.brief
    ds.stage = comp.stage
    ds.last_completeness = comp.model_dump()

    learned_facts = derive_learned_facts(ds)
    if decision.mark_missing:
        learned_facts["_missing_context"] = decision.mark_missing

    _log.info(
        "discovery-v2  stage=%s  ready=%s  score=%.2f  action=%s  wants_proposal=%s->%s  "
        "missing=%s",
        comp.stage, comp.ready, comp.score, decision.action,
        turn.wants_proposal, decision.effective_wants_proposal,
        comp.missing_required or "-",
    )

    turn = turn.model_copy(update={"wants_proposal": decision.effective_wants_proposal})
    return learned_facts, ds.model_dump(), turn
