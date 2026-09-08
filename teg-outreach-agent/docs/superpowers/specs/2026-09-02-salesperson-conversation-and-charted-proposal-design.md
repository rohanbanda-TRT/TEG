# TEG Outreach — Salesperson Conversation + Conditional Pricing + Charted Proposal — Design Spec

> **Status:** Approved design (2026-09-02)
> **Supersedes:** `2026-09-01-teg-conversation-and-detailed-proposal-design.md` in full.
> That spec's Thread A (KB-loader changes to surface organizer titles/bios) is
> obsolete — the regex loader was replaced by the agentic `KBExplorer`
> (`2026-09-01-agentic-kb-explorer-design.md`), which already surfaces
> `designation` / `background` / `teg_role` / `overview` into the dossier. Its
> Thread B (charted proposal) is carried forward here, revised.

## 1. Motivation

Live testing showed the chatbot behaving wrong for a sales context:

- It offered a tailored proposal on the **second message**, before learning
  anything about the prospect's business.
- It **volunteered stall prices and GST** unprompted, to a person who is on the
  TEG organizing team.
- The proposal PDF is a thin one-pager with **no charts**, despite the earlier
  spec calling for them.
- A pre-existing **testimonial guardrail is inverted**: it flags a correctly
  quoted, cleared testimonial (`As Sonu Sharma said, "..."`) and misses a
  fabricated one.

The chatbot's job is **conversion** — a consultative TEG business-development
rep who asks about the prospect's business, connects what they hear to what TEG
offers, and drives toward participation. Pricing is a detail that comes up *if
the prospect asks*, not a pitch.

## 2. Scope

One spec. Files changed:

| File | Change |
|---|---|
| `app/agents/persuasion.py` | salesperson `_system()` prompt; discovery + pricing + proposal-offer rules; `_Analysis` gains `asked_about_price`, `discovery` |
| `app/agents/guardrails.py` | delete regex testimonial check → LLM-backed `check_testimonial()`; pricing checks become conditional on `price_ok`; new `unsolicited_price` code |
| `app/agents/proposal.py` | richer `Proposal` build; Investment section conditional on `price_requested`; `sector_fit` weights; `overpromise` check on `roi_framing` |
| `app/proposal/charts.py` | **new** — 5 inline-SVG chart functions |
| `app/proposal/templates/proposal.html.j2` | restructured ~10 sections; charts via `\| safe`; Investment `{% if price_requested %}` |
| `app/proposal/render.py` | `render_html` builds charts; reads industry list + peer count via `KBExplorer` with a constant fallback |
| `app/domain/schemas.py` | `Proposal` + `SectorFitRow` new fields; `PersuasionTurn` carries `asked_about_price` |
| `app/orchestrator.py` | thread `price_requested` + discovery through `run_turn` → session row → `generate_proposal` |
| `app/store/models.py` + `app/store/migrations/versions/0003_*.py` | `chat_sessions.price_requested: bool` |
| `config/settings.py` + `.env.example` | `proposal_hard_timeout_s` 60→90, `proposal_soft_timeout_s` 12→15 |

**No new heavy dependency. One migration (`0003`).**

## 3. Conversation — `PersuasionAgent`

### 3.1 `_system(persona, dossier, *, learned_facts, price_requested)` rewrite

The method gains `learned_facts: dict` and `price_requested: bool` parameters
(the caller already has both). The prompt is built from these blocks:

**Role framing (always):**
> You are a business-development representative for Tech Expo Gujarat 2026
> (27–29 Nov 2026, GUCEC Ahmedabad). You are talking to a prospect who just
> enquired. Your goal is conversion — helping them see why participating is
> worth it for their business. You are consultative, not pushy: ask about their
> business, listen, and connect what you hear to what TEG offers. Write ONLY
> the message to send — one warm, specific paragraph (2–4 sentences) ending in
> a single question. No preamble, headings, or labels.

**Tone block** (keyed on `dossier.relationship`):
- `insider`: "This person is on the Tech Expo Gujarat organizing team. Do NOT
  pitch them, quote prices, or push a CTA unless they explicitly ask. Talk
  peer-to-peer as a fellow organiser. Ask what they need sorted for
  {company} this year (booth, a bigger presence, speaking, something else)."
