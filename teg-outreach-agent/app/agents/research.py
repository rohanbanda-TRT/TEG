from __future__ import annotations

import asyncio

from pydantic import BaseModel

from app.agents.base import Agent
from app.domain.schemas import IntakeResult, ResearchDossier, SourceRef
from app.kb._names import _norm
from app.kb.explorer import ExploreResult, KBExplorer
from app.obs import get_logger
from app.research.linkedin import LinkedInStub
from app.research.page_scraper import PageScraper
from app.research.tools import ResearchQuery, ResearchTool
from app.research.web_search import get_web_search
from config.outreach_rules import load_rules
from config.settings import get_settings

_log = get_logger("agent.research")

# TEG spans tech verticals AND broader industries — the event is explicitly not
# IT-only. Both the explorer goal and the web-fallback classifier use this list.
_TEG_SECTORS = (
    "AI & Machine Learning, Fintech, Cybersecurity, Cloud & Infrastructure, "
    "Data & Analytics, Software Development & IT Services, Digital Marketing & SEO, "
    "HR Tech, IoT & Hardware, Enterprise Software (ERP, CRM, HRMS), Healthcare Tech, "
    "E-commerce & Retail Technology, Telecom & VoIP, Energy & Power, "
    "Real Estate & Construction Technology, Manufacturing & Industrial Technology, "
    "Consulting & Professional Services, Education, Agriculture, Automobile, "
    "Pharmaceutical, Textile, Jewellery, Retail, Logistics, Finance"
)

_COMPANY_GOAL = (
    "Profile the company {company} for a Tech Expo Gujarat 2026 outreach dossier.\n"
    "Look for its profile: list_dir exhibitors/companies/ and scan for a matching "
    "filename, or grep '{company}' across the KB; read_file what you find. Then "
    "read sector_wise_participation.md for the sector and its peer table.\n"
    "Return facts:\n"
    "- sector: the ONE best-fitting TEG sector. TEG is NOT IT-only; choose from: "
    + _TEG_SECTORS
    + "\n- company_size, hq, founder, website\n"
    "- teg_history: which past editions / sponsor tier, or omit if none\n"
    "- sector_peers: up to 5 OTHER TEG exhibitors in that same sector from "
    "sector_wise_participation.md, excluding {company} itself (comma-separated)\n"
    "If no file mentions {company}, set found=false — but still return a "
    "best-guess 'sector' and its 'sector_peers' if the KB makes one obvious."
)

_PERSON_GOAL = (
    "Profile {person}, associated with {company}. Look for a profile file: "
    "list_dir organizers_team/ and speakers/individuals/ and scan for a matching "
    "name, or grep '{person}'. If no file is theirs, check the company's file "
    "under exhibitors/companies/ for a founder/leadership mention.\n"
    "Return facts: designation, seniority, is_technical (true/false), teg_role "
    "(organizer / speaker / founder / none), background.\n"
    "If no file mentions this person, set found=false."
)

_PEERS_GOAL = (
    "List up to 5 TEG exhibitors in the '{sector}' sector from "
    "sector_wise_participation.md. Return them in facts key 'sector_peers' "
    "(comma-separated). Exclude {company}."
)


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


def _split_peers(raw: str, own: str) -> list[str]:
    own_n = _norm(own)
    out: list[str] = []
    seen: set[str] = set()
    for part in (raw or "").split(","):
        name = part.strip().strip("*")
        if not name:
            continue
        n = _norm(name)
        if not n or n == own_n or n in seen:
            continue
        seen.add(n)
        out.append(name)
    return out[:5]


