from __future__ import annotations

import asyncio
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.agents.analysis import AnalysisAgent
from app.agents.persuasion import PersuasionAgent
from app.agents.proposal import ProposalAgent
from app.agents.research import ResearchAgent, _Budget
from app.domain.schemas import (
    HandoffPacket,
    IntakePayload,
    IntakeResult,
    PersuasionTurn,
    ProposalCard,
    ResearchDossier,
)
from app.graph.node import FnNode
from app.graph.runner import run_graph
from app.llm.base import get_llm
from app.obs import get_logger
from app.proposal.email import send_proposal_link_email
from app.research.brief import render_company_brief
from app.store.db import SessionLocal
from app.store.repositories import (
    CompanyBriefRepo,
    DossierRepo,
    HandoffRepo,
    InquiryRepo,
    MessageRepo,
    ProposalRepo,
    SessionRepo,
)
from app.verify.claims import CLAIMS as _VERIFY_CLAIMS
from config.settings import get_settings

_log = get_logger("orchestrator")


def _slug(s: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^A-Za-z0-9]+", "-", s)).strip("-") or "company"


# ---- inquiry pipeline, as a graph (docs/superpowers/specs/
# 2026-09-10-verification-harness-and-graph-design.md §3.3.3) ----
#
# analyze_intake and persuasion_init run as their own tiny (un-timed)
# run_graph() calls, exactly matching today's un-timed behavior for those
# two steps. The research layer — research_company / research_person /
# verify_relevant_teg_claims, joined by merge_dossier — runs as ONE
# run_graph() call wrapped in the same asyncio.wait_for(...,
# pipeline_hard_timeout_s) the old sequential code used, with the SAME
# ask_prospect fallback dossier on timeout. This is deliberately three
# separate run_graph() calls, not one graph spanning the whole pipeline —
# a single flat timeout across analyze_intake/persuasion_init too would
# change behavior neither of them has today (they're currently un-timed),
# and a research timeout must still let the pipeline continue to
# persuasion_init with a substitute dossier, which a single graph's
# all-or-nothing timeout can't express without inventing new soft-fail
# semantics for merge_dossier the spec doesn't ask for.

# Intent hints that don't cleanly map to a pricing-sensitive claim set fall
# back to "consider every v1 claim relevant" rather than guessing.
_INTENT_RELEVANT_CLAIMS: dict[str, tuple[str, ...]] = {
    "exhibitor": ("payment_plan_dates", "dates_venue", "scale_targets"),
    "sponsor": ("payment_plan_dates", "dates_venue", "scale_targets"),
    "startup_pitch": ("payment_plan_dates", "dates_venue", "scale_targets"),
    "visitor": ("visitor_pricing_published", "dates_venue"),
    "speaker": ("dates_venue", "scale_targets"),
}


def _latest_verification_log() -> Path | None:
    log_dir = Path(get_settings().kb_path).resolve() / "_verification_log"
    if not log_dir.is_dir():
        return None
    files = sorted(log_dir.glob("*.md"))
    return files[-1] if files else None


