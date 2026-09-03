"""PersuasionAgent driven by the `claude` CLI backend.

The prospect-facing reply is the one place a hook cannot intercept, so the
guardrails must run on the returned text in our own code. These pin that.
"""
import json

import pytest

from app.agents.persuasion import PersuasionAgent, _Analysis
from app.claude.cli import ClaudeCli, ClaudeResult
from app.domain.schemas import IntakeResult, ResearchDossier
from app.llm.fake import FakeLLMClient

pytestmark = pytest.mark.asyncio


class _FakeClaude(ClaudeCli):
    def __init__(self, payloads: list[dict]) -> None:
        self._payloads = list(payloads)
        self.calls: list[dict] = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        if not self._payloads:
            raise AssertionError("claude called more times than the test queued")
        return ClaudeResult(data=self._payloads.pop(0), cost_usd=0.01, session_id="s")


def _analysis(**over) -> dict:
    base = _Analysis(
        reply="What outcome would make TEG worth it for you this year?",
        discovery={"goal": "India clients"},
    )
    return json.loads(base.model_copy(update=over).model_dump_json())


def _dossier(relationship="cold", peers=None):
    return ResearchDossier(
        sector="AI & Machine Learning", relationship=relationship,
        company_profile={"hq": "Ahmedabad"}, person_profile={"designation": "CTO"},
        peer_companies=peers if peers is not None else ["ViitorCloud", "NeuraMonks"],
    )


def _intake():
    return IntakeResult(
        person_name="Rohan B", company_name_raw="DataZen", company_name_canonical="DataZen",
        provided_fields=[], intent_hint="exhibitor", consent_status="unknown",
    )


async def _respond(claude, **over):
    agent = PersuasionAgent(FakeLLMClient(structured=[]), claude_cli=claude)
    kw = dict(
        intake=_intake(), dossier=_dossier(),
        state={"persona": "it_tech_service", "target_cta": "book_stall",
               "cta_status": "none", "learned_facts": {}, "price_requested": False},
        history=[{"role": "agent", "content": "Hello"}],
        prospect_message="tell me more",
    )
    kw.update(over)
    return await agent.respond(**kw)


async def test_reply_comes_back_through_the_claude_backend():
    claude = _FakeClaude([_analysis()])

    out = await _respond(claude)

    assert "worth it for you" in out.reply_text
    assert len(claude.calls) == 1


async def test_the_conversation_skill_is_loaded_into_the_system_prompt():
    claude = _FakeClaude([_analysis()])

    await _respond(claude)

    system = claude.calls[0]["system_prompt"]
    assert "TEG Business Development Rep" in system
    assert "Do not bring up cost" in system


async def test_the_session_runs_with_no_tools():
    claude = _FakeClaude([_analysis()])

    await _respond(claude)

    # prospect text reaches this prompt: the reply session must stay tool-free
    assert claude.calls[0].get("tools") in (None, [], [""])


async def test_unprompted_pricing_is_caught_and_regenerated():
    bad = _analysis(reply="Stalls start at just ₹1,17,000 + GST — shall I book you in?")
    claude = _FakeClaude([bad, _analysis()])

    out = await _respond(claude)

    assert len(claude.calls) == 2, "an unprompted price must trigger a regeneration"
    assert "₹" not in out.reply_text


async def test_a_peer_not_on_the_list_is_caught():
    bad = _analysis(reply="Companies like Infosys and Wipro are already exhibiting with us.")
    claude = _FakeClaude([bad, _analysis()])

    out = await _respond(claude)

    assert len(claude.calls) == 2
    assert "Infosys" not in out.reply_text


async def test_discovery_is_carried_through():
    claude = _FakeClaude([_analysis(discovery={"goal": "India pipeline", "scale": "4 people"})])

    out = await _respond(claude)

    learned = out.updated_state["learned_facts"]
    assert learned["goal"] == "India pipeline"
    assert learned["scale"] == "4 people"


async def test_asked_about_price_is_carried_through():
    claude = _FakeClaude([_analysis(asked_about_price=True)])

    out = await _respond(claude)

    assert out.asked_about_price is True


async def test_wants_proposal_is_carried_through():
    claude = _FakeClaude([_analysis(wants_proposal=True)])

    out = await _respond(claude)

    assert out.wants_proposal is True
