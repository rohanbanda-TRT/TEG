"""Live integration check: the KB explorer resolves real facts from the real KB.

Deselected by default (``-m 'not integration'``). Run with a key:

    GEMINI_API_KEY=... TAVILY_API_KEY=... \
        .venv/bin/python -m pytest tests/e2e/test_kb_explorer_live.py -q -m integration
"""
import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="needs GEMINI_API_KEY"),
]


async def test_research_resolves_kb_company_and_organizer():
    from app.agents.research import ResearchAgent
    from app.domain.schemas import IntakeResult
    from app.llm.base import get_llm

    d = await ResearchAgent(get_llm()).run(
        IntakeResult(
            person_name="Tapan Patel",
            company_name_raw="Third Rock Techkno",
            company_name_canonical="Third Rock Techkno",
            provided_fields=[],
            intent_hint="exhibitor",
            consent_status="unknown",
        )
    )

    assert d.sector == "AI & Machine Learning"
    assert d.relationship == "insider"          # Tapan Patel is a TEG organizer
    assert d.peer_companies                     # real sector peers, not empty
    assert "Third Rock Techkno" not in d.peer_companies
    assert d.ask_prospect == []                 # both tracks resolved from the KB
    assert d.research_cost["web_calls"] == 0    # KB was enough; no web spend


async def test_research_classifies_sector_for_non_kb_company():
    """A company not in the KB still gets a sector (the reported sector=None bug)."""
    from app.agents.research import ResearchAgent
    from app.domain.schemas import IntakeResult
    from app.llm.base import get_llm

    d = await ResearchAgent(get_llm()).run(
        IntakeResult(
            person_name="Tushar Mandale",
            company_name_raw="Itorix Infotech LLP",
            company_name_canonical="Itorix Infotech LLP",
            provided_fields=[],
            intent_hint="unknown",
            consent_status="unknown",
        )
    )

    assert d.sector is not None and d.sector != "None"
    assert d.peer_companies  # peers for whatever sector was chosen
