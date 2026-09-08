from __future__ import annotations

import httpx
import trafilatura

from app.research.tools import ResearchQuery, ResearchResult, ResearchTool

_UA = "Mozilla/5.0 (compatible; TEG-Outreach/0.1; +https://techexpogujarat.com)"


class PageScraper(ResearchTool):
    name = "scrape"

    async def lookup(self, query: ResearchQuery) -> ResearchResult:
        url = query.subject.strip()
        if not url.lower().startswith("http"):
            return ResearchResult(available=False, tool_name=self.name)
        text: str | None = None
        async with httpx.AsyncClient(
            timeout=8.0, follow_redirects=True, headers={"User-Agent": _UA}
        ) as client:
            for attempt in range(2):
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    text = trafilatura.extract(resp.text)
                    break
                except httpx.HTTPError as exc:  # noqa: PERF203
                    if attempt == 1:
                        return ResearchResult(
                            available=False, tool_name=self.name, notes=str(exc)
                        )
        if not text:
            return ResearchResult(available=False, tool_name=self.name)
        return ResearchResult(
            available=True,
            fields={"page_text": text[:4000]},
            confidence={"page_text": 0.6},
            source_url=url,
            tool_name=self.name,
        )
