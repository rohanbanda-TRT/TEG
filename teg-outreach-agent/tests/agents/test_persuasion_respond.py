from app.agents.persuasion import PersuasionAgent, _Analysis, _PersonaChoice
from app.domain.schemas import IntakeResult, ResearchDossier
from app.llm.fake import FakeLLMClient


def _intake(intent="unknown", company="Acme Corp"):
    return IntakeResult(
        person_name="Rohan B", company_name_raw=company, company_name_canonical=company,
        provided_fields=[], intent_hint=intent, consent_status="unknown",
    )


def _state(persona="visitor", **kw):
    base = {
        "persona": persona, "target_cta": "register_visitor", "cta_status": "none",
        "cta_detail": {}, "learned_facts": {}, "persona_remapped": False, "needs_review": False,
    }
    base.update(kw)
    return base


async def test_respond_basic_turn_updates_cta():
    llm = FakeLLMClient(structured=[_Analysis(
        reply="Happy to help — shall I send the registration link?",
        detected_cta="register_visitor", cta_status="offered", cta_type=None,
        cta_detail={}, should_handoff=False, learned_facts={},
    )])
    d = ResearchDossier(sector="Software Development", relationship="cold", peer_companies=["NeuraMonks"])
    turn = await PersuasionAgent(llm).respond(
        intake=_intake(), dossier=d, state=_state("it_tech_service"),
        history=[{"role": "agent", "content": "hi"}], prospect_message="tell me more",
    )
    assert turn.cta_status == "offered"
    assert turn.persona == "it_tech_service"


async def test_respond_reclassifies_persona_on_first_reply_after_unresolved():
    # queue order doesn't matter: FakeLLMClient matches by schema
    llm = FakeLLMClient(
        structured=[
            _PersonaChoice(persona="non_tech_sponsor", reason="real estate developer"),
            _Analysis(
                reply="A category-exclusive sponsorship could work well. Shall I set up a call?",
                detected_cta="request_sponsor_call", cta_status="offered", cta_type=None,
                cta_detail={}, should_handoff=False, learned_facts={"sector": "Real Estate"},
            ),
        ],
    )
    d = ResearchDossier(sector=None, relationship="cold", ask_prospect=["company_description", "role"])
    turn = await PersuasionAgent(llm).respond(
        intake=_intake(intent="sponsor"), dossier=d, state=_state("visitor"),
        history=[{"role": "agent", "content": "what does your company do?"}],
        prospect_message="We're a real estate developer, I run marketing.",
    )
    assert turn.persona == "non_tech_sponsor"
    assert turn.updated_state["persona_remapped"] is True


async def test_respond_does_not_reclassify_once_remapped():
    llm = FakeLLMClient(structured=[_Analysis(
        reply="Sounds good.", detected_cta=None, cta_status="offered", cta_type=None,
        cta_detail={}, should_handoff=False, learned_facts={},
    )])
    d = ResearchDossier(sector=None, relationship="cold", ask_prospect=["role"])
    turn = await PersuasionAgent(llm).respond(
        intake=_intake(), dossier=d, state=_state("it_tech_service", persona_remapped=True),
        history=[{"role": "agent", "content": "?"}, {"role": "prospect", "content": "we do software"}],
        prospect_message="tell me about stalls",
    )
    assert turn.persona == "it_tech_service"
    # only the _Analysis call was made, no _PersonaChoice
    assert [c["schema"] for c in llm.calls if c["kind"] == "structured"] == ["_Analysis"]


async def test_respond_handoff_after_repeated_deflection():
    llm = FakeLLMClient(structured=[_Analysis(
        reply="No problem — I'll have the team follow up when you're ready.",
        detected_cta=None, cta_status="none", cta_type=None, cta_detail={},
        should_handoff=True, learned_facts={},
    )])
    d = ResearchDossier(sector="Software Development", relationship="cold")
    turn = await PersuasionAgent(llm).respond(
        intake=_intake(), dossier=d, state=_state("it_tech_service"),
        history=[{"role": "agent", "content": "x"}] * 7, prospect_message="just researching for now",
    )
    assert turn.should_handoff is True


async def test_respond_guardrail_fallback_sets_needs_review():
    bad = _Analysis(
        reply="Visitor tickets are ₹400, super cheap!", detected_cta=None,
        cta_status="none", cta_type=None, cta_detail={}, should_handoff=False, learned_facts={},
    )
    llm = FakeLLMClient(structured=[bad, bad])
    d = ResearchDossier(sector="Software Development", relationship="cold", peer_companies=["NeuraMonks"])
    turn = await PersuasionAgent(llm).respond(
        intake=_intake(intent="visitor"), dossier=d, state=_state("visitor"),
        history=[{"role": "agent", "content": "x"}], prospect_message="how much is a ticket?",
    )
    assert "₹400" not in turn.reply_text
    assert turn.updated_state["needs_review"] is True
    assert turn.guardrail_flags
