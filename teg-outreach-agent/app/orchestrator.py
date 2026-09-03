from __future__ import annotations

import asyncio
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.agents.analysis import AnalysisAgent
from app.agents.persuasion import PersuasionAgent
from app.agents.proposal import ProposalAgent
from app.agents.research import ResearchAgent
from app.domain.schemas import (
    HandoffPacket,
    IntakePayload,
    IntakeResult,
    PersuasionTurn,
    ProposalCard,
    ResearchDossier,
)
from app.llm.base import get_llm
from app.obs import get_logger
from app.proposal.email import send_proposal_email
from app.proposal.render import render_first_page_png, render_html, render_pdf
from app.store.db import SessionLocal
from app.store.repositories import (
    DossierRepo,
    HandoffRepo,
    InquiryRepo,
    MessageRepo,
    ProposalRepo,
    SessionRepo,
)
from config.settings import get_settings

_log = get_logger("orchestrator")


def _slug(s: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^A-Za-z0-9]+", "-", s)).strip("-") or "company"


def _derive_learned_facts(ds) -> dict:
    """Flatten the DiscoveryState's current signals into the dict ProposalAgent
    already consumes. Keeps the proposal pipeline unchanged while the extraction
    underneath it gets richer and evidence-safe."""
    out: dict[str, str] = {}
    for key, field in ds.fields.items():
        if key.startswith("_"):
            continue
        cur = field.current()
        if cur is not None and field.status in ("known", "inferred"):
            out[key] = cur.value
    return out


@dataclass
class PipelineResult:
    inquiry_id: uuid.UUID
    session_id: uuid.UUID
    opening_message: str
    persona: str


