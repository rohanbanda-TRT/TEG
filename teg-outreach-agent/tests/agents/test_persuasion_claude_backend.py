"""PersuasionAgent driven by the `claude` CLI backend.

The prospect-facing reply is the one place a hook cannot intercept, so the
guardrails must run on the returned text in our own code. These pin that.
"""
import json

import pytest

from app.agents.persuasion import PersuasionAgent, _Analysis, _PersonaChoice, _strip_tool_artifacts
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


async def test_trailing_tool_call_artifacts_are_stripped_from_the_reply():
    """A real, observed failure: the model answers correctly, then appends
    literal tool-call closing-tag syntax as trailing text inside the reply
    string itself (e.g. "...on your mind?</message>\n</invoke>"). No content
    guardrail catches this — check_message checks policy, not formatting —
    so it must be stripped explicitly before it can reach a prospect."""
    leaky = _analysis(
        reply="What's pulling you toward Tech Expo Gujarat right now?</message>\n</invoke>"
    )
    claude = _FakeClaude([leaky])

    out = await _respond(claude)

    assert out.reply_text == "What's pulling you toward Tech Expo Gujarat right now?"
    assert "</message>" not in out.reply_text
    assert "</invoke>" not in out.reply_text


def test_strip_tool_artifacts_removes_trailing_tag_debris():
    leaky = "What's pulling you toward Tech Expo Gujarat right now?</message>\n</invoke>"
    assert _strip_tool_artifacts(leaky) == "What's pulling you toward Tech Expo Gujarat right now?"


def test_strip_tool_artifacts_leaves_clean_text_alone():
    clean = "Could you tell me a bit about what Lemolite does?"
    assert _strip_tool_artifacts(clean) == clean


def test_strip_tool_artifacts_does_not_eat_a_reply_that_is_only_tags():
    # A pathological all-tag "reply" must not collapse to an empty string —
    # fall back to the original text rather than return nothing at all.
    only_tags = "</message></invoke>"
    assert _strip_tool_artifacts(only_tags) == only_tags


async def test_init_personalised_opening_strips_tool_call_artifacts():
    """Same leak, but on the OTHER text-generation path (_generate_text,
    used by init() for the opening message) — this is the one that was
    actually observed: the prompt used to say "Return the message in the
    `message` field", explicitly naming the schema's field in prose on top
    of the schema itself, which is suspected of priming this."""
    persona_payload = json.loads(
        _PersonaChoice(persona="it_tech_service", reason="software services").model_dump_json()
    )
    leaky_payload = {"message": (
        "Hi Jignesh, good to connect. Lemolite's mix of AI-ML and Python work "
        "alongside full-stack and eCommerce builds is a fairly broad spread for "
        "a team your size — most shops pick one lane. What's pulling you toward "
        "Tech Expo Gujarat right now?</message>\n</invoke>"
    )}
    # classify_persona() also uses the claude backend when claude_cli is set,
    # so it consumes the first queued call before _generate_text's.
    claude = _FakeClaude([persona_payload, leaky_payload])
    agent = PersuasionAgent(FakeLLMClient(structured=[]), claude_cli=claude)

    dossier = _dossier()  # no ask_prospect -> company_known, hits the personalised path
    out = await agent.init(_intake(), dossier)

    assert "</message>" not in out.opening_message
    assert "</invoke>" not in out.opening_message
    assert out.opening_message.endswith("Tech Expo Gujarat right now?")
    # The prompt no longer explicitly names the field — the schema already
    # conveys it, and naming it again is what's suspected of priming the leak.
    user_prompt = claude.calls[-1]["user_prompt"]
    assert "`message` field" not in user_prompt
