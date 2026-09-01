from app.agents.persuasion import PersuasionAgent, _Analysis
from app.domain.schemas import IntakeResult, ResearchDossier
from app.llm.fake import FakeLLMClient


def _intake():
    return IntakeResult(person_name="X", company_name_raw="Y", company_name_canonical="Y",
                        provided_fields=[], intent_hint="exhibitor", consent_status="unknown")


def _state(persona="it_tech_service"):
    return {"persona": persona, "target_cta": "book_stall", "cta_status": "offered",
            "cta_detail": {}, "learned_facts": {}, "persona_remapped": True, "needs_review": False}


async def test_respond_propagates_wants_proposal():
    llm = FakeLLMClient(structured=[_Analysis(
        reply="Sure — one moment.", detected_cta=None, cta_status="offered", cta_type=None,
        cta_detail={}, should_handoff=False, learned_facts={}, wants_proposal=True,
    )])
    d = ResearchDossier(sector="Software Development", relationship="cold", peer_companies=["NeuraMonks"])
    turn = await PersuasionAgent(llm).respond(
        intake=_intake(), dossier=d, state=_state(),
        history=[{"role": "agent", "content": "x"}, {"role": "prospect", "content": "y"}],
        prospect_message="can you send me a proposal?",
    )
    assert turn.wants_proposal is True


async def test_respond_wants_proposal_defaults_false():
    llm = FakeLLMClient(structured=[_Analysis(
        reply="Ok.", detected_cta=None, cta_status="offered", cta_type=None,
        cta_detail={}, should_handoff=False, learned_facts={},
    )])
    d = ResearchDossier(sector="Software Development", relationship="cold")
    turn = await PersuasionAgent(llm).respond(
        intake=_intake(), dossier=d, state=_state(),
        history=[{"role": "agent", "content": "x"}, {"role": "prospect", "content": "y"}],
        prospect_message="tell me more",
    )
    assert turn.wants_proposal is False
