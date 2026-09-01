# TEG Personalized Proposal (Live PDF) — Design Spec

> **Status:** Approved design (2026-09-01)
> **Owner:** rohanb@thirdrocktechkno.com
> **Builds on:** `docs/superpowers/specs/2026-08-31-teg-outreach-agent-design.md` (the outreach agent — already built on branch `feat/teg-outreach-agent`)
> **Related KB:** `teg-kb-agent/knowledge_base/` (read-only), + one new file this project adds

---

## 1. Purpose

During a live chat on the TEG inquiry page, the prospect can get a **personalized proposal document** — an HTML-rendered PDF, generated on the spot from *their* conversation and *their* company's research dossier. It shows: what we understood about their situation, the specific pain points TEG addresses for them, how they'd generate leads at the event, proof the event works, the pricing option that fits them, sector peers already participating, and next steps.

The PDF appears **inline in the chat** as a WhatsApp-style attachment card (first-page thumbnail + filename + size + Open/Download), plus a plain URL, plus optional email delivery.

This exists to convert a warm conversation into something the prospect can **forward to their team / decision-makers** — the moment where "sounds interesting" becomes a shareable internal case.

---

## 2. Scope

### In scope
- A new KB file: `event_goals_and_problem.md` (the "what is TEG *for*" content — currently missing).
- A `ProposalAgent` (on-demand, not part of `run_pipeline`).
- One structured LLM call → `Proposal` object → Jinja2 HTML template → WeasyPrint PDF + first-page PNG.
- The same `check_message` guardrails applied per section, plus two new checks (no competitor mentions, no commitment/signature language).
- Live generation during the chat with a typing/progress indicator; regeneration on repeat request (versioned).
- Inline attachment card in the widget + URL + optional email (email off by default).
- `proposals` table; PDFs on the filesystem under `proposals/`, purged by the existing retention job.
- New API: `POST /sessions/{id}/proposal`, `GET /proposals/{id}.pdf`, `GET /proposals/{id}/preview.png`.
- Widget: attachment-card rendering, progress state, "get a proposal" affordance.

