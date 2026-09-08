"""Decide what the conversation should do this turn.

Pure function. Runs *after* the model produced its turn, using the merged
DiscoveryState + completeness + the turn's signals. Owns the proposal trigger
(the model only *wishes*; the policy decides) and the mandatory validation gate.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.agents.discovery_completeness import Completeness
from app.domain.discovery import VALIDATED_FIELD, DiscoveryState, TurnSignals

PolicyAction = Literal[
    "continue_discovery",
    "answer_then_continue",
    "soft_defer",
    "allow_on_insist",
    "validate",
    "propose",
]

# turns after which, if the picture is half-decent, we stop making the prospect
# wait — respect their time even if discovery isn't textbook-complete
_INSIST_TURN_CEILING = 10
_INSIST_SCORE_FLOOR = 0.5
_SOFT_DEFER_LIMIT = 2

# human phrasing for the next-probe hint
_PROBE_HINT: dict[str, str] = {
    "objective": "why they're really considering TEG and what a good outcome looks like",
    "objective_type": "whether this is about winning clients, partners, investors, visibility, or testing a market",
    "what_they_sell": "what they actually sell and the offering they'd most want to win business for",
    "high_value_offering": "their highest-value offering or the engagement they want to land",
    "growth_posture": "whether this is a committed push or more of a test to see if it's worth it",
    "desired_outcome": "roughly how many opportunities or what concrete result would make it worth it",
    "success_criteria": "what would make them call this a success",
    "target_industries": "which industries their buyers are actually in",
    "target_company_type": "the size and kind of company they're trying to reach",
    "target_buyer_role": "which role or decision-maker they need in the room",
    "target_geography": "which geography they're targeting",
    "target_market": "the specific market they want to test",
    "target_audience": "who they want to reach",
    "acquisition_channels": "how they win clients today — referrals, outbound, events, ads, partners",
    "acquisition_constraints": "what makes reaching those buyers hard from where they are now",
    "growth_direction": "where they want the business to grow next",
    "partner_type": "the kind of partner they're looking for",
    "partnership_objective": "what the partnership should achieve",
    "desired_relationship": "the kind of partner relationship they want",
    "funding_objective": "what the raise is for",
    "investor_type": "the kind of investor they want to meet",
    "funding_stage": "their funding stage",
    "visibility_objective": "what the visibility push should achieve",
    "desired_exposure": "the kind of exposure or audience they want",
    "test_hypothesis": "the specific thing they want to find out by being there",
    "distributor_profile": "the kind of distributor they need",
    "distribution_objective": "what the distribution arrangement should achieve",
    "talent_profile": "the kind of talent they want to hire",
    "hiring_objective": "what the hiring push should achieve",
    "hiring_requirements": "their hiring requirements",
    "what_is_launching": "what exactly they're launching",
    "launch_audience": "who the launch is aimed at",
    "launch_objective": "what the launch should achieve",
    "team_attending": "how many people they'd bring and who",
    "event_experience": "whether they've exhibited or done out-of-state events before",
    "setup_need": "what kind of stall or setup they're picturing",
}


class PolicyDecision(BaseModel):
    action: PolicyAction
    effective_wants_proposal: bool
    brief: str = ""                       # instruction fed into the NEXT turn's context
    mark_missing: list[str] = Field(default_factory=list)   # for the _missing_context guard
    bump_soft_defer: bool = False         # orchestrator increments state.soft_defer_count


def _blocking_missing(comp: Completeness) -> list[str]:
    return [k for k in comp.missing_required if k != VALIDATED_FIELD]


def _top_probe(comp: Completeness) -> str:
    for k in _blocking_missing(comp):
        if k in _PROBE_HINT:
            return _PROBE_HINT[k]
    return "the most important thing you don't yet understand about their business"


def _missing_phrase(comp: Completeness) -> str:
    keys = _blocking_missing(comp)
    return ", ".join(keys) if keys else "nothing major"


def decide(
    comp: Completeness,
    signals: TurnSignals | None,
    state: DiscoveryState,
    agent_turns: int,
    *,
    model_wants_proposal: bool,
) -> PolicyDecision:
    intents = list(signals.intents) if signals else []
    asked_proposal = "requested_proposal" in intents
    insists = "insists_proposal" in intents
    asked_price = bool(signals and signals.asked_about_price)
    has_open_q = bool(signals and signals.open_questions)

    ceiling_reached = agent_turns >= _INSIST_TURN_CEILING and comp.score >= _INSIST_SCORE_FLOOR

    # 1. respect their time — insist / repeated defer / ceiling → allow, mark gaps
    if not comp.ready and (insists or state.soft_defer_count >= _SOFT_DEFER_LIMIT or ceiling_reached):
        return PolicyDecision(
            action="allow_on_insist",
            effective_wants_proposal=True,
            mark_missing=_blocking_missing(comp),
            brief=(
                "Build the proposal now — the prospect wants it and has waited enough. "
                f"These were NOT established in the conversation: {_missing_phrase(comp)}. "
                "State plainly where the proposal is working from an assumption, and do "
                "not invent any of the missing details."
            ),
        )

    # 2. discovery complete, not yet confirmed → mandatory brief playback
    if comp.ready and not comp.validated:
        return PolicyDecision(
            action="validate",
            effective_wants_proposal=False,
            brief=(
                "Discovery is sufficient. Your reply this turn must be a short "
                "1-3 sentence playback of what you understand: their objective, "
                "their target, whether this is a committed push or a test, their key "
                "constraints, and what success looks like. End by asking if that's "
                "right. Do NOT ask new discovery questions and do NOT offer the "
                "proposal yet — wait for them to confirm or correct."
            ),
        )

    # 3. complete + confirmed → propose
    if comp.ready and comp.validated:
        if model_wants_proposal:
            return PolicyDecision(action="propose", effective_wants_proposal=True)
        return PolicyDecision(
            action="propose",
            effective_wants_proposal=False,
            brief=(
                "Discovery is complete and the prospect has confirmed your understanding. "
                "Offer to build the tailored proposal now: say briefly what it will cover "
                "(who to target, how to use the B2B meetings, the setup, the investment, "
                "and the path from conversations to opportunities), then ask if they want it."
            ),
        )

    # 4. they asked for a proposal but discovery isn't there yet → soft defer
    if asked_proposal:
        return PolicyDecision(
            action="soft_defer",
            effective_wants_proposal=False,
            bump_soft_defer=True,
            brief=(
                "The prospect asked for a proposal. Acknowledge warmly and say that one "
                "or two more details will make it genuinely specific to them rather than "
                f"a generic pack, then ask about {_top_probe(comp)}."
            ),
        )

    # 5. they asked us something → answer, then keep going
    if has_open_q:
        price_bit = (
            " If they asked about cost, give the single indicative pricing line you were "
            "handed (always '+ GST', 'indicative, confirmed at booking') and nothing more."
            if asked_price else ""
        )
        return PolicyDecision(
            action="answer_then_continue",
            effective_wants_proposal=False,
            brief=(
                f"Answer the prospect's question first.{price_bit} Then continue "
                f"discovery — the most useful thing to learn next is {_top_probe(comp)}."
            ),
        )

    # 6. default — keep discovering, one valuable question
    return PolicyDecision(
        action="continue_discovery",
        effective_wants_proposal=False,
        brief=(
            f"Discovery stage: {comp.stage}. Still unknown: {_missing_phrase(comp)}. "
            f"Ask about the single most valuable one — likely {_top_probe(comp)}. "
            "If the prospect's last message already answered several areas, acknowledge "
            "that and move to the next gap — never re-ask something you already know."
        ),
    )
