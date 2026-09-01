from __future__ import annotations

import asyncio

from pydantic import BaseModel

from app.agents.base import Agent
from app.domain.schemas import IntakeResult, ResearchDossier, SourceRef
from app.kb.loader import get_kb
from app.obs import get_logger

_log = get_logger("agent.research")
from app.research.kb_retriever import KBRetriever
from app.research.linkedin import LinkedInStub
from app.research.page_scraper import PageScraper
from app.research.tools import ResearchQuery, ResearchResult, ResearchTool
from app.research.web_search import get_web_search
from config.outreach_rules import load_rules
from config.settings import get_settings

_COMPANY_WANT = ["sector", "company_size", "hq", "founder", "website", "teg_history", "booth_number"]
_PERSON_WANT = ["designation", "seniority", "is_technical", "linkedin_url", "teg_role", "background"]


class _Synthesis(BaseModel):
    sector: str | None = None
    company_size: str | None = None
    hq: str | None = None
    founder: str | None = None
    designation: str | None = None
    seniority: str | None = None
    is_technical: bool | None = None
    person_company_match: bool | None = None


class _Budget:
    def __init__(self, max_web_per_track: int, max_scrapes: int) -> None:
        self.web_left_company = max_web_per_track
        self.web_left_person = max_web_per_track
        self.scrapes_left = max_scrapes
        self.web_calls = 0
        self.scrape_calls = 0