- `returning`: "This company/person has taken part in TEG before — welcome them
  back and reference their specific history."
- `cold`: "First contact — warm and curious, not familiar."

**Personalization rule:**
> When you know the person's role, address them through it (e.g. "As {company}'s
> CMO, the brand-visibility angle will matter to you..."). Reference one
> concrete fact about {company} from the overview — not a generic line. If you
> do NOT know their role, ask it naturally in your first reply.

**Discovery rule:**
> You are also gathering context for a possible tailored proposal. Over the
> conversation, naturally learn and record in `discovery`: `goal` (the outcome
> they want from TEG), `target_market` (who they sell to / their buyer
> industries), `scale` (rough team size or similar), and optionally `timeline`
> and `concern`. One light question per turn — never interrogate. Prefer
> questions that also move the pitch forward.
>
> So far you know: {the keys present in learned_facts}. Still missing for a
> proposal: {of goal/target_market/scale, the ones absent}.

**Pricing rule:**
> Do NOT bring up cost, stall prices, sponsorship figures, or GST. Only if the
> prospect directly asks what something costs, or raises budget, may you give
> this one indicative line: "{_PRICING_LINE[persona]}" — always "+ GST" and
> "indicative, confirmed at booking". Never volunteer a number they did not ask
> for.
>
> (This block is included whether or not `price_requested`; when
> `price_requested` is true the model has already been asked and may repeat the
> line as needed.)

**Proposal-offer rule:**
> You may offer to put together a tailored proposal only once you know their
> `goal`, `target_market`, and a rough sense of `scale`, AND they have shown
> genuine interest in participating. Until then, keep the conversation going.
> If the prospect explicitly asks for a proposal / something in writing, honour
> that regardless of what you have learned.

**Hard rules (kept):** only name peer companies from the given list; never
invent statistics or testimonials; a visitor *ticket* price is never stated.

### 3.2 `_Analysis` schema

```python
class _Analysis(BaseModel):
    reply: str
    detected_cta: str | None = None
    cta_status: CtaStatus = "none"
    cta_type: str | None = None
    cta_detail: dict = {}
    should_handoff: bool = False
    discovery: dict = {}          # {goal?, target_market?, scale?, timeline?, concern?} — new this turn
    asked_about_price: bool = False   # the prospect asked about cost / raised budget this turn
    wants_proposal: bool = False
```

`discovery` is the turn-level field the model fills with facts learned *this
turn*. It replaces the old free-form `learned_facts` field on `_Analysis` (same
role, clearer keys). The accumulated state key is still `state["learned_facts"]`
and the merge is unchanged in mechanism:
`state["learned_facts"] = {**state["learned_facts"], **analysis.discovery}`.
Downstream (`generate_proposal`) still reads `cs.learned_facts`.

### 3.3 `respond()` flow

Unchanged structure. Additions:
- `system = self._system(persona, dossier, learned_facts=state["learned_facts"], price_requested=state.get("price_requested", False))`
- guardrails: `check_message(..., price_ok=state.get("price_requested", False))`
  plus `await check_testimonial(analysis.reply, self.llm)` (see §4.2)
- after analysis: `state["price_requested"] = state.get("price_requested", False) or analysis.asked_about_price`
- `PersuasionTurn` gains `asked_about_price: bool` so the orchestrator can persist it

### 3.4 `init()`

Same `_system()` call (with `learned_facts={}`, `price_requested=False`). The
opening never mentions price. The insider tone block already forbids a pitch.
The "ask-company" branch (company genuinely unresolved) is unchanged.

### 3.5 What the conversation layer does NOT change

- The persona classifier (`classify_persona`), the pipeline structure, history
  persistence, the handoff-packet generation.
- No hard turn-count or keyword gate anywhere — the proposal-offer and pricing
  rules are prompt instructions; state (`learned_facts`, `price_requested`)
  only *informs* the prompt.

## 4. Guardrails — `app/agents/guardrails.py`

### 4.1 Conditional pricing checks

`check_message(text, *, allowed_peers, persona, price_ok: bool = False)`:

- **`visitor_price`** — always runs (a visitor ticket price is never allowed in
  an agent message).
- **`missing_gst`** — always runs (any stall/sponsor ₹ figure must carry
  "+ GST").
