from __future__ import annotations

from app.agents.base import Agent
from app.agents.guardrails import PROPOSAL_SAFE_SECTIONS, check_message
from app.domain.schemas import (
    IntakeResult,
    Persona,
    Proposal,
    ProposalPackage,
    ProposalPain,
    ResearchDossier,
)
from app.kb.loader import get_kb
from config.settings import get_settings

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
    def __init__(self, llm, *, model: str | None = None) -> None:
        super().__init__(llm)
        s = get_settings()
        self._model = model or s.proposal_model or s.llm_model_main

    async def run(self, data):  # ProposalAgent uses build(), not run()
        raise NotImplementedError("ProposalAgent has no run(); call build()")

    async def build(
        self, *, intake: IntakeResult, dossier: ResearchDossier, persona: Persona,
        transcript: list[dict], learned_facts: dict, session_ref: str, version: int,
    ) -> tuple[Proposal, list[str]]:
        kb = get_kb()
        gp = kb.goals_and_pains()
        own = intake.company_name_canonical.lower()
        peers = [
            p for p in (dossier.peer_companies or kb.peers_in_sector(dossier.sector or "", 6))
            if p.lower() != own
        ][:5]
        testimonials = kb.cleared_testimonials()
        base_pains = gp.pains_by_persona.get(persona)
        fallback_pkg = _PRICING_BY_PERSONA[persona]

        system = (
            "You write a one-page personalized proposal for a Tech Expo Gujarat 2026 inquiry. "
            "Ground every claim in the facts provided. RULES: no invented statistics; you may quote "
            "at most 2 of the cleared testimonials verbatim with attribution; only name peer companies "
            "from the provided list; never state a visitor ticket price; every price is '+ GST' and "
            "'indicative, confirmed at booking'; never name another event or expo; no signature blocks, "
            "no 'you agree', no binding-offer language — this is an information document, not a contract. "
            "Personalize 'what_you_told_us' and the pain points from the actual conversation; keep 2-4 pains."
        )
        convo = "\n".join(f"{m['role']}: {m['content']}" for m in transcript) or "(no messages yet)"
        pain_lines = "\n".join(f"- {p} -> {a}" for p, a in (base_pains.pains if base_pains else []))
        testi = "\n".join(f'- {t["name"]} ({t["role"]}): "{t["quote"]}"' for t in testimonials)
        user = (
            f"Persona: {persona}\n"
            f"Person: {intake.person_name}  Company: {intake.company_name_canonical}  Sector: {dossier.sector}\n"
            f"Company facts: {dossier.company_profile}\nPerson facts: {dossier.person_profile}\n"
            f"Learned in chat: {learned_facts}\n\n"
            f"Conversation:\n{convo}\n\n"
            f"TEG goals: {gp.goals}\n\nTEG mechanism: {gp.mechanism}\n\nEvidence: {gp.evidence}\n\n"
            f"Base pain points for this persona (personalize, keep 2-4):\n{pain_lines}\n\n"
            f"Cleared testimonials (quote at most 2 verbatim):\n{testi}\n\n"
            f"Peer companies you may name (only these): {peers}\n\n"
            f"Fallback recommended package (use unless the conversation points elsewhere): "
            f"{fallback_pkg.model_dump()}\n\n"
            f"Echo these exactly: generated_on='__DATE__', session_ref='{session_ref}', version={version}, "
            f"company='{intake.company_name_canonical}', person='{intake.person_name}', persona='{persona}'.\n"
            "Produce the Proposal."
        )

        proposal = await self.llm.generate_structured(
            system=system, messages=[{"role": "user", "content": user}],
            schema=Proposal, model=self._model,
        )

        def all_violations(p: Proposal) -> list:
            texts: list[tuple[str, str]] = [
                ("what_you_told_us", p.what_you_told_us),
                ("lead_generation", p.lead_generation),
                ("price_line", p.recommended_package.price_line),
            ]
            for i, pn in enumerate(p.pains):
                texts.append((f"pain::{i}", pn.pain))
                texts.append((f"teg_answer::{i}", pn.teg_answer))
            for i, pr in enumerate(p.proof):
                texts.append((f"proof::{i}", pr))
            for i, ns in enumerate(p.next_steps):
                texts.append((f"next_step::{i}", ns))
            found = []
            for label, txt in texts:
                for v in check_message(txt, allowed_peers=peers, persona=persona):
                    found.append((label, v))
            return found

        violations = all_violations(proposal)
        if violations:
            codes = sorted({v.code for _, v in violations})
            proposal = await self.llm.generate_structured(
                system=system + f"\nYour previous draft violated: {codes}. Fix every one.",
                messages=[{"role": "user", "content": user}],
                schema=Proposal, model=self._model,
            )
            violations = all_violations(proposal)

        flags: list[str] = []
        if violations:
            flags = sorted({v.code for _, v in violations})
            bad = {label for label, _ in violations}
            if "what_you_told_us" in bad:
                proposal.what_you_told_us = PROPOSAL_SAFE_SECTIONS["what_you_told_us"][persona]
            if "lead_generation" in bad:
                proposal.lead_generation = PROPOSAL_SAFE_SECTIONS["lead_generation"][persona]
            if "price_line" in bad:
                proposal.recommended_package = fallback_pkg
            for i in range(len(proposal.pains)):
                if f"pain::{i}" in bad or f"teg_answer::{i}" in bad:
                    src = (
                        base_pains.pains[i % len(base_pains.pains)][0]
                        if base_pains and base_pains.pains else "Reaching the right buyers"
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
        if not proposal.contact:
            proposal.contact = "info@techexpogujarat.com · +91 98989 23712"
        return proposal, flags
