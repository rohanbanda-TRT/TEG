from __future__ import annotations

import re

from pydantic import BaseModel

from app.agents.base import Agent
from app.agents.guardrails import SAFE_TEMPLATES, check_message
from app.domain.schemas import (
    CtaStatus,
    IntakeResult,
    Persona,
    PersuasionInit,
    PersuasionTurn,
    ResearchDossier,
)
from app.kb.loader import get_kb
from config.outreach_rules import load_rules

_IT_SECTORS = {
    "software development", "software development & it services", "it services",
    "cloud & infrastructure", "enterprise software", "data & analytics",
    "devops / cloud / hosting", "saas / productivity / messaging",
}
_AI_SECTORS = {"ai & machine learning", "ai / ml", "ai solutions", "ai consulting"}


def _size_lt_50(profile: dict) -> bool:
    raw = str(profile.get("company_size") or "")
    m = re.search(r"\d+", raw)
    if not m:
        return True  # unknown -> allow startup classification
    return int(m.group()) < 50


def map_persona(intake: IntakeResult, dossier: ResearchDossier) -> Persona:
    sector = (dossier.sector or "").strip().lower()
    if dossier.ask_prospect:
        return "visitor"
    if any(s in sector for s in _AI_SECTORS) and _size_lt_50(dossier.company_profile):
        return "ai_startup"
    if any(s in sector for s in _IT_SECTORS) or "software" in sector:
        return "it_tech_service"
    if intake.intent_hint == "sponsor":
        return "non_tech_sponsor"
    if intake.intent_hint == "visitor":
        return "visitor"
    if sector and any(s in sector for s in _IT_SECTORS | _AI_SECTORS):
        return "it_tech_service"
    return "visitor"


def target_cta_for(persona: Persona) -> str:
    return {
        "it_tech_service": "book_stall",
        "ai_startup": "catalyst_zone_or_pitch",
        "non_tech_sponsor": "request_sponsor_call",
        "visitor": "register_visitor",
    }[persona]


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
    learned_facts: dict = {}


class _RemapHint(BaseModel):
    sector: str | None = None
    role: str | None = None
    size: str | None = None


