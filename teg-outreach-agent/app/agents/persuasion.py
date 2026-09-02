from __future__ import annotations

import re
from typing import get_args

from pydantic import BaseModel

from app.agents.base import Agent
from app.agents.guardrails import SAFE_TEMPLATES, check_message, check_testimonial
from app.domain.schemas import (
    CtaStatus,
    IntakeResult,
    Persona,
    PersuasionInit,
    PersuasionTurn,
    ResearchDossier,
)
from app.obs import get_logger
from config.outreach_rules import load_rules
from config.settings import get_settings

_log = get_logger("agent.persuasion")

_PERSONA_VALUES: tuple[Persona, ...] = get_args(Persona)

_PERSONA_DEFINITIONS = (
    "- it_tech_service: an IT / software / technology services or product company "
    "(software dev, cloud, SaaS, data, ERP/CRM, IoT, cybersecurity, QA, digital "
    "engineering, automation). They would exhibit to reach B2B buyers.\n"
    "- ai_startup: a small / early-stage AI or deep-tech company (roughly < 50 people, "
    "or self-describes as a startup) that wants an affordable stall, AI demo space, or "
    "investor access.\n"
    "- non_tech_sponsor: a company from a non-tech industry (real estate, automobile, "
    "banking, manufacturing, FMCG, etc.) interested in sponsoring / brand association, "
    "not exhibiting a tech product.\n"
    "- visitor: an individual attending to learn / discover / network — no clear "
    "exhibiting or sponsoring intent, or we genuinely can't tell what they'd do."
)


class _PersonaChoice(BaseModel):
    persona: Persona
    reason: str


async def classify_persona(
    llm,
    intake: IntakeResult,
    dossier: ResearchDossier,
    *,
    extra_context: str = "",
    model: str | None = None,
) -> Persona:
    """Ask the LLM to pick the best persona from the full picture.

    Falls back to ``visitor`` on any LLM failure — the safest, lowest-commitment pitch.
    """
    facts = {
        "company": intake.company_name_canonical,
        "resolved_sector": dossier.sector,
        "company_profile": dossier.company_profile,
        "person_profile": dossier.person_profile,
        "relationship_to_teg": dossier.relationship,
        "stated_intent": intake.intent_hint,
        "person_designation": intake.provided_fields and dossier.person_profile.get("designation"),
    }
    user = (
        "Classify this Tech Expo Gujarat 2026 inquiry into ONE persona.\n\n"
        f"Known facts:\n{facts}\n"
        + (f"\nWhat the prospect just told us in chat:\n{extra_context}\n" if extra_context else "")
        + "\nPersonas:\n"
        + _PERSONA_DEFINITIONS
        + "\n\nPick the single best fit. If the company clearly sells or builds "
        "technology, prefer it_tech_service (or ai_startup when it's a small AI/deep-tech "
        "firm) over visitor, even if their customers are in another industry."
    )
    try:
        choice = await llm.generate_structured(
            system="You are a precise B2B event lead classifier. Return exactly one persona.",
            messages=[{"role": "user", "content": user}],
            schema=_PersonaChoice,
            model=model,
        )
    except Exception as exc:  # noqa: BLE001 — classification must never break the pipeline
        _log.warning("persona classification failed (%s) -> visitor", exc)
        return "visitor"
    persona = choice.persona if choice.persona in _PERSONA_VALUES else "visitor"
    _log.info("persona=%s  reason=%s", persona, choice.reason)
    return persona


def target_cta_for(persona: Persona) -> str:
    return {
        "it_tech_service": "book_stall",
        "ai_startup": "catalyst_zone_or_pitch",
        "non_tech_sponsor": "request_sponsor_call",
        "visitor": "register_visitor",
    }[persona]


def _price_free(text: str) -> str:
    """Strip any sentence containing a ₹ figure — used when a safe-template
    fallback fires but the prospect never asked about cost."""
    keep = [
        s for s in re.split(r"(?<=[.!?])\s+", text)
        if "₹" not in s
    ]
    return " ".join(keep).strip() or (
        "Tech Expo Gujarat 2026 runs 27-29 November 2026 at GUCEC, Ahmedabad. "
        "What would make taking part worthwhile for your team?"
    )


