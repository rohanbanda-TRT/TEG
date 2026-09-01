from typing import Literal

from pydantic import BaseModel, Field

IntentHint = Literal["visitor", "exhibitor", "sponsor", "startup_pitch", "speaker", "unknown"]
ConsentStatus = Literal["given", "not_given", "unknown"]
Relationship = Literal["cold", "returning", "insider"]
Persona = Literal["it_tech_service", "ai_startup", "non_tech_sponsor", "visitor"]
CtaStatus = Literal["none", "offered", "in_progress", "completed", "declined"]
OutcomeStatus = Literal["new", "contacted", "qualified", "lost"]


class IntakePayload(BaseModel):
    person_name: str
    company_name: str
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    designation: str | None = None
    participation_type: str | None = None
    tech_category: str | None = None
    message: str | None = None
    preferred_contact_time: str | None = None
    consent: bool | None = None
    source: str = "inquiry_page"


class IntakeResult(BaseModel):
    person_name: str
    company_name_raw: str
    company_name_canonical: str
    provided_fields: list[str]
    intent_hint: IntentHint
    consent_status: ConsentStatus


class SourceRef(BaseModel):
    field: str
    url: str | None
    tool: str
    confidence: float


class ResearchDossier(BaseModel):
    company_profile: dict = Field(default_factory=dict)
    person_profile: dict = Field(default_factory=dict)
    person_company_match: bool | None = None
    relationship: Relationship = "cold"
    sector: str | None = None
    peer_companies: list[str] = Field(default_factory=list)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    sources: list[SourceRef] = Field(default_factory=list)
    review_flags: list[str] = Field(default_factory=list)
    ask_prospect: list[str] = Field(default_factory=list)
    research_cost: dict[str, int] = Field(default_factory=dict)


class PersuasionInit(BaseModel):
    persona: Persona
    target_cta: str
    opening_message: str


class PersuasionTurn(BaseModel):
    reply_text: str
    detected_cta: str | None = None
    cta_status: CtaStatus = "none"
    cta_type: str | None = None
    cta_detail: dict = Field(default_factory=dict)
    should_handoff: bool = False
    updated_state: dict = Field(default_factory=dict)
    guardrail_flags: list[str] = Field(default_factory=list)
    persona: Persona
    wants_proposal: bool = False


class HandoffPacket(BaseModel):
    summary: str
    recommended_next_step: str
    suggested_followup_message: str
    prospect_confidence: Literal["high", "medium", "low"]
    key_facts: dict = Field(default_factory=dict)


class ProposalPain(BaseModel):
    pain: str
    teg_answer: str


class ProposalPackage(BaseModel):
    name: str
    price_line: str
    includes: list[str] = Field(default_factory=list)
    payment_plan: str


class Proposal(BaseModel):
    company: str
    person: str
    person_role: str | None = None
    sector: str | None = None
    persona: Persona
    generated_on: str
    session_ref: str
    version: int
    what_you_told_us: str
    pains: list[ProposalPain] = Field(default_factory=list)
    lead_generation: str
    proof: list[str] = Field(default_factory=list)
    recommended_package: ProposalPackage
    peer_companies: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    contact: str


class ProposalCard(BaseModel):
    proposal_id: str
    version: int
    filename: str
    bytes: int
    pdf_url: str
    png_url: str