class PersuasionAgent(Agent):
    def __init__(self, llm) -> None:
        super().__init__(llm)
        self._rules = load_rules()

    async def run(self, data):  # PersuasionAgent uses init()/respond(), not run()
        raise NotImplementedError("PersuasionAgent has no run(); call init() or respond()")

    def _system(self, persona: Persona, dossier: ResearchDossier) -> str:
        props = self._rules.persona_triggers.get(persona, {}).get("value_props", [])
        tone = {
            "insider": "This person is a TEG organiser — warm, peer-to-peer, no hard sell.",
            "returning": "This company/person has been part of TEG before — acknowledge that, welcome them back.",
            "cold": "First contact — warm and helpful, not familiar.",
        }[dossier.relationship]
        return (
            "You are a helpful TEG 2026 outreach assistant on the inquiry page. "
            "Be encouraging and specific, never pushy. One short paragraph, end with one soft ask.\n"
            f"Tone: {tone}\n"
            f"Persona value props to draw on: {'; '.join(props)}\n"
            f"Pricing you may quote: {_PRICING_LINE[persona]}\n"
            "Rules: never state a visitor ticket price; every price is '+ GST' and 'indicative, "
            "confirmed at booking'; only mention peer companies from the provided list; "
            "no invented statistics or testimonials."
        )

    async def init(self, intake: IntakeResult, dossier: ResearchDossier) -> PersuasionInit:
        persona = map_persona(intake, dossier)
        cta = target_cta_for(persona)

        if dossier.ask_prospect:
            q = await self.llm.generate(
                system=(
                    "You are a TEG 2026 assistant. The prospect just submitted an inquiry but we "
                    "could not identify their company or role. Ask ONE friendly question to learn "
                    "what their company does and their role, so you can tailor the conversation."
                ),
                messages=[{"role": "user", "content": (
                    f"Name: {intake.person_name}\nCompany as entered: {intake.company_name_raw}"
                )}],
                max_tokens=120,
            )
            return PersuasionInit(persona=persona, target_cta=cta, opening_message=q.strip())

        peers = dossier.peer_companies[:3]
        user = (
            f"Person: {intake.person_name}\nCompany: {intake.company_name_canonical}\n"
            f"Sector: {dossier.sector}\nRelationship: {dossier.relationship}\n"
            f"Company facts: {dossier.company_profile}\n"
            f"Peer companies you may name (only these): {peers}\n"
            f"Their stated intent: {intake.intent_hint}\n"
            "Write the opening message."
        )
        system = self._system(persona, dossier)
        text = await self.llm.generate(system=system, messages=[{"role": "user", "content": user}], max_tokens=300)
        for _ in range(1):
            v = check_message(text, allowed_peers=peers, persona=persona)
            if not v:
                break
            text = await self.llm.generate(
                system=system + f"\nYour previous draft violated: {[x.code for x in v]}. Fix it.",
                messages=[{"role": "user", "content": user}], max_tokens=300,
            )
        if check_message(text, allowed_peers=peers, persona=persona):
            text = SAFE_TEMPLATES[persona]
            if peers:
                text += f" Companies like {' and '.join(peers[:2])} are already taking part."
        return PersuasionInit(persona=persona, target_cta=cta, opening_message=text.strip())

    async def respond(
        self, *, intake: IntakeResult, dossier: ResearchDossier, state: dict,
        history: list[dict], prospect_message: str,
    ) -> PersuasionTurn:
        persona: Persona = state.get("persona", "visitor")

        # one-time persona re-map for the unresolved-identity case
        first_prospect_turn = sum(1 for m in history if m.get("role") == "prospect") == 0
        if (
            dossier.ask_prospect
            and not state.get("persona_remapped")
            and first_prospect_turn
        ):
            hint = await self.llm.generate_structured(
                system=(
                    "From the prospect's message, infer their company's sector, the person's "
                    "role, and any headcount mentioned. Null if not stated."
                ),
                messages=[{"role": "user", "content": prospect_message}],
                schema=_RemapHint,
            )
            patched = dossier.model_copy(update={
                "sector": hint.sector or dossier.sector,
                "company_profile": {
                    **dossier.company_profile,
                    "company_size": hint.size or dossier.company_profile.get("company_size"),
                },
                "ask_prospect": [],
            })
            persona = map_persona(intake, patched)
            state["persona"] = persona
            state["target_cta"] = target_cta_for(persona)
            state["persona_remapped"] = True
            dossier = patched

        peers = dossier.peer_companies[:3]
        system = self._system(persona, dossier) + (
            f"\nTarget CTA: {state.get('target_cta')}. Current cta_status: {state.get('cta_status')}. "
            "Advance it naturally; set cta_status to 'completed' only if the prospect clearly commits. "
            "Set should_handoff true if they say they're just researching or repeatedly deflect. "
            "Return learned_facts for anything new they told you."
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
        flags: list[str] = []
        v = check_message(analysis.reply, allowed_peers=peers, persona=persona)
        if v:
            analysis = await self.llm.generate_structured(
                system=system + f"\nPrevious draft violated {[x.code for x in v]}. Fix it.",
                messages=[{"role": "user", "content": user}], schema=_Analysis,
            )
            v = check_message(analysis.reply, allowed_peers=peers, persona=persona)
        if v:
            analysis.reply = SAFE_TEMPLATES[persona]
            flags = [x.code for x in v]
            state["needs_review"] = True

        turn_count = sum(1 for m in history if m.get("role") == "agent")
        should_handoff = analysis.should_handoff or (
            turn_count >= 6 and analysis.cta_status in ("none", "offered")
        )

        merged_facts = {**state.get("learned_facts", {}), **analysis.learned_facts}
        state["learned_facts"] = merged_facts
        state["cta_status"] = analysis.cta_status
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
        )
