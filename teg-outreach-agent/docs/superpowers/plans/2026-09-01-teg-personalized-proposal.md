# TEG Personalized Proposal (Live PDF) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** During a live inquiry-page chat, generate a personalized proposal PDF (HTML → WeasyPrint) from the conversation + research dossier and show it inline as a WhatsApp-style attachment card, plus a download URL and optional email.

**Architecture:** A new `ProposalAgent` runs on demand when the prospect asks for (or accepts an offer of) a proposal. It makes one structured LLM call to build a `Proposal` object, guards every text field with the existing `check_message` plus two new checks, renders it through a Jinja2 template to a PDF + first-page PNG with WeasyPrint (no browser), stores files + a `proposals` row, and pushes an `attachment` message over the chat WebSocket. Regeneration produces a new version. A new KB file (`event_goals_and_problem.md`) gives the agent the "what TEG is for" content + a per-persona pain-point library.

**Tech Stack:** Adds to the existing `teg-outreach-agent` stack — `weasyprint>=62`, `jinja2>=3.1`. System libs (libpango, libcairo, libgdk-pixbuf) are already present. `Pillow` comes transitively with WeasyPrint.

**Design spec:** `docs/superpowers/specs/2026-09-01-teg-personalized-proposal-design.md` — read it before starting.

## Global Constraints

- Branch: `feat/teg-outreach-agent` (the outreach agent lives here; this extends it). The KB file (Task 1) goes on `main` because the KB lives on `main`.
- Python 3.12+. Run pytest via `teg-outreach-agent/.venv/bin/python -m pytest` from inside `teg-outreach-agent/`.
- The knowledge base at `teg-kb-agent/knowledge_base/` is read-only to the code. Task 1 *adds* one file to it (on `main`); the code only *reads* the KB.
- No browser / headless Chromium. WeasyPrint only for PDF.
- No real network, no real LLM, in any test. WeasyPrint runs for real (offline, deterministic).
- Every free-text field in a generated `Proposal` passes `app.agents.guardrails.check_message` **plus** the two new checks (`competitor_mention`, `commitment_language`). On violation: regenerate the whole Proposal once; if still failing, replace the offending field with a persona-specific safe-template string and record `guardrail_flags`.
- All prices quoted "+ GST" and "indicative, confirmed at booking". Only the 4 cleared testimonials, max 2 per proposal, verbatim. Peers only from `sector_wise_participation.md`. Never a visitor ticket price. Never name another event/expo. No signature/commitment language.
- All agent I/O and the `Proposal` schema are typed Pydantic models. LLM access only via `LLMClient`.
- Config via env (`config/settings.py`), defaults from spec §8.
- Local Postgres: `bash scripts/pg.sh start` (or the running scratchpad instance on `127.0.0.1:5433`). `tests/conftest.py` already sets `DATABASE_URL` + provides a `db_schema` fixture.
- Conventional-commit messages. Commit at the end of every task.
- End commit messages with:
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`
  `Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ`

---

## File Structure

```
# Part A — KB (on main)
teg-kb-agent/knowledge_base/event_goals_and_problem.md   # new: goals, problem, mechanism, evidence, pain library
teg-kb-agent/knowledge_base/INDEX.md                     # modify: tree + counts + quick-ref
teg-kb-agent/knowledge_base/event_overview/event_info.md # modify: one pointer line
teg-kb-agent/SKILL.md                                    # modify: routing table row

# Part B — code (on feat/teg-outreach-agent)
teg-outreach-agent/
├── pyproject.toml                          # + weasyprint, jinja2
├── config/settings.py                      # + PROPOSAL_* , EMAIL_* , PROPOSAL_DIR
├── app/
│   ├── domain/schemas.py                   # + Proposal, ProposalPain, ProposalPackage, ProposalCard
│   ├── kb/loader.py                        # + goals_and_pains() accessor + PersonaPains dataclass
│   ├── agents/guardrails.py               # + competitor_mention, commitment_language; + PROPOSAL_SAFE_SECTIONS
│   ├── agents/persuasion.py               # _Analysis + wants_proposal: bool; system prompt tweak
│   ├── agents/proposal.py                 # new: ProposalAgent
│   ├── proposal/
│   │   ├── __init__.py
│   │   ├── render.py                      # new: render_html / render_pdf / render_first_page_png
│   │   ├── email.py                       # new: optional SMTP send
│   │   └── templates/proposal.html.j2     # new: Jinja2 template
│   ├── orchestrator.py                    # + generate_proposal(session_id, email=None) -> ProposalCard
│   ├── store/models.py                    # + ProposalRow; chat_messages.attachment column
│   ├── store/repositories.py              # + ProposalRepo; MessageRepo.append(attachment=...)
│   ├── store/migrations/versions/0002_proposals.py   # new
│   ├── api/proposals.py                   # new: GET .pdf / preview.png ; POST /sessions/{id}/proposal
│   ├── api/chat.py                        # modify: proposal_pending / attachment / proposal_failed frames
│   ├── api/inquiries.py                   # (get_orchestrator already exported — no change)
│   ├── main.py                            # + include proposals.router
│   └── jobs/retention.py                  # + purge proposals rows + files
├── proposals/                             # generated files (gitignored)
│   └── .gitkeep
└── widget/src/
    ├── ui.ts                              # + renderAttachmentCard(), pending skeleton
    └── index.ts                           # + handle attachment / proposal_pending / proposal_failed frames

tests/
├── kb/test_goals_and_pains.py
├── agents/test_proposal_agent.py
├── agents/test_guardrails_proposal.py
├── proposal/test_render.py
├── store/test_proposal_repo.py
├── orchestrator/test_generate_proposal.py
├── api/test_proposals_api.py
├── api/test_chat_proposal.py
├── jobs/test_retention_proposals.py
└── e2e/test_proposal_flow.py
```

---

## Task List (overview)

1. KB file `event_goals_and_problem.md` + KB integration (on `main`)
2. Dependencies + config + `proposals/` dir
3. Domain schemas: `Proposal`, `ProposalPain`, `ProposalPackage`, `ProposalCard`
4. KB loader: `goals_and_pains()` accessor
5. Guardrails: `competitor_mention` + `commitment_language` + `PROPOSAL_SAFE_SECTIONS`
6. `ProposalAgent`
7. Renderer: HTML template + `render_html` / `render_pdf` / `render_first_page_png`
8. Optional email sender
9. Postgres: `ProposalRow` + `chat_messages.attachment` + migration
10. `ProposalRepo` + `MessageRepo` attachment support
11. Orchestrator: `generate_proposal()`
12. Persuasion `_Analysis.wants_proposal` + prompt tweak + orchestrator hook in `run_turn`
13. API: `GET /proposals/{id}.pdf`, `GET /proposals/{id}/preview.png`, `POST /sessions/{id}/proposal`
14. WS chat: `proposal_pending` / `attachment` / `proposal_failed` frames
15. Retention: purge proposals
16. Widget: attachment card + pending skeleton + WS frame handling
17. E2E: chat → ask for proposal → attachment frame → fetch PDF

---

## Task 1: KB file `event_goals_and_problem.md` + integration

**Branch:** `main` (the KB lives on main, not the feature branch). Do `cd /home/com-028/Desktop/TRT/PROJ/TECHEXPO && git checkout main` first. Commit here, then the rest of the plan works on `feat/teg-outreach-agent`.

**Files:**
- Create: `teg-kb-agent/knowledge_base/event_goals_and_problem.md`
- Modify: `teg-kb-agent/knowledge_base/INDEX.md`
- Modify: `teg-kb-agent/knowledge_base/event_overview/event_info.md`
- Modify: `teg-kb-agent/SKILL.md`
- Test: none (content file; Task 4 adds the parser + test that depends on this file's structure)

**Interfaces:**
- Consumes: existing KB files (`event_overview/event_info.md`, `past_editions/past_editions_history.md`, `testimonials/exhibitor_testimonials.md`, `sponsors_partners/sponsors_and_partners.md`, `venture_capital/venture_capital_and_investors.md`, `outreach_config.md`) — cite them.
- Produces: `event_goals_and_problem.md` with these EXACT `## ` / `### ` headings so Task 4's parser can read it:
  - `## 1. The Problem TEG Was Created To Solve`
  - `## 2. TEG's Stated Goals`
  - `## 3. The Mechanism`
  - `## 4. Evidence It Works`
  - `## 5. Persona Pain-Point Library`
  - `### IT/Tech Service` · `### AI/Deep-Tech Startup` · `### Non-Tech Sponsor` · `### Visitor` (under section 5)
  - `## 6. What TEG Is NOT`
  - Under each persona in §5: a markdown table with columns `| Pain | How TEG addresses it |`

- [ ] **Step 1: Write the KB file**

Create `teg-kb-agent/knowledge_base/event_goals_and_problem.md`:

```markdown
# TEG — Goals, the Problem It Solves & Per-Persona Pain Points

> **Purpose:** What Tech Expo Gujarat is *for* — the problem it was created to address, its stated goals, how it delivers them, the evidence it works, and a per-persona pain-point library used to personalize outreach and proposals.
> **Document type:** Synthesis of official framing (techexpogujarat.com/about-us) + existing KB facts. Aspirational/marketing language is quoted as such; all figures cite their source file.
> **Last updated:** September 2026

---

## 1. The Problem TEG Was Created To Solve

TEG's own origin framing: *"A group of CXOs saw what Gujarat was missing — a unified tech stage built by the community, for the community."*

Expanded, grounded in what the KB records about Gujarat's tech ecosystem:

- **Fragmentation.** Gujarat's tech companies, buyers, startups and investors had no single stage to meet — deals and partnerships depended on scattered, one-off introductions.
- **Local tech was under-discovered by local buyers.** Capable Gujarat software/AI firms were serving clients elsewhere (often overseas) while regional SMEs/MSMEs didn't know they existed. (TEG 2024 testimonial, Kanaksinh Rana: *"First time you've shown that there are so many tech companies in Gujarat … delivering advanced tech solutions to international companies. This was not known before to many."* — `testimonials/exhibitor_testimonials.md`)
- **Slow AI/tech adoption by the broader business ecosystem.** Manufacturing, textile, pharma, real estate, agriculture and finance businesses in the state were not systematically exposed to AI/automation/SaaS options.
- **Limited in-state investor access for startups.** Founders had to leave Gujarat to raise; there was no recurring, curated investor-founder forum in the state (the TEG Business Retreat later filled this — `related_events/related_events.md`).
- No place where, in TEG's words, *"innovation meets the sectors that power Gujarat's economy."*

---

## 2. TEG's Stated Goals

From techexpogujarat.com/about-us (quoted):

- **"A movement to position Gujarat at the forefront of India's and the world's technological future."**
- Converge *"the state's brightest techpreneurs, industry pioneers, investors, and innovators"* to *"build, collaborate, and lead."*
- Serve *"diverse industries"* — *"from fintech and healthtech to real estate, manufacturing, and beyond"* — creating *"a single stage where innovation meets the sectors that power Gujarat's economy."*
- **Mission:** *"To empower industries to lead the AI revolution by connecting a collaborative ecosystem of investors and innovators to drive global technology transformation and leadership."*
- **Vision:** *"To position Gujarat as a global innovation hub where industry leaders and entrepreneurs collaborate to shape the future of intelligent enterprises."*
- **Values:** *"Build with integrity, collaborate without boundaries, and innovate with purpose."*

The event is explicitly **not IT-only** — it is designed for the state's broader business ecosystem to discover and adopt AI/tech (`event_overview/event_info.md`).

*(No specific numerical targets for connections, deals, or adoption rates are stated by the organizer.)*

---

## 3. The Mechanism

How TEG turns those goals into outcomes for a participant:

| Mechanism | What it does for a participant |
|---|---|
| **15,000+ cross-industry decision-makers under one roof** (target; `event_overview/event_info.md`) | Reach buyers across manufacturing, BFSI, pharma, retail, real estate, agriculture, education you could not economically reach one-by-one |
| **Pre-scheduled 1:1 curated B2B meetings** (all stall packages; `exhibitors/exhibitors_directory.md`) | Qualified conversations instead of waiting for casual footfall |
| **Live product demonstration space** | Show complex products working, not just talk about them |
| **The TEG app** (networking, in-app messaging with visitors) | Keep the pipeline warm before, during and after the event |
| **Investor / VC track** (TEG Business Retreat, TEG Ignite; `venture_capital/venture_capital_and_investors.md`) | Startup access to a 15+ VC pool (₹1.5 cr raised in one day at the Retreat) |
| **Omnichannel visibility** (venue + digital + print + regional media) | Build a local brand presence, not just a stall |
| **Category-exclusive sponsorship** (`sponsors_partners/sponsors_and_partners.md`) | Own the association with the region's innovation story; keep competitors out of your category |

---

## 4. Evidence It Works

All figures cite their KB source; **no new numbers are invented here.**

- **TEG 2024 (first edition, actuals):** 8,000+ attendees · 125+ exhibitors · 50+ sponsors · 20+ named speakers (`event_overview/event_info.md`, `past_editions/past_editions_history.md`).
- **Growth trajectory:** TEG 2024 (8,000 / 125) → TEG 2026 targets (15,000+ / 250+) — roughly double the scale (`INDEX.md`).
- **TEG Business Retreat 2025:** 150+ CXO attendees · 15+ VCs · **₹1.5 crore raised in one day** (organizer-stated; `related_events/related_events.md`, `venture_capital/venture_capital_and_investors.md`).
- **Attributed testimonials (cleared for external use):** 4 on record — Sonu Sharma, Savjibhai Dholakia, Chitrak Shah, Kanaksinh Rana (`testimonials/exhibitor_testimonials.md`). These speak to *scale and credibility*, not exhibitor ROI.
- **Recurring participants:** several companies exhibited/sponsored across multiple editions (e.g. BizCompass, GTPL-adjacent, ViitorCloud) — see `exhibitors/companies/` and `sponsors_partners/sponsors_and_partners.md`.

> ⚠️ The ₹1.5 cr and portfolio-value figures are organizer claims, not independently verified. Cite as claims.

---

## 5. Persona Pain-Point Library

Base set. Outreach and proposals start here and personalize from the actual conversation. Each row's "how TEG addresses it" is KB-grounded.

### IT/Tech Service

| Pain | How TEG addresses it |
|---|---|
| Revenue concentrated in one geography / client base; no local pipeline | 15,000+ India-market decision-makers + pre-scheduled B2B matchmaking tuned to your target sectors |
| Low brand visibility in the home market | On-ground + website + regional PR/media presence; association with the "AI & future-tech" narrative |
| Leads are casual footfall, low intent | Curated 1:1 meetings with pre-qualified prospects, not walk-by traffic |
| Hard to convey a complex product in a meeting | Dedicated live product-demonstration space |
| Competing on price with no visible differentiation | Positioning alongside keynote names and the event's innovation framing |

### AI/Deep-Tech Startup

| Pain | How TEG addresses it |
|---|---|
| No in-state investor access; have to leave Gujarat to raise | The TEG investor/VC track — a 15+ VC pool (₹1.5 cr raised in one day at the Retreat) |
| Can't afford a flagship-expo booth | Catalyst Zone startup stall at ₹35,000 + GST (indicative, confirmed at booking) |
| No channel to enterprise buyers | Cross-industry decision-makers + B2B matchmaking |
| Unproven; no social proof | Experience Zone AI demos; association with the event's innovation narrative |

### Non-Tech Sponsor

| Pain | How TEG addresses it |
|---|---|
| Brand not linked to the region's innovation / AI story | Category-exclusive sponsorship + explicit "AI revolution" association |
| A competitor could claim the category first | Category exclusivity — once a brand locks a category, direct competitors are excluded |
| Limited access to C-suite decision-makers | Networking alongside keynote speakers and industry leaders |
| Regional media spend is fragmented and hard to measure | Omnichannel package — venue signage + digital + print + regional media in one |

### Visitor

| Pain | How TEG addresses it |
|---|---|
| Don't know which local providers solve my problem | 250+ exhibitors across 18 industries in one place |
| Vendor selection takes months of separate meetings | Compressed into 3 days + the TEG app for follow-up |
| Unsure whether regional tech is enterprise-grade | See it demonstrated live; meet the founders directly |

---

## 6. What TEG Is NOT

- **Not IT-only** — it is built for the whole business ecosystem to adopt tech.
- **Not a job fair.**
- **Not a pure startup-pitch event** — that role is played by the invite-only TEG Business Retreat.
- **Not free** — attendance is ticketed ("There is NO FREE entry").

---

*Source: techexpogujarat.com/about-us (goals, problem framing, quotes); `event_overview/event_info.md`, `past_editions/past_editions_history.md`, `testimonials/exhibitor_testimonials.md`, `sponsors_partners/sponsors_and_partners.md`, `venture_capital/venture_capital_and_investors.md`, `related_events/related_events.md`, `exhibitors/exhibitors_directory.md`, `outreach_config.md` (persona definitions). Organizer-stated figures (₹1.5 cr, VC portfolio value) are unverified claims.*
```

