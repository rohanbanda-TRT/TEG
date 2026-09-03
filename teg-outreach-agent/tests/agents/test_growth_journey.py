"""The growth journey — the six-stage argument at the heart of the proposal.

Today -> next growth move -> what limits it -> what TEG opens -> how you'd
work it -> where it could lead. The stage set is fixed (it IS the pitch); the
content inside each stage is per-prospect.
"""
import json

import pytest

from app.agents.proposal import ProposalAgent
from app.claude.cli import ClaudeCli, ClaudeResult
from app.domain.schemas import GROWTH_STAGES, JourneyStage
from app.llm.fake import FakeLLMClient

from tests.agents.test_proposal_agent import _dossier, _explorer, _good_proposal, _intake

# asyncio_mode = auto in pytest config — async tests need no explicit mark


class _FakeClaude(ClaudeCli):
    def __init__(self, payloads: list[dict]) -> None:
        self._payloads = list(payloads)
        self.calls: list[dict] = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        if not self._payloads:
            raise AssertionError("claude called more times than the test queued")
        return ClaudeResult(data=self._payloads.pop(0), cost_usd=0.4, session_id="s")


def _journey(**over) -> list[dict]:
    """A well-formed six-stage journey."""
    base = {
        "today": ["Pune-based", "10+ years", "multi-industry digital work"],
        "growth_move": ["Expand into Gujarat", "Reach new accounts"],
        "barrier": ["No local relationships", "Hard to differentiate"],
        "teg_opportunity": ["SME/MSME audience", "Three days of interaction"],
        "action": ["Target", "Engage", "Demonstrate", "Qualify"],
        "potential": ["Gujarat pipeline", "New relationships"],
    }
    base.update(over)
    return [
        {"stage": s, "title": f"Heading for {s}", "points": base[s]}
        for s in GROWTH_STAGES
    ]


def _payload(**over) -> dict:
    journey = over.pop("growth_journey", _journey())
    d = json.loads(_good_proposal(**over).model_dump_json())
    d["growth_journey"] = journey
    return d


async def _build(claude, **over):
    kw = dict(
        intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[{"role": "prospect", "content": "we want Gujarat clients"}],
        learned_facts={"goal": "Gujarat pipeline"}, session_ref="x", version=1,
        price_requested=True,
    )
    kw.update(over)
    agent = ProposalAgent(FakeLLMClient(structured=[]), explorer=_explorer(), claude_cli=claude)
    return await agent.build(**kw)


def test_the_six_stages_are_fixed_and_ordered():
    assert GROWTH_STAGES == (
        "today", "growth_move", "barrier", "teg_opportunity", "action", "potential",
    )


async def test_a_well_formed_journey_survives_intact():
    claude = _FakeClaude([_payload()])

    p, flags = await _build(claude)

    assert [s.stage for s in p.growth_journey] == list(GROWTH_STAGES)
    assert p.growth_journey[0].points == ["Pune-based", "10+ years", "multi-industry digital work"]
    assert flags == []


async def test_stages_are_reordered_into_the_canonical_sequence():
    """The argument only works in order — a shuffled journey is repaired."""
    shuffled = list(reversed(_journey()))
    claude = _FakeClaude([_payload(), _payload()])
    claude._payloads[0]["growth_journey"] = shuffled

    p, _ = await _build(claude)

    assert [s.stage for s in p.growth_journey] == list(GROWTH_STAGES)


async def test_an_unknown_stage_is_dropped():
    bad = _journey() + [{"stage": "bonus", "title": "Extra", "points": ["x"]}]
    claude = _FakeClaude([_payload(), _payload()])
    claude._payloads[0]["growth_journey"] = bad

    p, _ = await _build(claude)

    assert [s.stage for s in p.growth_journey] == list(GROWTH_STAGES)
    assert all(s.stage in GROWTH_STAGES for s in p.growth_journey)


async def test_a_duplicate_stage_keeps_only_the_first():
    dupes = _journey() + [{"stage": "today", "title": "Again", "points": ["y"]}]
    claude = _FakeClaude([_payload(), _payload()])
    claude._payloads[0]["growth_journey"] = dupes

    p, _ = await _build(claude)

    assert len(p.growth_journey) == len(GROWTH_STAGES)
    assert p.growth_journey[0].title == "Heading for today"


async def test_points_are_capped_at_five_per_stage():
    fat = _journey(today=[f"point {i}" for i in range(9)])
    claude = _FakeClaude([_payload(), _payload()])
    claude._payloads[0]["growth_journey"] = fat

    p, _ = await _build(claude)

    assert len(p.growth_journey[0].points) == 5


async def test_an_incomplete_journey_is_dropped_entirely():
    """A partial journey renders as a broken argument — better to show none."""
    partial = [s for s in _journey() if s["stage"] in ("today", "action")]
    claude = _FakeClaude([_payload(), _payload()])
    claude._payloads[0]["growth_journey"] = partial

    p, _ = await _build(claude)

    assert p.growth_journey == []


async def test_a_missing_journey_is_not_an_error():
    claude = _FakeClaude([_payload()])
    claude._payloads[0]["growth_journey"] = []

    p, flags = await _build(claude)

    assert p.growth_journey == []


async def test_journey_text_goes_through_the_guardrails():
    """A promised outcome inside a stage must be caught like any other copy."""
    promising = _journey(potential=["You will get 5 new clients in Gujarat."])
    claude = _FakeClaude([_payload(), _payload()])
    claude._payloads[0]["growth_journey"] = promising

    p, _ = await _build(claude)

    assert len(claude.calls) == 2, "a promise inside the journey must regenerate"


def test_journey_stage_accepts_any_string_the_clamp_is_the_gate():
    # the model is permissive; _clamp_growth_journey filters to GROWTH_STAGES,
    # so one stray key never fails the whole proposal
    s = JourneyStage(stage="nonsense", title="x", points=[])
    assert s.stage == "nonsense"