class ResearchAgent(Agent):
    def __init__(self, llm, tools: list[ResearchTool] | None = None) -> None:
        super().__init__(llm)
        if tools is None:
            tools = [KBRetriever(), get_web_search(), PageScraper(), LinkedInStub()]
        tools = [t for t in tools if t is not None]
        self._kb = next((t for t in tools if t.name == "kb"), KBRetriever())
        self._web = next((t for t in tools if t.name == "web"), None)
        self._scraper = next((t for t in tools if t.name == "scrape"), None)
        self._linkedin = next((t for t in tools if t.name == "linkedin"), None)
        self._rules = load_rules()
        self._auto = self._rules.confidence_thresholds["company_name"]["auto_accept"]

    async def run(self, intake: IntakeResult) -> ResearchDossier:
        s = get_settings()
        budget = _Budget(s.research_max_searches_per_track, s.research_max_scrapes)
        _log.info("research start  company=%r  person=%r  (web=%s)",
                  intake.company_name_canonical, intake.person_name,
                  "on" if self._web is not None else "off")

        company_task = self._track(
            "company", intake.company_name_canonical, intake.person_name, _COMPANY_WANT, budget,
        )
        person_task = self._track(
            "person", intake.person_name, intake.company_name_canonical, _PERSON_WANT, budget,
        )
        (c_fields, c_conf, c_sources, c_id_conf, c_kb_notes), \
        (p_fields, p_conf, p_sources, p_id_conf, p_kb_notes) = await asyncio.gather(
            company_task, person_task
        )

        raw_ctx = " ".join(
            v for v in (
                c_fields.get("web_context", ""), c_fields.get("page_text", ""),
                p_fields.get("web_context", ""), p_fields.get("page_text", ""),
            ) if v
        )
        synth = _Synthesis()
        llm_calls = 0
        if raw_ctx.strip():
            _log.info("synthesising %d chars of web/scrape text into firmographic facts", len(raw_ctx))
            synth = await self.llm.generate_structured(
                system=(
                    "Extract firmographic and role facts from research text. "
                    "Only state a field if the text supports it; else leave it null. "
                    "person_company_match: does the text place this person at this company?"
                ),
                messages=[{"role": "user", "content": (
                    f"Person: {intake.person_name}\nCompany: {intake.company_name_canonical}\n\n"
                    f"Research text:\n{raw_ctx[:6000]}"
                )}],
                schema=_Synthesis,
            )
            llm_calls = 1

        company_profile = {
            "sector": c_fields.get("sector") or synth.sector,
            "company_size": synth.company_size,
            "hq": synth.hq,
            "founder": synth.founder,
            "website": c_fields.get("website"),
            "teg_history": c_fields.get("teg_history"),
            "overview": c_fields.get("overview"),
        }
        person_profile = {
            "designation": p_fields.get("role") or synth.designation,
            "seniority": synth.seniority,
            "is_technical": synth.is_technical,
            "linkedin_url": p_fields.get("linkedin_url"),
            "teg_role": p_fields.get("teg_role"),
            "background": p_fields.get("overview"),
        }

        # relationship
        relationship = "cold"
        teg_hist = (company_profile.get("teg_history") or "").lower()
        if p_fields.get("teg_role") == "organizer":
            relationship = "insider"
        elif any(k in teg_hist for k in ("2024", "2026", "sponsor")) or p_fields.get("teg_role") == "speaker":
            relationship = "returning"

        sector = company_profile.get("sector")
        peers: list[str] = []
        if sector:
            own = intake.company_name_canonical.lower()
            peers = [p for p in get_kb().peers_in_sector(sector, 6) if p.lower() != own][:5]

        field_confidence: dict[str, float] = {}
        for k, v in list(c_conf.items()) + list(p_conf.items()):
            field_confidence[k] = max(field_confidence.get(k, 0.0), v)

        sources = c_sources + p_sources

        ask_prospect: list[str] = []
        if c_id_conf < 0.5:
            ask_prospect.append("company_description")
        if p_id_conf < 0.5:
            ask_prospect.append("role")

        _log.info(
            "research done  relationship=%s  sector=%r  peers=%d  ask_prospect=%s  "
            "company_id_conf=%.2f  person_id_conf=%.2f  cost=%s",
            relationship, sector, len(peers), ask_prospect or "none",
            c_id_conf, p_id_conf,
            {"web": budget.web_calls, "scrape": budget.scrape_calls, "llm": llm_calls},
        )
        _log.debug("   company_profile=%s", {k: v for k, v in company_profile.items() if v})
        _log.debug("   person_profile=%s", {k: v for k, v in person_profile.items() if v})

        return ResearchDossier(
            company_profile={k: v for k, v in company_profile.items() if v is not None},
            person_profile={k: v for k, v in person_profile.items() if v is not None},
            person_company_match=synth.person_company_match,
            relationship=relationship,
            sector=sector,
            peer_companies=peers,
            field_confidence=field_confidence,
            sources=sources,
            review_flags=(["person_company_mismatch"] if synth.person_company_match is False else []),
            ask_prospect=ask_prospect,
            research_cost={
                "web_calls": budget.web_calls,
                "scrape_calls": budget.scrape_calls,
                "llm_calls": llm_calls,
            },
        )

    async def _track(self, track, subject, context, want, budget):
        fields: dict[str, str] = {}
        conf: dict[str, float] = {}
        sources: list[SourceRef] = []

        kb_res = await self._kb.lookup(ResearchQuery(track=track, subject=subject, context=context, want=want))
        id_field = "sector" if track == "company" else "teg_role"
        id_conf = 0.0
        if kb_res.available:
            fields.update(kb_res.fields)
            conf.update(kb_res.confidence)
            id_conf = max(id_conf, kb_res.confidence.get(id_field, 0.0), kb_res.confidence.get("role", 0.0))
            for f in kb_res.fields:
                sources.append(SourceRef(field=f, url=None, tool="kb", confidence=kb_res.confidence.get(f, 0.0)))
        _log.info("[%s] KB %s  id_conf=%.2f  fields=%s", track,
                  "hit" if kb_res.available else "miss", id_conf, list(kb_res.fields.keys()) or "-")

        need_web = (not kb_res.available) or id_conf < self._auto or any(w not in fields for w in ("sector", "role", "designation"))
        web_left = budget.web_left_company if track == "company" else budget.web_left_person
        if need_web and self._web is not None and web_left > 0:
            _log.info("[%s] web search  subject=%r  context=%r", track, subject, context)
            res = await self._web.lookup(ResearchQuery(track=track, subject=subject, context=context, want=want))
            budget.web_calls += 1
            if track == "company":
                budget.web_left_company -= 1
            else:
                budget.web_left_person -= 1
            _log.info("[%s] web %s  url=%s  fields=%s", track,
                      "hit" if res.available else "miss", res.source_url or "-",
                      list(res.fields.keys()) or "-")
            if res.available:
                fields.update(res.fields)
                conf.update({k: max(conf.get(k, 0.0), v) for k, v in res.confidence.items()})
                for f in res.fields:
                    sources.append(SourceRef(field=f, url=res.source_url, tool="web", confidence=res.confidence.get(f, 0.0)))
                # a web hit that returned context is a real "found something" signal
                if res.fields.get("web_context"):
                    id_conf = max(id_conf, 0.6)
                # try a scrape on the surfaced url
                if self._scraper is not None and res.source_url and budget.scrapes_left > 0:
                    _log.info("[%s] scrape  url=%s", track, res.source_url)
                    sc = await self._scraper.lookup(ResearchQuery(track=track, subject=res.source_url, context=context, want=["page_text"]))
                    budget.scrape_calls += 1
                    budget.scrapes_left -= 1
                    if sc.available:
                        fields.update(sc.fields)
                        conf.update(sc.confidence)
                        sources.append(SourceRef(field="page_text", url=sc.source_url, tool="scrape", confidence=0.6))

        if self._linkedin is not None:
            await self._linkedin.lookup(ResearchQuery(track=track, subject=subject, context=context, want=["linkedin_url"]))

        return fields, conf, sources, id_conf, kb_res.notes
