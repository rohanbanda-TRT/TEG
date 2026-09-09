from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.schemas import (
    HandoffPacket, IntakePayload, IntakeResult, OutcomeStatus, PersuasionInit,
    ResearchDossier, SourceRef,
)
from app.kb._names import _norm
from app.store.models import (
    ChatMessage, ChatSession, CompanyBriefRow, HandoffPacketRow, Inquiry, ProposalRow,
    ResearchDossierRow,
)


class InquiryRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def create(self, payload: IntakePayload, intake: IntakeResult) -> Inquiry:
        row = Inquiry(
            person_name=intake.person_name,
            company_name_raw=intake.company_name_raw,
            company_name_canonical=intake.company_name_canonical,
            email=payload.email, phone=payload.phone, city=payload.city,
            designation=payload.designation, participation_type=payload.participation_type,
            tech_category=payload.tech_category, message=payload.message,
            preferred_contact_time=payload.preferred_contact_time,
            consent_status=intake.consent_status, intent_hint=intake.intent_hint,
            source=payload.source,
        )
        self.s.add(row)
        return row

    async def get(self, inquiry_id: uuid.UUID) -> Inquiry | None:
        return await self.s.get(Inquiry, inquiry_id)


class DossierRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def create(self, inquiry_id: uuid.UUID, dossier: ResearchDossier) -> ResearchDossierRow:
        row = ResearchDossierRow(
            inquiry_id=inquiry_id,
            company_profile=dossier.company_profile,
            person_profile=dossier.person_profile,
            person_company_match=dossier.person_company_match,
            relationship=dossier.relationship,
            sector=dossier.sector,
            peer_companies=dossier.peer_companies,
            field_confidence=dossier.field_confidence,
            sources=[s.model_dump() for s in dossier.sources],
            review_flags=dossier.review_flags,
            ask_prospect=dossier.ask_prospect,
            research_cost=dossier.research_cost,
        )
        self.s.add(row)
        return row

    async def get(self, dossier_id: uuid.UUID) -> ResearchDossierRow | None:
        return await self.s.get(ResearchDossierRow, dossier_id)

    @staticmethod
    def to_domain(row: ResearchDossierRow) -> ResearchDossier:
        return ResearchDossier(
            company_profile=row.company_profile or {},
            person_profile=row.person_profile or {},
            person_company_match=row.person_company_match,
            relationship=row.relationship,
            sector=row.sector,
            peer_companies=row.peer_companies or [],
            field_confidence=row.field_confidence or {},
            sources=[SourceRef(**s) for s in (row.sources or [])],
            review_flags=row.review_flags or [],
            ask_prospect=row.ask_prospect or [],
            research_cost=row.research_cost or {},
        )


class CompanyBriefRepo:
    """One reusable research brief per company, keyed by the same
    normalized-name convention app.kb._names._norm already provides for
    peer/exhibitor matching — not raw company name, so name variants
    ("Third Rock Techkno" vs "Third Rock Techkno Pvt. Ltd.") hit one row."""

    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def get_by_company(self, company_name: str) -> CompanyBriefRow | None:
        key = _norm(company_name)
        if not key:
            return None
        return (await self.s.execute(
            select(CompanyBriefRow).where(CompanyBriefRow.company_key == key)
        )).scalars().first()

    async def upsert(
        self, company_name: str, dossier: ResearchDossier, brief_markdown: str,
    ) -> CompanyBriefRow:
        """The LIGHT pass. Sets light_researched_at explicitly — the field
        the light-staleness check reads — never relying on updated_at's
        onupdate, which would also fire on a deep-only write (see the
        comment on CompanyBriefRow.updated_at)."""
        key = _norm(company_name)
        row = await self.get_by_company(company_name)
        if row is None:
            row = CompanyBriefRow(company_key=key, company_name_canonical=company_name,
                                  brief_markdown=brief_markdown)
            self.s.add(row)
        row.company_name_canonical = company_name
        row.dossier_json = dossier.model_dump()
        row.brief_markdown = brief_markdown
        row.light_researched_at = func.now()
        return row

    async def upsert_deep_findings(self, company_name: str, findings) -> CompanyBriefRow:
        """The DEEP pass (app/research/deep.py) — additive, alongside the
        light dossier, never overwriting dossier_json/brief_markdown.
        Creates a row if the deep pass somehow lands before any light pass
        ever has (an empty light dossier placeholder, upgraded to a real
        one whenever the light pass next runs)."""
        key = _norm(company_name)
        row = await self.get_by_company(company_name)
        if row is None:
            row = CompanyBriefRow(
                company_key=key, company_name_canonical=company_name,
                dossier_json={}, brief_markdown="",
            )
            self.s.add(row)
        row.company_name_canonical = company_name
        row.deep_findings_json = findings.model_dump()
        row.depth = "deep"
        row.deep_researched_at = func.now()
        return row


class SessionRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def create(self, inquiry_id, dossier_id, init: PersuasionInit) -> ChatSession:
        row = ChatSession(
            inquiry_id=inquiry_id, dossier_id=dossier_id,
            persona=init.persona, target_cta=init.target_cta, cta_status="none",
        )
        self.s.add(row)
        return row

    async def get(self, session_id) -> ChatSession | None:
        return await self.s.get(ChatSession, session_id)

    async def update_state(
        self, session_id, *, cta_status, cta_type, cta_detail, learned_facts,
        persona, persona_remapped, needs_review, price_requested: bool | None = None,
        discovery_state: dict | None = None,
    ) -> None:
        row = await self.s.get(ChatSession, session_id)
        row.cta_status = cta_status
        row.cta_type = cta_type
        row.cta_detail = cta_detail
        row.learned_facts = learned_facts
        row.persona = persona
        row.persona_remapped = persona_remapped
        row.needs_review = needs_review
        if price_requested is not None:
            row.price_requested = price_requested
        if discovery_state is not None:
            row.discovery_state = discovery_state

    async def finalize(self, session_id, *, outcome_status: OutcomeStatus, handoff_generated: bool) -> None:
        row = await self.s.get(ChatSession, session_id)
        row.outcome_status = outcome_status
        row.handoff_generated = handoff_generated
        row.ended_at = func.now()


class MessageRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def next_turn_index(self, session_id) -> int:
        rows = (await self.s.execute(
            select(ChatMessage.turn_index).where(ChatMessage.session_id == session_id)
        )).scalars().all()
        return (max(rows) + 1) if rows else 0

    async def append(
        self, session_id, role, content, *, turn_index: int,
        guardrail_flags=None, detected_intent=None, attachment: dict | None = None,
    ) -> ChatMessage:
        row = ChatMessage(
            session_id=session_id, turn_index=turn_index, role=role, content=content,
            guardrail_flags=guardrail_flags or [], detected_intent=detected_intent or {},
            attachment=attachment,
        )
        self.s.add(row)
        return row

    async def history(self, session_id) -> list[dict]:
        rows = (await self.s.execute(
            select(ChatMessage).where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.turn_index)
        )).scalars().all()
        return [{"role": r.role, "content": r.content} for r in rows]


class HandoffRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def create(self, session_id, packet: HandoffPacket) -> HandoffPacketRow:
        row = HandoffPacketRow(
            session_id=session_id, summary=packet.summary,
            recommended_next_step=packet.recommended_next_step,
            suggested_followup_message=packet.suggested_followup_message,
            prospect_confidence=packet.prospect_confidence, key_facts=packet.key_facts,
        )
        self.s.add(row)
        return row

    async def get_by_session(self, session_id) -> HandoffPacketRow | None:
        return (await self.s.execute(
            select(HandoffPacketRow).where(HandoffPacketRow.session_id == session_id)
        )).scalars().first()


class ProposalRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def next_version(self, session_id) -> int:
        rows = (await self.s.execute(
            select(ProposalRow.version).where(ProposalRow.session_id == session_id)
        )).scalars().all()
        return (max(rows) + 1) if rows else 1

    async def create(
        self, session_id, *, proposal, version: int, pdf_path: str, png_path: str,
        bytes_: int, guardrail_flags: list[str], emailed_to: str | None = None,
    ) -> ProposalRow:
        row = ProposalRow(
            session_id=session_id, version=version,
            proposal_json=proposal.model_dump(), pdf_path=pdf_path, png_path=png_path,
            bytes=bytes_, guardrail_flags=guardrail_flags, emailed_to=emailed_to,
        )
        self.s.add(row)
        return row

    async def get(self, proposal_id) -> ProposalRow | None:
        return await self.s.get(ProposalRow, proposal_id)

    async def list_for_session(self, session_id) -> list[ProposalRow]:
        return list((await self.s.execute(
            select(ProposalRow).where(ProposalRow.session_id == session_id)
            .order_by(ProposalRow.version)
        )).scalars().all())
