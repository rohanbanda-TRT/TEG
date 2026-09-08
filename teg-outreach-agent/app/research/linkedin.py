from __future__ import annotations

from app.research.tools import ResearchQuery, ResearchResult, ResearchTool
from config.settings import get_settings


class LinkedInStub(ResearchTool):
    name = "linkedin"

    def __init__(self) -> None:
        provider = get_settings().linkedin_provider
        if provider != "none":
            raise NotImplementedError(
                f"linkedin_provider={provider!r} is not implemented. "
                "This system ships with no paid LinkedIn enrichment."
            )

    async def lookup(self, query: ResearchQuery) -> ResearchResult:
        return ResearchResult(
            available=False, tool_name=self.name, notes="linkedin provider disabled"
        )