class ResearchAgent(Agent):
    def __init__(
        self, llm, *,
        explorer: KBExplorer | None = None,
        tools: list[ResearchTool] | None = None,
    ) -> None:
        super().__init__(llm)
        self._explorer = explorer or KBExplorer(llm)
        if tools is None:
            tools = [get_web_search(), PageScraper(), LinkedInStub()]
        tools = [t for t in tools if t is not None]
        self._web = next((t for t in tools if t.name == "web"), None)
        self._scraper = next((t for t in tools if t.name == "scrape"), None)
        self._linkedin = next((t for t in tools if t.name == "linkedin"), None)
        self._rules = load_rules()
        # The explorer reports its own confidence in having read the right profile.
        # That is a different scale from the fuzzy name-match score in
        # outreach_rules (auto_accept=0.95), so it gets its own threshold: at or
        # above this we trust the KB and skip the web spend.
        self._kb_trust = 0.7

    async def run(self, intake: IntakeResult) -> ResearchDossier:
        s = get_settings()
        budget = _Budget(s.research_max_searches_per_track, s.research_max_scrapes)
        company = intake.company_name_canonical
        person = intake.person_name
        _log.info("research start  company=%r  person=%r  (web=%s)",
                  company, person, "on" if self._web is not None else "off")

        (c_fields, c_id_conf, c_sources, c_ex), (p_fields, p_id_conf, p_sources, p_ex) = (
            await asyncio.gather(
                self._company_track(intake, budget),
                self._person_track(intake, budget),
            )
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
            _log.info("synthesising %d chars of web/scrape text into firmographic facts",
                      len(raw_ctx))
            synth = await self.llm.generate_structured(
                system=(
                    "Extract firmographic and role facts from research text. "
                    "Only state a field if the text supports it; else leave it null. "
                    "person_company_match: does the text place this person at this company?\n"
                    "sector: if the text describes what the company does but names no formal "
                    "industry, classify it into the CLOSEST Tech Expo Gujarat sector from this "
                    "list (TEG is not IT-only): " + _TEG_SECTORS + ". Leave sector null only "
                    "if the text says nothing about what the company does."
                ),
                messages=[{"role": "user", "content": (
                    f"Person: {person}\nCompany: {company}\n\nResearch text:\n{raw_ctx[:6000]}"
                )}],
                schema=_Synthesis,
            )
            llm_calls = 1

        # A KB hit means we read the company's own profile — trust its sector.
        # A KB miss leaves only the explorer's guess from the company name, which
        # is weaker than a classification made from real web text about the firm.
        if c_ex.found:
            sector = c_fields.get("sector") or synth.sector
        else:
            sector = synth.sector or c_fields.get("sector")
        _log.info("[sector] kb=%r (found=%s)  synth=%r  -> %r",
                  c_fields.get("sector"), c_ex.found, synth.sector, sector)

        peers = _split_peers(c_fields.get("sector_peers", ""), company)
        # Re-fetch peers when we have a sector but no peers for it, or when the
        # sector we settled on is not the one those peers were drawn from.
        if sector and (not peers or sector != c_fields.get("sector")):
            ex = await self._explore(_PEERS_GOAL.format(sector=sector, company=company))
            fresh = _split_peers(ex.facts.get("sector_peers", ""), company)
            peers = fresh or peers
        _log.info("[peers] sector=%r -> %s", sector, peers or "none")

        company_profile = {
            "sector": sector,
            "company_size": c_fields.get("company_size") or synth.company_size,
            "hq": c_fields.get("hq") or synth.hq,
            "founder": c_fields.get("founder") or synth.founder,
            "website": c_fields.get("website"),
            "teg_history": c_fields.get("teg_history"),
            "overview": c_ex.summary or None,
        }
        person_profile = {
            "designation": p_fields.get("designation") or synth.designation,
            "seniority": p_fields.get("seniority") or synth.seniority,
            "is_technical": synth.is_technical,
            "linkedin_url": p_fields.get("linkedin_url"),
            "teg_role": p_fields.get("teg_role"),
            "background": p_fields.get("background") or (p_ex.summary or None),
        }

        relationship = "cold"
        teg_hist = (company_profile.get("teg_history") or "").lower()
        if p_fields.get("teg_role") == "organizer":
            relationship = "insider"
        elif any(k in teg_hist for k in ("2024", "2026", "sponsor")) or \
                p_fields.get("teg_role") == "speaker":
            relationship = "returning"

        field_confidence: dict[str, float] = {}
        for k in c_fields:
            field_confidence[k] = max(field_confidence.get(k, 0.0), c_id_conf)
        for k in p_fields:
            field_confidence[k] = max(field_confidence.get(k, 0.0), p_id_conf)

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
            sources=c_sources + p_sources,
            review_flags=(["person_company_mismatch"] if synth.person_company_match is False else []),
            ask_prospect=ask_prospect,
            research_cost={
                "web_calls": budget.web_calls,
                "scrape_calls": budget.scrape_calls,
                "llm_calls": llm_calls,
            },
        )

    # ---- tracks ----

    async def _explore(self, goal: str) -> ExploreResult:
        try:
            return await asyncio.wait_for(
                self._explorer.explore(goal), timeout=get_settings().kb_explore_timeout_s
            )
        except TimeoutError:
            _log.warning("kb explore timed out after %ss", get_settings().kb_explore_timeout_s)
            return ExploreResult()

    async def _company_track(self, intake: IntakeResult, budget):
        company = intake.company_name_canonical
        ex = await self._explore(_COMPANY_GOAL.format(company=company))
        fields = dict(ex.facts)
        id_conf = ex.confidence if ex.found else 0.0
        sources = [
            SourceRef(field=k, url=None, tool="kb", confidence=ex.confidence) for k in ex.facts
        ]
        _log.info("[company] KB %s  id_conf=%.2f  fields=%s",
                  "hit" if ex.found else "miss", id_conf, list(fields) or "-")
        if not ex.found or ex.confidence < self._kb_trust:
            fields, id_conf, sources = await self._web_fallback(
                "company", company, intake.person_name, budget, fields, id_conf, sources,
            )
        return fields, id_conf, sources, ex

    async def _person_track(self, intake: IntakeResult, budget):
        person = intake.person_name
        ex = await self._explore(
            _PERSON_GOAL.format(person=person, company=intake.company_name_canonical)
        )
        fields = dict(ex.facts)
        id_conf = ex.confidence if ex.found else 0.0
        sources = [
            SourceRef(field=k, url=None, tool="kb", confidence=ex.confidence) for k in ex.facts
        ]
        _log.info("[person] KB %s  id_conf=%.2f  fields=%s",
                  "hit" if ex.found else "miss", id_conf, list(fields) or "-")
        if not ex.found:
            fields, id_conf, sources = await self._web_fallback(
                "person", person, intake.company_name_canonical, budget, fields, id_conf, sources,
            )
        return fields, id_conf, sources, ex

    async def _web_fallback(self, track, subject, context, budget, fields, id_conf, sources):
        """Tavily search -> optional scrape, when the KB explorer came up short."""
        web_left = budget.web_left_company if track == "company" else budget.web_left_person
        if self._web is None or web_left <= 0:
            return fields, id_conf, sources

        _log.info("[%s] web search  subject=%r  context=%r", track, subject, context)
        res = await self._web.lookup(
            ResearchQuery(track=track, subject=subject, context=context, want=[])
        )
        budget.web_calls += 1
        if track == "company":
            budget.web_left_company -= 1
        else:
            budget.web_left_person -= 1
        _log.info("[%s] web %s  url=%s  fields=%s", track,
                  "hit" if res.available else "miss", res.source_url or "-",
                  list(res.fields.keys()) or "-")
        if not res.available:
            return fields, id_conf, sources

        fields.update(res.fields)
        for f in res.fields:
            sources.append(SourceRef(field=f, url=res.source_url, tool="web",
                                     confidence=res.confidence.get(f, 0.0)))
        # a web hit that returned context is a real "found something" signal
        if res.fields.get("web_context"):
            id_conf = max(id_conf, 0.6)

        if self._scraper is not None and res.source_url and budget.scrapes_left > 0:
            _log.info("[%s] scrape  url=%s", track, res.source_url)
            sc = await self._scraper.lookup(ResearchQuery(
                track=track, subject=res.source_url, context=context, want=["page_text"],
            ))
            budget.scrape_calls += 1
            budget.scrapes_left -= 1
            if sc.available:
                fields.update(sc.fields)
                sources.append(SourceRef(field="page_text", url=sc.source_url,
                                         tool="scrape", confidence=0.6))
        return fields, id_conf, sources
