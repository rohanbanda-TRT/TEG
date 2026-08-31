from app.agents.analysis import AnalysisAgent, _CanonResult
from app.domain.schemas import IntakePayload
from app.llm.fake import FakeLLMClient


async def test_strips_honorific_and_titlecases():
    llm = FakeLLMClient(structured=[_CanonResult(canonical="Acme Corp", intent_hint="unknown")])
    out = await AnalysisAgent(llm).run(IntakePayload(person_name="dr. rohan  b", company_name="acme corp"))
    assert out.person_name == "Rohan B"


async def test_canonical_from_llm_when_matches_kb():
    llm = FakeLLMClient(structured=[_CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor")])
    out = await AnalysisAgent(llm).run(IntakePayload(person_name="Rohan B", company_name="TRT"))
    assert out.company_name_canonical == "Third Rock Techkno"
    assert out.company_name_raw == "TRT"
    assert out.intent_hint == "exhibitor"


async def test_canonical_falls_back_when_llm_hallucinates():
    llm = FakeLLMClient(structured=[_CanonResult(canonical="Completely Different Co", intent_hint="unknown")])
    out = await AnalysisAgent(llm).run(IntakePayload(person_name="X", company_name="Acme Corp"))
    assert out.company_name_canonical == "Acme Corp"


async def test_provided_fields_and_consent():
    llm = FakeLLMClient(structured=[_CanonResult(canonical="Acme", intent_hint="visitor")])
    out = await AnalysisAgent(llm).run(IntakePayload(
        person_name="X", company_name="Acme", email="x@y.com", message="want to attend", consent=False,
    ))
    assert set(out.provided_fields) == {"email", "message"}
    assert out.consent_status == "not_given"


async def test_intent_hint_from_participation_type_overrides_llm():
    llm = FakeLLMClient(structured=[_CanonResult(canonical="Acme", intent_hint="unknown")])
    out = await AnalysisAgent(llm).run(IntakePayload(
        person_name="X", company_name="Acme", participation_type="sponsor",
    ))
    assert out.intent_hint == "sponsor"
