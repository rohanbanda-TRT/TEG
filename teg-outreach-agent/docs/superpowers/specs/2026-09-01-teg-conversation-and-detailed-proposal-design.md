# TEG Outreach — Personalized Conversation + Detailed Proposal with Charts — Design Spec

> **Status:** Approved design (2026-09-01)
> **Owner:** rohanb@thirdrocktechkno.com
> **Builds on:** `2026-08-31-teg-outreach-agent-design.md` (the agent), `2026-09-01-teg-personalized-proposal-design.md` (the proposal). Both are built on branch `feat/teg-outreach-agent`.
> **Motivation:** A real test showed the opening chat feels scripted — it acknowledged "Third Rock Techkno" as a returning exhibitor but never used Tapan Patel's role (Co-Founder & CMO, per the KB), never referenced what TRT actually does, and pitched stall prices to a person who is *on the TEG organizing team*. The KB has all of this; the pipeline just doesn't surface it into the prompts. Separately: the proposal is a thin one-pager and should be a detailed, chart-bearing document.

---

## 1. Two threads

**Thread A — Personalized, discovery-minded conversation.** Make the chat use who the person is (role, background) and what their company does, adapt tone to the relationship (a TEG organizer is a peer, not a sales target), and actively gather the facts a good proposal needs.

**Thread B — Detailed proposal with charts.** Turn the one-page proposal into a 2–4 page document with inline-SVG charts drawn from KB data.

Both threads change existing files (`kb/loader.py`, `agents/research.py`, `agents/persuasion.py`, `agents/proposal.py`, `proposal/render.py`, `proposal/templates/`). No new heavy dependencies. No DB migration.

---

## 2. Thread A — Personalized + discovery-minded conversation

### 2.1 KB loader — extract organizer/speaker person details

`app/kb/loader.py`, `_load_people`:

