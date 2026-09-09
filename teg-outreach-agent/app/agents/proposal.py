from __future__ import annotations

import json
import re
from pathlib import Path

from app.agents.base import Agent
from app.claude.cli import ClaudeCli
from app.claude.prompt_builder import render_skill
from app.claude.skill_loader import load_skill
from app.agents.guardrails import (
    PROPOSAL_SAFE_SECTIONS,
    GuardrailViolation,
    check_message,
    check_overpromise,
    check_testimonial,
)
from app.domain.schemas import (
    GROWTH_STAGES,
    MAX_JOURNEY_POINTS,
    ConversationSignals,
    IntakeResult,
    JourneyStage,
    Persona,
    Proposal,
    ProposalPackage,
    ProposalPain,
    ResearchDossier,
    SectorFitRow,
)
from app.kb.explorer import KBExplorer, default_explorer
from app.kb.facts import load as _load_facts
from app.kb.pricing import load_pricing
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


# ---- package-tier accuracy + cross-field self-consistency ----
# docs/superpowers/specs/2026-09-10-verification-harness-and-graph-design.md §3.2

_TIER_INDEX = {"base": 0, "mid": 1, "upsized": 2}

_CONVO_SIGNALS_SYSTEM = (
    "Read the conversation transcript between a Tech Expo Gujarat outreach agent "
    "and a prospect. Extract ONLY whether the prospect explicitly asked for a "
    "bigger stall/sponsorship tier than the standard base offering — e.g. a "
    "corner stall, a 6x6, multiple demo stations, a bigger booth, a higher "
    "sponsorship category. "
    "requested_tier: 'mid' for a moderately bigger ask (e.g. a corner stall), "
    "'upsized' for a clearly bigger ask (e.g. a 6x6 or the largest tier), null if "
    "there is no such signal at all. "
    "signal_confidence: 'explicit' ONLY if the prospect said so in plain words "
    "(e.g. 'we need a corner stall for two demo stations'); 'inferred' if you are "
    "reading between the lines from context clues rather than a direct statement; "
    "null if requested_tier is null. NEVER GUESS — when in doubt between explicit "
    "and inferred, choose inferred; when in doubt whether there is a signal at "
    "all, leave requested_tier null. "
    "demo_stations: an integer count of demo stations/booths mentioned, or null. "
    "notes: one short sentence quoting or paraphrasing what in the transcript led "
    "to your answer, for a human reviewer — empty string if requested_tier is null."
)


async def _extract_conversation_signals(llm, transcript: list[dict]) -> ConversationSignals:
    """Structured extraction from `transcript` — the piece that lets
    build_generation_prompt (here, ProposalAgent.build()) pick the right
    package tier on the FIRST pass instead of relying only on the
    after-the-fact consistency check below."""
    if not transcript:
        return ConversationSignals()
    convo = "\n".join(f"{m['role']}: {m['content']}" for m in transcript)
    try:
        return await llm.generate_structured(
            system=_CONVO_SIGNALS_SYSTEM,
            messages=[{"role": "user", "content": f"Transcript:\n{convo}"}],
            schema=ConversationSignals,
        )
    except Exception as exc:  # noqa: BLE001 — a soft-fail: stay at the base tier
        _log.warning("extract_conversation_signals failed (%s); no signal", exc)
        return ConversationSignals()


def _select_tier(persona: Persona, signals: ConversationSignals) -> ProposalPackage:
    ladder = load_pricing()[persona]
    if signals.requested_tier is None or signals.signal_confidence != "explicit":
        # Never Guess — same convention teg-kb-agent's own SKILL.md already
        # enforces for the KB itself; an inferred-but-not-explicit signal is
        # not enough to change what the prospect is offered.
        return ladder[0]
    idx = _TIER_INDEX[signals.requested_tier]
    return ladder[min(idx, len(ladder) - 1)]  # visitor's 1-entry ladder always resolves to itself


