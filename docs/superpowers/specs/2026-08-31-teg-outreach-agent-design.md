# TEG Inquiry Outreach System — Design Spec

> **Status:** Approved design (2026-08-31)
> **Owner:** rohanb@thirdrocktechkno.com
> **Related:** `teg-kb-agent/` (the knowledge base this system reads), `teg-kb-agent/knowledge_base/outreach_config.md` (the 3-agent pipeline rules), `teg-kb-agent/knowledge_base/data_schema.md` §8–§9 (Lead & Compliance data)

---

## 1. Purpose

A prospect lands on the Tech Expo Gujarat (TEG) inquiry page and submits, at minimum, **their name and their company name**. The system:

1. **Researches** the person and the company — knowledge base first, then free web tools, and if it still can't identify them, it asks the prospect directly in the chat.
2. **Opens a live chat widget** on the inquiry page, where a persona-tuned agent has an encouraging, factually-guarded conversation aimed at getting the prospect to take a concrete participation action (book a stall, request a sponsorship call, register as a visitor, submit a startup pitch).
3. **Persists** a structured lead record, the research dossier, the full transcript, the CTA outcome, and — if the chat doesn't close — a handoff packet for the TEG sales team.

The system implements the **3-agent pipeline** already sketched in `outreach_config.md`:

| Agent | Role |
|---|---|
| **Analysis Agent** | Light intake normalizer — canonicalizes the name + company, records which fields were provided, guesses intent, reads consent status. Not a blocking schema gate. |
| **Research Agent** | KB-first enrichment of both the person and the company, with free web fallback, per the confidence thresholds in `outreach_config.md`. |
| **Persuasion Agent** | Maps the prospect to a persona, builds an opening pitch, then runs the live conversation turn-by-turn under the `outreach_config.md` guardrails, tracking a target CTA. |

---

## 2. Scope

### In scope
- FastAPI backend service (`teg-outreach-agent/`), a new sibling package to `teg-kb-agent/` in this repo.
- The 3 agents, an orchestrator, a provider-agnostic LLM client (Anthropic adapter first).
- Research tooling: local KB retriever + Tavily/Brave web search (MCP) + `httpx`/readability page scraper. **No paid LinkedIn. No browser automation. No scraping of LinkedIn.**
- An embeddable chat widget (static JS/CSS) for the inquiry page.
- Postgres persistence (SQLAlchemy + Alembic).
- Tests: each agent in isolation, research tools mocked, orchestrator, and one end-to-end path.

### Out of scope (explicitly)
- Paid people-data / LinkedIn enrichment APIs (Apify, People Data Labs, Proxycurl). A `linkedin_lookup()` interface slot exists but ships as a no-op.
- Headless-browser / Playwright scraping of any kind.
- Automated outbound email sequences (the earlier "drafted messages" and "email sequence" options were **not** chosen).
- CRM integration (the handoff packet is a record + text; wiring it into a CRM is a later project).
- Auth / accounts for prospects — the chat is anonymous, keyed to a session id.
- Editing the knowledge base. This system only *reads* `teg-kb-agent/knowledge_base/`.
- Visitor ticket pricing logic (amounts still unpublished; see `registration/registration_and_passes.md`).

---

## 3. Architecture

```
Inquiry page (widget)                FastAPI backend
────────────────────                ──────────────────────────────────
1. Prospect submits name+company ──▶ POST /inquiries
                                     │
                                     ▼  orchestrator.run_pipeline()
                                     ├─▶ [Analysis Agent]
                                     │     canonicalize names, record provided
                                     │     fields, intent hint, consent status
                                     │
                                     ├─▶ [Research Agent]
                                     │     company track + person track, in parallel:
                                     │       KB match → web search → page scrape
                                     │       → "ask prospect" flag if unresolved
                                     │     per outreach_config.md thresholds
                                     │     → ResearchDossier (fields + confidence + sources)
                                     │
                                     └─▶ [Persuasion Agent .init()]
                                           persona map, target CTA, opening message
                                     │
                                     ▼  persist: inquiry, dossier, chat_session
2. "Preparing your session…" ◀───────┘
                                     │
3. Widget opens WS /chat/{session_id}
   ⇄ turn loop ─────────────────────▶ [Persuasion Agent .respond(history, msg)]
                                       guardrails + format rules applied each turn
                                       detect CTA intent, advance cta_status
                                     │
4. Session ends (CTA done / prospect
   leaves / handoff) ───────────────▶ persist: messages, cta outcome,
                                       outcome_status, handoff_packet
```

