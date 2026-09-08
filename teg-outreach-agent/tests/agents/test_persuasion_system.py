from app.agents.persuasion import PersuasionAgent
from app.domain.schemas import ResearchDossier
from app.llm.fake import FakeLLMClient


def _agent():
    return PersuasionAgent(FakeLLMClient())


def _dossier(rel="cold", **over):
    return ResearchDossier(relationship=rel, sector="AI & Machine Learning", **over)


def test_system_lists_missing_discovery_facts():
    s = _agent()._system(
        "it_tech_service", _dossier(), learned_facts={"goal": "more India clients"},
        price_requested=False,
    )
    assert "Still missing for a proposal" in s
    tail = s.split("Still missing for a proposal:")[1].splitlines()[0]
    assert "target_market" in tail and "scale" in tail
    assert "goal" not in tail


def test_system_all_discovery_present_says_none():
    s = _agent()._system(
        "it_tech_service", _dossier(),
        learned_facts={"goal": "x", "target_market": "y", "scale": "z"},
        price_requested=False,
    )
    assert "Still missing for a proposal: none" in s


def test_system_insider_forbids_pitch_and_price():
    s = _agent()._system("it_tech_service", _dossier(rel="insider"), learned_facts={}, price_requested=False)
    assert "organizing team" in s
    assert "Do NOT pitch" in s


def test_system_pricing_rule_present():
    s = _agent()._system("it_tech_service", _dossier(), learned_facts={}, price_requested=False)
    assert "do NOT bring up cost" in s


def test_system_is_salesperson_framed():
    s = _agent()._system("visitor", _dossier(), learned_facts={}, price_requested=False)
    assert "business-development representative" in s
    assert "conversion" in s
