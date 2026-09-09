from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.store.db import Base


def _uuid_col(**kw):
    return mapped_column(UUID(as_uuid=True), default=uuid.uuid4, **kw)


class Inquiry(Base):
    __tablename__ = "inquiries"
    id: Mapped[uuid.UUID] = _uuid_col(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    person_name: Mapped[str] = mapped_column(Text, nullable=False)
    company_name_raw: Mapped[str] = mapped_column(Text, nullable=False)
    company_name_canonical: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)
    designation: Mapped[str | None] = mapped_column(Text)
    participation_type: Mapped[str | None] = mapped_column(Text)
    tech_category: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    preferred_contact_time: Mapped[str | None] = mapped_column(Text)
    consent_status: Mapped[str] = mapped_column(String(16), nullable=False)
    intent_hint: Mapped[str] = mapped_column(String(24), nullable=False)
    source: Mapped[str | None] = mapped_column(Text)


class ResearchDossierRow(Base):
    __tablename__ = "research_dossiers"
    id: Mapped[uuid.UUID] = _uuid_col(primary_key=True)
    inquiry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inquiries.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    company_profile: Mapped[dict] = mapped_column(JSONB, default=dict)
    person_profile: Mapped[dict] = mapped_column(JSONB, default=dict)
    person_company_match: Mapped[bool | None] = mapped_column(Boolean)
    relationship: Mapped[str] = mapped_column(String(16), nullable=False)
    sector: Mapped[str | None] = mapped_column(Text)
    peer_companies: Mapped[list] = mapped_column(JSONB, default=list)
    field_confidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    sources: Mapped[list] = mapped_column(JSONB, default=list)
    review_flags: Mapped[list] = mapped_column(JSONB, default=list)
    ask_prospect: Mapped[list] = mapped_column(JSONB, default=list)
    research_cost: Mapped[dict] = mapped_column(JSONB, default=dict)


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[uuid.UUID] = _uuid_col(primary_key=True)
    inquiry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inquiries.id"), nullable=False)
    dossier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_dossiers.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    persona: Mapped[str | None] = mapped_column(String(24))
    target_cta: Mapped[str | None] = mapped_column(String(32))
    cta_status: Mapped[str] = mapped_column(String(16), nullable=False, default="none")
    cta_type: Mapped[str | None] = mapped_column(String(32))
    cta_detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    outcome_status: Mapped[str | None] = mapped_column(String(16))
    handoff_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    learned_facts: Mapped[dict] = mapped_column(JSONB, default=dict)
    persona_remapped: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    price_requested: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    discovery_state: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[uuid.UUID] = _uuid_col(primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(12), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    guardrail_flags: Mapped[list] = mapped_column(JSONB, default=list)
    detected_intent: Mapped[dict] = mapped_column(JSONB, default=dict)
    attachment: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class HandoffPacketRow(Base):
    __tablename__ = "handoff_packets"
    id: Mapped[uuid.UUID] = _uuid_col(primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    summary: Mapped[str | None] = mapped_column(Text)
    recommended_next_step: Mapped[str | None] = mapped_column(Text)
    suggested_followup_message: Mapped[str | None] = mapped_column(Text)
    prospect_confidence: Mapped[str | None] = mapped_column(String(8))
    key_facts: Mapped[dict] = mapped_column(JSONB, default=dict)
    delivered_to: Mapped[str | None] = mapped_column(Text)


class CompanyBriefRow(Base):
    """One reusable research brief per company — keyed by a normalized
    company-name key (see app.kb._names._norm, the same normalization the
    peer/exhibitor-matching code already uses), not raw company name, so
    "Third Rock Techkno" and "Third Rock Techkno Pvt. Ltd." hit the same row.
    """
    __tablename__ = "company_briefs"
    id: Mapped[uuid.UUID] = _uuid_col(primary_key=True)
    company_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    company_name_canonical: Mapped[str] = mapped_column(Text, nullable=False)
    dossier_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    brief_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )


class ProposalRow(Base):
    __tablename__ = "proposals"
    id: Mapped[uuid.UUID] = _uuid_col(primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    proposal_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    pdf_path: Mapped[str | None] = mapped_column(Text)
    png_path: Mapped[str | None] = mapped_column(Text)
    bytes: Mapped[int | None] = mapped_column(Integer)
    guardrail_flags: Mapped[list] = mapped_column(JSONB, default=list)
    emailed_to: Mapped[str | None] = mapped_column(Text)
