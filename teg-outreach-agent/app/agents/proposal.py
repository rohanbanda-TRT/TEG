from __future__ import annotations

import json

from app.agents.base import Agent
from app.agents.guardrails import (
    PROPOSAL_SAFE_SECTIONS,
    check_message,
    check_overpromise,
    check_testimonial,
)
from app.domain.schemas import (
    IntakeResult,
    Persona,
    Proposal,
    ProposalPackage,
    ProposalPain,
    ResearchDossier,
    SectorFitRow,
)
from app.kb.explorer import KBExplorer
from app.kb.facts import load as _load_facts
from app.obs import get_logger
from config.settings import get_settings

_log = get_logger("agent.proposal")

# KB persona-pain-library headings, keyed by our Persona literal
_PERSONA_KB_HEADING = {
    "it_tech_service": "IT/Tech Service",
    "ai_startup": "AI/Deep-Tech Startup",
    "non_tech_sponsor": "Non-Tech Sponsor",
    "visitor": "Visitor",
}


def _split_csv(raw: str) -> list[str]:
    return [p.strip().strip("*") for p in (raw or "").split(",") if p.strip()]


_PRICING_BY_PERSONA: dict[Persona, ProposalPackage] = {
    "it_tech_service": ProposalPackage(
        name="3m x 3m stall",
        price_line="₹1,17,000 + GST (indicative, confirmed at booking); larger stalls up to ₹4,68,000 + GST for 6m x 6m",
        includes=[
            "2 exhibitor passes", "5 visitor passes", "modular stall + fascia",
            "pre-scheduled 1:1 B2B meetings", "TEG Community Network Portal access",
        ],
        payment_plan="4 instalments of 25% (9 Apr / 30 Jun / 31 Jul / 31 Aug 2026)",
    ),
    "ai_startup": ProposalPackage(
        name="Catalyst Zone (2m x 2m startup stall)",
        price_line="₹35,000 + GST (indicative, confirmed at booking)",
        includes=[
            "2 exhibitor passes", "modular stall + fascia",
            "pre-scheduled 1:1 B2B meetings", "TEG Community Network Portal access",
        ],
        payment_plan="4 instalments of 25% (9 Apr / 30 Jun / 31 Jul / 31 Aug 2026)",
    ),
    "non_tech_sponsor": ProposalPackage(
        name="Official Category Partner (e.g. AI / Real Estate / Banking Partner)",
        price_line=(
            "from ₹6,00,000 + GST for a category partnership up to ₹35,00,000 + GST for "
            "Title Sponsor (all indicative, confirmed at booking)"
        ),
        includes=[
            "category exclusivity", "3m x 3m stall (tier-dependent)",
            "15 visitor + 2-3 VIP passes", "website logo", "stage mention", "on-stage trophy",
        ],
        payment_plan="4 instalments of 25% (9 Apr / 30 Jun / 31 Jul / 31 Aug 2026)",
    ),
    "visitor": ProposalPackage(
        name="Visitor pass",
        price_line="ticketed entry (no free entry); current pricing on the official ticketing portal",
        includes=[
            "access to 250+ exhibitors across 18 industries", "keynote sessions",
            "the TEG networking app",
        ],
        payment_plan="—",
    ),
}


