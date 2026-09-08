from app.agents.research import ResearchAgent, _Synthesis
from app.domain.schemas import IntakeResult
from app.kb.explorer import ExploreResult, KBExplorer
from app.llm.fake import FakeLLMClient
from app.research.tools import ResearchResult, ResearchTool


class _FixedExplorer(KBExplorer):
    """Returns a canned ExploreResult per goal substring; no LLM, no files."""

    def __init__(self, by_goal_substr: dict[str, ExploreResult]) -> None:
        self._map = by_goal_substr
        self.goals: list[str] = []

    async def explore(self, goal: str) -> ExploreResult:
        self.goals.append(goal)
        for k, v in self._map.items():
            if k.lower() in goal.lower():
                return v
        return ExploreResult()


class StubTool(ResearchTool):
    def __init__(self, name, result):
        self.name = name
        self._result = result
        self.queries = []

    async def lookup(self, query):
        self.queries.append(query)
        return self._result


def _intake(company="Third Rock Techkno", person="Tapan Patel", intent="exhibitor"):
    return IntakeResult(
        person_name=person, company_name_raw=company, company_name_canonical=company,
        provided_fields=[], intent_hint=intent, consent_status="unknown",
    )


async def test_kb_hit_fills_dossier_without_web():
    explorer = _FixedExplorer({
        "profile the company": ExploreResult(
            found=True, confidence=0.9,
            summary="custom AI & software dev",
            facts={
                "sector": "AI & Machine Learning",
                "website": "https://www.thirdrocktechkno.com/",
                "teg_history": "TEG 2024 exhibitor; TEG 2026 exhibitor",
                "sector_peers": "ViitorCloud, Green Apex, NeuraMonks",
            },
            sources=["exhibitors/companies/third_rock_techkno.md"]),
        "profile tapan patel": ExploreResult(
            found=True, confidence=0.9,
            facts={"designation": "CMO", "teg_role": "organizer", "is_technical": "false"},
            sources=["organizers_team/tapan_patel.md"]),
    })
    web = StubTool("web", ResearchResult(available=False, tool_name="web"))
    agent = ResearchAgent(FakeLLMClient(), explorer=explorer, tools=[web])
    d = await agent.run(_intake())
    assert d.sector == "AI & Machine Learning"
    assert d.relationship == "insider"
    assert "ViitorCloud" in d.peer_companies
    assert "Third Rock Techkno" not in d.peer_companies
    assert d.company_profile["website"] == "https://www.thirdrocktechkno.com/"
    assert d.person_profile["designation"] == "CMO"
    assert web.queries == []  # KB was enough; no web spend


async def test_kb_miss_falls_back_to_web_then_ask_prospect():
    explorer = _FixedExplorer({})  # everything -> found=False
    web = StubTool("web", ResearchResult(available=False, tool_name="web"))
    llm = FakeLLMClient(structured=[_Synthesis()])
    agent = ResearchAgent(llm, explorer=explorer, tools=[web])
    d = await agent.run(_intake(company="Zzxqwerty Nonexistent Ltd", person="Nobody Atall"))
    assert "company_description" in d.ask_prospect
    assert "role" in d.ask_prospect
    assert d.relationship == "cold"
    assert len(web.queries) >= 1  # web WAS tried


async def test_web_context_synthesised_when_kb_misses_company():
    explorer = _FixedExplorer({})
    web = StubTool("web", ResearchResult(
        available=True, tool_name="web",
        fields={"web_context": "Acme is a 30-person ERP firm in Surat. Rohan is CTO."},
        confidence={"web_context": 0.6}, source_url="https://acme.example"))
    scraper = StubTool("scrape", ResearchResult(available=False, tool_name="scrape"))
    llm = FakeLLMClient(structured=[_Synthesis(
        sector="Enterprise Software", company_size="30", hq="Surat",
        designation="CTO", is_technical=True, person_company_match=True)])
    agent = ResearchAgent(llm, explorer=explorer, tools=[web, scraper])
    d = await agent.run(_intake(company="Acme Corp", person="Rohan B", intent="unknown"))
    assert d.company_profile["hq"] == "Surat"
    assert d.person_profile["designation"] == "CTO"
    assert d.person_company_match is True
    assert d.research_cost["web_calls"] >= 1