def _read_verification_flags(intake: IntakeResult) -> list[str]:
    """Read-only, no live call — the mechanism that keeps §3.1's
    verification harness out of the per-inquiry latency budget entirely.
    Verification happens on its own schedule (scripts/run_verification.py);
    this only ever reads whatever the most recent scheduled pass wrote."""
    path = _latest_verification_log()
    if path is None:
        return []
    relevant = set(_INTENT_RELEVANT_CLAIMS.get(intake.intent_hint, tuple(_VERIFY_CLAIMS)))
    flags: list[str] = []
    for line in path.read_text("utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or set(cells[0]) <= set("- "):
            continue
        claim_id, status = cells[0], cells[3]
        if claim_id in relevant and status == "conflicting":
            flags.append(f"verification::{claim_id}")
    return flags


def _analyze_intake_node(orch: "Orchestrator") -> FnNode:
    async def fn(ctx: dict) -> dict:
        intake = await orch.analysis.run(ctx["payload"])
        return {"intake": intake}

    return FnNode(name="analyze_intake", fn=fn,
                  reads=frozenset({"payload"}), writes=frozenset({"intake"}))


def _research_company_node(orch: "Orchestrator") -> FnNode:
    async def fn(ctx: dict) -> dict:
        out = await orch.research.run_company_track(ctx["intake"], budget=ctx["_research_budget"])
        return {"company_partial": out}

    return FnNode(name="research_company", fn=fn,
                  reads=frozenset({"intake", "_research_budget"}),
                  writes=frozenset({"company_partial"}))


def _research_person_node(orch: "Orchestrator") -> FnNode:
    async def fn(ctx: dict) -> dict:
        out = await orch.research.run_person_track(ctx["intake"], budget=ctx["_research_budget"])
        return {"person_partial": out}

    return FnNode(name="research_person", fn=fn,
                  reads=frozenset({"intake", "_research_budget"}),
                  writes=frozenset({"person_partial"}))


def _verify_relevant_teg_claims_node() -> FnNode:
    async def fn(ctx: dict) -> dict:
        try:
            flags = _read_verification_flags(ctx["intake"])
        except Exception as exc:  # noqa: BLE001 — must never block or slow the pipeline
            _log.warning("verify_relevant_teg_claims failed (%s); no confidence flags", exc)
            flags = []
        return {"kb_confidence_flags": flags}

    return FnNode(name="verify_relevant_teg_claims", fn=fn,
                  reads=frozenset({"intake"}), writes=frozenset({"kb_confidence_flags"}))


def _merge_dossier_node(orch: "Orchestrator") -> FnNode:
    async def fn(ctx: dict) -> dict:
        dossier = await orch.research.merge_tracks(
            ctx["intake"], ctx["company_partial"], ctx["person_partial"],
            kb_confidence_flags=ctx["kb_confidence_flags"], budget=ctx["_research_budget"],
        )
        return {"dossier": dossier}

    return FnNode(
        name="merge_dossier", fn=fn,
        reads=frozenset({"intake", "company_partial", "person_partial", "kb_confidence_flags"}),
        writes=frozenset({"dossier"}),
    )


def _persuasion_init_node(orch: "Orchestrator") -> FnNode:
    async def fn(ctx: dict) -> dict:
        init = await orch.persuasion.init(ctx["intake"], ctx["dossier"])
        return {"init": init}

    return FnNode(name="persuasion_init", fn=fn,
                  reads=frozenset({"intake", "dossier"}), writes=frozenset({"init"}))


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

        intake_ctx = await run_graph([_analyze_intake_node(self)], {"payload": payload})
        intake: IntakeResult = intake_ctx["intake"]

        # Company Research Brief reuse — checked BEFORE the research graph
        # runs at all, so a fresh hit skips research entirely rather than
        # just skipping persistence. Only ever reused when fresh (see
        # settings.company_brief_staleness_days); a stale or missing entry
        # falls through to the normal research path below unchanged.
        dossier = await self._reuse_company_brief(intake)
        if dossier is not None:
            _log.info("reusing stored company brief for %r -> skipping research",
                      intake.company_name_canonical)
        else:
            try:
                budget = _Budget(settings.research_max_searches_per_track, settings.research_max_scrapes)
                research_ctx = await asyncio.wait_for(
                    run_graph(
                        [
                            _research_company_node(self),
                            _research_person_node(self),
                            _verify_relevant_teg_claims_node(),
                            _merge_dossier_node(self),
                        ],
                        {"intake": intake, "_research_budget": budget},
                    ),
                    timeout=settings.pipeline_hard_timeout_s,
                )
                dossier = research_ctx["dossier"]
                # Only a real, completed research pass is worth caching — a
                # timeout fallback below is a thin synthetic dossier, and
                # saving THAT as "the" brief for company_brief_staleness_days
                # would poison every future lookup for this company.
                await self._save_company_brief(intake, dossier)
            except TimeoutError:
                _log.warning("research timed out after %ss -> ask_prospect fallback",
                             settings.pipeline_hard_timeout_s)
                dossier = ResearchDossier(ask_prospect=["company_description", "role"])

        init_ctx = await run_graph(
            [_persuasion_init_node(self)], {"intake": intake, "dossier": dossier},
        )
        init = init_ctx["init"]
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

    async def _reuse_company_brief(self, intake: IntakeResult) -> ResearchDossier | None:
        """None on a miss OR a stale hit — either way, run_pipeline falls
        through to normal research. Never raises: a brief-lookup failure
        degrades to "do the research," not to a broken pipeline."""
        try:
            async with SessionLocal() as s:
                row = await CompanyBriefRepo(s).get_by_company(intake.company_name_canonical)
        except Exception as exc:  # noqa: BLE001 — a cache miss must never break the pipeline
            _log.warning("company brief lookup failed (%s); researching fresh", exc)
            return None
        if row is None:
            return None
        age = datetime.now(UTC) - row.updated_at
        staleness = timedelta(days=get_settings().company_brief_staleness_days)
        if age > staleness:
            _log.info("company brief for %r is stale (age=%s > %s) -> researching fresh",
                      intake.company_name_canonical, age, staleness)
            return None
        return ResearchDossier.model_validate(row.dossier_json)

    async def _save_company_brief(self, intake: IntakeResult, dossier: ResearchDossier) -> None:
        """Never raises out into run_pipeline — a failed save just means the
        NEXT inquiry for this company re-researches too, which is safe."""
        try:
            markdown = render_company_brief(dossier)
            async with SessionLocal() as s:
                await CompanyBriefRepo(s).upsert(intake.company_name_canonical, dossier, markdown)
                await s.commit()
            self._write_prospect_brief_file(intake.company_name_canonical, markdown)
        except Exception as exc:  # noqa: BLE001
            _log.warning("saving company brief for %r failed (%s)", intake.company_name_canonical, exc)

    @staticmethod
    def _write_prospect_brief_file(company_name: str, markdown: str) -> None:
        """teg-kb-agent/prospect_briefs/<slug>.md — a sibling of
        knowledge_base/, same "generated staging artifact, not sourced
        content" pattern _verification_log/ already established. Never
        written INTO knowledge_base/ — that directory is TEG's own sourced
        content, never prospect data."""
        from app.kb._names import _norm

        slug = _norm(company_name).replace(" ", "-") or "company"
        briefs_dir = Path(get_settings().kb_path).resolve().parent / "prospect_briefs"
        briefs_dir.mkdir(parents=True, exist_ok=True)
        (briefs_dir / f"{slug}.md").write_text(markdown, encoding="utf-8")

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
        _log.info("proposal built  flags=%s", flags or "-")

        # Delivered as the live `/p/{id}` page only — no PDF/PNG render pass.
        # That render (headless Chromium via playwright) was the slow, most
        # failure-prone part of this path; dropping it also means a
        # proposal's numbers can never drift from what the page shows.
        filename = f"TEG-2026-Proposal-{_slug(proposal.company)}-v{version}"

        async with SessionLocal() as s:
            row = await ProposalRepo(s).create(
                session_id, proposal=proposal, version=version,
                pdf_path=None, png_path=None, bytes_=None,
                guardrail_flags=flags, emailed_to=None,
            )
            await s.flush()
            page_url = f"/p/{row.id}"
            blurb = (proposal.hero_subline or proposal.executive_summary or "")[:160]
            title = f"Your TEG 2026 proposal for {proposal.company}"

            emailed_to = None
            if email:
                full_url = (
                    f"{settings.public_base_url}{page_url}"
                    if settings.public_base_url else page_url
                )
                ok = await send_proposal_link_email(
                    to=email, page_url=full_url, company=proposal.company
                )
                emailed_to = email if ok else None
                row.emailed_to = emailed_to

            card = {
                "kind": "proposal_link", "proposal_id": str(row.id), "version": version,
                "page_url": page_url, "title": title, "blurb": blurb,
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
            page_url=page_url, title=title, blurb=blurb,
        )