**Key decisions:**
- **Pipeline runs before the chat opens.** The prospect sees a brief "preparing your session" state (target < 8s). The Persuasion Agent starts the conversation already primed with the dossier, persona, and opening pitch.
- **Research is frozen for the session.** The Research Agent does not run again mid-conversation. If the prospect reveals new info (their actual role, what the company does, a specific need), the Persuasion Agent incorporates it into the conversation and into `session_state.learned_facts` — which feeds the handoff packet — but it does **not** re-trigger research or write back to the dossier. The dossier stays an immutable record of what automated research found. (Revisit in a later iteration if needed.)
- **Agents do not call each other.** The orchestrator sequences them and owns persistence.
- **Graceful degradation everywhere.** Any research tool being unconfigured, rate-limited, or down is logged and skipped; the pipeline continues with whatever was gathered. Worst case: a generic-but-still-guarded pitch plus an in-chat qualifying question.

---

## 4. Components & boundaries

Each unit has one purpose, a typed interface, and is testable alone.

### 4.1 `app/agents/`
- `base.py` — `Agent` ABC. Contract: `async def run(self, input: PydanticModel) -> PydanticModel`. Each agent holds its own system prompt and an `LLMClient` handle. No agent imports another agent.
- `analysis.py` — `AnalysisAgent(IntakePayload) -> IntakeResult`
- `research.py` — `ResearchAgent(IntakeResult) -> ResearchDossier`. Holds a list of `ResearchTool`s and a per-inquiry budget.
- `persuasion.py` — `PersuasionAgent`:
  - `async def init(dossier, intake) -> PersuasionInit` (persona, target_cta, opening_message)
  - `async def respond(session_state, history, prospect_message) -> PersuasionTurn` (reply_text, detected_cta, cta_status, should_handoff, updated_state)

### 4.2 `app/orchestrator.py`
- `run_pipeline(payload) -> {inquiry_id, session_id}` — runs Analysis → Research → Persuasion.init, persists each result, returns ids.
- `run_turn(session_id, prospect_message) -> PersuasionTurn` — loads session + dossier, calls `PersuasionAgent.respond`, persists the message pair and any state change.
- `end_session(session_id, reason)` — writes final `outcome_status`, generates the handoff packet if the CTA wasn't completed.