_PRICING_LINE = {
    "it_tech_service": "A 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed at booking); larger stalls scale up to ₹4,68,000 + GST for 6m x 6m.",
    "ai_startup": "The startup-focused Catalyst Zone is ₹35,000 + GST (indicative, confirmed at booking).",
    "non_tech_sponsor": "Sponsorship runs from the Title Sponsor at ₹35,00,000 + GST down to focused partner slots (all + GST, indicative, confirmed at booking).",
    "visitor": "Entry is ticketed (no free entry); current visitor pricing is on the official ticketing portal.",
}


class _Analysis(BaseModel):
    reply: str
    detected_cta: str | None = None
    cta_status: CtaStatus = "none"
    cta_type: str | None = None
    cta_detail: dict = {}
    should_handoff: bool = False
    discovery: dict = {}          # {goal?, target_market?, scale?, timeline?, concern?} learned this turn
    asked_about_price: bool = False   # the prospect asked about cost / raised budget this turn
    wants_proposal: bool = False


class PersuasionAgent(Agent):
    def __init__(self, llm, *, fast_model: str | None = None) -> None:
        super().__init__(llm)
        self._rules = load_rules()
        self._fast_model = fast_model or get_settings().llm_model_fast

    async def run(self, data):  # PersuasionAgent uses init()/respond(), not run()
        raise NotImplementedError("PersuasionAgent has no run(); call init() or respond()")

    _REQUIRED_DISCOVERY = ("goal", "target_market", "scale")

    def _system(
        self, persona: Persona, dossier: ResearchDossier, *,
        learned_facts: dict, price_requested: bool,
    ) -> str:
        props = self._rules.persona_triggers.get(persona, {}).get("value_props", [])
        tone = {
            "insider": (
                "This person is on the Tech Expo Gujarat organizing team. Do NOT pitch "
                "them, quote prices, or push a CTA unless they explicitly ask. Talk "
                "peer-to-peer as a fellow organiser. Ask what they need sorted for their "
                "company this year (booth, a bigger presence, speaking, something else)."
            ),
            "returning": (
                "This company/person has taken part in TEG before — welcome them back "
                "and reference their specific history."
            ),
            "cold": "First contact — warm and curious, not familiar.",
        }[dossier.relationship]
        peers = dossier.peer_companies[:3]
        peer_line = (
            f"Social proof: companies in their own sector are already taking part — "
            f"{', '.join(peers)}. You may name one or two naturally to show they'd be in "
            f"good company. Never name a company not on this list.\n"
            if peers and dossier.relationship != "insider"
            else "Do not name other companies unless given a peer list.\n"
        )
        known = sorted(k for k in self._REQUIRED_DISCOVERY if learned_facts.get(k))
        missing = [k for k in self._REQUIRED_DISCOVERY if not learned_facts.get(k)]
        _ = price_requested  # the pricing rule below is stated unconditionally
        return (
            "You are a business-development representative for Tech Expo Gujarat 2026 "
            "(27-29 Nov 2026, GUCEC Ahmedabad), talking to a prospect who just enquired. "
            "Your goal is conversion — helping them see why participating is worth it for "
            "their business. Be consultative, not pushy: ask about their business, listen, "
            "connect what you hear to what TEG offers. Write ONLY the message to send — one "
            "warm, specific paragraph (2-4 sentences) ending in a single question. No "
            "preamble, headings, or labels.\n\n"
            f"Tone: {tone}\n\n"
            f"{peer_line}\n"
            "Personalization: when you know the person's role, address them through it and "
            "reference one concrete fact about their company from the overview — not a "
            "generic line. If you do NOT know their role, ask it naturally in your first "
            "reply.\n\n"
            "Discovery: you are also gathering context for a possible tailored proposal. "
            "Naturally learn and record in `discovery`: goal (the outcome they want from "
            "TEG), target_market (who they sell to / their buyer industries), scale (rough "
            "team size or similar), and optionally timeline and concern. One light question "
            "per turn — never interrogate. Prefer questions that also move the pitch "
            f"forward.\nSo far you know: {known or 'nothing yet'}. "
            f"Still missing for a proposal: {', '.join(missing) if missing else 'none'}.\n\n"
            "Pricing: do NOT bring up cost, stall prices, sponsorship figures, or GST. Only "
            "if the prospect directly asks what something costs, or raises budget, may you "
            f"give this one indicative line: \"{_PRICING_LINE[persona]}\" — always '+ GST' "
            "and 'indicative, confirmed at booking'. Never volunteer a number they did not "
            "ask for.\n\n"
            "Proposal offer: offer to put together a tailored proposal only once you know "
            "their goal, target_market, and a rough sense of scale, AND they have shown "
            "genuine interest. Until then, keep the conversation going. If the prospect "
            "explicitly asks for a proposal or something in writing, honour that "
            "regardless.\n\n"
            f"You may draw on these benefits (paraphrase, do not list): {'; '.join(props)}.\n"
            "Hard rules: only name peer companies from the list you are given; never invent "
            "statistics or testimonials; never state a visitor ticket price."
        )

    async def init(self, intake: IntakeResult, dossier: ResearchDossier) -> PersuasionInit:
        ask = list(dossier.ask_prospect or [])
        company_known = "company_description" not in ask
        _log.info(
            "init  ask_prospect=%s  company_known=%s  relationship=%s  sector=%r",
            ask or "none", company_known, dossier.relationship, dossier.sector,
        )

        # Company genuinely not identified (KB miss + web miss) -> we must ask about
        # the company. Only reach here when research could not describe the company.
        if ask and not company_known:
            persona = "visitor"
            cta = target_cta_for(persona)
            _log.info("init path=ask-company  (company unresolved after KB + web)")
            q = await self.llm.generate(
                system=(
                    "You are a TEG 2026 assistant. The prospect just submitted an inquiry but we "
                    "could not identify their company or role. Ask ONE friendly question to learn "
                    "what their company does and their role, so you can tailor the conversation."
                ),
                messages=[{"role": "user", "content": (
                    f"Name: {intake.person_name}\nCompany as entered: {intake.company_name_raw}"
                )}],
                max_tokens=512,
            )
            return PersuasionInit(persona=persona, target_cta=cta, opening_message=q.strip())

        persona = await classify_persona(self.llm, intake, dossier, model=self._fast_model)
        cta = target_cta_for(persona)
        _log.info("init path=personalised  persona=%s  cta=%s  role_known=%s",
                  persona, cta, "role" not in ask)

        peers = dossier.peer_companies[:3]
        role_line = (
            "We already know their company; we do NOT know this person's role. "
            "Reference one specific, accurate fact about their company (from Company facts), "
            "then end by asking what their role there is — do NOT ask what the company does."
            if "role" in ask else
            "Address them by their role where natural and reference one specific company fact."
        )
        user = (
            f"Person: {intake.person_name}\nCompany: {intake.company_name_canonical}\n"
            f"Sector: {dossier.sector}\nRelationship: {dossier.relationship}\n"
            f"Company facts: {dossier.company_profile}\n"
            f"Person facts: {dossier.person_profile}\n"
            f"Peer companies you may name (only these): {peers}\n"
            f"Their stated intent: {intake.intent_hint}\n"
            f"{role_line}\n"
            "Write the opening message."
        )
        system = self._system(persona, dossier, learned_facts={}, price_requested=False)
        text = await self.llm.generate(system=system, messages=[{"role": "user", "content": user}], max_tokens=2048)

        async def _violations(t: str) -> list:
            vs = check_message(t, allowed_peers=peers, persona=persona, price_ok=False)
            vt = await check_testimonial(t, self.llm)
            return [*vs, vt] if vt else vs

        v = await _violations(text)
        if v:
            text = await self.llm.generate(
                system=system + f"\nYour previous draft violated: {[x.code for x in v]}. Fix it.",
                messages=[{"role": "user", "content": user}], max_tokens=2048,
            )
            v = await _violations(text)
        if v:
            text = _price_free(SAFE_TEMPLATES[persona])
        return PersuasionInit(persona=persona, target_cta=cta, opening_message=text.strip())

    async def respond(
        self, *, intake: IntakeResult, dossier: ResearchDossier, state: dict,
        history: list[dict], prospect_message: str,
    ) -> PersuasionTurn:
        persona: Persona = state.get("persona", "visitor")
        _log.info("respond  persona=%s  cta_status=%s  history=%d turns  msg=%r",
                  persona, state.get("cta_status"), len(history), prospect_message[:120])

        # one-time persona re-classification for the unresolved-identity case:
        # once the prospect answers our qualifying question, classify from the full
        # picture (dossier + what they just told us).
        first_prospect_turn = sum(1 for m in history if m.get("role") == "prospect") == 0
        if (
            dossier.ask_prospect
            and not state.get("persona_remapped")
            and first_prospect_turn
        ):
            persona = await classify_persona(
                self.llm, intake, dossier,
                extra_context=prospect_message, model=self._fast_model,
            )
            state["persona"] = persona
            state["target_cta"] = target_cta_for(persona)
            state["persona_remapped"] = True
            dossier = dossier.model_copy(update={"ask_prospect": []})

        peers = dossier.peer_companies[:3]
        price_requested = state.get("price_requested", False)
        system = self._system(
            persona, dossier, learned_facts=state.get("learned_facts", {}),
            price_requested=price_requested,
        ) + (
            f"\nTarget CTA: {state.get('target_cta')}. Current cta_status: {state.get('cta_status')}. "
            "Advance it naturally; set cta_status to 'completed' only if the prospect clearly commits. "
            "Set should_handoff true if they say they're just researching or repeatedly deflect. "
            "Set asked_about_price true if the prospect asked about cost or raised budget this turn. "
            "Set wants_proposal true if they ask for a proposal / PDF / 'something in writing', or "
            "accept an offer of one."
        )
        convo = "\n".join(f"{m['role']}: {m['content']}" for m in history[-8:])
        user = (
            f"Person: {intake.person_name}\nCompany: {intake.company_name_canonical}\n"
            f"Peer companies you may name (only these): {peers}\n\n"
            f"Conversation so far:\n{convo}\n\nprospect: {prospect_message}\n\n"
            "Produce the next reply."
        )

        analysis = await self.llm.generate_structured(
            system=system, messages=[{"role": "user", "content": user}], schema=_Analysis,
        )

        async def _violations(a: _Analysis) -> list:
            vs = check_message(
                a.reply, allowed_peers=peers, persona=persona,
                price_ok=price_requested or a.asked_about_price,
            )
            vt = await check_testimonial(a.reply, self.llm)
            return [*vs, vt] if vt else vs

        flags: list[str] = []
        v = await _violations(analysis)
        if v:
            analysis = await self.llm.generate_structured(
                system=system + f"\nPrevious draft violated {[x.code for x in v]}. Fix it.",
                messages=[{"role": "user", "content": user}], schema=_Analysis,
            )
            v = await _violations(analysis)
        if v:
            analysis.reply = (
                SAFE_TEMPLATES[persona]
                if (price_requested or analysis.asked_about_price)
                else _price_free(SAFE_TEMPLATES[persona])
            )
            flags = [x.code for x in v]
            state["needs_review"] = True
            _log.warning("guardrails forced safe template  flags=%s", flags)

        _log.info(
            "turn done  cta=%s/%s  handoff=%s  wants_proposal=%s  asked_price=%s  discovery=%s",
            analysis.cta_type, analysis.cta_status, analysis.should_handoff,
            analysis.wants_proposal, analysis.asked_about_price, list(analysis.discovery) or "-",
        )
        turn_count = sum(1 for m in history if m.get("role") == "agent")
        should_handoff = analysis.should_handoff or (
            turn_count >= 6 and analysis.cta_status in ("none", "offered")
        )

        merged_facts = {**state.get("learned_facts", {}), **analysis.discovery}
        state["learned_facts"] = merged_facts
        state["cta_status"] = analysis.cta_status
        state["price_requested"] = price_requested or analysis.asked_about_price
        if analysis.cta_detail:
            state["cta_detail"] = {**state.get("cta_detail", {}), **analysis.cta_detail}

        return PersuasionTurn(
            reply_text=analysis.reply.strip(),
            detected_cta=analysis.detected_cta,
            cta_status=analysis.cta_status,
            cta_type=analysis.cta_type,
            cta_detail=state["cta_detail"],
            should_handoff=should_handoff,
            updated_state=state,
            guardrail_flags=flags,
            persona=persona,
            wants_proposal=analysis.wants_proposal,
            asked_about_price=analysis.asked_about_price,
        )