def _journey_action_agrees_with_playout(growth_journey, how_a_teg_plays_out: list[str]) -> bool:
    """Both fields describe TEG's own three-day plan (no transcript signal to
    check either against — see check_section_consistency's docstring), so
    this stays a narrow, deterministic prose-vs-prose check: do the two
    fields name the same explicit day numbers, when either names any at all?
    """
    action = next((s for s in growth_journey if s.stage == "action"), None)
    if action is None or not how_a_teg_plays_out:
        return True
    action_text = " ".join([action.title, *action.points])
    playout_text = " ".join(how_a_teg_plays_out)
    action_days = set(re.findall(r"\bday\s*(\d+)\b", action_text, re.I))
    playout_days = set(re.findall(r"\bday\s*(\d+)\b", playout_text, re.I))
    if action_days and playout_days and action_days.isdisjoint(playout_days):
        return False
    return True


def check_section_consistency(
    p: Proposal, signals: ConversationSignals, price_requested: bool,
) -> list[GuardrailViolation]:
    """Cross-field checks the per-field guardrail loop structurally can't see.

    The package-tier check compares against `signals` — the structured
    extraction from the real transcript — rather than against another
    generated field, so a shared blind spot in generation can't produce two
    fields that agree with each other while both disagree with what the
    prospect actually said. The other two checks stay prose-vs-prose (or
    prose-vs-flag) deliberately: neither has a structured signal to compare
    against instead (see the comments on each).
    """
    out: list[GuardrailViolation] = []

    # Package tier vs. the structured transcript signal. `visitor` has no
    # tier-ladder concept at all (a single fixed entry, §5 non-goal) — skip
    # explicitly rather than relying on _select_tier's single-entry ladder to
    # collapse any mismatch away silently.
    if p.persona != "visitor" and signals.requested_tier and signals.signal_confidence == "explicit":
        expected = _select_tier(p.persona, signals)
        if p.recommended_package.name != expected.name:
            out.append(GuardrailViolation(
                "SECTION_INCONSISTENCY::package_tier",
                f"recommended_package is '{p.recommended_package.name}' but the transcript "
                f"explicitly signals '{signals.requested_tier}' ('{expected.name}')",
            ))

    # price_requested vs. whether a price actually shipped. price_requested
    # is already ground truth (a build() parameter, not extracted from
    # prose) — the only question is whether recommended_package respected it.
    if p.recommended_package.price_line and not price_requested:
        out.append(GuardrailViolation(
            "SECTION_INCONSISTENCY::price_without_request",
            "a price appears though price_requested is False",
        ))

    # growth_journey's "action" stage vs. how_a_teg_plays_out — kept
    # prose-vs-prose: both fields are TEG's own three-day plan, not anything
    # the prospect said, so conversation_signals has nothing to check either
    # one against.
    if p.growth_journey and not _journey_action_agrees_with_playout(
        p.growth_journey, p.how_a_teg_plays_out,
    ):
        out.append(GuardrailViolation(
            "SECTION_INCONSISTENCY::journey_playout_mismatch",
            "growth_journey's action stage and how_a_teg_plays_out describe incompatible day-of plans",
        ))

    return out


def _inferred_tier_note(persona: Persona, signals: ConversationSignals) -> str | None:
    """A real signal exists but isn't explicit enough for _select_tier to act
    on — surfaced as its own, distinct, low-severity flag so a human reviewer
    can tell "we corrected it" (SECTION_INCONSISTENCY::package_tier) from "we
    noticed a hint and did nothing — you may want to look"
    (SECTION_INCONSISTENCY::package_tier_inferred_only). Never changes
    recommended_package."""
    if persona == "visitor":
        return None
    if signals.requested_tier and signals.signal_confidence == "inferred":
        return "SECTION_INCONSISTENCY::package_tier_inferred_only"
    return None