- **Currently:** organizer files (`organizers_team/*.md`) and speaker files (`speakers/individuals/*.md`) are parsed with `_headers()` (blockquote `> **Key:** value` lines) and `_section("## Overview")`. Organizer files have **no `## Overview`** and their key line is `> **TEG Role:**` — so `PersonRecord.role` and `.overview` come back empty.
- **Fix:**
  - `PersonRecord` gains `title: str | None` (a real job title like "Co-Founder & Chief Marketing Officer"), keeping `role` as the raw header value (e.g. "Core Organizer").
  - For organizer + speaker files:
    - `role` ← `> **TEG Role:**` or `> **Affiliation:**` header (whichever present).
    - `company` ← `> **Company:**` header (already done for some).
    - `overview` ← the **first prose paragraph** after the `---` following the blockquote header block (the file's opening bio sentence(s)). Cap ~600 chars.
    - `title` ← extracted from that first paragraph with a pattern like `^<Name> is (?:the )?([A-Z][^.]+?) (?:of|at) <Company>` → e.g. "Co-Founder and Chief Marketing Officer". If no match, `title = None`.
  - A `_first_paragraph(md: str) -> str` helper: skip the `# heading`, the `> ...` blockquote block, and `---` separators; return the first non-empty prose line/paragraph.

- **Test additions** (`tests/kb/test_loader.py`): `find_person("Tapan Patel")` → `role` contains "Organizer", `title` contains "Marketing" (or "CMO"), `overview` mentions "Third Rock Techkno" and "AI". `find_person("Ankur Warikoo")` (speaker) → `overview` non-empty.

### 2.2 ResearchAgent + KBRetriever — surface person title, company overview, insider

**Most of the downstream plumbing already exists** — the gap is that the KB loader returns empty `role`/`overview` for organizers (2.1 fixes that), so nothing flows. Specifically, today:
- `research.py` already builds `company_profile["overview"] = c_fields.get("overview")` and `person_profile["background"] = p_fields.get("overview")` and `person_profile["designation"] = p_fields.get("role") or synth.designation`.
- `research.py` already sets `relationship = "insider"` when `p_fields.get("teg_role") == "organizer"`.
- `KBRetriever` (person branch) already sets `fields["role"] = rec_p.role`, `fields["overview"] = rec_p.overview`, `fields["teg_role"] = rec_p.kind`.

**The only code change here:** in `KBRetriever`, prefer the new `title`:
```python
if rec_p.title or rec_p.role:
    fields["role"] = rec_p.title or rec_p.role
```
so a real job title ("Co-Founder & CMO"), when the loader extracted one, becomes `person_profile["designation"]`.

Everything else is verification, not new code:
- `test_research.py` — add a case: `KBRetriever` returns a person with `teg_role == "organizer"` and a `role`/`overview` → assert `dossier.relationship == "insider"`, `person_profile["designation"]` populated, `person_profile["background"]` populated, `company_profile["overview"]` populated.
- No change to the research budget, the two-track cascade, `_Synthesis`, or `ask_prospect`. If the person is genuinely unresolved (no KB, no web title), `person_profile["designation"]` stays absent and `ask_prospect` may include `"role"` as today.

### 2.3 PersuasionAgent — role-aware, relationship-adapted, discovery-minded

`app/agents/persuasion.py`.

**`_system(persona, dossier)` rewrite.** The prompt now includes:
- `person` name, `person_profile.designation` (title), `person_profile.background`, `person_profile.teg_role`.
- `company` name, `company_profile.overview`, resolved `sector`.
- `relationship` and a **tone block** keyed on it:
  - **`insider`** (person is a TEG organizer):
    > "This person is a member of the Tech Expo Gujarat organizing team. Do NOT pitch them, quote stall prices, or push a CTA unless they explicitly ask. Talk peer-to-peer, as a fellow organiser. Acknowledge you're building the event together. Ask what they need sorted for [company] this year (booth, a bigger presence, speaking, something else)."
  - **`returning`**: "This company/person has taken part in TEG before — welcome them back and reference their specific history."
  - **`cold`**: "First contact — warm and helpful, not familiar."
- **Personalization rule:**
  > "When you know the person's role, address them through it (e.g. 'As [company]'s CMO, the brand-visibility angle will matter to you...'). Reference one concrete, specific fact about [company] drawn from the overview — not a generic line. If you do NOT know their role, ask it naturally in your first reply so you can tailor the rest."
- **Discovery rule (new):**
  > "You are also gathering context for a possible tailored proposal. Over the conversation, naturally learn and record in learned_facts: the outcome they want from TEG, their target market / industries, rough team size, timeline, budget signals (without assuming a number), and any specific concern or blocker. One light question per turn — never interrogate. Prefer questions that also move the conversation forward."
- Keep the existing hard rules (no visitor price, '+ GST'/'indicative', peers only from the list, no fabricated stats/testimonials).
- Keep `_PRICING_LINE` but the prompt only surfaces it when `relationship != "insider"`.

**`init(intake, dossier)`:**
- If `dossier.ask_prospect` non-empty → unchanged (qualifying question).
- If `relationship == "insider"` → the opening is the peer check-in (no persona pitch, no price). Persona is still computed for `target_cta` bookkeeping, but the opening message is generated with the insider tone block and does not mention stalls/pricing.
- Otherwise → the persona pitch, now built from the richer prompt (role + company overview + one specific fact).
- The user-content passed to `llm.generate` gains: `Person role: <designation>`, `Person background: <background>`, `Company overview: <overview>`.

**`respond(...)`:** the system prompt gains the same tone + personalization + discovery blocks. `_Analysis.learned_facts` already flows to `state["learned_facts"]` → the session row → the ProposalAgent. No new field needed.

**Guardrails / classifier unchanged.**

### 2.4 What Thread A does NOT change
- The persona classifier (`classify_persona`), all guardrails, the pipeline structure, the data model.
- History persistence — `chat_messages` already stores every turn; `Orchestrator.run_turn` already passes the full transcript to `respond`, and `generate_proposal` passes it to the ProposalAgent.

---

## 3. Thread B — Detailed proposal with charts

### 3.1 Richer `Proposal` schema

`app/domain/schemas.py` — `Proposal` gains:
- `executive_summary: str` — 3-4 sentences: who they are (role + company), what they want, why TEG fits, the headline recommendation.
- `how_a_teg_plays_out: list[str]` — 3-6 bullets walking a participant through the 3 days (pre-event matchmaking → day 1 demos → day 2 meetings → follow-up), tuned to their goal.
- `roi_framing: str` — a careful paragraph: what one closed deal / partnership in their target market is worth relative to the stall cost, framed as "if a single engagement covers the investment many times over" — **no invented numbers, no promised outcomes**. Guardrailed.
- `sector_fit: list[SectorFitRow]` where `SectorFitRow(lever: str, weight: int)` — 4-6 rows: TEG value levers (e.g. "India-market buyer access", "pre-scheduled B2B meetings", "live demo space", "brand visibility", "investor access") each with a 1-5 `weight` for how much it matters for *this* sector, derived by the LLM from the persona pain-library. Drives the sector-fit chart.

`ProposalPain`, `ProposalPackage`, `ProposalCard` unchanged.

### 3.2 Charts — hand-built inline SVG from KB data

New module `app/proposal/charts.py`. Each function returns an `<svg>…</svg>` string (viewBox-scaled, no external refs, system-font labels, TEG palette). WeasyPrint renders inline SVG natively.

- `growth_bar() -> str` — grouped bars: **Attendees** (8,000 → 15,000) and **Exhibitors** (125 → 250), TEG 2024 vs TEG 2026. Numbers from `KnowledgeBase.goals_and_pains().evidence` / `event_info` — pass them in from the caller (KB-sourced, not hardcoded in the chart module).
- `industry_mix_bars(industries: list[str]) -> str` — horizontal bars, one per industry (the 18 from the KB), equal-length with a subtle gradient, header "Buyers attend across every sector — illustrative, not to scale". Purpose is the "not IT-only" point.
- `funnel(steps: list[tuple[str, str]]) -> str` — a 4-step downward funnel: "15,000+ visitors" → "curated 1:1 B2B meetings" → "qualified conversations" → "partnerships". Labelled "Illustrative of the TEG mechanism".
- `sector_peer_stat(sector: str, count: int) -> str` — a single big-number panel: "**N**" + "companies in [sector] already confirmed for TEG 2026" (count from `sector_wise_participation.md` via `KnowledgeBase.peers_in_sector` — actually a full count, see 3.4).
- `sector_fit_bars(rows: list[SectorFitRow]) -> str` — horizontal bars, one per lever, bar length = `weight/5`, header "How TEG's levers weigh for your sector — illustrative".

Chart style constants (colours, font, sizes) live at the top of `charts.py`. Every chart caps at ~520px wide to fit the A4 content column.

### 3.3 Template + renderer

`app/proposal/templates/proposal.html.j2` — restructured into sections:
1. Cover (unchanged: company, person + role, date, version, ref)
2. **Executive summary**
3. **Where TEG can help — your priorities** (the pain→answer table, unchanged)
4. **How your sector benefits** — the `sector_fit` chart + a one-line intro
5. **The track record** — `proof` bullets + the **growth chart**
6. **Who's in the room** — the **industry-mix chart** + `peer_companies` list + the **sector-peer stat**
7. **How a TEG plays out for you** — `how_a_teg_plays_out` bullets + the **funnel chart**
8. **The investment** — `recommended_package` as a proper table + `roi_framing`
9. **Next steps** + contact
10. Dated "not a contract" footer (unchanged)

Charts are passed into the template as pre-rendered SVG strings (Jinja `| safe`). `render_html(proposal)` builds them:
```python
charts = {
    "growth": growth_bar(attendees=(8000, 15000), exhibitors=(125, 250)),
    "industry": industry_mix_bars(INDUSTRIES),
    "funnel": funnel(FUNNEL_STEPS),
    "peer_stat": sector_peer_stat(proposal.sector, peer_count),
    "sector_fit": sector_fit_bars(proposal.sector_fit),
}
```
`render_html` gains the data it needs (industry list, peer count) — either passed in by the orchestrator or looked up from `get_kb()` inside `render.py` (acceptable — `render.py` may read the KB for static facts; it's offline and deterministic).

`render_pdf` / `render_first_page_png` unchanged (still WeasyPrint + pymupdf).

### 3.4 KB support

`app/kb/loader.py`:
- `KnowledgeBase.sector_peer_count(sector: str) -> int` — total count of companies listed under that sector in `sector_wise_participation.md` (not capped at 5 like `peers_in_sector`).
- `KnowledgeBase.industries() -> list[str]` — the 18-industry list (from `faq/faq_event.md` or `event_goals_and_problem.md` §5-adjacent, or a constant if neither parses cleanly — but prefer parsing).

### 3.5 ProposalAgent — build the richer Proposal

`app/agents/proposal.py`:
- The `build()` LLM call's prompt is extended to produce the new fields (`executive_summary`, `how_a_teg_plays_out`, `roi_framing`, `sector_fit`). The pain-library rows are also the basis for `sector_fit` weights ("weight each lever 1-5 for this sector").
- **Guardrails** — the new free-text fields (`executive_summary`, each `how_a_teg_plays_out` bullet, `roi_framing`) run through the same `check_message` + competitor/commitment checks; safe-section fallbacks extended with `executive_summary` and `roi_framing` entries in `PROPOSAL_SAFE_SECTIONS`.
- `roi_framing` gets an extra check: no rupee figure that isn't a KB-sourced price; phrases like "guaranteed", "you will close", "X deals" → violation (reuse `awaiting_as_confirmed`-style pattern or a new `overpromise` code).
- `sector_fit` — validate 4-6 rows, weights clamped to 1-5.

### 3.6 Timeout

`config/settings.py` — `proposal_hard_timeout_s` 60 → 90 (the richer call is bigger). `.env.example` updated. The `proposal_soft_timeout_s` 12 → 15.

---

## 4. Data model / API

- **No migration.** `proposals.proposal_json` is JSONB — the richer `Proposal` serializes into it unchanged.
- **No new endpoints.** The card, URLs, WS frames, retention are all unchanged.
- `ProposalCard` unchanged.

---

## 5. Testing strategy

**Thread A:**
- `tests/kb/test_loader.py` — organizer/speaker title + first-paragraph bio extraction (Tapan Patel → title has "Marketing"/"CMO", overview mentions TRT).
- `tests/agents/test_research.py` — organizer person → `dossier.relationship == "insider"`, `person_profile["designation"]` populated from KB, `company_profile["overview"]` present.
- `tests/agents/test_persuasion_init.py` — (a) insider opening contains no "₹" and no "stall"/"booth", and reads as peer ("building"/"organis"/"together" or asks what they need); (b) known-role non-insider opening contains the role word and a company-specific token; (c) unknown-role opening asks about their role.
- `tests/agents/test_persuasion_respond.py` — a discovery turn: `_Analysis.learned_facts` carries a new fact the prospect stated; `respond` merges it into `updated_state["learned_facts"]` (already tested — extend with a target-market fact).

**Thread B:**
- `tests/proposal/test_charts.py` — each chart function returns a string starting `<svg` and containing the expected labels/numbers; `sector_fit_bars` handles 4 and 6 rows; no `<script>` or `http` in any output.
- `tests/proposal/test_render.py` — `render_html` contains the new section headings, the exec summary text, and `<svg` appears ≥ 4 times; `render_pdf` still returns valid multi-page `%PDF`; `render_first_page_png` still works.
- `tests/agents/test_proposal_agent.py` — the built `Proposal` has non-empty `executive_summary`, `how_a_teg_plays_out` (≥3), `roi_framing`, `sector_fit` (4-6 rows, weights 1-5); an overpromising `roi_framing` ("you will close 5 deals") is caught and safe-fallback'd with a flag.
- `tests/kb/test_loader.py` — `sector_peer_count("Software Development & IT Services")` returns an int ≥ 5; `industries()` returns 18 items.
- **E2E** (`tests/e2e/test_proposal_flow.py`, extend) — the persisted `proposal_json` has the new fields; the PDF is ≥ 2 pages.
- No real network / no real LLM. WeasyPrint + SVG render for real.

---

## 6. Success criteria

1. When the person is a TEG organizer, the opening is a peer check-in — no stall price, no "would you like a stall", and it asks what they need for their company this year.
2. When the person's role is known (KB or web), the opening addresses them through it and references a specific fact about their company (from the overview), not a generic line.
3. When the role is unknown, the agent's first reply asks for it, and uses it from then on.
4. Across a multi-turn chat the agent gathers proposal-relevant facts into `learned_facts` (target market, team size, goal, concern) with at most one question per turn.
5. The generated proposal is 2–4 pages with an executive summary, a sector-benefit section, and at least 4 inline SVG charts (growth, industry mix, funnel, sector peers/fit) drawn from KB data and labelled illustrative where not to-scale.
6. `roi_framing` never contains a fabricated number, a guaranteed outcome, or a deal-count promise.
7. Everything still renders without a browser; no new heavy dependency; no DB migration; the full test suite stays green.
