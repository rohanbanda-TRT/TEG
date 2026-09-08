from __future__ import annotations

import re

import httpx

from app.research.tools import ResearchQuery, ResearchResult, ResearchTool
from config.settings import get_settings

_LINKEDIN_RE = re.compile(r"https?://[a-z]{0,3}\.?linkedin\.com/\S+", re.I)


def _pack(results: list[dict]) -> ResearchResult:
    if not results:
        return ResearchResult(available=False, tool_name="web")
    snippets = " ".join(
        f"{r.get('title', '')}: {r.get('content', r.get('description', ''))}".strip()
        for r in results
    )
    linkedin = ""
    for r in results:
        m = _LINKEDIN_RE.search(r.get("url", ""))
        if m:
            linkedin = m.group(0).rstrip(".,)")
            break
    fields = {"web_context": snippets[:4000]}
    conf = {"web_context": 0.5}
    if linkedin:
        fields["linkedin_url"] = linkedin
        conf["linkedin_url"] = 0.5
    return ResearchResult(
        available=True, fields=fields, confidence=conf,
        source_url=results[0].get("url"), tool_name="web",
    )


class TavilySearch(ResearchTool):
    name = "web"

    async def lookup(self, query: ResearchQuery) -> ResearchResult:
        key = get_settings().tavily_api_key
        if not key:
            return ResearchResult(available=False, tool_name=self.name)
        q = f"{query.subject} {query.context}".strip()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post("https://api.tavily.com/search", json={
                    "api_key": key, "query": q, "max_results": 5, "search_depth": "basic",
                })
                resp.raise_for_status()
                return _pack(resp.json().get("results", []))
        except httpx.HTTPError:
            return ResearchResult(available=False, tool_name=self.name)


class BraveSearch(ResearchTool):
    name = "web"

    async def lookup(self, query: ResearchQuery) -> ResearchResult:
        key = get_settings().brave_api_key
        if not key:
            return ResearchResult(available=False, tool_name=self.name)
        q = f"{query.subject} {query.context}".strip()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": q, "count": 5},
                    headers={"X-Subscription-Token": key, "Accept": "application/json"},
                )
                resp.raise_for_status()
                web = resp.json().get("web", {}).get("results", [])
                return _pack(web)
        except httpx.HTTPError:
            return ResearchResult(available=False, tool_name=self.name)


def get_web_search() -> ResearchTool | None:
    provider = get_settings().web_search_provider
    if provider == "tavily":
        return TavilySearch()
    if provider == "brave":
        return BraveSearch()
    return None