### 4.3 `app/llm/`
- `base.py` — `LLMClient` interface: `generate(system, messages, **opts) -> str` and `generate_structured(system, messages, schema) -> BaseModel`.
- `anthropic_client.py` — first adapter. Model choice per call (a cheaper model for Analysis's normalization, a stronger one for Persuasion). Config-driven model names.
- Adding another provider = one new adapter file; agents are untouched.

### 4.4 `app/research/`
- `tools.py` — `ResearchTool` ABC: `async def lookup(self, query: ResearchQuery) -> ResearchResult`. Every tool reports `{value, confidence, source_url, tool_name}`.
- `kb_retriever.py` — loads the markdown KB via `app/kb/loader.py`, builds an in-memory index (start: BM25 / fuzzy filename + heading match; a vector store is a later option, not v1), returns matched company/person facts with a match score.
- `web_search.py` — MCP client for Tavily (primary) / Brave (fallback). Config picks which is active. Returns result snippets + urls.
- `page_scraper.py` — `httpx` GET + `readability-lxml` (or `trafilatura`) → clean text for a known URL (company About page, Clutch listing). Timeout + one retry. No JS rendering.
- `linkedin.py` — `LinkedInStub` implementing `ResearchTool`; always returns `ResearchResult(available=False)`. Documented slot for a future paid provider.

### 4.5 `app/kb/loader.py`
- Reads `../teg-kb-agent/knowledge_base/` (path configurable). Parses front-matter-free markdown: file → {title, headings, body, source-line}. Special handling for `companies/*.md`, `organizers_team/*.md`, `speakers/individuals/*.md`, `sector_wise_participation.md`, `pricing/pricing_and_packages.md`, `testimonials/exhibitor_testimonials.md`.
- Exposes: `find_company(name) -> CompanyRecord | None`, `find_person(name) -> PersonRecord | None`, `peers_in_sector(sector, limit) -> list[str]`, `pricing()`, `cleared_testimonials()`.

### 4.6 `app/store/`
- `models.py` — SQLAlchemy models for the 6 tables in §6.
- `repositories.py` — one repository class per aggregate (InquiryRepo, DossierRepo, SessionRepo, MessageRepo, HandoffRepo). Thin; no business logic.
- `migrations/` — Alembic.

### 4.7 `app/api/`
- `inquiries.py` — `POST /inquiries` (body = form payload) → `orchestrator.run_pipeline` → `{session_id}`. `GET /inquiries/{id}` for internal review.
- `chat.py` — `WS /chat/{session_id}`: on connect, send the opening message; on each inbound message, `orchestrator.run_turn` and stream the reply; on disconnect/timeout/END, `orchestrator.end_session`.
- Internal read endpoints for the sales team: `GET /sessions/{id}` (transcript + dossier + handoff).

### 4.8 `config/`
- `settings.py` — env-driven: DB URL, LLM provider + model names + API key, which web-search MCP is active + its key, per-inquiry research budget (max Tavily calls, max scrapes), pipeline timeout, data retention days.
- `outreach_rules.py` — parses `outreach_config.md` into typed objects: `ConfidenceThresholds`, `FieldClassification` (hard-requirements vs enrichable), `PersonaRules`, `Guardrails`, `OutputFormats`. If the markdown changes, this is the single reload point. Includes a test that fails if the markdown's structure drifts from what the parser expects.

### 4.9 `widget/`
- Static, framework-light (vanilla or Preact). Renders the form + the chat. `POST`s the form, then opens the WS. Shows the "preparing" state. No build step required to embed (single `<script>` + `<div>`), but a `dist/` bundle step is fine.
- Accessibility: keyboard-navigable, ARIA live region for incoming messages, respects reduced-motion.

---

## 5. The three agents in detail

### 5.1 Analysis Agent

**Input** `IntakePayload`: `person_name`, `company_name` (both required); optional `email`, `phone`, `city`, `designation`, `participation_type`, `tech_category`, `message`, `preferred_contact_time`, `consent` (bool|null).

**Behaviour:**
- Normalize `person_name`: strip honorifics (Mr./Ms./Dr./Shri), collapse whitespace, title-case.
- Canonicalize `company_name`: expand known abbreviations *only when unambiguous against the KB* (e.g. "TRT" → "Third Rock Techkno" because the KB has it), normalize legal suffixes ("Pvt. Ltd."/"Private Limited"/"LLP"), keep the raw string too.
- Record `provided_fields`: the set of optional fields that came in non-empty.
- `intent_hint`: from `participation_type` if given; else infer from `message` keywords (exhibit/stall/booth → exhibitor; sponsor/partner → sponsor; visit/attend/ticket → visitor; pitch/startup/funding → startup_pitch); else `unknown`.
- `consent_status`: `given` if `consent is True`; `not_given` if `consent is False`; `unknown` if absent.

**Output** `IntakeResult`: `person_name`, `company_name_raw`, `company_name_canonical`, `provided_fields: dict`, `intent_hint: enum`, `consent_status: enum`.

**Non-blocking:** missing email/phone is normal. Only `consent_status == not_given` changes behaviour — it suppresses any *proactive* post-chat follow-up (no handoff message drafted for outbound use), but the live chat still runs because the prospect initiated it.

**LLM use:** one `generate_structured()` call for canonicalization + intent, with the KB company list passed as context for disambiguation. Cheap model.

### 5.2 Research Agent

**Input:** `IntakeResult`.

**Two parallel tracks**, each a bounded cascade:

**Company track** — target fields: `sector`, `size`, `hq`, `founder(s)`, `website`, `tech_focus`, `teg_history` (2024 exhibitor? 2026 exhibitor? sponsor tier? Retreat/Ignite?), `booth_number`.
1. **KB match** — `kb.find_company(canonical)` fuzzy match. Per `outreach_config.md`: exact (case-insensitive) ≥95% → auto-accept; Levenshtein ≤2 → 70–94% → flag for review; substring 50–69% → flag; <50% → go to web. A KB hit typically fills most target fields at high confidence, plus `teg_history`.
2. **Web search** (Tavily) — on KB miss or to fill fields the KB lacks (current size, recent projects, funding). Max 2 calls.
3. **Page scrape** — if web results include the company's own site or a Clutch/DesignRush page, scrape the About page for founder/size/HQ. Max 3 scrapes.

**Person track** — target fields: `designation`, `seniority` (IC / manager / exec / founder), `is_technical` (bool guess), `linkedin_url` (if it appears in search snippets — not scraped), `teg_role` (organizer? past speaker? named founder in a company profile?), `background`.
1. **KB match** — `kb.find_person(name)` against `organizers_team/`, `speakers/individuals/`, and founder names inside `companies/*.md`. A hit here is high-signal (e.g. an organizer inquiring).
2. **Web search** — `"<name>" "<company>"` for title/role and press. Max 2 calls.
3. No scraping of LinkedIn. If a LinkedIn URL appears in a snippet, record it; do not fetch it.

**Cross-checks & derived fields:**
- `person_company_match`: does evidence place this person at this company? `true` / `false` / `null` (unknown). A `false` becomes a `review_flag` and the Persuasion Agent will gently verify in-chat.
- `relationship`: `insider` (person is a TEG organizer), `returning` (company is a past exhibitor/sponsor, or person is a past speaker), else `cold`.
- `sector`: resolved sector string, used to pull peers.
- `peer_companies`: `kb.peers_in_sector(sector, limit=5)` — **must** come from `sector_wise_participation.md` per the guardrail; never invented.

**Budget:** hard caps from config (default: ≤2 Tavily calls/track, ≤3 scrapes total, pipeline-wide 8s soft / 20s hard timeout). On exceeding, stop and emit what's gathered.

**Unresolved case:** if after the cascade the company or person is still `confidence < 0.5` on identity, set `dossier.ask_prospect = ["company_description", "role"]` (or whichever). The Persuasion Agent opens with a light qualifying question instead of asserting facts.

**Output** `ResearchDossier`: `company_profile: dict`, `person_profile: dict`, `person_company_match`, `relationship`, `sector`, `peer_companies: list[str]`, `field_confidence: dict[str, float]`, `sources: list[{field, url, tool, confidence}]`, `review_flags: list[str]`, `ask_prospect: list[str]`, `research_cost: dict`.

### 5.3 Persuasion Agent

**`init(dossier, intake) -> PersuasionInit`:**
- **Persona mapping** (from `outreach_config.md`):
  - Sector in {Software Development, Cloud & Infrastructure, Enterprise Software, Data & Analytics} → **IT/Tech Service**
  - Sector in {AI & Machine Learning} AND size < 50 → **AI/Deep-Tech Startup**
  - `intent_hint == sponsor` AND non-tech sector → **Non-Tech Sponsor**
  - `intent_hint == visitor` → **Visitor**
  - **Fallback order when none of the above match:**
    1. If `sector` resolved to any technology sector listed in `sector_wise_participation.md` → **IT/Tech Service**.
    2. Else if `sector` resolved to a non-tech sector AND `intent_hint == unknown` → **Visitor** (the safest, lowest-commitment pitch).
    3. Else if nothing resolved at all (`dossier.ask_prospect` non-empty) → **Visitor** persona for tone, but the opening message is the qualifying question; re-map the persona on the next turn once the prospect answers.
- **Value props**: pull the persona's props from `exhibitor_benefits_analysis.md` + `outreach_config.md`.
- **Target CTA** by persona: IT/Tech Service → *book a stall* (quote `pricing_and_packages.md`); AI Startup → *Catalyst Zone booking or submit a pitch deck*; Non-Tech Sponsor → *request a sponsorship call*; Visitor → *register for a visitor pass*.
- **Opening message**: acknowledge company + sector (from dossier), one persona value prop, name 3 peer companies from `peer_companies`, soft ask. If `dossier.ask_prospect` is non-empty, lead with the qualifying question instead. Tone from `relationship` (`insider`/`returning` → "welcome back", reference their specific history; `cold` → warm but not familiar).

**`respond(state, history, prospect_message) -> PersuasionTurn`:**
- Generate the next reply given the conversation, dossier, persona, and target CTA.
- **Persona re-mapping:** the persona is normally fixed at `init`. The one exception is the unresolved-identity case (fallback 3 above): if `init` could not resolve a sector, then on the first prospect reply that reveals what the company does, the agent re-runs persona mapping once and persists the new `persona` on the session. After that first re-map, the persona is fixed for the session.
- **Guardrails applied every turn** (from `outreach_config.md` + KB rules), enforced by a post-generation check that can force a regeneration:
  - No fabricated statistics or testimonials. Every quantitative claim must trace to a KB source file.
  - Only the **4 cleared testimonials** in `testimonials/exhibitor_testimonials.md` may be quoted, and only as speaker/scale voices — never attributed as exhibitor-ROI proof.
  - Peer lists only from `sector_wise_participation.md`.
  - Never assume budget, timeline, or decision authority.
  - Stay within **Confirmed** facts (per `SKILL.md` §5); never present "Awaiting Confirmation" items (e.g. visitor ticket amounts, unfilled sponsor categories) as settled.
  - Pricing: stall and sponsorship prices **are** confirmed (`pricing_and_packages.md`) — quote accurately, always "+ GST", note the asterisk/"indicative at booking" caveat, mention the 4-instalment payment plan when relevant.
  - Respect `consent_status == not_given`: answer in-chat, but don't push for contact details for later outbound.

  **Guardrail failure handling:** the post-generation check runs against the draft reply. On a violation, the agent regenerates once with the specific violation named in the prompt. If the second attempt also violates, the turn falls back to a **safe templated reply** for that persona (a generic, fully-KB-sourced response plus the CTA), the turn is recorded with `guardrail_flags` set, and the session is marked for review. The prospect never sees a violating message, and the system never silently ships one.
- **CTA tracking**: detect intent-to-act → advance `cta_status` (`none → offered → in_progress → completed | declined`). On `completed`, record `cta_type` + any detail (stall size chosen, callback time). On repeated deflection or an explicit "just researching", set `should_handoff = true`.
- **Callback**: if the prospect gives a preferred time (form field or in chat), capture it.

**Output** `PersuasionTurn`: `reply_text`, `detected_cta`, `cta_status`, `cta_type`, `should_handoff`, `updated_state`, `guardrail_flags`.

**Session end** (`orchestrator.end_session`):
- `outcome_status`: `qualified` (CTA completed or strong intent + callback), `contacted` (engaged, no commitment), `lost` (explicit no / bounced immediately).
- **Handoff packet** (always generated unless CTA completed cleanly): `summary` (who, company, what they want, where the conversation landed), `recommended_next_step`, `suggested_followup_message` (a draft a TEG rep can send — respects consent status), `prospect_confidence` (how sure we are about identity/fit), `key_facts` (dossier highlights + anything learned in chat).

---

## 6. Data model (Postgres)

```sql
inquiries (
  id                      uuid pk,
  created_at              timestamptz,
  person_name             text not null,
  company_name_raw        text not null,
  company_name_canonical  text,
  email                   text,
  phone                   text,
  city                    text,
  designation             text,
  participation_type      text,          -- visitor|exhibitor|sponsor|startup_pitch|speaker|null
  tech_category           text,
  message                 text,
  preferred_contact_time  text,
  consent_status          text not null, -- given|not_given|unknown
  intent_hint             text not null, -- + unknown
  source                  text           -- 'inquiry_page' etc.
)

research_dossiers (
  id                    uuid pk,
  inquiry_id            uuid fk -> inquiries,
  created_at            timestamptz,
  company_profile       jsonb,
  person_profile        jsonb,
  person_company_match  boolean,         -- nullable
  relationship          text not null,   -- cold|returning|insider
  sector                text,
  peer_companies        jsonb,           -- ["A","B","C"]
  field_confidence      jsonb,           -- {"sector":0.95,...}
  sources               jsonb,           -- [{"field","url","tool","confidence"}]
  review_flags          jsonb,           -- ["person_company_mismatch",...]
  ask_prospect          jsonb,           -- ["company_description","role"]
  research_cost         jsonb            -- {"tavily_calls":2,"scrape_calls":1}
)

chat_sessions (
  id                uuid pk,
  inquiry_id        uuid fk -> inquiries,
  dossier_id        uuid fk -> research_dossiers,
  started_at        timestamptz,
  ended_at          timestamptz,
  persona           text,                -- it_tech_service|ai_startup|non_tech_sponsor|visitor
  target_cta        text,
  cta_status        text not null,       -- none|offered|in_progress|completed|declined
  cta_type          text,
  cta_detail        jsonb,               -- {"stall_size":"3x3","callback":"2026-09-02 15:00"}
  outcome_status    text,                -- new|contacted|qualified|lost  (data_schema.md §8)
  handoff_generated boolean default false,
  learned_facts     jsonb,               -- facts the prospect revealed in chat (not written back to the dossier)
  persona_remapped  boolean default false,-- true if the unresolved-identity re-map fired
  needs_review      boolean default false -- set when a guardrail fallback was used
)

chat_messages (
  id              uuid pk,
  session_id      uuid fk -> chat_sessions,
  turn_index      int,
  role            text not null,         -- agent|prospect|system
  content         text not null,
  created_at      timestamptz,
  guardrail_flags jsonb,
  detected_intent jsonb
)

handoff_packets (
  id                     uuid pk,
  session_id             uuid fk -> chat_sessions,
  created_at             timestamptz,
  summary                text,
  recommended_next_step  text,
  suggested_followup_message text,
  prospect_confidence    text,           -- high|medium|low
  key_facts              jsonb,
  delivered_to           text            -- nullable; sales-team routing later
)
```

**Compliance (`data_schema.md` §9):** `consent_status` on `inquiries`; a `retention_days` config drives a scheduled purge of `chat_messages` + `research_dossiers` for inquiries older than the window (privacy-policy acknowledgement is on the inquiry form, not modelled separately for v1).

---

## 7. Repo layout

New sibling package to `teg-kb-agent/`:

```
teg-outreach-agent/
├── pyproject.toml
├── README.md
├── config/
│   ├── settings.py
│   └── outreach_rules.py            # parses ../teg-kb-agent/knowledge_base/outreach_config.md
├── app/
│   ├── api/{inquiries.py, chat.py, internal.py}
│   ├── agents/{base.py, analysis.py, research.py, persuasion.py}
│   ├── orchestrator.py
│   ├── llm/{base.py, anthropic_client.py}
│   ├── research/{tools.py, kb_retriever.py, web_search.py, page_scraper.py, linkedin.py}
│   ├── kb/loader.py
│   ├── store/{models.py, repositories.py, migrations/}
│   └── domain/schemas.py            # all Pydantic models
├── widget/
│   ├── src/
│   └── dist/
└── tests/
    ├── agents/       # each agent isolated, LLM + tools stubbed
    ├── research/     # KB retrieval golden tests, tool mocks
    ├── kb/           # loader parses the real KB correctly
    ├── orchestrator/
    ├── config/       # outreach_config.md structural-drift test
    └── e2e/          # POST /inquiries -> pipeline -> WS chat -> handoff
```

---

## 8. Configuration

All via env (`config/settings.py`), with sane defaults:

| Setting | Default | Notes |
|---|---|---|
| `DATABASE_URL` | — | Postgres |
| `LLM_PROVIDER` | `anthropic` | adapter selector |
| `LLM_MODEL_FAST` | a cheap model | Analysis Agent |
| `LLM_MODEL_MAIN` | a strong model | Research synthesis + Persuasion |
| `ANTHROPIC_API_KEY` | — | |
| `WEB_SEARCH_PROVIDER` | `tavily` | `tavily` \| `brave` \| `none` |
| `TAVILY_API_KEY` / `BRAVE_API_KEY` | — | free tiers |
| `RESEARCH_MAX_SEARCHES_PER_TRACK` | `2` | |
| `RESEARCH_MAX_SCRAPES` | `3` | |
| `PIPELINE_SOFT_TIMEOUT_S` | `8` | show "preparing" up to here |
| `PIPELINE_HARD_TIMEOUT_S` | `20` | then proceed degraded |
| `KB_PATH` | `../teg-kb-agent/knowledge_base` | |
| `DATA_RETENTION_DAYS` | `180` | purge job |
| `LINKEDIN_PROVIDER` | `none` | stub only; no paid option wired |

---

## 9. Testing strategy

- **Per-agent isolation:** `AnalysisAgent`, `ResearchAgent`, `PersuasionAgent` each tested with a stubbed `LLMClient` and (for Research) stubbed `ResearchTool`s. Fixtures cover: KB hit, KB miss, person=organizer, person/company mismatch, consent not given, unresolved identity.
- **KB retrieval golden tests:** given the real KB, `find_company("TRT")` → Third Rock Techkno; `find_person("Tejas Shah")` → organizer + MagnusMinds; `peers_in_sector("AI & Machine Learning")` ⊆ the file's list.
- **Guardrail tests:** feed the Persuasion Agent prompts that would tempt fabrication (a made-up testimonial, a non-file peer, a visitor price) and assert the post-generation check catches and regenerates. A separate test stubs the LLM to violate twice and asserts the **safe templated reply** is used, `guardrail_flags` is populated, and `needs_review` is set.
- **Persona re-map test:** unresolved identity at `init` → opening is a qualifying question; prospect answers → persona re-maps exactly once and `persona_remapped` is set; a later reply does not re-map again.
- **`outreach_config.md` drift test:** `outreach_rules.py` parser run against the live file; fails loudly if headings/tables it depends on change shape.
- **Orchestrator:** pipeline sequencing, persistence, degraded-path (tool down → still produces a session).
- **E2E:** one happy path (form → pipeline → 3-turn chat → CTA completed → record written) and one handoff path (prospect deflects → handoff packet generated).

---

## 10. Open questions / deferred

- **KB retrieval quality:** v1 is BM25/fuzzy. If persona pitches feel thin, add a vector index over the KB (pgvector) — deferred, not v1.
- **Widget hosting:** where the static bundle is served from (same FastAPI app vs. CDN) — decide at implementation.
- **Rate limiting / abuse:** the public `POST /inquiries` needs basic rate limiting (per-IP) and a CAPTCHA or similar before production. Noted, not designed here.
- **Sales-team delivery of handoff packets:** currently just a DB row + internal endpoint. Slack/email routing is a follow-up.
- **Multi-language:** Gujarati/Hindi prospects — English-only for v1.
- **Splededge / Ittive:** 2 KB companies still unidentified; unrelated to this system but affects `peer_companies` completeness for their sectors.

---

## 11. Success criteria

1. A form submission with only name + company produces, within the hard timeout, a chat session with a persona-appropriate, factually-grounded opening message.
2. When the company is in the KB, the opening message correctly reflects its sector, TEG history, and 3 real peer companies.
3. When neither person nor company can be identified, the agent opens with a qualifying question rather than a wrong assertion.
4. No message ever contains a fabricated statistic, an uncleared testimonial, an invented peer, or a visitor ticket price.
5. Every session ends with a persisted lead record (`outcome_status` set) and, unless the CTA completed cleanly, a handoff packet with a usable draft follow-up.
6. The whole research path runs on free tools; no paid API is required to operate.