async def test_structured_web_fields_count_as_identifying_the_company():
    """Regression: id_conf was raised only by a `web_context` field, which is
    Tavily's shape. ClaudeWebSearch returns structured fields instead, so a
    fully-researched company still came back as 'could not identify' and the
    agent opened by asking what the company does."""
    explorer = _FixedExplorer({})
    web = StubTool("web", ResearchResult(
        available=True, tool_name="web",
        fields={"sector": "Business Software / SaaS", "hq": "Chennai, India",
                "founder": "Sridhar Vembu", "company_size": "~17,000"},
        confidence={"sector": 0.7, "hq": 0.7, "founder": 0.7, "company_size": 0.7},
        source_url="https://en.wikipedia.org/wiki/Zoho_Corporation"))
    llm = FakeLLMClient(structured=[_Synthesis(sector="Business Software / SaaS")])
    agent = ResearchAgent(llm, explorer=explorer, tools=[web])

    d = await agent.run(_intake(company="Zoho Corporation", person="Priya Mehta"))

    assert "company_description" not in d.ask_prospect, (
        "structured web fields must count as identifying the company"
    )


async def test_a_low_confidence_web_hit_still_asks_the_prospect():
    """The tool's own confidence caps ours — a 0.3 guess must not read as
    'identified', or we'd open a pitch on a company we only inferred."""
    explorer = _FixedExplorer({})
    web = StubTool("web", ResearchResult(
        available=True, tool_name="web",
        fields={"sector": "Something plausible"},
        confidence={"sector": 0.3}, source_url=None))
    llm = FakeLLMClient(structured=[_Synthesis()])
    agent = ResearchAgent(llm, explorer=explorer, tools=[web])

    d = await agent.run(_intake(company="Ambiguous Ltd", person="Someone"))

    assert "company_description" in d.ask_prospect


async def test_sector_from_synthesis_when_kb_has_no_profile():
    """The Itorix case: company not in the KB, but the web text implies a sector."""
    explorer = _FixedExplorer({
        # explorer misses the company but still names a sector + peers
        "profile the company": ExploreResult(
            found=False, confidence=0.9,
            facts={"sector": "Digital Marketing & SEO",
                   "sector_peers": "AONE SEO Service, Elsner Technologies"}),
    })
    web = StubTool("web", ResearchResult(
        available=True, tool_name="web",
        fields={"web_context": "Itorix Infotech LLP is an SEO and web analytics agency in Pune."},
        confidence={"web_context": 0.6}, source_url="https://itorix.example"))
    llm = FakeLLMClient(structured=[_Synthesis(sector=None, hq="Pune")])
    agent = ResearchAgent(llm, explorer=explorer, tools=[web])
    d = await agent.run(_intake(company="Itorix Infotech LLP", person="Tushar Mandale"))
    assert d.sector == "Digital Marketing & SEO"
    assert "AONE SEO Service" in d.peer_companies


async def test_peers_backfilled_when_sector_known_but_no_peers():
    explorer = _FixedExplorer({
        "profile the company": ExploreResult(found=False, confidence=0.0, facts={}),
        "list up to 5 teg exhibitors": ExploreResult(
            found=True, confidence=0.8,
            facts={"sector_peers": "AONE SEO Service, Elsner Technologies"}),
    })
    web = StubTool("web", ResearchResult(
        available=True, tool_name="web",
        fields={"web_context": "an SEO agency"}, confidence={"web_context": 0.6},
        source_url="https://x.example"))
    llm = FakeLLMClient(structured=[_Synthesis(sector="Digital Marketing & SEO")])
    agent = ResearchAgent(llm, explorer=explorer, tools=[web])
    d = await agent.run(_intake(company="Some SEO Co", person="Someone"))
    assert d.sector == "Digital Marketing & SEO"
    assert "AONE SEO Service" in d.peer_companies
    assert any("list up to 5 teg exhibitors" in g.lower() for g in explorer.goals)