class Orchestrator:
    def __init__(
        self, *,
        analysis: AnalysisAgent | None = None,
        research: ResearchAgent | None = None,
        persuasion: PersuasionAgent | None = None,
        proposal: ProposalAgent | None = None,
    ) -> None:
        self.analysis = analysis or AnalysisAgent(get_llm())
        self.research = research or ResearchAgent(get_llm())
        self.persuasion = persuasion or PersuasionAgent(get_llm())
        self.proposal = proposal or ProposalAgent(get_llm())

    async def run_pipeline(self, payload: IntakePayload) -> PipelineResult:
        settings = get_settings()
        _log.info("=== run_pipeline  person=%r  company=%r ===",
                  payload.person_name, payload.company_name)
        intake = await self.analysis.run(payload)

        try:
            dossier = await asyncio.wait_for(
                self.research.run(intake), timeout=settings.pipeline_hard_timeout_s,
            )
        except TimeoutError:
            _log.warning("research timed out after %ss -> ask_prospect fallback",
                         settings.pipeline_hard_timeout_s)
            dossier = ResearchDossier(ask_prospect=["company_description", "role"])

        init = await self.persuasion.init(intake, dossier)
        _log.info("=== pipeline done  persona=%s  opening=%r ===",
                  init.persona, init.opening_message[:160])

        async with SessionLocal() as s:
            inq = await InquiryRepo(s).create(payload, intake)
            await s.flush()
            drow = await DossierRepo(s).create(inq.id, dossier)
            await s.flush()
            cs = await SessionRepo(s).create(inq.id, drow.id, init)
            await s.flush()
            if get_settings().discovery_v2_enabled:
                from app.agents.discovery_seed import seed_from_dossier

                cs.discovery_state = seed_from_dossier(dossier, intake).model_dump()
            mr = MessageRepo(s)
            await mr.append(cs.id, "agent", init.opening_message, turn_index=0)
            await s.commit()
            return PipelineResult(
                inquiry_id=inq.id, session_id=cs.id,
                opening_message=init.opening_message, persona=init.persona,
            )

    def _state_from_row(self, cs) -> dict:
        return {
            "persona": cs.persona,
            "target_cta": cs.target_cta,
            "cta_status": cs.cta_status,
            "cta_detail": cs.cta_detail or {},
            "learned_facts": cs.learned_facts or {},
            "persona_remapped": cs.persona_remapped,
            "needs_review": cs.needs_review,
            "price_requested": cs.price_requested,
            "discovery_state": cs.discovery_state or {},
        }

    def _apply_discovery_v2(self, cs, turn, history, prospect_turn_index):
        """Merge this turn's signals, re-assess completeness, run the policy.

        Returns (learned_facts, discovery_state_dump, turn) — `turn` is copied
        with its `wants_proposal` replaced by the policy-gated value.
        """
        from app.agents.discovery_completeness import assess
        from app.agents.discovery_merge import merge_turn
        from app.agents.discovery_policy import decide
        from app.domain.discovery import DiscoveryState, TurnSignals

        ds = DiscoveryState.model_validate(cs.discovery_state or {})
        ts = TurnSignals.model_validate(turn.turn_signals) if turn.turn_signals else None

        ds = merge_turn(ds, ts, prospect_turn_index)
        comp = assess(ds)
        agent_turns = sum(1 for m in history if m.get("role") == "agent") + 1
        decision = decide(
            comp, ts, ds, agent_turns, model_wants_proposal=turn.wants_proposal,
        )
        if decision.bump_soft_defer:
            ds.soft_defer_count += 1
        ds.pending_brief = decision.brief
        ds.stage = comp.stage
        ds.last_completeness = comp.model_dump()

        learned_facts = _derive_learned_facts(ds)
        if decision.mark_missing:
            learned_facts["_missing_context"] = decision.mark_missing

        _log.info(
            "discovery-v2  stage=%s  ready=%s  score=%.2f  action=%s  wants_proposal=%s->%s  "
            "missing=%s",
            comp.stage, comp.ready, comp.score, decision.action,
            turn.wants_proposal, decision.effective_wants_proposal,
            comp.missing_required or "-",
        )

        turn = turn.model_copy(update={"wants_proposal": decision.effective_wants_proposal})
        return learned_facts, ds.model_dump(), turn

    async def run_turn(self, session_id: uuid.UUID, prospect_message: str) -> PersuasionTurn:
        async with SessionLocal() as s:
            cs = await SessionRepo(s).get(session_id)
            inq = await InquiryRepo(s).get(cs.inquiry_id)
            drow = await DossierRepo(s).get(cs.dossier_id)
            dossier = DossierRepo.to_domain(drow)
            intake = IntakeResult(
                person_name=inq.person_name,
                company_name_raw=inq.company_name_raw,
                company_name_canonical=inq.company_name_canonical or inq.company_name_raw,
                provided_fields=[],
                intent_hint=inq.intent_hint,
                consent_status=inq.consent_status,
            )
            history = await MessageRepo(s).history(session_id)
            state = self._state_from_row(cs)

            turn = await self.persuasion.respond(
                intake=intake, dossier=dossier, state=state,
                history=history, prospect_message=prospect_message,
            )

            mr = MessageRepo(s)
            prospect_turn_index = await mr.next_turn_index(session_id)
            await mr.append(session_id, "prospect", prospect_message,
                            turn_index=prospect_turn_index)
            await s.flush()
            await mr.append(session_id, "agent", turn.reply_text,
                            turn_index=await mr.next_turn_index(session_id),
                            guardrail_flags=turn.guardrail_flags,
                            detected_intent={"detected_cta": turn.detected_cta})

            learned_facts = turn.updated_state.get("learned_facts", {})
            discovery_state_dump: dict | None = None
            if get_settings().discovery_v2_enabled:
                learned_facts, discovery_state_dump, turn = self._apply_discovery_v2(
                    cs, turn, history, prospect_turn_index,
                )

            await SessionRepo(s).update_state(
                session_id,
                cta_status=turn.cta_status, cta_type=turn.cta_type,
                cta_detail=turn.cta_detail,
                learned_facts=learned_facts,
                persona=turn.persona,
                persona_remapped=turn.updated_state.get("persona_remapped", False),
                needs_review=turn.updated_state.get("needs_review", False),
                price_requested=turn.updated_state.get("price_requested", False),
                discovery_state=discovery_state_dump,
            )
            await s.commit()
            return turn

    async def end_session(self, session_id: uuid.UUID, reason: str) -> HandoffPacket | None:
        async with SessionLocal() as s:
            cs = await SessionRepo(s).get(session_id)
            drow = await DossierRepo(s).get(cs.dossier_id)
            dossier = DossierRepo.to_domain(drow)
            history = await MessageRepo(s).history(session_id)

            if cs.cta_status == "completed" or cs.cta_status in ("in_progress", "offered") and (cs.cta_detail or {}).get("callback"):
                outcome = "qualified"
            elif reason == "bounced" or cs.cta_status == "declined":
                outcome = "lost"
            else:
                outcome = "contacted"

            packet: HandoffPacket | None = None
            if cs.cta_status != "completed":
                if dossier.ask_prospect:
                    confidence = "low"
                elif dossier.sector and dossier.person_profile.get("teg_role"):
                    confidence = "high"
                else:
                    confidence = "medium"
                convo = "\n".join(f"{m['role']}: {m['content']}" for m in history)
                packet = await self.persuasion.llm.generate_structured(
                    system=(
                        "Write a concise sales handoff for the TEG team. Summarise who this is, "
                        "what they want, where the conversation landed, and the best next step. "
                        "suggested_followup_message: a short draft the rep can send."
                    ),
                    messages=[{"role": "user", "content": (
                        f"Dossier: company={dossier.company_profile} person={dossier.person_profile} "
                        f"sector={dossier.sector} relationship={dossier.relationship}\n"
                        f"Learned in chat: {cs.learned_facts}\n\nTranscript:\n{convo}"
                    )}],
                    schema=HandoffPacket,
                )
                packet = packet.model_copy(update={"prospect_confidence": confidence})
                await HandoffRepo(s).create(session_id, packet)

            await SessionRepo(s).finalize(
                session_id, outcome_status=outcome, handoff_generated=packet is not None,
            )
            await s.commit()
            return packet

    async def generate_proposal(
        self, session_id: uuid.UUID, *, email: str | None = None
    ) -> ProposalCard:
        settings = get_settings()
        async with SessionLocal() as s:
            cs = await SessionRepo(s).get(session_id)
            inq = await InquiryRepo(s).get(cs.inquiry_id)
            drow = await DossierRepo(s).get(cs.dossier_id)
            dossier = DossierRepo.to_domain(drow)
            intake = IntakeResult(
                person_name=inq.person_name,
                company_name_raw=inq.company_name_raw,
                company_name_canonical=inq.company_name_canonical or inq.company_name_raw,
                provided_fields=[], intent_hint=inq.intent_hint, consent_status=inq.consent_status,
            )
            transcript = await MessageRepo(s).history(session_id)
            persona = cs.persona or "visitor"
            learned = cs.learned_facts or {}
            price_requested = bool(cs.price_requested)
            version = await ProposalRepo(s).next_version(session_id)

        _log.info("=== generate_proposal  session=%s  v%d  persona=%s  price_requested=%s ===",
                  str(session_id)[:8], version, persona, price_requested)
        proposal, flags = await asyncio.wait_for(
            self.proposal.build(
                intake=intake, dossier=dossier, persona=persona, transcript=transcript,
                learned_facts=learned, session_ref=str(session_id)[:8], version=version,
                price_requested=price_requested,
            ),
            timeout=settings.proposal_hard_timeout_s,
        )
        proposal.generated_on = datetime.now(UTC).date().isoformat()
        _log.info("proposal built  flags=%s  rendering pdf/png", flags or "-")

        html = render_html(proposal, price_requested=price_requested)
        pdf = await asyncio.to_thread(render_pdf, html)
        png = await asyncio.to_thread(render_first_page_png, html)

        out_dir = Path(settings.proposal_dir) / str(session_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = out_dir / f"v{version}.pdf"
        png_path = out_dir / f"v{version}.png"
        pdf_path.write_bytes(pdf)
        png_path.write_bytes(png)

        filename = f"TEG-2026-Proposal-{_slug(proposal.company)}-v{version}.pdf"
        emailed_to = None
        if email:
            ok = await send_proposal_email(
                to=email, pdf_bytes=pdf, filename=filename, company=proposal.company
            )
            emailed_to = email if ok else None

        async with SessionLocal() as s:
            row = await ProposalRepo(s).create(
                session_id, proposal=proposal, version=version,
                pdf_path=str(pdf_path), png_path=str(png_path), bytes_=len(pdf),
                guardrail_flags=flags, emailed_to=emailed_to,
            )
            await s.flush()
            page_url = f"/p/{row.id}"
            pdf_url = f"/proposals/{row.id}.pdf"
            png_url = f"/proposals/{row.id}/preview.png"
            blurb = (proposal.hero_subline or proposal.executive_summary or "")[:160]
            title = f"Your TEG 2026 proposal for {proposal.company}"
            card = {
                "kind": "proposal_link", "proposal_id": str(row.id), "version": version,
                "page_url": page_url, "pdf_url": pdf_url, "png_url": png_url,
                "title": title, "blurb": blurb,
            }
            mr = MessageRepo(s)
            await mr.append(
                session_id, "agent",
                f"I've put together a proposal for {proposal.company} — open it here: {page_url}",
                turn_index=await mr.next_turn_index(session_id),
                attachment=card,
            )
            if flags:
                cs2 = await SessionRepo(s).get(session_id)
                cs2.needs_review = True
            await s.commit()
            proposal_id = str(row.id)

        return ProposalCard(
            kind="proposal_link", proposal_id=proposal_id, version=version, filename=filename,
            bytes=len(pdf), pdf_url=pdf_url, png_url=png_url,
            page_url=page_url, title=title, blurb=blurb,
        )
