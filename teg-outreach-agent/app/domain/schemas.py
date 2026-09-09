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
    # Carries forward anything the verify_relevant_teg_claims graph node
    # flagged as stale/conflicting against the live web (see
    # docs/superpowers/specs/2026-09-10-verification-harness-and-graph-design.md
    # §3.3.3) — not required behavior, just making the signal available for
    # a downstream persuasion turn to use if it chooses to.
    kb_confidence_flags: list[str] = Field(default_factory=list)


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
    wants_proposal: bool = False          # discovery-v2: this is effective_wants_proposal (policy-gated)
    asked_about_price: bool = False
    turn_signals: dict | None = None      # discovery-v2: the model's per-turn signal payload


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


class SectorFitRow(BaseModel):
    lever: str
    weight: int  # 1-5, clamped by ProposalAgent


# The growth argument, in order. Fixed because the sequence IS the pitch:
# where they are -> where they could go -> what stops them -> what TEG opens ->
# what they'd do -> where it could lead. Only the content inside varies.
GROWTH_STAGES: tuple[str, ...] = (
    "today",
    "growth_move",
    "barrier",
    "teg_opportunity",
    "action",
    "potential",
)

MAX_JOURNEY_POINTS = 5


class JourneyStage(BaseModel):
    # A plain str, not a Literal: the model is told the six valid keys in the
    # prompt, and ProposalAgent._clamp_growth_journey is the gate — anything
    # off-list is dropped there, the same way target_industries is handled. A
    # strict Literal here would fail the whole proposal on one stray key.
    stage: str                     # one of GROWTH_STAGES
    title: str                     # the prospect-facing heading, written per company
    points: list[str] = Field(default_factory=list)  # 3-5 short, concrete points


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
    executive_summary: str = ""
    how_a_teg_plays_out: list[str] = Field(default_factory=list)
    roi_framing: str = ""
    sector_fit: list[SectorFitRow] = Field(default_factory=list)
    growth_journey: list[JourneyStage] = Field(default_factory=list)
    peers_in_sector_total: int = 0
    peer_context_line: str = ""
    scale_note: str = ""
    target_industries: list[str] = Field(default_factory=list)
    target_industries_note: str = ""
    hero_headline: str = ""
    hero_subline: str = ""
    section_ctas: dict[str, str] = Field(default_factory=dict)
    closing_cta_headline: str = ""
    closing_cta_body: str = ""


class ConversationSignals(BaseModel):
    """Structured extraction from the transcript, produced by
    extract_conversation_signals (see docs/superpowers/specs/
    2026-09-10-verification-harness-and-graph-design.md §3.2.2/§3.3.4).
    Feeds package-tier selection in ProposalAgent.build() — kept narrow
    (booth size / demo-station count / confidence) rather than a general
    summarization, so it stays easy to get right and to unit-test."""

    requested_tier: Literal["base", "mid", "upsized"] | None = None
    signal_confidence: Literal["explicit", "inferred"] | None = None
    demo_stations: int | None = None
    notes: str = ""


class ProposalCard(BaseModel):
    """A delivered proposal. `page_url` (the live `/p/{id}` page) is the only
    required delivery surface — `pdf_url`/`png_url` are unset on the current
    (link-only) path and only appear for proposals rendered before it."""

    kind: str = "proposal_link"
    proposal_id: str
    version: int
    filename: str = ""
    bytes: int | None = None
    pdf_url: str | None = None
    png_url: str | None = None
    page_url: str = ""
    title: str = ""
    blurb: str = ""