- [ ] **Step 2: Add the SKILL.md routing row**

In `teg-kb-agent/SKILL.md`, Step 1 "Identify the Question Domain" table, add a row after the `sector_wise_participation.md` row:

```
| Event goals, the problem TEG solves, per-persona pain points | `knowledge_base/event_goals_and_problem.md` |
```

- [ ] **Step 3: Add the event_info.md pointer**

In `teg-kb-agent/knowledge_base/event_overview/event_info.md`, after the `## What it is` paragraph, add:

```markdown
> For TEG's stated goals, the problem it was created to solve, the mechanism by which it delivers value, and a per-persona pain-point library, see `event_goals_and_problem.md`.
```

- [ ] **Step 4: Update INDEX.md**

In `teg-kb-agent/knowledge_base/INDEX.md`:
- In the file tree, add under the root-level files list:
  ```
  ├── event_goals_and_problem.md                     ← What TEG is FOR: goals, problem solved, mechanism, evidence, per-persona pain library
  ```
- In the "Total files" line, increment the root-level file count (from 5 to 6) and the total (from 214 to 215), and add `event_goals_and_problem.md` to the bracketed list.
- In "File Loading Guide — By Task Type", add:
  ```
  | **Personalized pitch / proposal / "why should we participate"** | `event_goals_and_problem.md` + `exhibitor_benefits_analysis.md` |
  ```
- Bump the INDEX "Last updated" line to note: "Sept 2026: added `event_goals_and_problem.md` (goals + per-persona pain library)."

- [ ] **Step 5: Verify and commit**

Run:
```bash
cd /home/com-028/Desktop/TRT/PROJ/TECHEXPO
grep -c "^## " teg-kb-agent/knowledge_base/event_goals_and_problem.md   # expect >= 6
grep -c "| Pain | How TEG addresses it |" teg-kb-agent/knowledge_base/event_goals_and_problem.md  # expect 4
git add teg-kb-agent/
git commit -m "kb: add event_goals_and_problem.md (what TEG is for + persona pain library)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

- [ ] **Step 6: Return to the feature branch**

```bash
git checkout feat/teg-outreach-agent
```
The rest of the plan runs here. The code reads the KB at `../teg-kb-agent/knowledge_base/` (KB_PATH), which on the feature branch's checkout will NOT have the new file until `main` is merged or the file is present. **Important:** for Tasks 4+ to pass, either (a) merge `main` into `feat/teg-outreach-agent` now, or (b) cherry-pick the Task 1 commit. Do `git merge main -m "merge: KB goals file"` (clean — no code overlap) so the feature branch's `../teg-kb-agent/knowledge_base/` has `event_goals_and_problem.md`.

---

## Task 2: Dependencies + config + `proposals/` dir

**Files:**
- Modify: `teg-outreach-agent/pyproject.toml`
- Modify: `teg-outreach-agent/config/settings.py`
- Modify: `teg-outreach-agent/.env.example`
- Modify: `teg-outreach-agent/.gitignore`
- Create: `teg-outreach-agent/proposals/.gitkeep`
- Test: `teg-outreach-agent/tests/config/test_proposal_settings.py`

**Interfaces:**
- Consumes: nothing new
- Produces (`config.settings.Settings` new fields):
  - `proposal_model: str = ""` (empty → falls back to `llm_model_main` at use)
  - `proposal_soft_timeout_s: int = 8`
  - `proposal_hard_timeout_s: int = 20`
  - `proposal_dir: str = "./proposals"`
  - `email_enabled: bool = False`
  - `smtp_host: str = ""`, `smtp_port: int = 587`, `smtp_user: str = ""`, `smtp_pass: str = ""`, `smtp_from: str = ""`

- [ ] **Step 1: Add deps and install**

In `pyproject.toml` `dependencies`, add: `"weasyprint>=62"`, `"jinja2>=3.1"`. Then:
```bash
cd teg-outreach-agent && .venv/bin/pip install -e ".[dev]"
```
Verify:
```bash
.venv/bin/python -c "import weasyprint, jinja2; print('weasyprint', weasyprint.__version__)"
```
If `weasyprint` import raises an `OSError` about `libgobject`/`libpango`/`libcairo`, run `ldconfig -p | grep -E 'pango|cairo|gobject|gdk'` — the libs were confirmed present on this machine; if a specific one is missing, note it and STOP (needs a system package). Do not add a browser fallback.

- [ ] **Step 2: Write the failing test**

```python
# tests/config/test_proposal_settings.py
from config.settings import Settings


def test_proposal_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    s = Settings()
    assert s.proposal_model == ""
    assert s.proposal_hard_timeout_s == 20
    assert s.proposal_dir == "./proposals"
    assert s.email_enabled is False
    assert s.smtp_port == 587
```

- [ ] **Step 3: Run to verify fail**

Run: `cd teg-outreach-agent && .venv/bin/python -m pytest tests/config/test_proposal_settings.py -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'proposal_model'`

- [ ] **Step 4: Add the fields to config/settings.py**

Add to the `Settings` class (after the existing fields, before nothing — order doesn't matter):
```python
    # --- proposal / PDF ---
    proposal_model: str = ""  # empty -> use llm_model_main
    proposal_soft_timeout_s: int = 8
    proposal_hard_timeout_s: int = 20
    proposal_dir: str = "./proposals"
    email_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from: str = ""
