"""ProposalAgent driven by the `claude` CLI backend.

The point of these: swapping the generation backend must not weaken a single
guardrail. Same clamps, same violation detection, same safe fallbacks.
"""
import json

import pytest

from app.agents.proposal import ProposalAgent
from app.claude.cli import ClaudeCli, ClaudeResult
from app.llm.fake import FakeLLMClient

from tests.agents.test_proposal_agent import (
    _dossier,
    _explorer,
    _good_proposal,
    _intake,
)

pytestmark = pytest.mark.asyncio


class _FakeClaude(ClaudeCli):
    """Returns queued payloads instead of spawning a process."""

    def __init__(self, payloads: list[dict]) -> None:
        self._payloads = list(payloads)
        self.calls: list[dict] = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        if not self._payloads:
            raise AssertionError("claude called more times than the test queued")
        return ClaudeResult(data=self._payloads.pop(0), cost_usd=0.4, session_id="s1")


def _payload(**over) -> dict:
    return json.loads(_good_proposal(**over).model_dump_json())


async def _build(claude, **over):
    kw = dict(
        intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[{"role": "prospect", "content": "we want India clients"}],
        learned_facts={"goal": "India clients"}, session_ref="x", version=1,
        price_requested=True,
    )
    kw.update(over)
    agent = ProposalAgent(FakeLLMClient(structured=[]), explorer=_explorer(), claude_cli=claude)
    return await agent.build(**kw)


async def test_clean_proposal_through_the_claude_backend():
    claude = _FakeClaude([_payload()])

    p, flags = await _build(claude)

    assert flags == []
    assert p.company == "DataZen Analytics"
    assert len(claude.calls) == 1


async def test_the_json_schema_and_model_are_passed_to_the_cli():
    claude = _FakeClaude([_payload()])

    await _build(claude)

    call = claude.calls[0]
    assert call["model"] == "claude-sonnet-5"
    schema = call["json_schema"]
    assert schema["title"] == "Proposal"
    # the landing-page + peer-context fields must reach the CLI's schema
    for field in ("hero_headline", "target_industries", "peers_in_sector_total"):
        assert field in schema["properties"]


async def test_the_skill_is_loaded_into_the_system_prompt():
    claude = _FakeClaude([_payload()])

    await _build(claude)

    system = claude.calls[0]["system_prompt"]
    assert "Proposal Writer" in system               # from SKILL.md
    assert "Persona Pain-Point Library" in system     # from references/
    assert "Never invent a fact" in system


async def test_guardrails_still_fire_and_regenerate_once():
    bad = _payload(roi_framing="You will close 5 deals with a guaranteed ROI of 400%.")
    claude = _FakeClaude([bad, _payload()])

    p, flags = await _build(claude)

    assert len(claude.calls) == 2, "a violating draft must trigger one regeneration"
    assert "violated" in claude.calls[1]["system_prompt"]
    assert flags == []
    assert "guaranteed" not in p.roi_framing.lower()


async def test_a_failed_regenerate_falls_back_to_the_first_draft():
    """Regression: the regenerate call raising (CLI timeout/error) propagated
    out of build() and the prospect got 'the team will follow up' instead of a
    proposal. It should fall back to the first draft + safe-fallback scrub."""
    bad = _payload(roi_framing="Guaranteed 10x ROI, you will close deals.")

    class _OneThenBoom(_FakeClaude):
        async def generate(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return ClaudeResult(data=bad, cost_usd=0.4, session_id="s")
            raise RuntimeError("claude timed out after 180s")

    claude = _OneThenBoom([])

    p, flags = await _build(claude)

    assert len(claude.calls) == 2, "it must have attempted the regenerate"
    assert flags, "the first draft's violation is still flagged"
    assert "guaranteed" not in p.roi_framing.lower(), "safe fallback scrubbed it"


async def test_safe_fallback_when_both_drafts_violate():
    bad = _payload(roi_framing="Guaranteed 10x ROI, you will close deals.")
    claude = _FakeClaude([bad, bad])

    p, flags = await _build(claude)

    assert flags, "repeat violations must surface as flags"
    assert "guaranteed" not in p.roi_framing.lower()


async def test_no_price_is_enforced_on_the_claude_path():
    priced = _payload()  # _good_proposal carries a real price line
    claude = _FakeClaude([priced, priced])

    p, _ = await _build(claude, price_requested=False)

    assert p.recommended_package.price_line == ""
    assert p.recommended_package.payment_plan == ""


async def test_clamps_apply_on_the_claude_path():
    claude = _FakeClaude([_payload(
        target_industries=["manufacturing", "Not A TEG Sector", "Finance"],
        section_ctas={"priorities": "x" * 80, "bogus": "drop"},
    )])

    p, _ = await _build(claude)

    assert "Not A TEG Sector" not in p.target_industries
    assert p.target_industries[0] == "Manufacturing"
    assert set(p.section_ctas) <= {"priorities", "charts", "investment"}
    assert all(len(v) <= 40 for v in p.section_ctas.values())


async def test_peers_are_still_restricted_to_the_allowed_list():
    claude = _FakeClaude([_payload(peer_companies=["NeuraMonks", "Some Random Ltd"])])

    p, _ = await _build(claude)

    assert "Some Random Ltd" not in p.peer_companies
