# TEG Inquiry Outreach Agent

FastAPI service + chat widget that researches a TEG 2026 inquiry-page prospect
(knowledge base first, then free web tools) and runs a persona-tuned,
factually-guarded conversation to drive participation.

## Conversation behaviour

The chatbot acts as a consultative TEG business-development rep: discovery-first
(it asks about the prospect's business and connects what it hears to what TEG
offers), and it **never volunteers pricing** — a stall/sponsor figure appears
in an agent message only after the prospect asks about cost (judged by the LLM,
not a keyword match). A tailored proposal is offered only once the agent has
learned the prospect's goal, target market and rough scale *and* they have shown
genuine interest; if the prospect explicitly asks for one, that is honoured. A
TEG organiser gets a peer check-in — no pitch, no price. All of this is
prompt-driven; session state (`learned_facts`, `price_requested`) only informs
the prompt.

The proposal PDF mirrors this: its **Investment** section shows figures and a
payment plan only when the prospect asked about cost; otherwise the package is
listed without numbers.

## Setup

```bash
cd teg-outreach-agent
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env      # fill DATABASE_URL, ANTHROPIC_API_KEY, TAVILY_API_KEY
createdb teg_outreach
alembic upgrade head
```

## Run

```bash
uvicorn app.main:app --reload
```

- `POST /inquiries` `{person_name, company_name}` -> `{session_id, opening_message, persona}`
- `WS /chat/{session_id}` -> live conversation
- `GET /sessions/{session_id}` -> transcript + dossier + handoff + proposals (internal)

## Personalized proposal (live PDF)

During the chat, when the prospect asks for a proposal / PDF / "something in writing"
(or accepts an offer of one), the Persuasion Agent sets `wants_proposal` and the
orchestrator runs a `ProposalAgent`: one LLM call builds a `Proposal` from the
conversation + research dossier + `event_goals_and_problem.md` (goals + per-persona
pain library). It is a 2–4 page document — executive summary, priorities table,
ROI framing (no numbers, no promised outcomes), a per-sector "how TEG's levers
weigh" section, a 3-day walk-through, and five hand-built inline-SVG charts
(growth, industry mix, funnel, sector peers, sector fit) from `charts.py`. Every
text field passes the chat guardrails plus proposal-only checks (no competitor
names, no commitment/signature language, no overpromising `roi_framing`, and an
LLM-verified testimonial check). It renders through a Jinja2 template to a PDF
with **WeasyPrint** (no browser) + a first-page PNG thumbnail (via `pymupdf`).

**Landing page.** Every proposal is also a hosted, animated web page at
`GET /p/{id}` — a React + Vite app in `proposal-page/` that fetches
`GET /proposals/{id}.json` and renders a full landing page: hero, priorities,
five scroll-revealed animated charts, a 3-day journey timeline, the ask, footer.
`ProposalAgent` writes the page copy (`hero_headline`, `hero_subline`,
`section_ctas`, `closing_cta_*`) under the same guardrails. Build it with
`cd proposal-page && npm install && npm run build` — the output goes to
`app/static/proposal/` (gitignored), which FastAPI serves; until it's built,
`GET /p/{id}` returns `503`. `cd proposal-page && npm test` runs the Vitest
component tests, `npm run test:e2e` the Playwright smoke.

The chat hands the prospect a `proposal_link` card (title + the hero subline +
"Open your proposal" + a secondary "Download PDF"). The PDF flow is unchanged:
still generated, still stored under `PROPOSAL_DIR`, still purged by retention,
still emailed if `EMAIL_ENABLED=true`. Asking again produces a new version.

- WS frames: `proposal_pending` -> `attachment` (`kind: "proposal_link"`, or `proposal_failed`)
- `POST /sessions/{id}/proposal` (body optional `{"email": "..."}`) -> `ProposalCard`
- `GET /proposals/{id}.json` · `GET /p/{id}` · `GET /proposals/{id}.pdf` · `GET /proposals/{id}/preview.png`
- Config: `PROPOSAL_MODEL` (default = `LLM_MODEL_MAIN`), `PROPOSAL_HARD_TIMEOUT_S`,
  `PROPOSAL_DIR`, `EMAIL_ENABLED`, `SMTP_*`

## Knowledge base

The agents read `../teg-kb-agent/knowledge_base` **agentically** — `KBExplorer`
(`app/kb/explorer.py`) runs a bounded LLM tool-use loop with read-only
`list_dir` / `read_file` / `grep` and navigates the KB by computing file paths
from names (the graph map is in the explorer's system prompt). No startup parse,
no regex over KB markdown in `app/`.

- **`app/kb/facts.json`** is a committed snapshot the deterministic guardrail
  layer reads (cleared testimonial wording + attributed names, canonical
  exhibitor name list). Regenerate after editing testimonials or the company
  list:

  ```bash
  python scripts/build_kb_facts.py            # rewrite the snapshot
  python scripts/build_kb_facts.py --check    # exit 1 if it is stale
  ```

  There is no CI yet, so run `--check` as part of the test command:

  ```bash
  python scripts/build_kb_facts.py --check && python -m pytest -q
  ```

- **Explorer transcripts** live in `tests/kb/transcripts/`. Replay tests run the
  recorded model turns against the *live* KB files, so a moved or renamed KB
  file fails the test. Re-record the named transcript when that happens:

  ```bash
  GEMINI_API_KEY=... python scripts/record_kb_transcript.py <name> "<goal>"
  ```

## Tests

```bash
createdb teg_outreach_test
python scripts/build_kb_facts.py --check   # KB snapshot up to date?
python -m pytest -q                        # unit + replay; integration deselected
```

Tests marked `integration` hit live Gemini / Tavily and are deselected by
default. Run them explicitly:

```bash
GEMINI_API_KEY=... TAVILY_API_KEY=... python -m pytest -q -m integration
```

## Retention

```bash
python -m app.jobs.retention   # run from cron
```

## Design docs

- Spec: `../docs/superpowers/specs/2026-08-31-teg-outreach-agent-design.md`
- Plan: `../docs/superpowers/plans/2026-08-31-teg-outreach-agent.md`
- Proposal spec: `../docs/superpowers/specs/2026-09-01-teg-personalized-proposal-design.md`
- Proposal plan: `../docs/superpowers/plans/2026-09-01-teg-personalized-proposal.md`
- Agentic KB explorer spec: `docs/superpowers/specs/2026-09-01-agentic-kb-explorer-design.md`
- Agentic KB explorer plan: `docs/superpowers/plans/2026-09-01-agentic-kb-explorer.md`
- Salesperson conversation + charted proposal spec: `docs/superpowers/specs/2026-09-02-salesperson-conversation-and-charted-proposal-design.md`
- Salesperson conversation + charted proposal plan: `docs/superpowers/plans/2026-09-02-salesperson-conversation-and-charted-proposal.md`
- Proposal landing page spec: `docs/superpowers/specs/2026-09-02-proposal-landing-page-design.md`
- Proposal landing page plan: `docs/superpowers/plans/2026-09-02-proposal-landing-page.md`