class ProposalAgent(Agent):
    def __init__(self, llm, *, model: str | None = None,
                 explorer: KBExplorer | None = None) -> None:
        super().__init__(llm)
        s = get_settings()
        self._model = model or s.proposal_model or s.llm_model_main
        self._explorer = explorer or KBExplorer(llm)

    async def run(self, data):  # ProposalAgent uses build(), not run()
        raise NotImplementedError("ProposalAgent has no run(); call build()")

    async def build(
        self, *, intake: IntakeResult, dossier: ResearchDossier, persona: Persona,
        transcript: list[dict], learned_facts: dict, session_ref: str, version: int,
        price_requested: bool = False,
    ) -> tuple[Proposal, list[str]]:
        own = intake.company_name_canonical.lower()
        heading = _PERSONA_KB_HEADING.get(persona, "Visitor")
        ex = await self._explorer.explore(
            "Read event_goals_and_problem.md and sector_wise_participation.md.\n"
            "Return facts:\n"
            "- goals: TEG's stated goals (section 2), 2-3 sentences\n"
            "- mechanism: how TEG delivers value (section 3), 2-3 sentences\n"
            "- evidence: past-edition numbers from section 4, verbatim\n"
            f"- pains: a JSON array of [pain, how_TEG_addresses_it] pairs from the "
            f"'### {heading}' subsection of the section 5 pain library (2-4 pairs)\n"
            f"- sector_peers: up to 5 TEG exhibitors in the '{dossier.sector}' sector, "
            f"excluding {intake.company_name_canonical} (comma-separated)\n"
            f"- sector_peer_count: the TOTAL number of companies that participated in the "
            f"'{dossier.sector}' sector at TEG 2024 (from that sector's table/summary in "
            "sector_wise_participation.md) — a single integer, or 0 if the sector is not listed\n"
            "- scale_note: one sentence stating the TEG 2024 -> TEG 2026 scale, using ONLY "
            "verbatim numbers from the KB (e.g. '125+ exhibitors and 8,000+ visitors at TEG "
            "2024; 250+ exhibitors and 15,000+ visitors targeted for TEG 2026')"
        )
        gp_goals = ex.facts.get("goals", "")
        gp_mechanism = ex.facts.get("mechanism", "")
        gp_evidence = ex.facts.get("evidence", "")
        try:
            base_pain_pairs: list = json.loads(ex.facts.get("pains", "[]"))
        except (ValueError, TypeError):
            base_pain_pairs = []
        base_pain_pairs = [
            tuple(p) for p in base_pain_pairs if isinstance(p, (list, tuple)) and len(p) == 2
        ]

        peers = [
            p for p in (
                _split_csv(ex.facts.get("sector_peers", "")) or dossier.peer_companies
            )
            if p.lower() != own
        ][:5]
        try:
            sector_peer_count = int(str(ex.facts.get("sector_peer_count", "0")).strip() or 0)
        except (ValueError, TypeError):
            sector_peer_count = 0
        sector_peer_count = max(sector_peer_count, len(peers))
        scale_note = ex.facts.get("scale_note", "")
        facts = _load_facts()
        testimonials = [
            {"name": t.name, "role": t.role, "quote": t.quote}
            for t in facts.cleared_testimonials
        ]
        industries = list(facts.official_industries)
        fallback_pkg = _PRICING_BY_PERSONA[persona]
        if price_requested:
            pkg_line = (
                f"Recommended package: {fallback_pkg.model_dump()} — use it unless the "
                "conversation points elsewhere, and include its price_line and payment_plan."
            )
        else:
            pkg_line = (
                f"Recommended package name: '{fallback_pkg.name}' with includes "
                f"{fallback_pkg.includes}. Set recommended_package.price_line and payment_plan "
                "to EMPTY strings — state NO figures anywhere in the proposal."
            )

        system = (
            "You write a detailed personalized proposal for a Tech Expo Gujarat 2026 inquiry. "
            "Ground every claim in the facts provided. RULES: no invented statistics. "
            "For testimonials: prefer NOT to quote any; if you do, use ONLY the exact wording and "
            "exact attributed name from the cleared list below, at most 2, and never paraphrase or "
            "re-attribute. Only name peer companies from the provided list. Never state a visitor "
            "ticket price; every price is '+ GST' and 'indicative, confirmed at booking'. Never name "
            "another event or expo. No signature blocks, no 'you agree', no binding-offer language — "
            "this is an information document, not a contract. Personalize 'what_you_told_us' and the "
            "pain points from the actual conversation; keep 2-4 pains."
        )
        convo = "\n".join(f"{m['role']}: {m['content']}" for m in transcript) or "(no messages yet)"
        pain_lines = "\n".join(f"- {p} -> {a}" for p, a in base_pain_pairs)
        testi = "\n".join(f'- {t["name"]} ({t["role"]}): "{t["quote"]}"' for t in testimonials)
        user = (
            f"Persona: {persona}\n"
            f"Person: {intake.person_name}  Company: {intake.company_name_canonical}  Sector: {dossier.sector}\n"
            f"Company facts: {dossier.company_profile}\nPerson facts: {dossier.person_profile}\n"
            f"Learned in chat: {learned_facts}\n\n"
            f"Conversation:\n{convo}\n\n"
            f"TEG goals: {gp_goals}\n\nTEG mechanism: {gp_mechanism}\n\nEvidence: {gp_evidence}\n\n"
            f"Base pain points for this persona (personalize, keep 2-4):\n{pain_lines}\n\n"
            f"Cleared testimonials (quote at most 2 verbatim):\n{testi}\n\n"
            f"TEG's 18 official buyer industries: {industries}\n"
            f"Peer companies you may name (only these): {peers}\n"
            f"Companies in the '{dossier.sector}' sector at TEG 2024 (total): {sector_peer_count}\n"
            f"Scale note (use verbatim, do not alter numbers): {scale_note!r}\n\n"
            f"{pkg_line}\n\n"
            "Also produce:\n"
            "- executive_summary: 3-4 sentences (their role + company, their goal, why TEG fits, "
            "the headline recommendation)\n"
            "- how_a_teg_plays_out: 3-6 bullets walking the 3 days, tuned to their goal\n"
            "- roi_framing: a value paragraph with NO numbers and NO promised outcomes — phrase it "
            "'if a single engagement covers the investment many times over'\n"
            "- sector_fit: 4-6 {lever, weight} rows; weight 1-5 = how much each TEG lever matters "
            f"for the '{dossier.sector}' sector (use the pain library)\n"
            f"- peers_in_sector_total: echo the integer {sector_peer_count} exactly\n"
            "- target_industries: from TEG's 18 official buyer industries listed above, the "
            "3-6 whose buyers this company actually sells to, based on the conversation and "
            "their company profile. Copy the names EXACTLY as listed. Most-relevant first. "
            "If the conversation gives no signal about who they sell to, return an empty list.\n"
            "- target_industries_note: one sentence saying why those industries are the ones "
            "that matter for them. No numbers, no promised outcomes. Empty if the list is empty.\n"
            "- peer_context_line: ONE sentence giving the named peers their context, e.g. "
            f"'{sector_peer_count} companies in {dossier.sector} exhibited at TEG 2024 — "
            "including the names below.' Use the real sector name and the real count; if the "
            "count is 0 or there are no named peers, set this to an empty string.\n"
            "Also write landing-page copy:\n"
            "- hero_headline: a punchy 6-12 word line naming the outcome for "
            f"{intake.company_name_canonical} (e.g. 'Turn TEG 2026 into your India-market "
            "pipeline'). No numbers, no guaranteed outcomes.\n"
            "- hero_subline: one sentence expanding the headline.\n"
            "- closing_cta_headline: a short line for the final call-to-action section.\n"
            "- closing_cta_body: 1-2 sentences pushing the reader to act (reply in chat / "
            "reach the team). No numbers, no promises.\n"
            "- section_ctas: a JSON object with short button labels for keys "
            "'priorities', 'charts', 'investment'.\n\n"
            f"Echo these exactly: generated_on='__DATE__', session_ref='{session_ref}', version={version}, "
            f"company='{intake.company_name_canonical}', person='{intake.person_name}', persona='{persona}'.\n"
            "Produce the Proposal."
        )

        _log.info(
            "build  persona=%s  company=%r  sector=%r  peers=%d  base_pains=%d  testimonials=%d  kb_found=%s",
            persona, intake.company_name_canonical, dossier.sector, len(peers),
            len(base_pain_pairs), len(testimonials), ex.found,
        )
        proposal = await self.llm.generate_structured(
            system=system, messages=[{"role": "user", "content": user}],
            schema=Proposal, model=self._model,
        )

        def _clamp_sector_fit(p: Proposal) -> None:
            p.sector_fit = [
                SectorFitRow(lever=r.lever, weight=max(1, min(5, r.weight)))
                for r in p.sector_fit[:6]
            ]

        def _force_no_price(p: Proposal) -> None:
            p.recommended_package.price_line = ""
            p.recommended_package.payment_plan = ""

        def all_violations(p: Proposal) -> list:
            texts: list[tuple[str, str]] = [
                ("what_you_told_us", p.what_you_told_us),
                ("lead_generation", p.lead_generation),
                ("price_line", p.recommended_package.price_line),
                ("executive_summary", p.executive_summary),
                ("roi_framing", p.roi_framing),
                ("hero_headline", p.hero_headline),
                ("hero_subline", p.hero_subline),
                ("closing_cta_body", p.closing_cta_body),
                ("peer_context_line", p.peer_context_line),
            ]
            for i, pn in enumerate(p.pains):
                texts.append((f"pain::{i}", pn.pain))
                texts.append((f"teg_answer::{i}", pn.teg_answer))
            for i, pr in enumerate(p.proof):
                texts.append((f"proof::{i}", pr))
            for i, ns in enumerate(p.next_steps):
                texts.append((f"next_step::{i}", ns))
            for i, st in enumerate(p.how_a_teg_plays_out):
                texts.append((f"walkthrough::{i}", st))
            found = []
            for label, txt in texts:
                for v in check_message(txt, allowed_peers=peers, persona=persona,
                                       price_ok=price_requested):
                    found.append((label, v))
            for label in ("roi_framing", "hero_headline", "hero_subline", "closing_cta_body"):
                op = check_overpromise(getattr(p, label))
                if op:
                    found.append((label, op))
            return found

        def _clamp_target_industries(p: Proposal) -> None:
            """Only ever name real TEG sectors, matched case-insensitively, no dupes."""
            by_lower = {i.lower(): i for i in industries}
            seen: set[str] = set()
            keep: list[str] = []
            for raw in p.target_industries:
                canon = by_lower.get(str(raw).strip().lower())
                if canon and canon not in seen:
                    seen.add(canon)
                    keep.append(canon)
            p.target_industries = keep[:6]
            if not p.target_industries:
                p.target_industries_note = ""

        def _clamp_section_ctas(p: Proposal) -> None:
            p.section_ctas = {
                k: str(v)[:40]
                for k, v in (p.section_ctas or {}).items()
                if k in ("priorities", "charts", "investment")
            }

        async def _testimonial_violation(p: Proposal):
            blob = " ".join([
                p.what_you_told_us, p.lead_generation, p.executive_summary, p.roi_framing,
                p.hero_subline, p.closing_cta_body,
                *(pn.teg_answer for pn in p.pains), *p.proof,
            ])
            return await check_testimonial(blob, self.llm)

        if not price_requested:
            _force_no_price(proposal)
        _clamp_sector_fit(proposal)
        _clamp_target_industries(proposal)
        _clamp_section_ctas(proposal)
        violations = all_violations(proposal)
        t_v = await _testimonial_violation(proposal)
        if t_v:
            violations.append(("proof::0", t_v))

        if violations:
            codes = sorted({v.code for _, v in violations})
            _log.warning("proposal draft violated %s -> regenerating once", codes)
            proposal = await self.llm.generate_structured(
                system=system + f"\nYour previous draft violated: {codes}. Fix every one.",
                messages=[{"role": "user", "content": user}],
                schema=Proposal, model=self._model,
            )
            if not price_requested:
                _force_no_price(proposal)
            _clamp_sector_fit(proposal)
            _clamp_target_industries(proposal)
            _clamp_section_ctas(proposal)
            violations = all_violations(proposal)
            t_v = await _testimonial_violation(proposal)
            if t_v:
                violations.append(("proof::0", t_v))

        flags: list[str] = []
        if violations:
            flags = sorted({v.code for _, v in violations})
            bad = {label for label, _ in violations}
            if "what_you_told_us" in bad:
                proposal.what_you_told_us = PROPOSAL_SAFE_SECTIONS["what_you_told_us"][persona]
            if "lead_generation" in bad:
                proposal.lead_generation = PROPOSAL_SAFE_SECTIONS["lead_generation"][persona]
            if "executive_summary" in bad:
                proposal.executive_summary = PROPOSAL_SAFE_SECTIONS["executive_summary"][persona]
            if "roi_framing" in bad:
                proposal.roi_framing = PROPOSAL_SAFE_SECTIONS["roi_framing"][persona]
            if "hero_headline" in bad:
                proposal.hero_headline = PROPOSAL_SAFE_SECTIONS["hero_headline"][persona]
            if "hero_subline" in bad:
                proposal.hero_subline = PROPOSAL_SAFE_SECTIONS["hero_subline"][persona]
            if "closing_cta_body" in bad:
                proposal.closing_cta_body = PROPOSAL_SAFE_SECTIONS["closing_cta_body"][persona]
            if "price_line" in bad:
                proposal.recommended_package = fallback_pkg
                if not price_requested:
                    _force_no_price(proposal)
            for i in range(len(proposal.pains)):
                if f"pain::{i}" in bad or f"teg_answer::{i}" in bad:
                    src = (
                        base_pain_pairs[i % len(base_pain_pairs)][0]
                        if base_pain_pairs else "Reaching the right buyers"
                    )
                    proposal.pains[i] = ProposalPain(
                        pain=src, teg_answer=PROPOSAL_SAFE_SECTIONS["pain_answer"][persona]
                    )
            proposal.proof = [
                (pr if f"proof::{i}" not in bad else PROPOSAL_SAFE_SECTIONS["proof_bullet"][persona])
                for i, pr in enumerate(proposal.proof)
            ] or [PROPOSAL_SAFE_SECTIONS["proof_bullet"][persona]]
            proposal.next_steps = [
                (ns if f"next_step::{i}" not in bad else PROPOSAL_SAFE_SECTIONS["next_step"][persona])
                for i, ns in enumerate(proposal.next_steps)
            ] or [PROPOSAL_SAFE_SECTIONS["next_step"][persona]]

        # force trusted fields
        proposal.company = intake.company_name_canonical
        proposal.person = intake.person_name
        proposal.persona = persona
        proposal.sector = dossier.sector
        proposal.session_ref = session_ref
        proposal.version = version
        proposal.peer_companies = [p for p in proposal.peer_companies if p in peers][:5] or peers[:3]
        proposal.peers_in_sector_total = sector_peer_count
        proposal.scale_note = scale_note
        if not proposal.peer_companies or "peer_context_line" in {label for label, _ in violations}:
            proposal.peer_context_line = ""
        if not proposal.contact:
            proposal.contact = "info@techexpogujarat.com · +91 98989 23712"
        _log.info("build done  package=%r  pains=%d  flags=%s",
                  proposal.recommended_package.name, len(proposal.pains), flags or "-")
        return proposal, flags