- **`awaiting_as_confirmed`** — always runs.
- **`unsolicited_price`** (new) — when `price_ok` is False and the text contains
  a ₹ figure in a stall/sponsor/pricing context, flag it. When `price_ok` is
  True this check is skipped.
- `competitor_mention`, `commitment_language` — unchanged.

Callers: `persuasion.respond` passes `price_ok=state.get("price_requested",
False)`; `persuasion.init` passes `price_ok=False`; `proposal.build` passes
`price_ok=price_requested`.

### 4.2 LLM-backed testimonial check

**Delete** `_QUOTE`, `_ATTRIB`, `_cleared_names()` and the `uncleared_testimonial`
branch inside `check_message`. **Add:**

```python
class _TestimonialCheck(BaseModel):
    quotes_testimonial: bool
    all_cleared: bool
    problem: str = ""

_QUOTE_SPAN = re.compile(r'["“”][^"“”]{20,}["“”]')

async def check_testimonial(text: str, llm) -> GuardrailViolation | None:
    if not _QUOTE_SPAN.search(text):
        return None                     # no quote -> no LLM call (common case)
    cleared = _load_facts().cleared_testimonials
    listing = "\n".join(f'- {t.name}: "{t.quote}"' for t in cleared)
    try:
        r = await llm.generate_structured(
            system=(
                "You verify testimonial usage. You are given a MESSAGE and the "
                "ONLY testimonials that may be quoted. Decide: does the message "
                "quote a testimonial at all? If so, is every quoted testimonial "
                "one of the allowed ones, word-for-word, attributed to the "
                "correct name? A paraphrase, a wrong name, or an unknown name "
                "is NOT cleared."
            ),
            messages=[{"role": "user", "content":
                       f"MESSAGE:\n{text}\n\nALLOWED TESTIMONIALS:\n{listing}"}],
            schema=_TestimonialCheck,
        )
    except Exception:                   # noqa: BLE001 — a guardrail that cannot verify blocks
        return GuardrailViolation("uncleared_testimonial", "verification unavailable")
    if r.quotes_testimonial and not r.all_cleared:
        return GuardrailViolation("uncleared_testimonial", r.problem[:120])
    return None
```

The `_QUOTE_SPAN` pre-filter keeps the LLM call off the hot path — most agent
replies and proposal fields contain no quote.

### 4.3 `overpromise` check on `roi_framing`

New pattern used only by `proposal.build` on the `roi_framing` string:

```python
_OVERPROMISE = re.compile(
    r"\b(guarantee[sd]?|you will (?:close|win|get)|"
    r"\d+\s*(?:deals|clients|leads|partnerships)\b|"
    r"\bROI of\b|\breturn of \d)", re.I,
)
```
Match → `GuardrailViolation("overpromise", ...)`. Also reuse the existing
`_RUPEE` check: a ₹ figure in `roi_framing` that is not one of the KB-sourced
package prices → `overpromise` (ROI framing must not invent monetary numbers).

### 4.4 Fallbacks

`PROPOSAL_SAFE_SECTIONS` gains `executive_summary` and `roi_framing` entries
(per-persona, price-free, no numbers). The regenerate-once-then-safe-template
loop in `proposal.build` covers the new fields.

## 5. Proposal — `app/agents/proposal.py`, schema, charts, template

### 5.1 `Proposal` schema additions (`app/domain/schemas.py`)

```python
class SectorFitRow(BaseModel):
    lever: str
    weight: int            # 1-5, clamped

class Proposal(BaseModel):
    # ... existing fields ...
    executive_summary: str = ""
    how_a_teg_plays_out: list[str] = Field(default_factory=list)
    roi_framing: str = ""
    sector_fit: list[SectorFitRow] = Field(default_factory=list)
```

`recommended_package` unchanged in shape, but `build()` leaves `price_line` and
`payment_plan` **empty strings** when `price_requested` is False.

`PersuasionTurn` gains `asked_about_price: bool = False`.

### 5.2 `ProposalAgent.build(..., price_requested: bool)` 

New keyword arg. The `explore()` goal is unchanged (goals / mechanism /
evidence / pain library / sector peers). The LLM prompt is extended:
- produce `executive_summary` (3–4 sentences: role + company, their goal, why
  TEG fits, the headline recommendation)
