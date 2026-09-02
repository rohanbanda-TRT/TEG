"""Live integration check: the salesperson agent never volunteers pricing.

Deselected by default (``-m 'not integration'``). Run with a key:

    GEMINI_API_KEY=... .venv/bin/python -m pytest tests/e2e/test_conversation_no_price.py -q -m integration
"""
import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="needs GEMINI_API_KEY"),
]


async def test_agent_never_volunteers_price():
    from app.agents.persuasion import PersuasionAgent
    from app.domain.schemas import IntakeResult, ResearchDossier
    from app.llm.base import get_llm

    agent = PersuasionAgent(get_llm())
    dossier = ResearchDossier(
        relationship="cold", sector="AI & Machine Learning",
        peer_companies=["ViitorCloud", "NeuraMonks"],
        company_profile={"overview": "an AI tooling startup"},
    )
    intake = IntakeResult(
        person_name="Sam", company_name_raw="Nova AI", company_name_canonical="Nova AI",
        provided_fields=[], intent_hint="exhibitor", consent_status="unknown",
    )
    state = {
        "persona": "it_tech_service", "cta_status": "none", "learned_facts": {},
        "cta_detail": {}, "target_cta": "book_stall",
    }
    history: list[dict] = []
    for msg in [
        "tell me about tech expo gujarat",
        "who usually exhibits there?",
        "what would we get out of it?",
    ]:
        turn = await agent.respond(
            intake=intake, dossier=dossier, state=state, history=history, prospect_message=msg,
        )
        assert "₹" not in turn.reply_text, f"volunteered price: {turn.reply_text}"
        history += [
            {"role": "prospect", "content": msg},
            {"role": "agent", "content": turn.reply_text},
        ]
        state = turn.updated_state


async def test_agent_gives_price_on_direct_ask():
    from app.agents.persuasion import PersuasionAgent
    from app.domain.schemas import IntakeResult, ResearchDossier
    from app.llm.base import get_llm

    agent = PersuasionAgent(get_llm())
    dossier = ResearchDossier(relationship="cold", sector="AI & Machine Learning",
                              peer_companies=["ViitorCloud"])
    intake = IntakeResult(person_name="Sam", company_name_raw="Nova AI",
                          company_name_canonical="Nova AI", provided_fields=[],
                          intent_hint="exhibitor", consent_status="unknown")
    turn = await agent.respond(
        intake=intake, dossier=dossier,
        state={"persona": "it_tech_service", "cta_status": "none", "learned_facts": {},
               "cta_detail": {}, "target_cta": "book_stall"},
        history=[{"role": "agent", "content": "hi"}],
        prospect_message="how much does a 3x3 stall cost?",
    )
    assert turn.asked_about_price is True
    # a figure is allowed now; if given it must carry GST + indicative wording
    if "₹" in turn.reply_text:
        assert "GST" in turn.reply_text
