from __future__ import annotations

from typing import get_args

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
from app.kb.loader import get_kb  # noqa: F401  (kept for downstream use / test patching)
from config.outreach_rules import load_rules
from config.settings import get_settings

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
    except Exception:  # noqa: BLE001 — classification must never break the pipeline
        return "visitor"
    return choice.persona if choice.persona in _PERSONA_VALUES else "visitor"


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
    wants_proposal: bool = False


class PersuasionAgent(Agent):
    def __init__(self, llm, *, fast_model: str | None = None) -> None:
        super().__init__(llm)
        self._rules = load_rules()
        self._fast_model = fast_model or get_settings().llm_model_fast

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
            "You are a helpful outreach assistant for Tech Expo Gujarat 2026 (27-29 Nov "
            "2026, GUCEC Ahmedabad). Write ONLY the message to send to the prospect - no "
            "preamble, no headings, no labels like 'Context:' or 'Reply:'. One warm, "
            "specific paragraph (2-4 sentences) that ends with a single soft question.\n\n"
            f"Tone: {tone}\n"
            f"You may draw on these benefits (paraphrase naturally, do not list them): "
            f"{'; '.join(props)}.\n"
            f"If pricing comes up you may say: {_PRICING_LINE[persona]}\n\n"
            "Hard rules: never state a visitor ticket price; every price is quoted as "
            "'+ GST' and 'indicative, confirmed at booking'; only name peer companies "
            "from the list you are given; never invent statistics or testimonials."
        )

    async def init(self, intake: IntakeResult, dossier: ResearchDossier) -> PersuasionInit:
        # Identity unresolved -> don't guess a persona yet; ask a qualifying question.
        # A provisional persona is still needed for tone/CTA on that first message.
        if dossier.ask_prospect:
            persona = "visitor"
            cta = target_cta_for(persona)
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
        text = await self.llm.generate(system=system, messages=[{"role": "user", "content": user}], max_tokens=2048)
        for _ in range(1):
            v = check_message(text, allowed_peers=peers, persona=persona)
            if not v:
                break
            text = await self.llm.generate(
                system=system + f"\nYour previous draft violated: {[x.code for x in v]}. Fix it.",
                messages=[{"role": "user", "content": user}], max_tokens=2048,
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
        system = self._system(persona, dossier) + (
            f"\nTarget CTA: {state.get('target_cta')}. Current cta_status: {state.get('cta_status')}. "
            "Advance it naturally; set cta_status to 'completed' only if the prospect clearly commits. "
            "Set should_handoff true if they say they're just researching or repeatedly deflect. "
            "Return learned_facts for anything new they told you. "
            "If the prospect asks for a proposal, a PDF, or 'something in writing', or accepts an "
            "offer of one, set wants_proposal=true. You MAY offer a tailored proposal once when "
            "they show real buying interest (asked about pricing, leads, ROI, or 'how it helps')."
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
            wants_proposal=analysis.wants_proposal,
        )
