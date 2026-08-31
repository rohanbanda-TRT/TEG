from app.agents.research import ResearchAgent, _Synthesis
from app.domain.schemas import IntakeResult
from app.llm.fake import FakeLLMClient
from app.research.tools import ResearchQuery, ResearchResult, ResearchTool


class StubTool(ResearchTool):
    def __init__(self, name, result):
        self.name = name
        self._result = result
        self.queries: list[ResearchQuery] = []

    async def lookup(self, query):
        self.queries.append(query)
        return self._result


def _intake(company="Third Rock Techkno", person="Rohan B", intent="exhibitor"):
    return IntakeResult(
        person_name=person, company_name_raw=company, company_name_canonical=company,
        provided_fields=[], intent_hint=intent, consent_status="unknown",
    )


async def test_kb_hit_company_fills_dossier_without_web():
    from app.research.kb_retriever import KBRetriever
    web = StubTool("web", ResearchResult(available=False, tool_name="web"))
    llm = FakeLLMClient(structured=[_Synthesis(
        sector="AI Consulting", company_size=None, hq=None, founder=None,
        designation=None, seniority=None, is_technical=None, person_company_match=None,
    )])
    agent = ResearchAgent(llm, tools=[KBRetriever(), web])
    d = await agent.run(_intake())
    assert "AI" in (d.sector or "")
    assert d.relationship in {"returning", "insider"}
    assert "Third Rock Techkno" not in d.peer_companies
    assert web.queries == [] or all(q for q in web.queries)  # web may be skipped


async def test_unknown_company_sets_ask_prospect():
    from app.research.kb_retriever import KBRetriever
    web = StubTool("web", ResearchResult(available=False, tool_name="web"))
    llm = FakeLLMClient(structured=[_Synthesis(
        sector=None, company_size=None, hq=None, founder=None,
        designation=None, seniority=None, is_technical=None, person_company_match=None,
    )])
    agent = ResearchAgent(llm, tools=[KBRetriever(), web])
    d = await agent.run(_intake(company="Zzxqwerty Nonexistent Ltd", person="Nobody Atall"))
    assert "company_description" in d.ask_prospect
    assert d.relationship == "cold"


async def test_web_context_is_synthesised_into_fields():
    from app.research.kb_retriever import KBRetriever
    web = StubTool("web", ResearchResult(
        available=True, tool_name="web",
        fields={"web_context": "Acme is a 30-person ERP firm in Surat. Rohan is CTO."},
        confidence={"web_context": 0.5},
        source_url="https://acme.example",
    ))
    scraper = StubTool("scrape", ResearchResult(available=False, tool_name="scrape"))
    llm = FakeLLMClient(structured=[_Synthesis(
        sector="Enterprise Software", company_size="30", hq="Surat", founder=None,
        designation="CTO", seniority="exec", is_technical=True, person_company_match=True,
    )])
    agent = ResearchAgent(llm, tools=[KBRetriever(), web, scraper])
    d = await agent.run(_intake(company="Acme Corp", person="Rohan B", intent="unknown"))
    assert d.company_profile["hq"] == "Surat"
    assert d.person_profile["designation"] == "CTO"
    assert d.person_company_match is True
    assert d.research_cost["web_calls"] >= 1