### Out of scope
- E-signatures, contracts, binding quotes. This is an information document.
- Competitor comparisons.
- Editing the rest of the KB (only *adds* `event_goals_and_problem.md`).
- A separate proposal for the sales team (the handoff packet already covers that; the sales team can read the prospect's proposal via `GET /sessions/{id}`).
- Multi-language proposals (English only, matching the chat).
- PDF hosting on a CDN / external storage.
- Browser-based (Chromium) rendering — WeasyPrint only, no browser dependency.

---

## 3. Part A — KB addition: `event_goals_and_problem.md`

New file at `teg-kb-agent/knowledge_base/event_goals_and_problem.md`. Committed to `main` (where the KB lives), before the code work. Content, all sourced from techexpogujarat.com/about-us + existing KB files (cited in the file's footer):

### Sections
1. **The problem TEG was created to solve** — verbatim: *"A group of CXOs saw what Gujarat was missing — a unified tech stage built by the community, for the community."* Expanded (KB-grounded): Gujarat's tech ecosystem was fragmented; local tech companies were under-discovered by local buyers; SMEs/MSMEs were slow to adopt AI/tech; startups had limited in-state investor access; no single stage where "innovation meets the sectors that power Gujarat's economy."
2. **TEG's stated goals** — position Gujarat as a global tech hub; converge techpreneurs + industry pioneers + investors + innovators to "build, collaborate, and lead"; serve diverse industries "from fintech and healthtech to real estate, manufacturing, and beyond"; drive AI/tech *adoption* across the broader business ecosystem (not IT-to-IT only). Mission/vision/values quoted.
3. **The mechanism (how the goal is delivered)** — 15,000+ cross-industry decision-makers under one roof · pre-scheduled 1:1 B2B matchmaking · live product demonstrations · the TEG app for networking · investor/VC track (Retreat/Ignite). This is *how* a participant gets discovered by buyers/partners/investors they otherwise couldn't reach.
4. **Evidence the mechanism works** — TEG 2024 actuals (8,000+ attendees, 125+ exhibitors, 50+ sponsors, 20+ speakers); growth trajectory to the 2026 targets; TEG Retreat 2025 (₹1.5 cr raised in one day, 15+ VCs); the 4 cleared testimonials (pointer to `testimonials/exhibitor_testimonials.md`). All figures cite their source file. **No new numbers invented.**
5. **Persona pain-point library (base set)** — a table: for each persona, 3-5 common pains and the TEG-specific counter, KB-grounded. This is the *base* the ProposalAgent personalizes from — the LLM adds/rewrites per the actual conversation.
   - **IT/Tech Service:** revenue concentrated in one geography → 15,000+ India-market buyers + B2B matchmaking · low local brand visibility → on-ground + digital + PR presence · casual-footfall leads → pre-scheduled qualified meetings · hard to demo complex products → live demo space · competing on price with no differentiation → "AI & future-tech" positioning alongside keynote names.
   - **AI/Deep-Tech Startup:** no in-state investor access → VC network (₹1.5 cr track record) · can't afford flagship-expo booths → Catalyst Zone ₹35,000 + GST · no channel to enterprise buyers → cross-industry decision-makers + matchmaking · unproven / no social proof → Experience Zone AI demos + association with the event's innovation narrative.
   - **Non-Tech Sponsor:** brand not linked to the region's innovation story → category-exclusive sponsorship + "AI revolution" association · competitors could take the category → exclusivity (once locked, competitors excluded) · limited C-suite access → networking alongside keynote speakers · fragmented regional media spend → omnichannel (venue + digital + print + regional media).
   - **Visitor:** don't know which local providers solve my problem → 250+ exhibitors across 18 industries in one place · vendor selection takes months of separate meetings → compressed into 3 days + the TEG app · unsure if regional tech is enterprise-grade → see it demonstrated live, meet the founders.
6. **What TEG is NOT** — not IT-only; not a job fair; not a pure startup pitch event (that's the Retreat); attendance is ticketed (no free entry).

### KB integration
- Add to `SKILL.md` Step 1 routing table: `Event goals, the problem TEG solves, per-persona pain points | knowledge_base/event_goals_and_problem.md`.
- Add to `INDEX.md` file tree + counts + a one-line quick-reference.
- Update `event_overview/event_info.md` with a pointer ("For TEG's goals and the problem it solves, see `event_goals_and_problem.md`").

---

## 4. Part B — The Proposal pipeline

### 4.1 Trigger
- The Persuasion Agent's turn prompt gains: *if the prospect shows real interest (asked about pricing, leads, or "how it helps"), you MAY offer: "I can put together a tailored one-page proposal for [company] you can share with your team — want that?"*
- Or the prospect asks directly ("can you send me details / something in writing / a proposal / a PDF").
- Detection: the `_Analysis` schema gains `wants_proposal: bool` (the LLM sets it when the prospect asks or accepts the offer). The orchestrator, seeing `wants_proposal`, calls the proposal flow after sending the turn reply.

### 4.2 `ProposalAgent`
- `app/agents/proposal.py` — `ProposalAgent(Agent)`, `async def build(self, *, intake, dossier, transcript, learned_facts, session_id, version) -> Proposal`.
- Inputs: the full `IntakeResult`, the `ResearchDossier`, the entire transcript (list of role/content), `learned_facts`, and — loaded once — `event_goals_and_problem.md` (via `get_kb()`), the persona pain-library base, `pricing_and_packages.md`, `peers_in_sector`, `cleared_testimonials`.
- **One `llm.generate_structured(Proposal)` call** on the main model (this is a rich, one-shot document — worth the stronger model), producing:

```python
class ProposalPain(BaseModel):
    pain: str            # inferred, in the prospect's own terms
    teg_answer: str      # KB-grounded, TEG-specific

class ProposalPackage(BaseModel):
    name: str            # e.g. "3m x 6m stall"
    price_line: str      # "₹2,34,000 + GST (indicative, confirmed at booking)"
    includes: list[str]
    payment_plan: str

class Proposal(BaseModel):
    company: str
    person: str
    person_role: str | None
    sector: str | None
    generated_on: str            # ISO date
    session_ref: str             # short session id
    version: int
    what_you_told_us: str        # 2-3 sentences from the conversation
    pains: list[ProposalPain]    # 2-4
    lead_generation: str         # how THEY generate leads, tuned to their target market
    proof: list[str]             # KB-grounded bullets; may include <= 2 cleared testimonials verbatim
    recommended_package: ProposalPackage
    peer_companies: list[str]    # 3-5 from sector_wise_participation.md
    next_steps: list[str]
    contact: str                 # from event_info.md
```

- **Persona → package mapping** reuses `target_cta_for` / `_PRICING_LINE` logic (IT service → 3×3–6×6 stalls; AI startup → Catalyst Zone; sponsor → sponsorship tiers; visitor → visitor registration, and the proposal reframes as "why attend").
- **Guardrails:** every free-text field (`what_you_told_us`, each `pain`/`teg_answer`, `lead_generation`, each `proof` bullet, each `next_step`) runs through `check_message(text, allowed_peers=peer_companies, persona=persona)` **plus two new checks**:
  - `competitor_mention` — names of other expos/events ("EFY Expo", "Tech Vapi", "vs other events", "unlike other expos") → violation.
  - `commitment_language` — "you agree", "by signing", "this constitutes", "binding", signature-block phrasing → violation.
  On any violation: one regeneration of the **whole Proposal** with the violations named; if still failing, the offending field is replaced with a **safe templated equivalent** for that section (persona-specific, fully KB-sourced) and `guardrail_flags` recorded on the `proposals` row (session flagged for review).
- `proof` may include at most **2 of the 4 cleared testimonials**, quoted verbatim, attributed — the guardrail enforces this.

### 4.3 Rendering
- `app/proposal/render.py`:
  - `render_html(proposal: Proposal) -> str` — Jinja2 template `app/proposal/templates/proposal.html.j2`. TEG brand palette (from the collateral: deep blue `#1b2a5b`-ish, the multi-colour accent, white ground), a cover band, clean section headings, a pricing table, a peer-logo-free peer list (names only), a dated + versioned footer with `session_ref` and "Indicative and subject to confirmation at booking. Not a contract or binding quote."
  - `render_pdf(html: str) -> bytes` — `weasyprint.HTML(string=html).write_pdf()`.
  - `render_first_page_png(html: str) -> bytes` — render the HTML to PNG at a low DPI, then crop to the first A4 page's height (WeasyPrint `write_png()` stacks all pages into one tall image; slice the top `page_height_px`). Target ~600px wide. `Pillow` (already a WeasyPrint dep) does the crop. If this proves fiddly, fall back to `pymupdf` (`fitz`) rendering page 0 of the PDF bytes — add `pymupdf` to deps only if needed and note it.
- No external CSS/fonts fetched at render time — the template inlines CSS and uses a system font stack (WeasyPrint has no network in this design).

### 4.4 Storage
- `proposals/` directory (gitignored), one subdir per session: `proposals/<session_id>/v<version>.pdf` and `v<version>.png`.
- `proposals` table:
  ```
  id            uuid pk
  session_id    uuid fk -> chat_sessions
  version       int
  created_at    timestamptz
  proposal_json jsonb          -- the Proposal object
  pdf_path      text
  png_path      text
  bytes         int            -- pdf size, for the card
  guardrail_flags jsonb
  emailed_to    text           -- nullable
  ```
- Retention: `app/jobs/retention.py` `purge_expired` extended to also delete `proposals` rows + their files for inquiries past `DATA_RETENTION_DAYS`.

### 4.5 Delivery
- **Inline card (primary):** the orchestrator, after generating a proposal, appends a `chat_messages` row with `role="agent"` and a new `attachment` jsonb column:
  ```json
  {"kind": "proposal", "proposal_id": "...", "version": 2,
   "filename": "TEG-2026-Proposal-Acme-v2.pdf", "bytes": 148213,
   "pdf_url": "/proposals/<id>.pdf", "png_url": "/proposals/<id>/preview.png"}
  ```
  and pushes it over the WS as `{"type":"attachment", ...}`. The widget renders a card: thumbnail (`png_url`) + filename + human size + "Open" (new tab) + "Download".
- **URL (secondary):** the same agent turn's `reply_text` includes the link in prose: *"Here's your proposal — [download PDF](…). Feel free to share it with your team."*
- **Email (optional, off by default):** if `EMAIL_ENABLED=true` and the prospect has given an email (form field or in chat — the agent may ask "want me to email you a copy?"), `app/proposal/email.py` sends the PDF via SMTP (`SMTP_HOST/PORT/USER/PASS/FROM` env). Failure is logged, non-fatal — the card + URL still work. `proposals.emailed_to` records the address.

### 4.6 Live generation UX (the loading state)
- On `wants_proposal`, the orchestrator:
  1. sends the normal turn reply first (so the conversation flows), containing a line like *"Give me a moment — putting together a proposal tailored to [company]…"*.
  2. pushes `{"type":"proposal_pending", "company": "..."}` over the WS → widget shows a skeleton attachment card with a spinner + a subtle "typing" dot.
  3. runs `ProposalAgent.build` → guardrails → render (target < 8s; hard cap 20s — on timeout, push `{"type":"proposal_failed"}` and the agent says it'll follow up).
  4. on success, pushes the `attachment` message → the skeleton card fills in.
- The chat input stays enabled throughout; the prospect can keep talking while it generates.

### 4.7 Regeneration
- Each `wants_proposal` (or an explicit "can you update that / redo it with…") produces a **new version**: `version = last_version + 1`, new files, new `proposals` row, new card in the chat labelled "v2", "v3". Older versions' URLs keep working until retention purges them.
- The build always uses the **current full transcript + latest `learned_facts`**, so a later proposal is strictly better-informed.

---

## 5. Data model changes

```sql
-- new
proposals (
  id, session_id (fk), version, created_at,
  proposal_json jsonb, pdf_path, png_path, bytes int,
  guardrail_flags jsonb, emailed_to text
)

-- changed
chat_messages
  + attachment jsonb   -- null for normal messages; the card payload for proposal messages
```

Alembic migration `0002_proposals.py`.

---

## 6. API changes

- `POST /sessions/{session_id}/proposal` — body optional `{"email": "..."}`. Generates the next version, returns the card payload. (The WS flow calls the same underlying orchestrator method; this endpoint is for the sales team / debugging / a manual "regenerate" button.)
- `GET /proposals/{proposal_id}.pdf` — serves the file with `Content-Disposition: inline; filename="..."`.
- `GET /proposals/{proposal_id}/preview.png` — serves the thumbnail.
- `GET /sessions/{session_id}` (existing internal endpoint) — response gains a `proposals: [{version, created_at, pdf_url, guardrail_flags}]` list.
- WS `/chat/{session_id}` — new outbound message types: `proposal_pending`, `attachment`, `proposal_failed`.

---

## 7. Component boundaries

```
teg-outreach-agent/
├── app/
│   ├── agents/proposal.py            # ProposalAgent + Proposal/ProposalPain/... schemas
│   ├── agents/guardrails.py          # + competitor_mention, commitment_language checks; + PROPOSAL_SAFE_SECTIONS
│   ├── proposal/
│   │   ├── render.py                 # render_html / render_pdf / render_first_page_png
│   │   ├── email.py                  # optional SMTP send
│   │   └── templates/proposal.html.j2
│   ├── orchestrator.py               # + generate_proposal(session_id, email=None) -> card payload
│   ├── store/models.py               # + proposals table, chat_messages.attachment
│   ├── store/repositories.py         # + ProposalRepo
│   ├── api/chat.py                   # handle wants_proposal -> pending/attachment/failed frames
│   ├── api/proposals.py              # GET .pdf / preview.png ; POST /sessions/{id}/proposal
│   └── jobs/retention.py             # + purge proposals
├── proposals/                        # generated files (gitignored)
└── widget/src/
    ├── ui.ts                         # renderAttachmentCard(), pending skeleton
    └── index.ts                      # handle attachment / proposal_pending / proposal_failed WS frames
```

New deps: `weasyprint`, `jinja2`. (`weasyprint` pulls `pydyf`, `cffi`, `Pillow`, and system libs `libpango`/`libcairo`/`libgdk-pixbuf` — check availability in Task 1; these are usually present on Ubuntu.)

---

## 8. Configuration

| Setting | Default | Notes |
|---|---|---|
| `PROPOSAL_MODEL` | = `LLM_MODEL_MAIN` | the document is worth the stronger model |
| `PROPOSAL_SOFT_TIMEOUT_S` | `8` | show pending state up to here |
| `PROPOSAL_HARD_TIMEOUT_S` | `20` | then `proposal_failed` |
| `PROPOSAL_DIR` | `./proposals` | generated files |
| `EMAIL_ENABLED` | `false` | gates the SMTP path |
| `SMTP_HOST/PORT/USER/PASS/FROM` | — | only read when `EMAIL_ENABLED` |

---

## 9. Testing strategy

- **KB file test:** `event_goals_and_problem.md` parses; `get_kb()` exposes a `goals_and_pains()` accessor returning the persona pain-library as structured data; golden assertions (IT-service pains include a geography/pipeline one; startup pains include investor access).
- **ProposalAgent:** stubbed `LLMClient` returning a `Proposal`; assert persona→package mapping, peer list ⊆ `sector_wise_participation.md`, cleared-testimonial cap.
- **Guardrail tests:** feed a `Proposal` with a competitor mention, a "by signing" clause, a made-up stat, an uncleared testimonial, an invented peer → assert each is caught and the safe-section fallback fires with flags.
- **Render tests:** `render_html` produces valid HTML containing the company name, the pricing line with "+ GST", the dated footer; `render_pdf` returns non-empty `%PDF` bytes; `render_first_page_png` returns non-empty PNG bytes. (No golden-image comparison — just "renders without error and contains the key strings".)
- **Orchestrator:** `wants_proposal` on a turn → a `proposals` row + a `chat_messages` row with `attachment` + the returned card payload; regeneration bumps `version`.
- **API:** `GET /proposals/{id}.pdf` returns `application/pdf`; `POST /sessions/{id}/proposal` creates v2.
- **WS:** a turn with `wants_proposal` emits `proposal_pending` then `attachment`; a forced render error emits `proposal_failed`.
- **Retention:** an old inquiry's proposals + files are deleted; a fresh one's are kept.
- **Widget:** `renderAttachmentCard` builds the card DOM from a payload; the pending skeleton shows then is replaced.
- **E2E:** full flow — inquiry → chat → prospect asks for a proposal → `attachment` frame received → `GET` the pdf url → 200 `%PDF`.
- **No real network / no real LLM in any test.** WeasyPrint runs for real (it's local, offline, deterministic); render tests may be marked `@pytest.mark.slow` if they add noticeable time, but stay in the default run.

---

## 10. Success criteria

1. Mid-conversation, when the prospect asks for a proposal (or accepts the offer), a PDF is generated and appears as an inline card in the chat within the hard timeout, plus a working download URL in the reply text.
2. The proposal's "what you told us" and pain-point sections reflect *this* conversation, not a template — a prospect who said "we want India-market clients" gets a lead-gen section about reaching India-market buyers, and a pain about geographic revenue concentration.
3. The recommended package matches the persona and quotes real pricing with "+ GST" and "indicative, confirmed at booking"; peer companies are real and from the sector file.
4. No proposal ever contains a fabricated statistic, an uncleared testimonial, an invented peer, a visitor ticket price, a competitor's name, or signature/commitment language — enforced by the guardrail pass with a safe fallback.
5. Every PDF carries a generation date, a version, and a session reference; a "not a contract" footer.
6. Asking again later produces a v2 with the fuller conversation; both versions' links work until retention purges them.
7. The whole flow runs without a browser (WeasyPrint only) and without email configured (card + URL always work).