- produce `how_a_teg_plays_out` (3–6 bullets walking the 3 days, tuned to their
  `goal` from `learned_facts`)
- produce `roi_framing` (value paragraph — **no numbers, no promised
  outcomes**, phrased "if a single engagement covers the investment many times
  over")
- produce `sector_fit` (4–6 `{lever, weight}` rows; weight 1–5 = how much each
  TEG lever matters for `dossier.sector`, derived from the pain library)
- **pricing:** if `price_requested`, fill `recommended_package.price_line` /
  `payment_plan` from `_PRICING_BY_PERSONA[persona]`; else set both to `""` and
  instruct "describe the package (name + what's included) but state NO figures".

**Guardrails on the new fields:** `executive_summary`, each
`how_a_teg_plays_out` bullet, and `roi_framing` run through
`check_message(price_ok=price_requested)` + `check_testimonial`. `roi_framing`
additionally runs the `overpromise` check (§4.3). `sector_fit` — validate 4–6
rows, `weight = max(1, min(5, weight))`.

Trusted-field forcing at the end is unchanged; add
`proposal.sector_fit = proposal.sector_fit[:6]` and the weight clamp.

### 5.3 `app/proposal/charts.py` (new)

Module constants at top: `NAVY = "#1b2a5b"`, `ACCENT = "#3b82f6"`,
`MUTED = "#64748b"`, `FONT = "-apple-system, Segoe UI, Roboto, sans-serif"`,
`W = 520` (max width).

Each function returns a complete `<svg viewBox=... width=...>...</svg>` string —
no external refs, no `<script>`, no `http`, system-font `<text>` labels only.

- `growth_bar(attendees: tuple[int, int], exhibitors: tuple[int, int]) -> str`
  — two grouped bar pairs (2024 vs 2026), value labels above bars, a legend.
- `industry_mix_bars(industries: list[str]) -> str` — one horizontal bar per
  industry, equal length, subtle left-to-right gradient, title "Buyers attend
  across every sector — illustrative, not to scale".
- `funnel(steps: list[tuple[str, str]]) -> str` — 4 stacked trapezoids
  narrowing downward, each with a label + sub-label, footer "Illustrative of
  the TEG mechanism".
- `sector_peer_stat(sector: str, count: int) -> str` — a panel: big `count`
  numeral + "companies in {sector} already confirmed for TEG 2026".
- `sector_fit_bars(rows: list[SectorFitRow]) -> str` — one horizontal bar per
  lever, bar length `= weight / 5 * inner_width`, weight shown as `N/5`, title
  "How TEG's levers weigh for your sector — illustrative".

### 5.4 `app/proposal/render.py`

`render_html(proposal, *, price_requested: bool)` — new keyword.

Builds the chart inputs:
- `attendees=(8000, 15000)`, `exhibitors=(125, 250)` — module constants in
  `render.py`, sourced from `event_info.md` (documented in a comment).
- `industries` and `sector_peer_count` — one
  `KBExplorer(get_llm()).explore("List the TEG target industries from
  event_overview/event_info.md, and the number of companies listed under the
  '{proposal.sector}' sector in sector_wise_participation.md. Return facts:
  industries (comma-separated), sector_peer_count (integer).")`. On miss/error,
  fall back to `_DEFAULT_INDUSTRIES` (the 18-item constant) and
  `len(proposal.peer_companies)`.
  - This is the one place outside the agents that calls the explorer. It is
    acceptable: `render.py` is offline and the call is cached-friendly. If the
    added latency is unwanted, the fallback constants alone are fine — the
    charts are labelled "illustrative".

Passes to the template: `proposal`, `price_requested`, and
`charts = {growth, industry, funnel, peer_stat, sector_fit}` (SVG strings).

`render_pdf` / `render_first_page_png` unchanged.

### 5.5 `app/proposal/templates/proposal.html.j2`

Restructured into sections (each `<section>` with an `<h2>`):

1. **Cover** — company, person + role, `generated_on`, `version`, `session_ref`
2. **Executive summary** — `{{ p.executive_summary }}`
3. **Your priorities** — the `p.pains` table (pain → TEG answer)
4. **How your sector benefits** — `{{ charts.sector_fit | safe }}` + one-line intro
5. **The track record** — `p.proof` bullets + `{{ charts.growth | safe }}`
6. **Who's in the room** — `{{ charts.industry | safe }}` + `p.peer_companies`
   list + `{{ charts.peer_stat | safe }}`
7. **How a TEG plays out for you** — `p.how_a_teg_plays_out` bullets +
   `{{ charts.funnel | safe }}`
8. **Investment** —
   `{% if price_requested %}` package table with `price_line` + `payment_plan` +
   `includes` + `{{ p.roi_framing }}`
   `{% else %}` package name + `includes` list only, then a line: "The team will
   share stall options and pricing tailored to your goals — just ask." +
   `{{ p.roi_framing }}`
   `{% endif %}`
9. **Next steps** — `p.next_steps` + `p.contact`
10. **Footer** — dated, "This is an information document, not a contract."

CSS: keep the existing TEG navy header + gradient bar; add `.chart { margin:
1rem 0; }`, `section { break-inside: avoid; }`.

### 5.6 Orchestrator threading

- `run_turn` — after `persuasion.respond`, persist
  `price_requested = turn.updated_state.get("price_requested", False)` onto the
  session row (via `SessionRepo.update_state`, new kwarg).
- `generate_proposal` — read `cs.price_requested`, pass to
  `self.proposal.build(..., price_requested=...)` and
  `render_html(..., price_requested=...)`.
- `_state_from_row` — include `"price_requested": cs.price_requested`.

### 5.7 Data model

`app/store/models.py` — `ChatSession.price_requested: Mapped[bool] =
mapped_column(default=False, server_default="false")`.

`app/store/migrations/versions/0003_price_requested.py` —
`revision="0003"`, `down_revision="0002"`,
`op.add_column("chat_sessions", sa.Column("price_requested", sa.Boolean(),
nullable=False, server_default="false"))`.

`SessionRepo.update_state` gains `price_requested: bool | None = None`.

### 5.8 Settings

`config/settings.py` — `proposal_soft_timeout_s: int = 15` (was 12),
`proposal_hard_timeout_s: int = 90` (was 60). `.env.example` updated.

## 6. Testing

### 6.1 Conversation (`tests/agents/test_persuasion_init.py`, `_respond.py`)

- **insider opening** — `dossier.relationship == "insider"` → opening has no
  `₹`, no `stall`/`booth`, and reads as peer (`build`/`organis`/`together` or
  asks what they need).
- **known-role opening** — `person_profile["designation"]` set → opening
  contains the role word and a company-specific token from the overview.
- **unknown-role opening** — `ask_prospect == ["role"]` → opening asks the role.
- **discovery turn** — prospect says "we sell to banks in the US";
  `_Analysis.discovery` carries `target_market`; `respond` merges it into
  `updated_state["learned_facts"]`.
- **pricing gate** — FakeLLM `_Analysis(reply="...no price...",
  asked_about_price=False)` for "tell me about TEG" → reply passes
  `check_message(price_ok=False)`. FakeLLM `_Analysis(reply="A 3m x 3m stall is
  ₹1,17,000 + GST (indicative, confirmed at booking)...",
  asked_about_price=True)` for "what does a stall cost?" → `updated_state`
  has `price_requested=True`; that reply passes `check_message(price_ok=True)`.
- **proposal-offer gate** — `_system()` output with
  `learned_facts={"goal": "x"}` contains "Still missing for a proposal:
  target_market, scale"; with all three keys present it does not.

### 6.2 Guardrails (`tests/agents/test_guardrails.py`)

- `check_message("... ₹1,17,000 for a stall ...", price_ok=False)` →
  `unsolicited_price` in codes.
- `check_message("... ₹1,17,000 + GST for a stall ...", price_ok=True)` → no
  `unsolicited_price`; `check_message("... ₹1,17,000 for a stall ...",
  price_ok=True)` → still `missing_gst`.
- `check_testimonial('As Sonu Sharma said, "<exact cleared quote>"',
  FakeLLMClient([_TestimonialCheck(quotes_testimonial=True, all_cleared=True)]))`
  → `None`.
- `check_testimonial('As Jane Doe said, "we tripled revenue"', FakeLLM(...
  all_cleared=False ...))` → `uncleared_testimonial`.
- `check_testimonial("no quotes here at all", fake)` → `None` **and**
  `fake.calls == []` (pre-filter, no LLM call).
- `check_testimonial('"a quote"', llm_that_raises)` → `uncleared_testimonial`
  (fail-safe).
- the `overpromise` regex: "you will close 5 deals" / "guaranteed ROI" / "₹5
  crore return" each match; "if a single partnership covers the cost several
  times over" does not.

### 6.3 Charts (`tests/proposal/test_charts.py`)

- each function → string starts `<svg`, contains expected label text / numbers.
- `growth_bar((8000, 15000), (125, 250))` contains "8,000"/"8000" and
  "15,000"/"15000" and "125" and "250".
- `sector_fit_bars` with 4 rows and with 6 rows both render; `weight=7` is
  drawn as 5/5 (clamped by the caller, but the fn must not overflow).
- no `<script>` and no `http` substring in any output.

### 6.4 Render (`tests/proposal/test_render.py`)

- `render_html(p, price_requested=True)` — contains "Executive summary",
  "Investment", `p.executive_summary`, `<svg` at least 4 times, and
  `p.recommended_package.price_line`.
- `render_html(p, price_requested=False)` — contains "Investment" section but
  NOT any `₹`; contains "share stall options and pricing".
- `render_pdf(html)` still returns bytes starting `%PDF` and (rough check) more
  than one `/Type /Page`.
- `render_first_page_png` still returns PNG bytes.
- These tests stub the explorer (or rely on the fallback constants) — no live
  Gemini.

### 6.5 Proposal agent (`tests/agents/test_proposal_agent.py`)

- built `Proposal` has non-empty `executive_summary`, `roi_framing`,
  `how_a_teg_plays_out` (≥3), `sector_fit` (4–6 rows, every `weight` in 1..5).
- `price_requested=False` → `recommended_package.price_line == ""` and
  `payment_plan == ""`.
- `price_requested=True` → `price_line` contains "+ GST".
- an overpromising `roi_framing` in the FakeLLM `Proposal` ("you will close 5
  deals") → `overpromise` in `flags` and the field replaced by the safe
  fallback.

### 6.6 E2E

- `tests/e2e/test_proposal_flow.py` (extend) — persisted `proposal_json` has
  `executive_summary`, `sector_fit`, `how_a_teg_plays_out`; the PDF is ≥ 2
  pages. Drive with `price_requested` both ways.
- `tests/e2e/test_conversation_no_price.py` (new, `integration`) — a live chat
  where the prospect never asks about cost; assert no agent turn contains `₹`.

### 6.7 Migration

- `tests/store/test_migrations.py` (or the existing schema test) — `0003`
  applies and adds `price_requested` defaulting to `False`.

## 7. Non-goals

- No change to `KBExplorer`, the research pipeline, `facts.json`, or the persona
  classifier.
- No new proposal API endpoints; `ProposalCard`, WS frames, retention unchanged.
- No hard turn-count / keyword gates — the sales behaviour is entirely
  prompt-driven, state-informed.
- Charts are hand-built SVG — no charting library, no headless browser.
- The `render.py` explorer call is optional polish; the fallback constants keep
  the charts correct if it is skipped.

## 8. Success criteria

1. The agent behaves like a consultative salesperson — asks about the
   prospect's business, connects it to TEG, drives toward participation.
2. No `₹` / pricing / GST in any agent chat message unless the prospect asked
   about cost first (LLM-judged via `asked_about_price`).
3. A tailored proposal is offered only after `goal`, `target_market` and
   `scale` are known AND interest is shown — prompt-driven, no hard gate.
4. The proposal PDF shows an Investment/pricing section with figures only when
   `price_requested`; otherwise the package is shown without any numbers.
5. The proposal is 2–4 pages with an executive summary, a sector-fit section,
   and ≥ 4 inline SVG charts drawn from KB data, labelled illustrative where
   not to scale.
6. `roi_framing` never contains a fabricated number, a guaranteed outcome, or a
   deal-count promise.
7. The testimonial guardrail passes correctly-quoted cleared testimonials and
   catches fabricated or misattributed ones (LLM-backed); it makes no LLM call
   when the text contains no quote.
8. Insider (organizer) conversations are peer check-ins — no pitch, no price.
9. Everything renders without a browser; no new heavy dependency; migration
   `0003` only; the full suite stays green.