class ProposalAgent(Agent):
    def __init__(self, llm, *, model: str | None = None,
                 explorer: KBExplorer | None = None,
                 claude_cli: "ClaudeCli | None" = None) -> None:
        super().__init__(llm)
        s = get_settings()
        self._model = model or s.proposal_model or s.llm_model_main
        self._explorer = explorer or default_explorer(llm)
        # Claude-CLI backend: opt-in, so the LLM-client path stays the default
        # until the CLI path is proven. Guardrails are identical either way.
        self._claude = claude_cli
        if self._claude is None and s.claude_cli_enabled:
            self._claude = ClaudeCli()
        self._claude_model = s.claude_cli_model
        self._claude_timeout_s = s.claude_cli_timeout_s
        self._skills_path = s.skills_path

    async def run(self, data):  # ProposalAgent uses build(), not run()
        raise NotImplementedError("ProposalAgent has no run(); call build()")

    async def _generate(self, system: str, user: str) -> Proposal:
        """One structured Proposal, from whichever backend is configured."""
        if self._claude is None:
            return await self.llm.generate_structured(
                system=system, messages=[{"role": "user", "content": user}],
                schema=Proposal, model=self._model,
            )
        # Pick up a key connected at runtime via POST /claude/connect. The
        # agent may outlive the connection change, so re-read it per call.
        if not self._claude.api_key:
            from app.api.claude_conn import get_api_key

            self._claude.api_key = get_api_key() or ""
        result = await self._claude.generate(
            model=self._claude_model,
            system_prompt=system,
            user_prompt=user,
            json_schema=Proposal.model_json_schema(),
            cwd=str(Path(self._skills_path).resolve().parent),
            timeout_s=self._claude_timeout_s,
        )
        # Validate here so a malformed payload fails the same way the LLM
        # client's own schema validation would, before any guardrail runs.
        return Proposal.model_validate(result.data)

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
        # Tier selection happens BEFORE generation, regardless of
        # price_requested — the package's name/includes appear in the
        # proposal either way (§3.2.2). check_section_consistency below is a
        # safety net for cases this first pass missed, not the only
        # mechanism doing tier selection.
        conversation_signals = await _extract_conversation_signals(self.llm, transcript)
        fallback_pkg = _select_tier(persona, conversation_signals)
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
            "You write a business-focused proposal answering: 'Could Tech Expo Gujarat become a "
            "growth channel for this prospect?' Ground every claim in the facts provided. "
            "RULES: no invented statistics, revenue, growth rates, lead counts, conversion rates, ROI, "
            "deal sizes, or sales cycles. For testimonials: prefer NOT to quote any; if you do, use "
            "ONLY the exact wording and exact attributed name from the cleared list below, at most 2, "
            "and never paraphrase or re-attribute. Only name peer companies from the provided list. "
            "Never state a visitor ticket price; every price is '+ GST' and 'indicative, confirmed at "
            "booking'. Never name another event or expo. No signature blocks, no 'you agree', no "
            "binding-offer language — this is an information document, not a contract. "
            "LANGUAGE RULES: Use tentative language ('could', 'may', 'potential', 'opportunity to "
            "explore') for anything not verified. Never state internal company problems unless "
            "explicitly supported. Never say '15,000+ decision-makers' — correct to '15,000+ visitors' "
            "with SME/MSME decision-makers as target audience. Personalize 'what_you_told_us' and "
            "the pain points from the actual conversation; keep 2-4 pains."
        )
        if self._claude is not None:
            # Skills-as-prompt-assets: the durable voice/rules live in
            # skills/teg-proposal/, editable without touching Python.
            try:
                skill = load_skill(
                    self._skills_path, "teg-proposal",
                    references=["pain-library.md", "teg-mechanism.md"],
                )
                system = render_skill(skill)
            except FileNotFoundError:
                _log.warning("teg-proposal skill missing; falling back to the inline prompt")
        convo = "\n".join(f"{m['role']}: {m['content']}" for m in transcript) or "(no messages yet)"
        pain_lines = "\n".join(f"- {p} -> {a}" for p, a in base_pain_pairs)
        testi = "\n".join(f'- {t["name"]} ({t["role"]}): "{t["quote"]}"' for t in testimonials)

        # discovery-v2 escape hatch: the prospect insisted on a proposal before
        # discovery was complete. Surface the gaps as an explicit instruction so
        # the model states its assumptions instead of fabricating.
        _missing_ctx = None
        if isinstance(learned_facts, dict) and learned_facts.get("_missing_context"):
            _missing_ctx = list(learned_facts["_missing_context"])
            learned_facts = {k: v for k, v in learned_facts.items() if k != "_missing_context"}
        missing_line = (
            f"NOT established in the conversation — do NOT invent these; where the "
            f"proposal needs them, say plainly it is working from an assumption: "
            f"{', '.join(_missing_ctx)}\n\n"
            if _missing_ctx else ""
        )

        user = (
            f"Persona: {persona}\n"
            f"Person: {intake.person_name}  Company: {intake.company_name_canonical}  Sector: {dossier.sector}\n"
            f"Company facts: {dossier.company_profile}\nPerson facts: {dossier.person_profile}\n"
            f"Learned in chat: {learned_facts}\n\n"
            f"{missing_line}"
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
        proposal = await self._generate(system, user)

        def _clamp_sector_fit(p: Proposal) -> None:
            p.sector_fit = [
                SectorFitRow(lever=r.lever, weight=max(1, min(5, r.weight)))
                for r in p.sector_fit[:6]
            ]

        def _clamp_growth_journey(p: Proposal) -> None:
            """The six stages, in order, once each, 3-5 points apiece.

            The argument only reads if the whole chain is present in sequence,
            so a partial journey is dropped entirely rather than shown broken.
            """
            by_stage: dict[str, JourneyStage] = {}
            for s in p.growth_journey:
                if s.stage in GROWTH_STAGES and s.stage not in by_stage:
                    by_stage[s.stage] = JourneyStage(
                        stage=s.stage,
                        title=str(s.title)[:120],
                        points=[str(pt)[:200] for pt in s.points][:MAX_JOURNEY_POINTS],
                    )
            if set(by_stage) == set(GROWTH_STAGES):
                p.growth_journey = [by_stage[k] for k in GROWTH_STAGES]
            else:
                p.growth_journey = []

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
            for si, stg in enumerate(p.growth_journey):
                texts.append((f"journey::{si}::title", stg.title))
                for pi, pt in enumerate(stg.points):
                    texts.append((f"journey::{si}::{pi}", pt))
            found = []
            for label, txt in texts:
                for v in check_message(txt, allowed_peers=peers, persona=persona,
                                       price_ok=price_requested):
                    found.append((label, v))
            for label in ("roi_framing", "hero_headline", "hero_subline", "closing_cta_body"):
                op = check_overpromise(getattr(p, label))
                if op:
                    found.append((label, op))
            # the growth journey argues outcomes — hold it to the same line
            for si, stg in enumerate(p.growth_journey):
                for pi, pt in enumerate([stg.title, *stg.points]):
                    op = check_overpromise(pt)
                    if op:
                        found.append((f"journey::{si}::{pi}", op))
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
        _clamp_growth_journey(proposal)
        _clamp_target_industries(proposal)
        _clamp_section_ctas(proposal)
        violations = all_violations(proposal)
        t_v = await _testimonial_violation(proposal)
        if t_v:
            violations.append(("proof::0", t_v))

        if violations:
            codes = sorted({v.code for _, v in violations})
            _log.warning("proposal draft violated %s -> regenerating once", codes)
            first_draft = proposal
            first_violations = violations
            try:
                proposal = await self._generate(
                    system + f"\nYour previous draft violated: {codes}. Fix every one.", user
                )
                if not price_requested:
                    _force_no_price(proposal)
                _clamp_sector_fit(proposal)
                _clamp_growth_journey(proposal)
                _clamp_target_industries(proposal)
                _clamp_section_ctas(proposal)
                violations = all_violations(proposal)
                t_v = await _testimonial_violation(proposal)
                if t_v:
                    violations.append(("proof::0", t_v))
            except (RuntimeError, TimeoutError) as exc:
                # A failed regenerate must not lose the proposal — fall back to
                # the first draft and let the safe-fallback pass below scrub the
                # flagged sections.
                _log.warning("regenerate failed (%s); using first draft + safe fallback", exc)
                proposal = first_draft
                violations = first_violations

        flags: list[str] = []
        if violations:
            flags = sorted({v.code for _, v in violations})
            bad = {label for label, _ in violations}
            # No safe stand-in for a per-prospect journey stage — if any part
            # of it still breaks a rule, drop the whole journey (the page just
            # omits that section).
            if any(label.startswith("journey::") for label in bad):
                proposal.growth_journey = []
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

        # Cross-field self-consistency (§3.2) — after the per-field guardrail
        # loop above, which structurally cannot see a field that's
        # individually clean but contradicts a *different* field.
        consistency_violations = check_section_consistency(
            proposal, conversation_signals, price_requested,
        )
        loops = 0
        while consistency_violations and loops < get_settings().proposal_consistency_max_loops:
            proposal = await self._regenerate_sections(
                proposal, consistency_violations, conversation_signals,
                system=system, user=user, persona=persona,
            )
            consistency_violations = check_section_consistency(
                proposal, conversation_signals, price_requested,
            )
            loops += 1

        if consistency_violations:
            for v in consistency_violations:
                if v.code not in flags:
                    flags.append(v.code)
            proposal = self._resolve_by_safety_order(
                proposal, consistency_violations, conversation_signals, persona,
            )

        inferred_note = _inferred_tier_note(persona, conversation_signals)
        if inferred_note and inferred_note not in flags:
            flags.append(inferred_note)

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

    async def _regenerate_sections(
        self, proposal: Proposal, violations: list[GuardrailViolation],
        signals: ConversationSignals, *, system: str, user: str, persona: Persona,
    ) -> Proposal:
        """Re-prompt naming the SPECIFIC contradiction (§3.2.3), not "fix it
        however" — for a package_tier violation this names the exact tier
        `signals` indicated, the same structured target `_select_tier` would
        have picked on a first pass. Only the violated field(s) are taken
        from the regenerated draft; everything else keeps the original
        proposal's content, so a retry aimed at one contradiction can't
        accidentally clobber an already-good field elsewhere."""
        codes = {v.code for v in violations}
        detail_bits: list[str] = []
        if "SECTION_INCONSISTENCY::package_tier" in codes:
            expected = _select_tier(persona, signals)
            detail_bits.append(
                f"recommended_package must be exactly the '{expected.name}' tier "
                f"(price_line={expected.price_line!r}, includes={expected.includes}, "
                f"payment_plan={expected.payment_plan!r}) — the transcript explicitly asked for it."
            )
        if "SECTION_INCONSISTENCY::price_without_request" in codes:
            detail_bits.append(
                "recommended_package.price_line and payment_plan must be EMPTY strings — "
                "no price was requested."
            )
        if "SECTION_INCONSISTENCY::journey_playout_mismatch" in codes:
            detail_bits.append(
                "how_a_teg_plays_out must describe the SAME three-day plan as growth_journey's "
                "'action' stage — make them agree on which day is which."
            )
        extra = (
            f"\nYour previous draft has section-consistency problems: {sorted(codes)}. "
            + " ".join(detail_bits)
        )
        try:
            regenerated = await self._generate(system + extra, user)
        except (RuntimeError, TimeoutError) as exc:
            _log.warning("section-consistency regenerate failed (%s); keeping prior draft", exc)
            return proposal

        updated = proposal.model_copy(deep=True)
        if "SECTION_INCONSISTENCY::package_tier" in codes or \
                "SECTION_INCONSISTENCY::price_without_request" in codes:
            updated.recommended_package = regenerated.recommended_package
        if "SECTION_INCONSISTENCY::journey_playout_mismatch" in codes:
            updated.how_a_teg_plays_out = regenerated.how_a_teg_plays_out
            updated.growth_journey = regenerated.growth_journey
        return updated

    def _resolve_by_safety_order(
        self, proposal: Proposal, violations: list[GuardrailViolation],
        signals: ConversationSignals, persona: Persona,
    ) -> Proposal:
        """Two rules, not one — see §3.2.4 for why. Rule A (package_tier) has
        a structured signal to correct TOWARD, so it corrects the canned
        field rather than protecting it as-is. Rule B (the other two kinds)
        has no such signal, so it scrubs to the safe fallback, as originally
        specified."""
        updated = proposal.model_copy(deep=True)
        for v in violations:
            if v.code == "SECTION_INCONSISTENCY::package_tier":
                # Rule A: recommended_package was the field that was wrong —
                # correct it to match the structured signal, don't protect it.
                updated.recommended_package = _select_tier(persona, signals)
            elif v.code == "SECTION_INCONSISTENCY::price_without_request":
                # Rule B: no "more correct" price to substitute — only the
                # fact that one shouldn't be there.
                updated.recommended_package.price_line = ""
                updated.recommended_package.payment_plan = ""
            elif v.code == "SECTION_INCONSISTENCY::journey_playout_mismatch":
                # Rule B: both fields are TEG-authored opinions with no
                # transcript truth behind either — scrub the narrower field,
                # keep growth_journey's six-stage structure intact.
                updated.how_a_teg_plays_out = [
                    PROPOSAL_SAFE_SECTIONS["how_a_teg_plays_out"][persona]
                ]
        return updated