```

- [ ] **Step 5: Update .env.example**

Append:
```
PROPOSAL_MODEL=
PROPOSAL_SOFT_TIMEOUT_S=8
PROPOSAL_HARD_TIMEOUT_S=20
PROPOSAL_DIR=./proposals
EMAIL_ENABLED=false
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=
SMTP_FROM=
```

- [ ] **Step 6: gitignore + proposals dir**

- Add `proposals/*` to `teg-outreach-agent/.gitignore` with `!proposals/.gitkeep`.
- `mkdir -p teg-outreach-agent/proposals && touch teg-outreach-agent/proposals/.gitkeep`

- [ ] **Step 7: Run tests, commit**

Run: `cd teg-outreach-agent && .venv/bin/python -m pytest tests/config/ -q` — all pass.
Full suite: `.venv/bin/python -m pytest -q` — still green (85 tests: 84 + 1).

```bash
cd /home/com-028/Desktop/TRT/PROJ/TECHEXPO
git add teg-outreach-agent/
git commit -m "feat(proposal): add weasyprint/jinja2 deps and proposal/email config

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 3: Domain schemas

**Files:**
- Modify: `teg-outreach-agent/app/domain/schemas.py`
- Test: `teg-outreach-agent/tests/domain/test_proposal_schemas.py`

**Interfaces:**
- Consumes: nothing
- Produces (append to `app.domain.schemas`, all `pydantic.BaseModel`):
  - `ProposalPain`: `pain: str`, `teg_answer: str`
  - `ProposalPackage`: `name: str`, `price_line: str`, `includes: list[str]`, `payment_plan: str`
  - `Proposal`: `company: str`, `person: str`, `person_role: str | None = None`, `sector: str | None = None`, `persona: Persona`, `generated_on: str`, `session_ref: str`, `version: int`, `what_you_told_us: str`, `pains: list[ProposalPain]`, `lead_generation: str`, `proof: list[str]`, `recommended_package: ProposalPackage`, `peer_companies: list[str]`, `next_steps: list[str]`, `contact: str`
  - `ProposalCard`: `proposal_id: str`, `version: int`, `filename: str`, `bytes: int`, `pdf_url: str`, `png_url: str`

- [ ] **Step 1: Write the failing test**

```python
# tests/domain/test_proposal_schemas.py
import pytest
from pydantic import ValidationError

from app.domain.schemas import Proposal, ProposalCard, ProposalPackage, ProposalPain


def _proposal(**over):
    base = dict(
        company="Acme", person="Rohan B", person_role="CTO", sector="Software Development",
        persona="it_tech_service", generated_on="2026-09-01", session_ref="ab12cd34", version=1,
        what_you_told_us="You build BI tools and want India-market clients.",
        pains=[ProposalPain(pain="US-heavy revenue", teg_answer="15,000+ India buyers")],
        lead_generation="Pre-scheduled B2B meetings with India-market buyers.",
        proof=["TEG 2024: 8,000+ attendees"],
        recommended_package=ProposalPackage(
            name="3m x 3m stall", price_line="₹1,17,000 + GST (indicative, confirmed at booking)",
            includes=["2 exhibitor passes"], payment_plan="25% x 4",
        ),
        peer_companies=["NeuraMonks", "ViitorCloud"], next_steps=["Book at techexpogujarat.com"],
        contact="info@techexpogujarat.com",
    )
    base.update(over)
    return base


def test_proposal_ok():
    p = Proposal(**_proposal())
    assert p.pains[0].teg_answer == "15,000+ India buyers"
    assert p.recommended_package.name == "3m x 3m stall"


def test_proposal_rejects_bad_persona():
    with pytest.raises(ValidationError):
        Proposal(**_proposal(persona="buyer"))


def test_proposal_card_shape():
    c = ProposalCard(
        proposal_id="x", version=2, filename="TEG-2026-Proposal-Acme-v2.pdf",
        bytes=148213, pdf_url="/proposals/x.pdf", png_url="/proposals/x/preview.png",
    )
    assert c.version == 2
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent && .venv/bin/python -m pytest tests/domain/test_proposal_schemas.py -v`
Expected: FAIL — `ImportError: cannot import name 'Proposal'`

- [ ] **Step 3: Append to app/domain/schemas.py**

```python
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
```
(`Field` and `Persona` are already imported at the top of the file.)

- [ ] **Step 4: Run tests, commit**

Run: `.venv/bin/python -m pytest tests/domain/ -q` — all pass. Full suite green.
```bash
cd /home/com-028/Desktop/TRT/PROJ/TECHEXPO && git add teg-outreach-agent/
git commit -m "feat(proposal): Proposal / ProposalPain / ProposalPackage / ProposalCard schemas

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 4: KB loader — `goals_and_pains()` accessor

**Files:**
- Modify: `teg-outreach-agent/app/kb/loader.py`
- Test: `teg-outreach-agent/tests/kb/test_goals_and_pains.py`

**Interfaces:**
- Consumes: `event_goals_and_problem.md` (present via the Task 1 merge into the feature branch)
- Produces (`app.kb.loader`):
  - `@dataclass PersonaPains: persona_key: str`, `pains: list[tuple[str, str]]` (each `(pain, how_teg_addresses_it)`)
  - `@dataclass GoalsAndPains: problem: str` (section 1 text), `goals: str` (section 2 text), `mechanism: str` (section 3 text), `evidence: str` (section 4 text), `what_teg_is_not: str` (section 6 text), `pains_by_persona: dict[str, PersonaPains]` (keys: `it_tech_service`, `ai_startup`, `non_tech_sponsor`, `visitor`)
  - `KnowledgeBase.goals_and_pains(self) -> GoalsAndPains`
  - mapping from the file's `### ` persona headings to the schema persona keys:
    `"IT/Tech Service" -> "it_tech_service"`, `"AI/Deep-Tech Startup" -> "ai_startup"`, `"Non-Tech Sponsor" -> "non_tech_sponsor"`, `"Visitor" -> "visitor"`

**Implementer note:** the file has `## 1. …` through `## 6. …` headings and, under `## 5. Persona Pain-Point Library`, four `### <persona>` subsections each containing a markdown table with a header row `| Pain | How TEG addresses it |`. Parse the table rows (skip the `|---|---|` separator).

- [ ] **Step 1: Write the failing test**

```python
# tests/kb/test_goals_and_pains.py
from app.kb.loader import GoalsAndPains, KnowledgeBase


def test_goals_and_pains_structure():
    gp = KnowledgeBase().goals_and_pains()
    assert isinstance(gp, GoalsAndPains)
    assert "unified tech stage" in gp.problem.lower() or "fragment" in gp.problem.lower()
    assert set(gp.pains_by_persona) == {
        "it_tech_service", "ai_startup", "non_tech_sponsor", "visitor"
    }


def test_it_service_pains_include_geography():
    gp = KnowledgeBase().goals_and_pains()
    it = gp.pains_by_persona["it_tech_service"]
    assert len(it.pains) >= 3
    joined = " ".join(p + " " + a for p, a in it.pains).lower()
    assert "geograph" in joined or "one geography" in joined or "pipeline" in joined


def test_startup_pains_include_investor_access():
    gp = KnowledgeBase().goals_and_pains()
    joined = " ".join(
        p + " " + a for p, a in gp.pains_by_persona["ai_startup"].pains
    ).lower()
    assert "investor" in joined or "vc" in joined


def test_each_pain_is_a_pair():
    gp = KnowledgeBase().goals_and_pains()
    for pp in gp.pains_by_persona.values():
        for row in pp.pains:
            assert isinstance(row, tuple) and len(row) == 2 and all(row)
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent && .venv/bin/python -m pytest tests/kb/test_goals_and_pains.py -v`
Expected: FAIL — `ImportError: cannot import name 'GoalsAndPains'` (or `AttributeError` on `goals_and_pains`)

- [ ] **Step 3: Add to app/kb/loader.py**

Add near the other dataclasses:
```python
@dataclass
class PersonaPains:
    persona_key: str
    pains: list[tuple[str, str]]


@dataclass
class GoalsAndPains:
    problem: str
    goals: str
    mechanism: str
    evidence: str
    what_teg_is_not: str
    pains_by_persona: dict[str, "PersonaPains"]
```

Add a module-level constant and a helper:
```python
_PERSONA_HEADING_MAP = {
    "IT/Tech Service": "it_tech_service",
    "AI/Deep-Tech Startup": "ai_startup",
    "Non-Tech Sponsor": "non_tech_sponsor",
    "Visitor": "visitor",
}


def _parse_pain_table(block: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---") or set(line) <= set("|- "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 2:
            continue
        if cells[0].lower() in ("pain",) or cells[1].lower().startswith("how teg"):
            continue
        if cells[0] and cells[1]:
            rows.append((cells[0], cells[1]))
    return rows
```

Add the method to `KnowledgeBase`:
```python
    def goals_and_pains(self) -> GoalsAndPains:
        f = self.root / "event_goals_and_problem.md"
        md = f.read_text(encoding="utf-8")

        def sect(n: int, title_fragment: str) -> str:
            marker = f"## {n}. "
            if marker not in md:
                return ""
            seg = md.split(marker, 1)[1]
            return seg.split("\n## ", 1)[0].split("\n#", 1)[0].strip()

        problem = sect(1, "Problem")
        goals = sect(2, "Goals")
        mechanism = sect(3, "Mechanism")
        evidence = sect(4, "Evidence")
        not_ = sect(6, "NOT")

        pains_section = sect(5, "Pain-Point Library")
        pains_by_persona: dict[str, PersonaPains] = {}
        for heading, key in _PERSONA_HEADING_MAP.items():
            token = f"### {heading}"
            if token not in pains_section:
                continue
            block = pains_section.split(token, 1)[1].split("\n### ", 1)[0]
            pains_by_persona[key] = PersonaPains(persona_key=key, pains=_parse_pain_table(block))

        return GoalsAndPains(
            problem=problem, goals=goals, mechanism=mechanism, evidence=evidence,
            what_teg_is_not=not_, pains_by_persona=pains_by_persona,
        )
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/kb/ -q`
Expected: PASS. If a test fails on the pain-table parse, run `sed -n '/## 5\./,/## 6\./p' ../teg-kb-agent/knowledge_base/event_goals_and_problem.md` and adjust `_parse_pain_table` to the real formatting — keep the 4 test assertions.

- [ ] **Step 5: Commit**

```bash
cd /home/com-028/Desktop/TRT/PROJ/TECHEXPO && git add teg-outreach-agent/
git commit -m "feat(proposal): KB loader goals_and_pains() accessor

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 5: Guardrails — competitor + commitment checks + proposal safe sections

**Files:**
- Modify: `teg-outreach-agent/app/agents/guardrails.py`
- Test: `teg-outreach-agent/tests/agents/test_guardrails_proposal.py`

**Interfaces:**
- Consumes: existing `GuardrailViolation`, `check_message`, `_kb_company_names`
- Produces (added to `app.agents.guardrails`):
  - two new violation codes emitted by `check_message` (via new internal checks): `competitor_mention`, `commitment_language`
  - `PROPOSAL_SAFE_SECTIONS: dict[str, dict[Persona, str]]` — safe fallback text per proposal field per persona. Fields: `what_you_told_us`, `lead_generation`, `pain_answer`, `proof_bullet`, `next_step`. Each maps to a `dict[Persona, str]` (4 keys). Values are generic, fully KB-sourced strings.
- `check_message` gains an optional kwarg `context: Literal["chat", "proposal"] = "chat"`. When `context == "proposal"`, the competitor + commitment checks run in addition to the existing ones. (They also run for chat — harmless — but making it explicit documents intent. Simplest: always run them.)

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/test_guardrails_proposal.py
from app.agents.guardrails import PROPOSAL_SAFE_SECTIONS, check_message


def test_flags_competitor_mention():
    for txt in (
        "Unlike EFY Expo, TEG focuses on AI.",
        "TEG is bigger than Tech Vapi 2026.",
        "Compared to other expos in Gujarat, TEG has more footfall.",
    ):
        v = check_message(txt, allowed_peers=[], persona="it_tech_service")
        assert any(x.code == "competitor_mention" for x in v), txt


def test_does_not_flag_generic_industry_language():
    v = check_message(
        "TEG brings together technology providers from across the region.",
        allowed_peers=[], persona="it_tech_service",
    )
    assert not any(x.code == "competitor_mention" for x in v)


def test_flags_commitment_language():
    for txt in (
        "By signing below, you agree to the stall terms.",
        "This proposal constitutes a binding offer.",
        "Authorised signatory: ____________",
    ):
        v = check_message(txt, allowed_peers=[], persona="non_tech_sponsor")
        assert any(x.code == "commitment_language" for x in v), txt


def test_does_not_flag_soft_cta():
    v = check_message(
        "When you're ready, you can book your stall at techexpogujarat.com.",
        allowed_peers=[], persona="it_tech_service",
    )
    assert not any(x.code == "commitment_language" for x in v)


def test_proposal_safe_sections_cover_all_fields_and_personas():
    for field in ("what_you_told_us", "lead_generation", "pain_answer", "proof_bullet", "next_step"):
        assert field in PROPOSAL_SAFE_SECTIONS
        for p in ("it_tech_service", "ai_startup", "non_tech_sponsor", "visitor"):
            assert PROPOSAL_SAFE_SECTIONS[field][p].strip()
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent && .venv/bin/python -m pytest tests/agents/test_guardrails_proposal.py -v`
Expected: FAIL — `ImportError: cannot import name 'PROPOSAL_SAFE_SECTIONS'` / new codes not produced

- [ ] **Step 3: Add to app/agents/guardrails.py**

Add regexes near the other module constants:
```python
# Names of other Gujarat / India tech expos and generic competitor phrasing.
_COMPETITOR = re.compile(
    r"\b(EFY\s*Expo|Tech\s*Vapi|Vibrant\s*Gujarat\s*(?:tech|expo)?|"
    r"other\s+(?:expos?|events?|shows?)|compared\s+to\s+other|unlike\s+(?:other|the\s+other))\b",
    re.I,
)
_COMMITMENT = re.compile(
    r"\b(by\s+signing|you\s+(?:hereby\s+)?agree\s+to|this\s+(?:proposal|document)\s+constitutes|"
    r"binding\s+(?:offer|agreement|quote)|authoris?ed\s+signator|signature\s*[:_]|"
    r"terms\s+and\s+conditions\s+apply\s+as\s+signed)\b",
    re.I,
)
```

In `check_message`, after the existing checks (before `return out`), add:
```python
    if _COMPETITOR.search(text):
        out.append(GuardrailViolation("competitor_mention", _COMPETITOR.search(text).group(0)))
    if _COMMITMENT.search(text):
        out.append(GuardrailViolation("commitment_language", _COMMITMENT.search(text).group(0)))
```

Add the safe-sections table (values are literal strings; keep them KB-true):
```python
PROPOSAL_SAFE_SECTIONS: dict[str, dict[Persona, str]] = {
    "what_you_told_us": {
        "it_tech_service": "You run a technology services company and are exploring how Tech Expo Gujarat 2026 could support your business development.",
        "ai_startup": "You run an early-stage AI/technology company and are exploring an affordable way to showcase it and meet investors and buyers at Tech Expo Gujarat 2026.",
        "non_tech_sponsor": "Your company is exploring a sponsorship association with Tech Expo Gujarat 2026 to build brand presence around the region's innovation story.",
        "visitor": "You are considering attending Tech Expo Gujarat 2026 to discover technology solutions relevant to your work.",
    },
    "lead_generation": {
        "it_tech_service": "Tech Expo Gujarat runs pre-scheduled 1:1 B2B meetings and a networking app, so you engage qualified decision-makers rather than waiting for casual footfall, with a live demo space to show your product working.",
        "ai_startup": "The event's pre-scheduled B2B meetings, Experience Zone demos and investor track put you in front of enterprise buyers and a 15+ VC pool in a few days.",
        "non_tech_sponsor": "A category-exclusive sponsorship gives you omnichannel visibility (venue, digital, print, regional media) and C-suite networking alongside keynote speakers.",
        "visitor": "In three days you can meet 250+ exhibitors across 18 industries and follow up through the TEG app, compressing months of vendor evaluation.",
    },
    "pain_answer": {
        "it_tech_service": "Tech Expo Gujarat connects you with 15,000+ cross-industry decision-makers and pre-scheduled meetings tuned to your target sectors.",
        "ai_startup": "The Catalyst Zone (₹35,000 + GST, indicative and confirmed at booking) plus the investor track give a small team an affordable route to buyers and VCs.",
        "non_tech_sponsor": "Category exclusivity means once you lock a category, direct competitors are excluded, and your brand is tied to the region's innovation narrative.",
        "visitor": "All the relevant providers are in one place, demonstrating live, so you can shortlist and meet founders directly.",
    },
    "proof_bullet": {
        "it_tech_service": "TEG 2024 drew 8,000+ attendees and 125+ exhibitors; TEG 2026 targets 15,000+ and 250+.",
        "ai_startup": "The TEG Business Retreat 2025 helped facilitate ₹1.5 crore in funding raised in one day (organizer-stated).",
        "non_tech_sponsor": "TEG 2024 had 50+ sponsors and 8,000+ attendees; it is Gujarat's largest tech expo.",
        "visitor": "TEG 2024 brought 8,000+ attendees and 125+ exhibitors together over two days.",
    },
    "next_step": {
        "it_tech_service": "Review the stall options and book at techexpogujarat.com/become-an-exhibitor, or reply here to have the team walk you through it.",
        "ai_startup": "Ask about the Catalyst Zone or the startup pitch track at techexpogujarat.com, or reply here.",
        "non_tech_sponsor": "Request a sponsorship call via techexpogujarat.com/become-a-sponsor.",
        "visitor": "Register at events.techexpogujarat.com when you're ready.",
    },
}
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/agents/test_guardrails.py tests/agents/test_guardrails_proposal.py -q`
Expected: ALL pass — including the existing `test_guardrails.py` (the two new checks must not fire on its inputs; if `test_allows_stall_price_with_gst` or similar now fails, tighten the new regexes — they should only match explicit competitor/commitment phrasing).

- [ ] **Step 5: Commit**

```bash
cd /home/com-028/Desktop/TRT/PROJ/TECHEXPO && git add teg-outreach-agent/
git commit -m "feat(proposal): competitor + commitment guardrails, proposal safe-section fallbacks

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 6: `ProposalAgent`

**Files:**
- Create: `teg-outreach-agent/app/agents/proposal.py`
- Test: `teg-outreach-agent/tests/agents/test_proposal_agent.py`

**Interfaces:**
- Consumes: `app.agents.base.Agent`, `app.domain.schemas` (`IntakeResult`, `ResearchDossier`, `Persona`, `Proposal`, `ProposalPain`, `ProposalPackage`), `app.kb.loader.get_kb`, `app.agents.guardrails` (`check_message`, `PROPOSAL_SAFE_SECTIONS`), `app.agents.persuasion` (`map_persona`? NO — persona is passed in), `config.settings.get_settings`, `config.outreach_rules.load_rules`
- Produces (`app.agents.proposal`):
  - `_PRICING_BY_PERSONA: dict[Persona, ProposalPackage]` — literal fallback packages built from `pricing_and_packages.md` facts (3×3 for it_tech_service, Catalyst Zone for ai_startup, AI Partner tier for non_tech_sponsor, a visitor "why attend" pseudo-package for visitor).
  - `ProposalAgent(Agent)`:
    - `__init__(self, llm, *, model: str | None = None)` — `self._model = model or get_settings().proposal_model or get_settings().llm_model_main`
    - `async def build(self, *, intake: IntakeResult, dossier: ResearchDossier, persona: Persona, transcript: list[dict], learned_facts: dict, session_ref: str, version: int) -> tuple[Proposal, list[str]]` — returns the guarded `Proposal` and a list of `guardrail_flags` (empty if clean).
      1. Load context: `kb.goals_and_pains()`, `kb.peers_in_sector(dossier.sector, 5)` minus own company, `kb.cleared_testimonials()`, the persona pain-library base for this persona.
      2. One `llm.generate_structured(Proposal, model=self._model)` call. System prompt: role, the guardrail rules verbatim (no fabrication / 4 cleared testimonials max 2 / peers only from the given list / no visitor price / "+ GST, indicative" / no competitor names / no signature or commitment language / it's an information document not a contract). User content: the persona, the dossier, the full transcript, `learned_facts`, the goals+mechanism+evidence text, the persona pain-library rows (as a starting point — "personalize these from the conversation, keep 2-4"), the cleared testimonials (verbatim, "you may quote at most 2"), the peer list, the fallback package for this persona ("use this unless the conversation clearly points to a different size/tier"), and `generated_on` / `session_ref` / `version` to echo back.
      3. Guardrail pass: for each free-text field (`what_you_told_us`, `lead_generation`, each `pains[i].pain`, each `pains[i].teg_answer`, each `proof[i]`, each `next_steps[i]`, `recommended_package.price_line`), run `check_message(text, allowed_peers=peer_list, persona=persona)`. Collect all violations.
      4. If any violations: regenerate the whole Proposal once with the violation codes named in the system prompt. Re-check.
      5. If still violations: replace each offending field with the matching `PROPOSAL_SAFE_SECTIONS[<field key>][persona]` (map: `what_you_told_us`→`what_you_told_us`, `lead_generation`→`lead_generation`, any `pain`/`teg_answer`→`pain_answer`, any `proof`→`proof_bullet`, any `next_step`→`next_step`, `price_line`→keep the persona fallback package's `price_line`). Return `guardrail_flags` = sorted unique violation codes.
      6. Force `generated_on`, `session_ref`, `version`, `company`, `person`, `persona` to the passed values (don't trust the LLM to echo them).

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/test_proposal_agent.py
from app.agents.proposal import ProposalAgent, _PRICING_BY_PERSONA
from app.domain.schemas import IntakeResult, Proposal, ProposalPackage, ProposalPain, ResearchDossier
from app.llm.fake import FakeLLMClient


def _intake(company="DataZen Analytics"):
    return IntakeResult(
        person_name="Rohan B", company_name_raw=company, company_name_canonical=company,
        provided_fields=[], intent_hint="exhibitor", consent_status="unknown",
    )


def _dossier(sector="Software Development"):
    return ResearchDossier(
        sector=sector, relationship="cold",
        company_profile={"company_size": "30", "hq": "Ahmedabad"},
        person_profile={"designation": "CTO"},
        peer_companies=["NeuraMonks", "ViitorCloud", "Perigeon"],
    )


def _good_proposal(**over):
    base = Proposal(
        company="DataZen Analytics", person="Rohan B", person_role="CTO",
        sector="Software Development", persona="it_tech_service",
        generated_on="X", session_ref="X", version=0,
        what_you_told_us="You build BI dashboards for SMEs and want India-market clients.",
        pains=[ProposalPain(pain="Revenue concentrated in US clients",
                            teg_answer="15,000+ India-market decision-makers plus pre-scheduled B2B meetings")],
        lead_generation="Pre-scheduled B2B meetings with India-market buyers across manufacturing and BFSI, plus a live demo space.",
        proof=["TEG 2024 drew 8,000+ attendees and 125+ exhibitors."],
        recommended_package=ProposalPackage(
            name="3m x 6m stall", price_line="₹2,34,000 + GST (indicative, confirmed at booking)",
            includes=["4 exhibitor passes", "10 visitor passes"], payment_plan="25% x 4 instalments",
        ),
        peer_companies=["NeuraMonks", "ViitorCloud"],
        next_steps=["Book at techexpogujarat.com/become-an-exhibitor"],
        contact="info@techexpogujarat.com",
    )
    return base.model_copy(update=over)


async def test_build_returns_clean_proposal():
    llm = FakeLLMClient(structured=[_good_proposal()])
    p, flags = await ProposalAgent(llm).build(
        intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[{"role": "prospect", "content": "we want India-market clients"}],
        learned_facts={"target_market": "India"}, session_ref="ab12cd34", version=2,
    )
    assert flags == []
    assert p.version == 2 and p.session_ref == "ab12cd34"
    assert p.company == "DataZen Analytics" and p.persona == "it_tech_service"
    assert "DataZen Analytics" not in p.peer_companies


async def test_build_falls_back_on_repeated_violation():
    bad = _good_proposal(
        proof=["As Jane Doe said, \"This event completely transformed our pipeline and closed ten deals in a week.\""],
        lead_generation="Unlike other expos in Gujarat, TEG has the best footfall.",
    )
    llm = FakeLLMClient(structured=[bad, bad])
    p, flags = await ProposalAgent(llm).build(
        intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[], learned_facts={}, session_ref="x", version=1,
    )
    assert "uncleared_testimonial" in flags
    assert "competitor_mention" in flags
    # offending fields replaced with safe text
    assert "Jane Doe" not in " ".join(p.proof)
    assert "other expos" not in p.lead_generation.lower()


async def test_pricing_fallback_table_has_all_personas():
    for k in ("it_tech_service", "ai_startup", "non_tech_sponsor", "visitor"):
        pkg = _PRICING_BY_PERSONA[k]
        assert "+ GST" in pkg.price_line or k == "visitor"
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent && .venv/bin/python -m pytest tests/agents/test_proposal_agent.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write app/agents/proposal.py**

```python
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
        includes=["2 exhibitor passes", "5 visitor passes", "modular stall + fascia",
                  "pre-scheduled 1:1 B2B meetings", "TEG Community Network Portal access"],
        payment_plan="4 instalments of 25% (9 Apr / 30 Jun / 31 Jul / 31 Aug 2026)",
    ),
    "ai_startup": ProposalPackage(
        name="Catalyst Zone (2m x 2m startup stall)",
        price_line="₹35,000 + GST (indicative, confirmed at booking)",
        includes=["2 exhibitor passes", "modular stall + fascia",
                  "pre-scheduled 1:1 B2B meetings", "TEG Community Network Portal access"],
        payment_plan="4 instalments of 25% (9 Apr / 30 Jun / 31 Jul / 31 Aug 2026)",
    ),
    "non_tech_sponsor": ProposalPackage(
        name="Official Category Partner (e.g. AI / Real Estate / Banking Partner)",
        price_line="from ₹6,00,000 + GST for a category partnership up to ₹35,00,000 + GST for Title Sponsor (all indicative, confirmed at booking)",
        includes=["category exclusivity", "3m x 3m stall (tier-dependent)", "15 visitor + 2-3 VIP passes",
                  "website logo", "stage mention", "on-stage trophy"],
        payment_plan="4 instalments of 25% (9 Apr / 30 Jun / 31 Jul / 31 Aug 2026)",
    ),
    "visitor": ProposalPackage(
        name="Visitor pass",
        price_line="ticketed entry (no free entry); current pricing on the official ticketing portal",
        includes=["access to 250+ exhibitors across 18 industries", "keynote sessions",
                  "the TEG networking app"],
        payment_plan="—",
    ),
}

_FIELD_TO_SAFE_KEY = {
    "what_you_told_us": "what_you_told_us",
    "lead_generation": "lead_generation",
    "pain": "pain_answer",
    "teg_answer": "pain_answer",
    "proof": "proof_bullet",
    "next_step": "next_step",
}


class ProposalAgent(Agent):
    def __init__(self, llm, *, model: str | None = None) -> None:
        super().__init__(llm)
        s = get_settings()
        self._model = model or s.proposal_model or s.llm_model_main

    async def build(
        self, *, intake: IntakeResult, dossier: ResearchDossier, persona: Persona,
        transcript: list[dict], learned_facts: dict, session_ref: str, version: int,
    ) -> tuple[Proposal, list[str]]:
        kb = get_kb()
        gp = kb.goals_and_pains()
        own = intake.company_name_canonical.lower()
        peers = [p for p in (dossier.peer_companies or kb.peers_in_sector(dossier.sector or "", 6))
                 if p.lower() != own][:5]
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
            bad_labels = {label for label, _ in violations}
            if "what_you_told_us" in bad_labels:
                proposal.what_you_told_us = PROPOSAL_SAFE_SECTIONS["what_you_told_us"][persona]
            if "lead_generation" in bad_labels:
                proposal.lead_generation = PROPOSAL_SAFE_SECTIONS["lead_generation"][persona]
            if "price_line" in bad_labels:
                proposal.recommended_package = fallback_pkg
            for i in range(len(proposal.pains)):
                if f"pain::{i}" in bad_labels or f"teg_answer::{i}" in bad_labels:
                    proposal.pains[i] = ProposalPain(
                        pain=(base_pains.pains[i % len(base_pains.pains)][0]
                              if base_pains and base_pains.pains else "Reaching the right buyers"),
                        teg_answer=PROPOSAL_SAFE_SECTIONS["pain_answer"][persona],
                    )
            proposal.proof = [
                (pr if f"proof::{i}" not in bad_labels else PROPOSAL_SAFE_SECTIONS["proof_bullet"][persona])
                for i, pr in enumerate(proposal.proof)
            ] or [PROPOSAL_SAFE_SECTIONS["proof_bullet"][persona]]
            proposal.next_steps = [
                (ns if f"next_step::{i}" not in bad_labels else PROPOSAL_SAFE_SECTIONS["next_step"][persona])
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
```

**Note on `generated_on`:** the agent leaves `__DATE__` as a placeholder — Task 11 (`orchestrator.generate_proposal`) sets the real ISO date before rendering. Alternatively set it here with `datetime.date.today().isoformat()`; either is fine, keep it consistent with the test (the test passes `version` and `session_ref` and asserts those, not the date).

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/agents/test_proposal_agent.py -q`
Expected: PASS (3). If the fallback test fails, check the `bad_labels` matching — the guardrail on `proof::0` must map to the `proof_bullet` safe key.

- [ ] **Step 5: Commit**

```bash
cd /home/com-028/Desktop/TRT/PROJ/TECHEXPO && git add teg-outreach-agent/
git commit -m "feat(proposal): ProposalAgent — builds a guarded personalized Proposal

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 7: Renderer — HTML template + PDF + first-page PNG

**Files:**
- Create: `teg-outreach-agent/app/proposal/__init__.py` (empty)
- Create: `teg-outreach-agent/app/proposal/render.py`
- Create: `teg-outreach-agent/app/proposal/templates/proposal.html.j2`
- Test: `teg-outreach-agent/tests/proposal/test_render.py`

**Interfaces:**
- Consumes: `app.domain.schemas.Proposal`, `weasyprint`, `jinja2`, `PIL` (Pillow)
- Produces (`app.proposal.render`):
  - `render_html(proposal: Proposal) -> str`
  - `render_pdf(html: str) -> bytes` — `%PDF`-prefixed bytes
  - `render_first_page_png(html: str, width: int = 600) -> bytes` — PNG bytes of the first page only, ~`width` px wide
  - `TEMPLATE_DIR: Path` (for tests)

- [ ] **Step 1: Write the failing test**

```python
# tests/proposal/test_render.py
from app.domain.schemas import Proposal, ProposalPackage, ProposalPain
from app.proposal.render import render_first_page_png, render_html, render_pdf


def _proposal():
    return Proposal(
        company="DataZen Analytics", person="Rohan B", person_role="CTO",
        sector="Software Development", persona="it_tech_service",
        generated_on="2026-09-01", session_ref="ab12cd34", version=2,
        what_you_told_us="You build BI dashboards and want India-market clients.",
        pains=[ProposalPain(pain="US-heavy revenue", teg_answer="15,000+ India buyers + B2B meetings")],
        lead_generation="Pre-scheduled B2B meetings with India-market buyers, plus a live demo space.",
        proof=["TEG 2024: 8,000+ attendees, 125+ exhibitors."],
        recommended_package=ProposalPackage(
            name="3m x 6m stall", price_line="₹2,34,000 + GST (indicative, confirmed at booking)",
            includes=["4 exhibitor passes", "10 visitor passes"], payment_plan="25% x 4",
        ),
        peer_companies=["NeuraMonks", "ViitorCloud", "Perigeon"],
        next_steps=["Book at techexpogujarat.com/become-an-exhibitor"],
        contact="info@techexpogujarat.com",
    )


def test_render_html_contains_key_strings():
    html = render_html(_proposal())
    assert "DataZen Analytics" in html
    assert "Rohan B" in html
    assert "₹2,34,000 + GST" in html
    assert "NeuraMonks" in html
    assert "v2" in html or "Version 2" in html
    assert "2026-09-01" in html
    assert "ab12cd34" in html
    assert "not a contract" in html.lower() or "not a binding" in html.lower()


def test_render_pdf_bytes():
    pdf = render_pdf(render_html(_proposal()))
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 2000


def test_render_first_page_png_bytes():
    png = render_first_page_png(render_html(_proposal()), width=600)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 1000
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent && .venv/bin/python -m pytest tests/proposal/test_render.py -v`
Expected: FAIL — module not found. (create `tests/proposal/__init__.py`)

- [ ] **Step 3: Write app/proposal/templates/proposal.html.j2**

```html
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page { size: A4; margin: 18mm 16mm; }
  * { box-sizing: border-box; }
  body { font-family: "DejaVu Sans", "Helvetica", "Arial", sans-serif; color: #1f2430; font-size: 10.5pt; line-height: 1.45; }
  .cover { background: #1b2a5b; color: #fff; padding: 18px 20px; border-radius: 6px; }
  .cover h1 { margin: 0 0 4px; font-size: 18pt; }
  .cover .sub { opacity: .85; font-size: 10pt; }
  .accent { height: 4px; background: linear-gradient(90deg,#e4572e,#f3a712,#2e9e4f,#1b6ca8); margin: 10px 0 16px; border-radius: 2px; }
  h2 { font-size: 12pt; color: #1b2a5b; border-bottom: 1px solid #d7dbe6; padding-bottom: 3px; margin: 16px 0 8px; }
  table { width: 100%; border-collapse: collapse; margin: 6px 0; }
  th, td { text-align: left; vertical-align: top; padding: 5px 8px; border: 1px solid #d7dbe6; font-size: 9.5pt; }
  th { background: #eef1f7; }
  ul { margin: 4px 0 4px 18px; padding: 0; }
  .pkg { background: #f6f8fc; border: 1px solid #d7dbe6; border-radius: 6px; padding: 10px 12px; }
  .pkg .price { font-weight: bold; color: #1b2a5b; }
  .peers { font-size: 9.5pt; }
  .footer { margin-top: 18px; padding-top: 8px; border-top: 1px solid #d7dbe6; font-size: 8pt; color: #6a7180; }
</style>
</head>
<body>
  <div class="cover">
    <h1>Tech Expo Gujarat 2026 — Proposal for {{ p.company }}</h1>
    <div class="sub">
      Prepared for {{ p.person }}{% if p.person_role %}, {{ p.person_role }}{% endif %}
      &nbsp;·&nbsp; {{ p.sector or "—" }}
      &nbsp;·&nbsp; {{ p.generated_on }} &nbsp;·&nbsp; Version {{ p.version }} &nbsp;·&nbsp; Ref {{ p.session_ref }}
    </div>
  </div>
  <div class="accent"></div>

  <h2>What you told us</h2>
  <p>{{ p.what_you_told_us }}</p>

  <h2>Where TEG can help — your priorities</h2>
  <table>
    <tr><th>Your challenge</th><th>How Tech Expo Gujarat 2026 addresses it</th></tr>
    {% for pain in p.pains %}
    <tr><td>{{ pain.pain }}</td><td>{{ pain.teg_answer }}</td></tr>
    {% endfor %}
  </table>

  <h2>How you'd generate leads at TEG</h2>
  <p>{{ p.lead_generation }}</p>

  <h2>The track record</h2>
  <ul>{% for pr in p.proof %}<li>{{ pr }}</li>{% endfor %}</ul>

  <h2>Recommended for {{ p.company }}</h2>
  <div class="pkg">
    <div class="price">{{ p.recommended_package.name }} — {{ p.recommended_package.price_line }}</div>
    <ul>{% for inc in p.recommended_package.includes %}<li>{{ inc }}</li>{% endfor %}</ul>
    <div>Payment: {{ p.recommended_package.payment_plan }}</div>
  </div>

  {% if p.peer_companies %}
  <h2>Companies like yours taking part</h2>
  <p class="peers">{{ p.peer_companies | join(" · ") }}</p>
  {% endif %}

  <h2>Next steps</h2>
  <ul>{% for ns in p.next_steps %}<li>{{ ns }}</li>{% endfor %}</ul>
  <p><strong>Contact:</strong> {{ p.contact }}</p>

  <div class="footer">
    Generated {{ p.generated_on }} · Version {{ p.version }} · Session ref {{ p.session_ref }}.
    All figures are indicative and subject to confirmation at booking. This document is for information
    only — it is not a contract, a binding quote, or an offer requiring signature.
  </div>
</body>
</html>
```

- [ ] **Step 4: Write app/proposal/render.py**

```python
from __future__ import annotations

import io
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image
from weasyprint import HTML

from app.domain.schemas import Proposal

TEMPLATE_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_html(proposal: Proposal) -> str:
    return _env.get_template("proposal.html.j2").render(p=proposal)


def render_pdf(html: str) -> bytes:
    return HTML(string=html).write_pdf()


def render_first_page_png(html: str, width: int = 600) -> bytes:
    # WeasyPrint stacks all pages vertically into one PNG; crop to the first page.
    doc = HTML(string=html).render()
    page = doc.pages[0]
    # write just the first page to PNG at a modest resolution
    png_bytes, png_w, png_h = doc.copy([page]).write_png(resolution=96)
    img = Image.open(io.BytesIO(png_bytes))
    if img.width != width:
        ratio = width / img.width
        img = img.resize((width, max(1, int(img.height * ratio))))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()
```

**Note:** the exact WeasyPrint API for a per-page PNG can vary by version. If `doc.copy([page]).write_png(...)` doesn't exist on the installed version, the reliable alternative: `HTML(string=html).write_png(resolution=96)` returns `(bytes, w, h)` for ALL pages stacked; open with Pillow and crop `img.crop((0, 0, img.width, first_page_height_px))`. Estimate `first_page_height_px` as `int(img.width * (297/210))` (A4 aspect). Implementer: pick whichever the installed WeasyPrint supports; the test only checks it's a valid non-trivial PNG.

- [ ] **Step 5: Run tests**

Run: `cd teg-outreach-agent && mkdir -p tests/proposal && touch tests/proposal/__init__.py app/proposal/__init__.py && .venv/bin/python -m pytest tests/proposal/ -q`
Expected: PASS (3). If `render_first_page_png` fails on the WeasyPrint API, apply the fallback from the Step 4 note.

- [ ] **Step 6: Commit**

```bash
cd /home/com-028/Desktop/TRT/PROJ/TECHEXPO && git add teg-outreach-agent/
git commit -m "feat(proposal): Jinja2 template + WeasyPrint HTML/PDF/PNG renderer

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 8: Optional email sender

**Files:**
- Create: `teg-outreach-agent/app/proposal/email.py`
- Test: `teg-outreach-agent/tests/proposal/test_email.py`

**Interfaces:**
- Consumes: `config.settings.get_settings`, stdlib `smtplib`, `email.message`
- Produces (`app.proposal.email`):
  - `async def send_proposal_email(*, to: str, pdf_bytes: bytes, filename: str, company: str) -> bool` — returns `True` on send, `False` if `email_enabled` is false or SMTP fails (logged, non-fatal). Runs the blocking `smtplib` call in a thread (`asyncio.to_thread`).

- [ ] **Step 1: Write the failing test**

```python
# tests/proposal/test_email.py
from unittest.mock import MagicMock, patch

import pytest

from app.proposal.email import send_proposal_email


async def test_returns_false_when_disabled(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("EMAIL_ENABLED", "false")
    from config.settings import get_settings
    get_settings.cache_clear()
    ok = await send_proposal_email(to="x@y.com", pdf_bytes=b"%PDF-x", filename="p.pdf", company="Acme")
    assert ok is False
    get_settings.cache_clear()


async def test_sends_when_enabled(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("EMAIL_ENABLED", "true")
    monkeypatch.setenv("SMTP_HOST", "smtp.example")
    monkeypatch.setenv("SMTP_FROM", "teg@example")
    from config.settings import get_settings
    get_settings.cache_clear()
    with patch("app.proposal.email.smtplib.SMTP") as m:
        srv = MagicMock()
        m.return_value.__enter__.return_value = srv
        ok = await send_proposal_email(to="x@y.com", pdf_bytes=b"%PDF-x", filename="p.pdf", company="Acme")
    assert ok is True
    srv.send_message.assert_called_once()
    get_settings.cache_clear()


async def test_returns_false_on_smtp_error(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("EMAIL_ENABLED", "true")
    monkeypatch.setenv("SMTP_HOST", "smtp.example")
    from config.settings import get_settings
    get_settings.cache_clear()
    with patch("app.proposal.email.smtplib.SMTP", side_effect=OSError("no route")):
        ok = await send_proposal_email(to="x@y.com", pdf_bytes=b"%PDF-x", filename="p.pdf", company="Acme")
    assert ok is False
    get_settings.cache_clear()
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent && .venv/bin/python -m pytest tests/proposal/test_email.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write app/proposal/email.py**

```python
from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from config.settings import get_settings

_log = logging.getLogger(__name__)


def _send_sync(to: str, pdf_bytes: bytes, filename: str, company: str) -> bool:
    s = get_settings()
    msg = EmailMessage()
    msg["Subject"] = f"Your Tech Expo Gujarat 2026 proposal — {company}"
    msg["From"] = s.smtp_from or s.smtp_user
    msg["To"] = to
    msg.set_content(
        f"Hi,\n\nAttached is your personalized Tech Expo Gujarat 2026 proposal for {company}.\n"
        "All figures are indicative and subject to confirmation at booking.\n\n— The TEG team"
    )
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=filename)
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port) as srv:
            srv.ehlo()
            if s.smtp_user:
                srv.starttls()
                srv.login(s.smtp_user, s.smtp_pass)
            srv.send_message(msg)
        return True
    except (OSError, smtplib.SMTPException) as exc:
        _log.warning("proposal email to %s failed: %s", to, exc)
        return False


async def send_proposal_email(*, to: str, pdf_bytes: bytes, filename: str, company: str) -> bool:
    if not get_settings().email_enabled:
        return False
    return await asyncio.to_thread(_send_sync, to, pdf_bytes, filename, company)
```

- [ ] **Step 4: Run tests, commit**

Run: `.venv/bin/python -m pytest tests/proposal/ -q` — all pass.
```bash
cd /home/com-028/Desktop/TRT/PROJ/TECHEXPO && git add teg-outreach-agent/
git commit -m "feat(proposal): optional SMTP email delivery (off by default)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 9: Postgres — `ProposalRow` + `chat_messages.attachment` + migration

**Files:**
- Modify: `teg-outreach-agent/app/store/models.py`
- Create: `teg-outreach-agent/app/store/migrations/versions/0002_proposals.py`
- Test: `teg-outreach-agent/tests/store/test_proposal_models.py`

**Interfaces:**
- Consumes: `app.store.db.Base`
- Produces (`app.store.models`):
  - `ProposalRow` (`__tablename__ = "proposals"`): `id` uuid pk, `session_id` uuid FK → `chat_sessions.id`, `version` int, `created_at` timestamptz server_default now, `proposal_json` JSONB, `pdf_path` Text, `png_path` Text, `bytes` Integer, `guardrail_flags` JSONB default list, `emailed_to` Text nullable
  - `ChatMessage` gains `attachment: Mapped[dict | None] = mapped_column(JSONB, nullable=True)`

- [ ] **Step 1: Write the failing test**

```python
# tests/store/test_proposal_models.py
import pytest
from sqlalchemy import select

from app.store.db import Base, SessionLocal, engine
from app.store.models import ChatMessage, ChatSession, Inquiry, ProposalRow, ResearchDossierRow


@pytest.fixture(autouse=True)
async def _schema():
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)
        await c.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)


async def test_proposal_row_and_attachment():
    async with SessionLocal() as s:
        inq = Inquiry(person_name="X", company_name_raw="Y", company_name_canonical="Y",
                      consent_status="unknown", intent_hint="exhibitor", source="t")
        s.add(inq); await s.flush()
        d = ResearchDossierRow(inquiry_id=inq.id, company_profile={}, person_profile={},
                               relationship="cold", peer_companies=[], field_confidence={},
                               sources=[], review_flags=[], ask_prospect=[], research_cost={})
        s.add(d); await s.flush()
        cs = ChatSession(inquiry_id=inq.id, dossier_id=d.id, cta_status="none")
        s.add(cs); await s.flush()
        s.add(ProposalRow(session_id=cs.id, version=1, proposal_json={"company": "Y"},
                          pdf_path="proposals/x/v1.pdf", png_path="proposals/x/v1.png",
                          bytes=12345, guardrail_flags=[]))
        s.add(ChatMessage(session_id=cs.id, turn_index=0, role="agent", content="here",
                          attachment={"kind": "proposal", "version": 1}))
        await s.commit()

        pr = (await s.execute(select(ProposalRow))).scalars().one()
        assert pr.version == 1 and pr.bytes == 12345
        m = (await s.execute(select(ChatMessage))).scalars().one()
        assert m.attachment["kind"] == "proposal"
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent && .venv/bin/python -m pytest tests/store/test_proposal_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'ProposalRow'`

- [ ] **Step 3: Add to app/store/models.py**

Add the `attachment` column to `ChatMessage` (after `detected_intent`):
```python
    attachment: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

Add the model:
```python
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
```

- [ ] **Step 4: Write the migration**

Create `app/store/migrations/versions/0002_proposals.py`:
```python
"""proposals table + chat_messages.attachment

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("attachment", JSONB(), nullable=True))
    op.create_table(
        "proposals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("proposal_json", JSONB(), nullable=True),
        sa.Column("pdf_path", sa.Text(), nullable=True),
        sa.Column("png_path", sa.Text(), nullable=True),
        sa.Column("bytes", sa.Integer(), nullable=True),
        sa.Column("guardrail_flags", JSONB(), nullable=True),
        sa.Column("emailed_to", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("proposals")
    op.drop_column("chat_messages", "attachment")
```

- [ ] **Step 5: Run tests + verify migration round-trips**

Run:
```bash
cd teg-outreach-agent
.venv/bin/python -m pytest tests/store/test_proposal_models.py -q
DATABASE_URL="postgresql+psycopg://teg@127.0.0.1:5433/teg_outreach_test" .venv/bin/alembic upgrade head
DATABASE_URL="postgresql+psycopg://teg@127.0.0.1:5433/teg_outreach_test" .venv/bin/alembic downgrade 0001
DATABASE_URL="postgresql+psycopg://teg@127.0.0.1:5433/teg_outreach_test" .venv/bin/alembic upgrade head
```
Expected: test passes; alembic up→down→up clean.

- [ ] **Step 6: Commit**

```bash
cd /home/com-028/Desktop/TRT/PROJ/TECHEXPO && git add teg-outreach-agent/
git commit -m "feat(proposal): proposals table + chat_messages.attachment + migration 0002

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 10: `ProposalRepo` + `MessageRepo` attachment support

**Files:**
- Modify: `teg-outreach-agent/app/store/repositories.py`
- Test: `teg-outreach-agent/tests/store/test_proposal_repo.py`

**Interfaces:**
- Consumes: `app.store.models.ProposalRow`, `ChatMessage`; `app.domain.schemas.Proposal`
- Produces (`app.store.repositories`):
  - `MessageRepo.append(...)` gains `attachment: dict | None = None` kwarg, stored on the row.
  - `ProposalRepo(session)`:
    - `async def next_version(self, session_id) -> int` — `max(version)+1` or `1`
    - `async def create(self, session_id, *, proposal: Proposal, version: int, pdf_path: str, png_path: str, bytes_: int, guardrail_flags: list[str], emailed_to: str | None = None) -> ProposalRow`
    - `async def get(self, proposal_id) -> ProposalRow | None`
    - `async def list_for_session(self, session_id) -> list[ProposalRow]` (ordered by version)

- [ ] **Step 1: Write the failing test**

```python
# tests/store/test_proposal_repo.py
import pytest
from app.domain.schemas import Proposal, ProposalPackage, ProposalPain
from app.store.db import Base, SessionLocal, engine
from app.store.models import ChatMessage, ChatSession, Inquiry, ResearchDossierRow
from app.store.repositories import MessageRepo, ProposalRepo
from sqlalchemy import select


@pytest.fixture(autouse=True)
async def _schema():
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)
        await c.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)


def _proposal():
    return Proposal(
        company="Y", person="X", persona="it_tech_service", generated_on="2026-09-01",
        session_ref="r", version=1, what_you_told_us="w",
        pains=[ProposalPain(pain="a", teg_answer="b")], lead_generation="l", proof=["p"],
        recommended_package=ProposalPackage(name="n", price_line="₹1 + GST", includes=[], payment_plan="x"),
        peer_companies=[], next_steps=["s"], contact="c",
    )


async def _seed(s):
    inq = Inquiry(person_name="X", company_name_raw="Y", company_name_canonical="Y",
                  consent_status="unknown", intent_hint="exhibitor", source="t")
    s.add(inq); await s.flush()
    d = ResearchDossierRow(inquiry_id=inq.id, company_profile={}, person_profile={},
                           relationship="cold", peer_companies=[], field_confidence={},
                           sources=[], review_flags=[], ask_prospect=[], research_cost={})
    s.add(d); await s.flush()
    cs = ChatSession(inquiry_id=inq.id, dossier_id=d.id, cta_status="none")
    s.add(cs); await s.flush()
    return cs


async def test_proposal_repo_versioning_and_attachment():
    async with SessionLocal() as s:
        cs = await _seed(s)
        pr = ProposalRepo(s)
        assert await pr.next_version(cs.id) == 1
        row1 = await pr.create(cs.id, proposal=_proposal(), version=1,
                               pdf_path="a/v1.pdf", png_path="a/v1.png", bytes_=10,
                               guardrail_flags=[])
        await s.flush()
        assert await pr.next_version(cs.id) == 2
        await MessageRepo(s).append(cs.id, "agent", "here", turn_index=0,
                                    attachment={"kind": "proposal", "proposal_id": str(row1.id)})
        await s.commit()

        rows = await ProposalRepo(s).list_for_session(cs.id)
        assert [r.version for r in rows] == [1]
        m = (await s.execute(select(ChatMessage))).scalars().one()
        assert m.attachment["kind"] == "proposal"
        got = await ProposalRepo(s).get(row1.id)
        assert got.pdf_path == "a/v1.pdf"
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent && .venv/bin/python -m pytest tests/store/test_proposal_repo.py -v`
Expected: FAIL — `ImportError: cannot import name 'ProposalRepo'`

- [ ] **Step 3: Modify app/store/repositories.py**

In `MessageRepo.append`, add the param and pass it:
```python
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
```

Add the repo (after `HandoffRepo`):
```python
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
```
Add `ProposalRow` to the `from app.store.models import (...)` line.

- [ ] **Step 4: Run tests, commit**

Run: `.venv/bin/python -m pytest tests/store/ -q` — all pass. Full suite green.
```bash
cd /home/com-028/Desktop/TRT/PROJ/TECHEXPO && git add teg-outreach-agent/
git commit -m "feat(proposal): ProposalRepo + MessageRepo attachment support

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 11: Orchestrator — `generate_proposal()`

**Files:**
- Modify: `teg-outreach-agent/app/orchestrator.py`
- Test: `teg-outreach-agent/tests/orchestrator/test_generate_proposal.py`

**Interfaces:**
- Consumes: `app.agents.proposal.ProposalAgent`, `app.proposal.render` (`render_html`, `render_pdf`, `render_first_page_png`), `app.proposal.email.send_proposal_email`, `app.store.repositories` (`ProposalRepo`, `MessageRepo`, `SessionRepo`, `InquiryRepo`, `DossierRepo`), `app.domain.schemas.ProposalCard`, `config.settings.get_settings`
- Produces (added to `app.orchestrator.Orchestrator`):
  - `__init__` gains `proposal: ProposalAgent | None = None` (default `ProposalAgent(get_llm())`)
  - `async def generate_proposal(self, session_id: uuid.UUID, *, email: str | None = None) -> ProposalCard` —
    1. Load session + inquiry + dossier; rebuild `IntakeResult` (as `run_turn` does); `persona = session.persona or "visitor"`; `transcript = MessageRepo.history`; `learned_facts = session.learned_facts`.
    2. `version = await ProposalRepo.next_version(session_id)`; `session_ref = str(session_id)[:8]`.
    3. `proposal, flags = await asyncio.wait_for(proposal_agent.build(...), timeout=settings.proposal_hard_timeout_s)`. Set `proposal.generated_on = date.today().isoformat()` (replace the `__DATE__` placeholder).
    4. `html = render_html(proposal)`; `pdf = render_pdf(html)`; `png = render_first_page_png(html)` — the render calls are sync/CPU; wrap in `asyncio.to_thread`.
    5. Write files: `{settings.proposal_dir}/{session_id}/v{version}.pdf` and `.png` (mkdir parents).
    6. `filename = f"TEG-2026-Proposal-{slug(company)}-v{version}.pdf"` (slug = alnum + dashes).
    7. `emailed_to = None`; if `email`: `ok = await send_proposal_email(...)`; `emailed_to = email if ok else None`.
    8. `row = await ProposalRepo.create(...)`; commit.
    9. Append a `chat_messages` row: `role="agent"`, `content=f"Here's your proposal for {company} — [download PDF]({pdf_url}). Feel free to share it with your team."`, `turn_index = next`, `attachment = card_payload`.
    10. Return `ProposalCard(proposal_id=str(row.id), version=version, filename=filename, bytes=len(pdf), pdf_url=f"/proposals/{row.id}.pdf", png_url=f"/proposals/{row.id}/preview.png")`.
  - A module-level `_slug(s: str) -> str` helper.

- [ ] **Step 1: Write the failing test**

```python
# tests/orchestrator/test_generate_proposal.py
import pytest
from pathlib import Path

from app.agents.analysis import AnalysisAgent, _CanonResult
from app.agents.persuasion import PersuasionAgent, _PersonaChoice
from app.agents.proposal import ProposalAgent
from app.agents.research import ResearchAgent, _Synthesis
from app.domain.schemas import IntakePayload, Proposal, ProposalPackage, ProposalPain
from app.llm.fake import FakeLLMClient
from app.orchestrator import Orchestrator
from app.research.kb_retriever import KBRetriever
from app.research.tools import ResearchResult, ResearchTool
from app.store.db import Base, SessionLocal, engine
from app.store.models import ChatMessage, ProposalRow
from sqlalchemy import select


@pytest.fixture(autouse=True)
async def _schema():
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)
        await c.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)


class _DeadWeb(ResearchTool):
    name = "web"
    async def lookup(self, q):
        return ResearchResult(available=False, tool_name="web")


def _good_proposal():
    return Proposal(
        company="Third Rock Techkno", person="Tapan Patel", person_role="CMO",
        sector="Software Development", persona="it_tech_service",
        generated_on="__DATE__", session_ref="x", version=0,
        what_you_told_us="You are an AI + software consulting firm exploring TEG.",
        pains=[ProposalPain(pain="Revenue concentrated in US clients",
                            teg_answer="15,000+ India-market decision-makers plus B2B meetings")],
        lead_generation="Pre-scheduled B2B meetings with India-market buyers plus a live demo space.",
        proof=["TEG 2024 drew 8,000+ attendees and 125+ exhibitors."],
        recommended_package=ProposalPackage(
            name="3m x 3m stall", price_line="₹1,17,000 + GST (indicative, confirmed at booking)",
            includes=["2 exhibitor passes"], payment_plan="25% x 4",
        ),
        peer_companies=["NeuraMonks", "ViitorCloud"],
        next_steps=["Book at techexpogujarat.com/become-an-exhibitor"],
        contact="info@techexpogujarat.com",
    )


async def _seed_session(tmp_path):
    orch = Orchestrator(
        analysis=AnalysisAgent(FakeLLMClient(structured=[_CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor")])),
        research=ResearchAgent(FakeLLMClient(structured=[_Synthesis(
            sector="AI Consulting", company_size="200", hq="Ahmedabad", founder=None,
            designation=None, seniority=None, is_technical=None, person_company_match=None,
        )]), tools=[KBRetriever(), _DeadWeb()]),
        persuasion=PersuasionAgent(FakeLLMClient(
            structured=[_PersonaChoice(persona="it_tech_service", reason="software services")],
            responses=["Welcome back. A 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed at booking). Want details?"],
        )),
        proposal=ProposalAgent(FakeLLMClient(structured=[_good_proposal()])),
    )
    res = await orch.run_pipeline(IntakePayload(person_name="Tapan Patel", company_name="Third Rock Techkno"))
    return orch, res.session_id


async def test_generate_proposal_writes_files_row_and_message(tmp_path, monkeypatch):
    monkeypatch.setenv("PROPOSAL_DIR", str(tmp_path / "proposals"))
    from config.settings import get_settings
    get_settings.cache_clear()
    orch, sid = await _seed_session(tmp_path)
    card = await orch.generate_proposal(sid)

    assert card.version == 1
    assert card.filename.startswith("TEG-2026-Proposal-Third-Rock-Techkno-v1")
    assert card.bytes > 2000
    assert card.pdf_url == f"/proposals/{card.proposal_id}.pdf"

    pdf_file = tmp_path / "proposals" / str(sid) / "v1.pdf"
    assert pdf_file.exists() and pdf_file.read_bytes()[:5] == b"%PDF-"

    async with SessionLocal() as s:
        pr = (await s.execute(select(ProposalRow))).scalars().one()
        assert pr.version == 1
        assert pr.proposal_json["generated_on"] != "__DATE__"
        msgs = (await s.execute(select(ChatMessage).order_by(ChatMessage.turn_index))).scalars().all()
        assert msgs[-1].attachment["kind"] == "proposal"
        assert "download PDF" in msgs[-1].content
    get_settings.cache_clear()


async def test_generate_proposal_bumps_version(tmp_path, monkeypatch):
    monkeypatch.setenv("PROPOSAL_DIR", str(tmp_path / "proposals"))
    from config.settings import get_settings
    get_settings.cache_clear()
    orch, sid = await _seed_session(tmp_path)
    # re-queue a second proposal for the agent
    orch.proposal.llm._structured.append(_good_proposal())
    c1 = await orch.generate_proposal(sid)
    c2 = await orch.generate_proposal(sid)
    assert (c1.version, c2.version) == (1, 2)
    get_settings.cache_clear()
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent && .venv/bin/python -m pytest tests/orchestrator/test_generate_proposal.py -v`
Expected: FAIL — `AttributeError: 'Orchestrator' object has no attribute 'generate_proposal'`

- [ ] **Step 3: Add to app/orchestrator.py**

Imports:
```python
import re
from datetime import date
from pathlib import Path

from app.agents.proposal import ProposalAgent
from app.domain.schemas import ProposalCard
from app.proposal.email import send_proposal_email
from app.proposal.render import render_first_page_png, render_html, render_pdf
from app.store.repositories import ProposalRepo
```

`__init__` — add the param and default:
```python
        proposal: ProposalAgent | None = None,
    ) -> None:
        self.analysis = analysis or AnalysisAgent(get_llm())
        self.research = research or ResearchAgent(get_llm())
        self.persuasion = persuasion or PersuasionAgent(get_llm())
        self.proposal = proposal or ProposalAgent(get_llm())
```

Helper + method:
```python
def _slug(s: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^A-Za-z0-9]+", "-", s)).strip("-") or "company"


class Orchestrator:
    ...
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
            version = await ProposalRepo(s).next_version(session_id)

        proposal, flags = await asyncio.wait_for(
            self.proposal.build(
                intake=intake, dossier=dossier, persona=persona, transcript=transcript,
                learned_facts=learned, session_ref=str(session_id)[:8], version=version,
            ),
            timeout=settings.proposal_hard_timeout_s,
        )
        proposal.generated_on = date.today().isoformat()

        html = render_html(proposal)
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
            pdf_url = f"/proposals/{row.id}.pdf"
            png_url = f"/proposals/{row.id}/preview.png"
            card = {
                "kind": "proposal", "proposal_id": str(row.id), "version": version,
                "filename": filename, "bytes": len(pdf), "pdf_url": pdf_url, "png_url": png_url,
            }
            mr = MessageRepo(s)
            await mr.append(
                session_id, "agent",
                f"Here's your proposal for {proposal.company} — [download PDF]({pdf_url}). "
                "Feel free to share it with your team.",
                turn_index=await mr.next_turn_index(session_id),
                attachment=card,
            )
            if flags:
                cs2 = await SessionRepo(s).get(session_id)
                cs2.needs_review = True
            await s.commit()

        return ProposalCard(
            proposal_id=str(row.id), version=version, filename=filename,
            bytes=len(pdf), pdf_url=pdf_url, png_url=png_url,
        )
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/orchestrator/test_generate_proposal.py -q`
Expected: PASS (2). Watch: `orch.proposal.llm` in the version test — `FakeLLMClient` stores its queue as `_structured`; appending works. If the test's `_good_proposal()` with `generated_on="__DATE__"` fails a guardrail, it won't — `__DATE__` is inert text.

- [ ] **Step 5: Commit**

```bash
cd /home/com-028/Desktop/TRT/PROJ/TECHEXPO && git add teg-outreach-agent/
git commit -m "feat(proposal): orchestrator generate_proposal — build, render, store, message

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 12: Persuasion `_Analysis.wants_proposal` + prompt tweak + `run_turn` hook

**Files:**
- Modify: `teg-outreach-agent/app/agents/persuasion.py`
- Modify: `teg-outreach-agent/app/orchestrator.py`
- Modify: `teg-outreach-agent/app/domain/schemas.py` (`PersuasionTurn` gains `wants_proposal: bool = False`)
- Test: `teg-outreach-agent/tests/agents/test_persuasion_wants_proposal.py`
- Test: `teg-outreach-agent/tests/orchestrator/test_run_turn_proposal.py`

**Interfaces:**
- `_Analysis` gains `wants_proposal: bool = False`.
- `PersuasionAgent._system` (or the respond prompt suffix) gains: *"If the prospect shows real buying interest (asked about pricing, leads, ROI, or 'how it helps'), you MAY offer once: 'I can put together a tailored proposal for [company] you can share with your team — want that?'. Set wants_proposal=true if the prospect asks for a proposal / something in writing / a PDF, or accepts that offer."*
- `PersuasionTurn` gains `wants_proposal: bool` and `respond()` copies it from `_Analysis`.
- `Orchestrator.run_turn`: after persisting the turn, `if turn.wants_proposal: try: card = await self.generate_proposal(session_id) ; ... ` — but `run_turn` returns a `PersuasionTurn`, not the card. Design: `run_turn` returns `PersuasionTurn` unchanged; the **WS handler** (Task 14) checks `turn.wants_proposal` and calls `generate_proposal` itself (so it can emit the `proposal_pending` frame first). So Task 12's orchestrator change is only: nothing in `run_turn` — just make sure `turn.wants_proposal` is populated and returned. (Keep `run_turn` lean.)

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/test_persuasion_wants_proposal.py
from app.agents.persuasion import PersuasionAgent, _Analysis, _PersonaChoice
from app.domain.schemas import IntakeResult, ResearchDossier
from app.llm.fake import FakeLLMClient


def _intake():
    return IntakeResult(person_name="X", company_name_raw="Y", company_name_canonical="Y",
                        provided_fields=[], intent_hint="exhibitor", consent_status="unknown")


def _state(persona="it_tech_service"):
    return {"persona": persona, "target_cta": "book_stall", "cta_status": "offered",
            "cta_detail": {}, "learned_facts": {}, "persona_remapped": True, "needs_review": False}


async def test_respond_propagates_wants_proposal():
    llm = FakeLLMClient(structured=[_Analysis(
        reply="Sure — one moment.", detected_cta=None, cta_status="offered", cta_type=None,
        cta_detail={}, should_handoff=False, learned_facts={}, wants_proposal=True,
    )])
    d = ResearchDossier(sector="Software Development", relationship="cold", peer_companies=["NeuraMonks"])
    turn = await PersuasionAgent(llm).respond(
        intake=_intake(), dossier=d, state=_state(),
        history=[{"role": "agent", "content": "x"}, {"role": "prospect", "content": "y"}],
        prospect_message="can you send me a proposal?",
    )
    assert turn.wants_proposal is True
```

```python
# tests/orchestrator/test_run_turn_proposal.py
import pytest
from sqlalchemy import select

from app.agents.analysis import AnalysisAgent, _CanonResult
from app.agents.persuasion import PersuasionAgent, _Analysis, _PersonaChoice
from app.agents.research import ResearchAgent, _Synthesis
from app.domain.schemas import IntakePayload
from app.llm.fake import FakeLLMClient
from app.orchestrator import Orchestrator
from app.research.kb_retriever import KBRetriever
from app.research.tools import ResearchResult, ResearchTool
from app.store.db import Base, SessionLocal, engine
from app.store.models import ProposalRow


@pytest.fixture(autouse=True)
async def _schema():
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)
        await c.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)


class _DeadWeb(ResearchTool):
    name = "web"
    async def lookup(self, q):
        return ResearchResult(available=False, tool_name="web")


async def test_run_turn_populates_wants_proposal_without_generating():
    orch = Orchestrator(
        analysis=AnalysisAgent(FakeLLMClient(structured=[_CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor")])),
        research=ResearchAgent(FakeLLMClient(structured=[_Synthesis(
            sector="AI Consulting", company_size="200", hq=None, founder=None,
            designation=None, seniority=None, is_technical=None, person_company_match=None)]),
            tools=[KBRetriever(), _DeadWeb()]),
        persuasion=PersuasionAgent(FakeLLMClient(
            structured=[_PersonaChoice(persona="it_tech_service", reason="s"),
                        _Analysis(reply="Sure.", detected_cta=None, cta_status="offered", cta_type=None,
                                  cta_detail={}, should_handoff=False, learned_facts={}, wants_proposal=True)],
            responses=["Welcome. A 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed at booking)."])),
    )
    res = await orch.run_pipeline(IntakePayload(person_name="Tapan Patel", company_name="Third Rock Techkno"))
    turn = await orch.run_turn(res.session_id, "send me a proposal please")
    assert turn.wants_proposal is True
    # run_turn itself does NOT generate a proposal
    async with SessionLocal() as s:
        assert (await s.execute(select(ProposalRow))).scalars().first() is None
```

- [ ] **Step 2: Run to verify fail** — `AttributeError` on `wants_proposal`.

- [ ] **Step 3: Apply the changes**

- `app/domain/schemas.py`: `PersuasionTurn` — add `wants_proposal: bool = False`.
- `app/agents/persuasion.py`:
  - `_Analysis` — add `wants_proposal: bool = False`.
  - In `respond`, the returned `PersuasionTurn(...)` — add `wants_proposal=analysis.wants_proposal`.
  - In the `respond` system prompt suffix (the block that already says "Advance it naturally…"), append: `" If the prospect asks for a proposal, a PDF, or 'something in writing', or accepts an offer of one, set wants_proposal=true. You MAY offer a tailored proposal once when they show real buying interest."`
- `app/orchestrator.py`: `run_turn` — no functional change needed; confirm the returned `PersuasionTurn` carries `wants_proposal` (it will, via `respond`).

- [ ] **Step 4: Run tests** — the new tests pass; `tests/agents/test_persuasion_respond.py` and `tests/orchestrator/test_run_turn.py` still pass (the extra `_Analysis` field defaults to `False`, and `FakeLLMClient` schema-matching is unaffected).

- [ ] **Step 5: Commit**

```bash
cd /home/com-028/Desktop/TRT/PROJ/TECHEXPO && git add teg-outreach-agent/
git commit -m "feat(proposal): PersuasionAgent detects wants_proposal; PersuasionTurn carries it

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 13: API — proposal endpoints

**Files:**
- Create: `teg-outreach-agent/app/api/proposals.py`
- Modify: `teg-outreach-agent/app/main.py`
- Modify: `teg-outreach-agent/app/api/internal.py` (`GET /sessions/{id}` gains `proposals: [...]`)
- Test: `teg-outreach-agent/tests/api/test_proposals_api.py`

**Interfaces:**
- Consumes: `app.orchestrator.Orchestrator` via `app.api.inquiries.get_orchestrator`, `app.store.db.SessionLocal`, `app.store.repositories.ProposalRepo`
- Produces (`app.api.proposals`):
  - `router` (`APIRouter`):
    - `GET /proposals/{proposal_id}.pdf` → `FileResponse(pdf_path, media_type="application/pdf", filename=..., content_disposition_type="inline")`; 404 if row/file missing.
    - `GET /proposals/{proposal_id}/preview.png` → `FileResponse(png_path, media_type="image/png")`; 404 if missing.
    - `POST /sessions/{session_id}/proposal` → body optional `{"email": "..."}` → `orch.generate_proposal(session_id, email=...)` → returns the `ProposalCard` as JSON; 202.
  - `app.main.create_app()` includes `proposals.router`.
  - `app.api.internal.get_session` response adds `"proposals": [{"version","created_at","pdf_url","png_url","guardrail_flags","emailed_to"} ...]`.

**Note on the `.pdf` route:** FastAPI path params don't capture a trailing `.pdf` by default. Use `@router.get("/proposals/{proposal_id}.pdf")` — FastAPI treats the literal `.pdf` as part of the path template and binds `proposal_id` to the segment before it. If that proves flaky, use `/proposals/{proposal_id}/file.pdf` and update `generate_proposal`'s `pdf_url` accordingly. Keep the URL shape consistent everywhere.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_proposals_api.py
import pytest
from fastapi.testclient import TestClient

from app.agents.analysis import AnalysisAgent, _CanonResult
from app.agents.persuasion import PersuasionAgent, _PersonaChoice
from app.agents.proposal import ProposalAgent
from app.agents.research import ResearchAgent, _Synthesis
from app.api.inquiries import get_orchestrator
from app.domain.schemas import Proposal, ProposalPackage, ProposalPain
from app.llm.fake import FakeLLMClient
from app.main import create_app
from app.orchestrator import Orchestrator
from app.research.kb_retriever import KBRetriever
from app.research.tools import ResearchResult, ResearchTool

pytestmark = pytest.mark.usefixtures("db_schema")


class _DeadWeb(ResearchTool):
    name = "web"
    async def lookup(self, q):
        return ResearchResult(available=False, tool_name="web")


def _good_proposal():
    return Proposal(
        company="Third Rock Techkno", person="Tapan Patel", person_role="CMO",
        sector="Software Development", persona="it_tech_service",
        generated_on="__DATE__", session_ref="x", version=0,
        what_you_told_us="AI + software consulting firm exploring TEG.",
        pains=[ProposalPain(pain="US-heavy revenue", teg_answer="15,000+ India buyers + B2B meetings")],
        lead_generation="Pre-scheduled B2B meetings with India-market buyers plus a live demo space.",
        proof=["TEG 2024 drew 8,000+ attendees and 125+ exhibitors."],
        recommended_package=ProposalPackage(
            name="3m x 3m stall", price_line="₹1,17,000 + GST (indicative, confirmed at booking)",
            includes=["2 exhibitor passes"], payment_plan="25% x 4"),
        peer_companies=["NeuraMonks"], next_steps=["Book at techexpogujarat.com"],
        contact="info@techexpogujarat.com",
    )


def _orch():
    return Orchestrator(
        analysis=AnalysisAgent(FakeLLMClient(structured=[_CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor")])),
        research=ResearchAgent(FakeLLMClient(structured=[_Synthesis(
            sector="AI Consulting", company_size="200", hq="Ahmedabad", founder=None,
            designation=None, seniority=None, is_technical=None, person_company_match=None)]),
            tools=[KBRetriever(), _DeadWeb()]),
        persuasion=PersuasionAgent(FakeLLMClient(
            structured=[_PersonaChoice(persona="it_tech_service", reason="software services")],
            responses=["Welcome. A 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed at booking)."])),
        proposal=ProposalAgent(FakeLLMClient(structured=[_good_proposal()])),
    )


def test_post_proposal_then_get_pdf_and_png(tmp_path, monkeypatch):
    monkeypatch.setenv("PROPOSAL_DIR", str(tmp_path / "proposals"))
    from config.settings import get_settings
    get_settings.cache_clear()

    app = create_app()
    shared = _orch()
    app.dependency_overrides[get_orchestrator] = lambda: shared
    client = TestClient(app)

    posted = client.post("/inquiries", json={"person_name": "Tapan Patel", "company_name": "Third Rock Techkno"}).json()
    sid = posted["session_id"]

    r = client.post(f"/sessions/{sid}/proposal", json={})
    assert r.status_code == 202
    card = r.json()
    assert card["version"] == 1
    assert card["pdf_url"].endswith(".pdf")

    pdf = client.get(card["pdf_url"])
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content[:5] == b"%PDF-"

    png = client.get(card["png_url"])
    assert png.status_code == 200
    assert png.headers["content-type"] == "image/png"

    sess = client.get(f"/sessions/{sid}").json()
    assert len(sess["proposals"]) == 1
    assert sess["proposals"][0]["version"] == 1
    get_settings.cache_clear()


def test_get_missing_proposal_404(tmp_path, monkeypatch):
    monkeypatch.setenv("PROPOSAL_DIR", str(tmp_path / "proposals"))
    from config.settings import get_settings
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_orchestrator] = lambda: _orch()
    client = TestClient(app)
    r = client.get("/proposals/00000000-0000-0000-0000-000000000000.pdf")
    assert r.status_code == 404
    get_settings.cache_clear()
```

- [ ] **Step 2: Run to verify fail** — module not found / routes missing.

- [ ] **Step 3: Write app/api/proposals.py**

```python
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.api.inquiries import get_orchestrator
from app.orchestrator import Orchestrator
from app.store.db import SessionLocal
from app.store.repositories import ProposalRepo

router = APIRouter()


@router.get("/proposals/{proposal_id}.pdf")
async def get_pdf(proposal_id: uuid.UUID) -> FileResponse:
    async with SessionLocal() as s:
        row = await ProposalRepo(s).get(proposal_id)
    if row is None or not row.pdf_path or not Path(row.pdf_path).is_file():
        raise HTTPException(404)
    fname = f"TEG-2026-Proposal-v{row.version}.pdf"
    return FileResponse(row.pdf_path, media_type="application/pdf", filename=fname,
                        content_disposition_type="inline")


@router.get("/proposals/{proposal_id}/preview.png")
async def get_png(proposal_id: uuid.UUID) -> FileResponse:
    async with SessionLocal() as s:
        row = await ProposalRepo(s).get(proposal_id)
    if row is None or not row.png_path or not Path(row.png_path).is_file():
        raise HTTPException(404)
    return FileResponse(row.png_path, media_type="image/png")


@router.post("/sessions/{session_id}/proposal", status_code=status.HTTP_202_ACCEPTED)
async def make_proposal(
    session_id: uuid.UUID,
    payload: dict = Body(default={}),
    orch: Orchestrator = Depends(get_orchestrator),
) -> dict:
    card = await orch.generate_proposal(session_id, email=payload.get("email"))
    return card.model_dump()
```

- [ ] **Step 4: main.py + internal.py**

`main.py` `create_app`: `from app.api import proposals` and `app.include_router(proposals.router)`.

`internal.py` `get_session`: after building the response dict, add:
```python
        prows = await ProposalRepo(s).list_for_session(session_id)
        ... "proposals": [
            {"version": p.version, "created_at": p.created_at.isoformat() if p.created_at else None,
             "pdf_url": f"/proposals/{p.id}.pdf", "png_url": f"/proposals/{p.id}/preview.png",
             "guardrail_flags": p.guardrail_flags or [], "emailed_to": p.emailed_to}
            for p in prows
        ],
```
(import `ProposalRepo`).

- [ ] **Step 5: Run tests, commit**

Run: `.venv/bin/python -m pytest tests/api/ -q` — all pass. Full suite green.
```bash
cd /home/com-028/Desktop/TRT/PROJ/TECHEXPO && git add teg-outreach-agent/
git commit -m "feat(proposal): API — GET pdf/png, POST /sessions/{id}/proposal, session listing

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 14: WS chat — `proposal_pending` / `attachment` / `proposal_failed`

**Files:**
- Modify: `teg-outreach-agent/app/api/chat.py`
- Test: `teg-outreach-agent/tests/api/test_chat_proposal.py`

**Interfaces:**
- Consumes: `Orchestrator.run_turn`, `Orchestrator.generate_proposal`
- The WS message loop: after `turn = await orch.run_turn(...)` and sending the `reply` frame, if `turn.wants_proposal`:
  1. send `{"type": "proposal_pending", "company": <canonical company>}`
  2. `try: card = await asyncio.wait_for(orch.generate_proposal(session_id), timeout=settings.proposal_hard_timeout_s)` → send `{"type": "attachment", **card.model_dump()}`
  3. `except (TimeoutError, asyncio.TimeoutError, Exception)` → send `{"type": "proposal_failed"}` (and log). The conversation continues.
- The company name for `proposal_pending`: load it once from the inquiry at connect time, or pass through. Simplest: `orch` doesn't expose it; query `InquiryRepo` in the handler at connect, keep `company` in a local var.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_chat_proposal.py
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.agents.analysis import AnalysisAgent, _CanonResult
from app.agents.persuasion import PersuasionAgent, _Analysis, _PersonaChoice
from app.agents.proposal import ProposalAgent
from app.agents.research import ResearchAgent, _Synthesis
from app.api.inquiries import get_orchestrator
from app.domain.schemas import Proposal, ProposalPackage, ProposalPain
from app.llm.fake import FakeLLMClient
from app.main import create_app
from app.orchestrator import Orchestrator
from app.research.kb_retriever import KBRetriever
from app.research.tools import ResearchResult, ResearchTool

pytestmark = pytest.mark.usefixtures("db_schema")


class _DeadWeb(ResearchTool):
    name = "web"
    async def lookup(self, q):
        return ResearchResult(available=False, tool_name="web")


def _good_proposal():
    return Proposal(
        company="Third Rock Techkno", person="Tapan Patel", persona="it_tech_service",
        sector="Software Development", generated_on="__DATE__", session_ref="x", version=0,
        what_you_told_us="w",
        pains=[ProposalPain(pain="US-heavy revenue", teg_answer="15,000+ India buyers")],
        lead_generation="Pre-scheduled B2B meetings plus a live demo space.",
        proof=["TEG 2024 drew 8,000+ attendees."],
        recommended_package=ProposalPackage(name="3m x 3m stall",
            price_line="₹1,17,000 + GST (indicative, confirmed at booking)",
            includes=["2 exhibitor passes"], payment_plan="25% x 4"),
        peer_companies=["NeuraMonks"], next_steps=["Book at techexpogujarat.com"],
        contact="info@techexpogujarat.com",
    )


def _orch(proposal_llm):
    return Orchestrator(
        analysis=AnalysisAgent(FakeLLMClient(structured=[_CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor")])),
        research=ResearchAgent(FakeLLMClient(structured=[_Synthesis(
            sector="AI Consulting", company_size="200", hq=None, founder=None,
            designation=None, seniority=None, is_technical=None, person_company_match=None)]),
            tools=[KBRetriever(), _DeadWeb()]),
        persuasion=PersuasionAgent(FakeLLMClient(
            structured=[_PersonaChoice(persona="it_tech_service", reason="s"),
                        _Analysis(reply="Sure, one moment.", detected_cta=None, cta_status="offered",
                                  cta_type=None, cta_detail={}, should_handoff=False, learned_facts={},
                                  wants_proposal=True)],
            responses=["Welcome. A 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed at booking)."])),
        proposal=ProposalAgent(proposal_llm),
    )


def test_ws_proposal_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("PROPOSAL_DIR", str(tmp_path / "proposals"))
    from config.settings import get_settings
    get_settings.cache_clear()

    app = create_app()
    shared = _orch(FakeLLMClient(structured=[_good_proposal()]))
    app.dependency_overrides[get_orchestrator] = lambda: shared
    client = TestClient(app)

    posted = client.post("/inquiries", json={"person_name": "Tapan Patel", "company_name": "Third Rock Techkno"}).json()
    sid = posted["session_id"]

    with client.websocket_connect(f"/chat/{sid}") as ws:
        assert ws.receive_json()["type"] == "opening"
        ws.send_json({"type": "message", "text": "can you send me a proposal?"})
        assert ws.receive_json()["type"] == "reply"
        assert ws.receive_json()["type"] == "proposal_pending"
        att = ws.receive_json()
        assert att["type"] == "attachment"
        assert att["kind"] == "proposal" and att["version"] == 1
        assert att["pdf_url"].endswith(".pdf")
        ws.send_json({"type": "end"})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()

    # the pdf is fetchable
    pdf = client.get(att["pdf_url"])
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"
    get_settings.cache_clear()


def test_ws_proposal_failure_emits_failed(tmp_path, monkeypatch):
    monkeypatch.setenv("PROPOSAL_DIR", str(tmp_path / "proposals"))
    from config.settings import get_settings
    get_settings.cache_clear()

    class _BoomProposal(ProposalAgent):
        async def build(self, **kw):
            raise RuntimeError("render boom")

    app = create_app()
    shared = _orch(FakeLLMClient())
    shared.proposal = _BoomProposal(FakeLLMClient())
    app.dependency_overrides[get_orchestrator] = lambda: shared
    client = TestClient(app)

    posted = client.post("/inquiries", json={"person_name": "Tapan Patel", "company_name": "Third Rock Techkno"}).json()
    sid = posted["session_id"]
    with client.websocket_connect(f"/chat/{sid}") as ws:
        ws.receive_json()  # opening
        ws.send_json({"type": "message", "text": "proposal please"})
        ws.receive_json()  # reply
        ws.receive_json()  # proposal_pending
        assert ws.receive_json()["type"] == "proposal_failed"
        ws.send_json({"type": "end"})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
    get_settings.cache_clear()
```

- [ ] **Step 2: Run to verify fail** — no proposal frames emitted.

- [ ] **Step 3: Modify app/api/chat.py**

Add `import asyncio` and `from config.settings import get_settings` and `from app.store.repositories import InquiryRepo, SessionRepo` (SessionRepo already imported). At connect, after loading the session, also load the company:
```python
    async with SessionLocal() as s:
        cs = await SessionRepo(s).get(session_id)
        if cs is None:
            await websocket.close(code=4404)
            return
        inq = await InquiryRepo(s).get(cs.inquiry_id)
        company = (inq.company_name_canonical or inq.company_name_raw) if inq else "your company"
        history = await MessageRepo(s).history(session_id)
```
In the message loop, after sending the `reply` frame:
```python
            if turn.wants_proposal:
                await websocket.send_json({"type": "proposal_pending", "company": company})
                try:
                    card = await asyncio.wait_for(
                        orch.generate_proposal(session_id),
                        timeout=get_settings().proposal_hard_timeout_s,
                    )
                    await websocket.send_json({"type": "attachment", **card.model_dump()})
                except Exception:  # noqa: BLE001 — a failed proposal must not kill the chat
                    await websocket.send_json({"type": "proposal_failed"})
```

- [ ] **Step 4: Run tests, commit**

Run: `.venv/bin/python -m pytest tests/api/ -q` — all pass. Full suite green.
```bash
cd /home/com-028/Desktop/TRT/PROJ/TECHEXPO && git add teg-outreach-agent/
git commit -m "feat(proposal): WS chat emits proposal_pending / attachment / proposal_failed

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 15: Retention — purge proposals

**Files:**
- Modify: `teg-outreach-agent/app/jobs/retention.py`
- Test: `teg-outreach-agent/tests/jobs/test_retention_proposals.py`

**Interfaces:**
- `purge_expired` also: for the old inquiries' sessions, delete `proposals` rows AND their files (`pdf_path`, `png_path`, and the session's proposal directory if empty). Add `"proposals"` to the returned counts dict.

- [ ] **Step 1: Write the failing test**

```python
# tests/jobs/test_retention_proposals.py
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select, text

from app.jobs.retention import purge_expired
from app.store.db import Base, SessionLocal, engine
from app.store.models import ChatSession, Inquiry, ProposalRow, ResearchDossierRow


@pytest.fixture(autouse=True)
async def _schema():
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)
        await c.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)


async def test_purge_removes_old_proposals_and_files(tmp_path):
    pdf = tmp_path / "old" / "v1.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-old")
    async with SessionLocal() as s:
        inq = Inquiry(person_name="X", company_name_raw="Y", company_name_canonical="Y",
                      consent_status="unknown", intent_hint="exhibitor", source="t")
        s.add(inq); await s.flush()
        d = ResearchDossierRow(inquiry_id=inq.id, company_profile={}, person_profile={},
                               relationship="cold", peer_companies=[], field_confidence={},
                               sources=[], review_flags=[], ask_prospect=[], research_cost={})
        s.add(d); await s.flush()
        cs = ChatSession(inquiry_id=inq.id, dossier_id=d.id, cta_status="none")
        s.add(cs); await s.flush()
        s.add(ProposalRow(session_id=cs.id, version=1, proposal_json={},
                          pdf_path=str(pdf), png_path=str(pdf.with_suffix(".png")), bytes=8,
                          guardrail_flags=[]))
        await s.flush()
        await s.execute(text("UPDATE inquiries SET created_at = :ts WHERE id = :id"),
                        {"ts": datetime.now(timezone.utc) - timedelta(days=400), "id": inq.id})
        await s.commit()

    counts = await purge_expired()
    assert counts["proposals"] >= 1
    assert not pdf.exists()
    async with SessionLocal() as s:
        assert (await s.execute(select(ProposalRow))).scalars().first() is None
```

- [ ] **Step 2: Run to verify fail** — `KeyError: 'proposals'` or the file still exists.

- [ ] **Step 3: Modify app/jobs/retention.py**

Add `ProposalRow` to the model imports. In `purge_expired`, in the block that already computes `session_ids` for old inquiries, before deleting `chat_sessions`:
```python
        if session_ids:
            prows = (await s.execute(
                select(ProposalRow).where(ProposalRow.session_id.in_(session_ids))
            )).scalars().all()
            for pr in prows:
                for p in (pr.pdf_path, pr.png_path):
                    if p:
                        Path(p).unlink(missing_ok=True)
                if pr.pdf_path:
                    parent = Path(pr.pdf_path).parent
                    try:
                        parent.rmdir()  # only if empty
                    except OSError:
                        pass
            counts["proposals"] = (await s.execute(
                delete(ProposalRow).where(ProposalRow.session_id.in_(session_ids))
            )).rowcount or 0
```
Add `"proposals": 0` to the initial `counts` dict and `from pathlib import Path` to the imports.

- [ ] **Step 4: Run tests, commit**

Run: `.venv/bin/python -m pytest tests/jobs/ -q` — all pass.
```bash
cd /home/com-028/Desktop/TRT/PROJ/TECHEXPO && git add teg-outreach-agent/
git commit -m "feat(proposal): retention job purges proposal rows and files

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 16: Widget — attachment card + pending skeleton + WS frames

**Files:**
- Modify: `teg-outreach-agent/widget/src/ui.ts`
- Modify: `teg-outreach-agent/widget/src/index.ts`
- Modify: `teg-outreach-agent/widget/src/api.ts` (add the new `ChatEvent` types)
- Modify: `teg-outreach-agent/widget/src/ui.test.ts` (add card tests)

**Interfaces:**
- `api.ts` `ChatEvent` union gains: `| { type: 'proposal_pending'; company?: string } | { type: 'attachment'; kind: string; proposal_id: string; version: number; filename: string; bytes: number; pdf_url: string; png_url: string } | { type: 'proposal_failed' }`.
- `ui.ts` — `renderChat` return object gains:
  - `showProposalPending(company?: string): void` — appends a skeleton card with a spinner + "Preparing a proposal for {company}…"
  - `showAttachment(att): void` — replaces the skeleton (if present) with a real card: `<img src={png_url}>` thumbnail + filename + human-readable size + "Open" (`<a href={pdf_url} target=_blank>`) + "Download" (`<a href={pdf_url} download={filename}>`).
  - `showProposalFailed(): void` — replaces the skeleton with "Couldn't generate the proposal just now — the team will follow up."
  - a `humanSize(bytes)` helper (exported for the test).
- `index.ts` `mount` — the `sock.onEvent` handler routes the three new frame types to the above.

- [ ] **Step 1: Add the failing tests to ui.test.ts**

```typescript
// append to src/ui.test.ts
import { humanSize } from "./ui.ts";

test("humanSize formats", () => {
  assert.equal(humanSize(900), "900 B");
  assert.equal(humanSize(148213), "145 KB");
});

test("renderChat shows attachment card with links", () => {
  const root = new El("div") as any;
  const chat = renderChat(root);
  chat.showAttachment({
    kind: "proposal", proposal_id: "p1", version: 2,
    filename: "TEG-2026-Proposal-Acme-v2.pdf", bytes: 148213,
    pdf_url: "/proposals/p1.pdf", png_url: "/proposals/p1/preview.png",
  });
  const card = root.querySelector("[data-attachment]") ?? root.querySelector("div");
  assert.ok(card);
  // an anchor to the pdf exists
  const found = JSON.stringify(root).includes("/proposals/p1.pdf");
  assert.ok(found);
});

test("renderChat pending then attachment replaces skeleton", () => {
  const root = new El("div") as any;
  const chat = renderChat(root);
  chat.showProposalPending("Acme");
  chat.showAttachment({
    kind: "proposal", proposal_id: "p1", version: 1,
    filename: "f.pdf", bytes: 1000, pdf_url: "/proposals/p1.pdf", png_url: "/x.png",
  });
  // only one card remains (skeleton replaced, not duplicated)
  const cards = JSON.stringify(root).match(/data-attachment/g) || [];
  assert.equal(cards.length, 1);
});
```
(The DOM shim `El` may need `remove()` / `replaceWith()` — extend it minimally in the test file if `showAttachment` uses them; keep assertions intact.)

- [ ] **Step 2: Run to verify fail** — `cd teg-outreach-agent/widget && npm test` → fails on missing `humanSize` / `showAttachment`.

- [ ] **Step 3: Implement in ui.ts**

Add:
```typescript
export function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
```

In `renderChat`, keep a `let pendingCard: HTMLElement | null = null;` and add to the returned object:
```typescript
    showProposalPending(company?: string) {
      const card = h("div", { "data-attachment": "pending", class: "teg-card teg-card-pending" },
        `Preparing a proposal${company ? ` for ${company}` : ""}…`);
      log.appendChild(card);
      pendingCard = card;
    },
    showAttachment(att: any) {
      const card = h("div", { "data-attachment": "proposal", class: "teg-card" });
      const thumb = h("img", { src: att.png_url, alt: "Proposal preview", class: "teg-card-thumb" });
      const meta = h("div", { class: "teg-card-meta" }, `${att.filename} · ${humanSize(att.bytes)}`);
      const open = h("a", { href: att.pdf_url, target: "_blank", rel: "noopener", class: "teg-card-btn" }, "Open");
      const dl = h("a", { href: att.pdf_url, download: att.filename, class: "teg-card-btn" }, "Download");
      card.appendChild(thumb); card.appendChild(meta); card.appendChild(open); card.appendChild(dl);
      if (pendingCard && pendingCard.replaceWith) { pendingCard.replaceWith(card); }
      else { log.appendChild(card); }
      pendingCard = null;
    },
    showProposalFailed() {
      const msg = "Couldn't generate the proposal just now — the team will follow up.";
      if (pendingCard) { pendingCard.textContent = msg; pendingCard.setAttribute("data-attachment", "failed"); }
      else { log.appendChild(h("div", { class: "teg-msg teg-agent" }, msg)); }
      pendingCard = null;
    },
```
Add minimal CSS for `.teg-card` in the `<style>` the widget injects (or inline styles on the elements).

- [ ] **Step 4: Wire index.ts**

In `mount`'s `sock.onEvent`:
```typescript
      else if (ev.type === "proposal_pending") { chat.showProposalPending(ev.company); }
      else if (ev.type === "attachment") { chat.showAttachment(ev); }
      else if (ev.type === "proposal_failed") { chat.showProposalFailed(); }
```

- [ ] **Step 5: Run tests + build**

```bash
cd teg-outreach-agent/widget && npm test && npm run build
```
Expected: all widget tests pass (10: 7 prior + 3 new); `dist/` rebuilds.

- [ ] **Step 6: Commit**

```bash
cd /home/com-028/Desktop/TRT/PROJ/TECHEXPO && git add teg-outreach-agent/widget/
git commit -m "feat(proposal): widget attachment card, pending skeleton, WS frame handling

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 17: E2E — chat → ask for proposal → attachment → fetch PDF

**Files:**
- Create: `teg-outreach-agent/tests/e2e/test_proposal_flow.py`
- Modify: `teg-outreach-agent/README.md` (document the proposal feature + the `POST /sessions/{id}/proposal` endpoint)

**Interfaces:** no new production code — proves spec §10 criteria 1, 2, 3, 4, 5.

- [ ] **Step 1: Write the E2E test**

```python
# tests/e2e/test_proposal_flow.py
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.agents.analysis import AnalysisAgent, _CanonResult
from app.agents.persuasion import PersuasionAgent, _Analysis, _PersonaChoice
from app.agents.proposal import ProposalAgent
from app.agents.research import ResearchAgent, _Synthesis
from app.api.inquiries import get_orchestrator
from app.domain.schemas import Proposal, ProposalPackage, ProposalPain
from app.llm.fake import FakeLLMClient
from app.main import create_app
from app.orchestrator import Orchestrator
from app.research.kb_retriever import KBRetriever
from app.research.tools import ResearchResult, ResearchTool

pytestmark = pytest.mark.usefixtures("db_schema")


class _DeadWeb(ResearchTool):
    name = "web"
    async def lookup(self, q):
        return ResearchResult(available=False, tool_name="web")


def test_full_proposal_flow(tmp_path, monkeypatch):
    """Criteria 1-5: mid-chat proposal request -> personalized PDF card -> fetchable PDF."""
    monkeypatch.setenv("PROPOSAL_DIR", str(tmp_path / "proposals"))
    from config.settings import get_settings
    get_settings.cache_clear()

    proposal = Proposal(
        company="Third Rock Techkno", person="Tapan Patel", person_role="CMO",
        sector="Software Development", persona="it_tech_service",
        generated_on="__DATE__", session_ref="x", version=0,
        what_you_told_us="You're an AI + software consulting firm serving mostly US clients, "
                         "looking to build an India-market pipeline.",
        pains=[
            ProposalPain(pain="Revenue concentrated in US clients; thin India pipeline",
                         teg_answer="15,000+ India-market decision-makers plus pre-scheduled B2B "
                                    "meetings tuned to manufacturing, BFSI, pharma and retail"),
            ProposalPain(pain="Low brand visibility in the home market",
                         teg_answer="On-ground, website and regional PR presence at the state's largest tech expo"),
        ],
        lead_generation="Pre-scheduled B2B matchmaking with India-market buyers across your target "
                        "sectors, plus a live demo space to show your AI work.",
        proof=["TEG 2024 drew 8,000+ attendees and 125+ exhibitors; TEG 2026 targets 15,000+ and 250+.",
               "The TEG Business Retreat 2025 helped facilitate ₹1.5 crore raised in one day (organizer-stated)."],
        recommended_package=ProposalPackage(
            name="3m x 6m stall",
            price_line="₹2,34,000 + GST (indicative, confirmed at booking)",
            includes=["4 exhibitor passes", "10 visitor passes", "pre-scheduled 1:1 B2B meetings",
                      "live demo space"],
            payment_plan="4 instalments of 25% (9 Apr / 30 Jun / 31 Jul / 31 Aug 2026)"),
        peer_companies=["NeuraMonks", "ViitorCloud", "Perigeon"],
        next_steps=["Review stall options at techexpogujarat.com/become-an-exhibitor",
                    "Or reply here and the team will walk you through booking"],
        contact="info@techexpogujarat.com · +91 98989 23712",
    )

    orch = Orchestrator(
        analysis=AnalysisAgent(FakeLLMClient(structured=[_CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor")])),
        research=ResearchAgent(FakeLLMClient(structured=[_Synthesis(
            sector="AI Consulting", company_size="200", hq="Ahmedabad", founder=None,
            designation=None, seniority=None, is_technical=None, person_company_match=None)]),
            tools=[KBRetriever(), _DeadWeb()]),
        persuasion=PersuasionAgent(FakeLLMClient(
            structured=[
                _PersonaChoice(persona="it_tech_service", reason="AI + software services"),
                _Analysis(reply="Absolutely — putting that together now.", detected_cta=None,
                          cta_status="offered", cta_type=None, cta_detail={}, should_handoff=False,
                          learned_facts={"target_market": "India"}, wants_proposal=True),
            ],
            responses=["Welcome back, Third Rock Techkno. A 3m x 3m stall is ₹1,17,000 + GST "
                       "(indicative, confirmed at booking). Want the options?"])),
        proposal=ProposalAgent(FakeLLMClient(structured=[proposal])),
    )
    app = create_app()
    app.dependency_overrides[get_orchestrator] = lambda: orch
    client = TestClient(app)

    posted = client.post("/inquiries", json={
        "person_name": "Tapan Patel", "company_name": "Third Rock Techkno",
        "message": "how can Tech Expo help my company grow?",
    }).json()
    sid = posted["session_id"]

    with client.websocket_connect(f"/chat/{sid}") as ws:
        assert ws.receive_json()["type"] == "opening"
        ws.send_json({"type": "message",
                      "text": "we serve mostly US clients, want India-market clients. can you send a proposal?"})
        assert ws.receive_json()["type"] == "reply"
        assert ws.receive_json()["type"] == "proposal_pending"
        att = ws.receive_json()
        assert att["type"] == "attachment" and att["version"] == 1
        pdf_url = att["pdf_url"]
        ws.send_json({"type": "end"})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()

    # PDF is real and personalized
    pdf = client.get(pdf_url)
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"

    # the session view lists it, no guardrail flags (clean proposal)
    sess = client.get(f"/sessions/{sid}").json()
    assert sess["proposals"][0]["version"] == 1
    assert sess["proposals"][0]["guardrail_flags"] == []

    # the proposal_json persisted is personalized to the conversation
    from app.store.db import SessionLocal
    from app.store.models import ProposalRow
    from sqlalchemy import select
    import anyio

    async def _check():
        async with SessionLocal() as s:
            pr = (await s.execute(select(ProposalRow))).scalars().one()
            j = pr.proposal_json
            assert "India" in j["what_you_told_us"]
            assert any("India" in p["teg_answer"] or "India" in p["pain"] for p in j["pains"])
            assert "+ GST" in j["recommended_package"]["price_line"]
            assert j["generated_on"] != "__DATE__"
    anyio.run(_check)
    get_settings.cache_clear()
```

- [ ] **Step 2: Run the E2E**

Run: `cd teg-outreach-agent && .venv/bin/python -m pytest tests/e2e/test_proposal_flow.py -q`
Expected: PASS. If `anyio.run` conflicts with the sync test, use `asyncio.run(_check())` (matches the other e2e file's pattern).

- [ ] **Step 3: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: ALL PASS (~105 tests). Fix any cross-task regressions.

- [ ] **Step 4: Update README.md**

Add a "Personalized proposal" section: what it is, that it fires mid-chat on `wants_proposal`, the `POST /sessions/{id}/proposal` endpoint, `GET /proposals/{id}.pdf`, the `PROPOSAL_*` / `EMAIL_*` env vars, and that WeasyPrint (not a browser) renders it.

- [ ] **Step 5: Commit**

```bash
cd /home/com-028/Desktop/TRT/PROJ/TECHEXPO && git add teg-outreach-agent/
git commit -m "test(proposal): end-to-end proposal flow; README

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Final verification

- [ ] `cd teg-outreach-agent && .venv/bin/python -m pytest -q` — ALL PASS
- [ ] `cd teg-outreach-agent/widget && npm test` — ALL PASS
- [ ] `.venv/bin/ruff check .` — clean (or only pre-existing findings)
- [ ] `DATABASE_URL=...teg_outreach_test .venv/bin/alembic downgrade base && ... alembic upgrade head` — clean round-trip
- [ ] `grep -RniE "playwright|selenium|chromium" teg-outreach-agent/app/` — nothing (WeasyPrint only)
- [ ] Manual: run `scripts/try_it.py` (extend it to send "can you send me a proposal?" and print the resulting attachment URL), fetch the PDF, eyeball it — company name, personalized pain points, real pricing with "+ GST", real peers, dated footer, no competitor names, no signature language.
