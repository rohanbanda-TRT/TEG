# TEG Outreach — Proposal Landing Page — Design Spec

> **Status:** Approved design (2026-09-02)
> **Relationship to prior specs:** additive. The WeasyPrint PDF flow from
> `2026-09-01-teg-personalized-proposal-design.md` and
> `2026-09-02-salesperson-conversation-and-charted-proposal-design.md` stays
> **untouched**. This adds a hosted, animated landing page as a second way to
> deliver the same `Proposal` data.

## 1. Motivation

Feedback: the proposal should be "a web page, not a report" — "think like a
landing page, full fancy thing". The PDF is a document; prospects should get a
personalized, animated marketing page at a URL they can open and share.

## 2. Scope

One feature, two decoupled halves joined by a JSON contract.

**Backend (Python):**
| File | Change |
|---|---|
| `app/domain/schemas.py` | `Proposal` gains `hero_headline`, `hero_subline`, `section_ctas`, `closing_cta_headline`, `closing_cta_body` |
| `app/agents/proposal.py` | prompt writes the new fields; they run the guardrail loop; per-persona safe fallbacks |
| `app/agents/guardrails.py` | `PROPOSAL_SAFE_SECTIONS` gains `hero_headline`, `hero_subline`, `closing_cta_body` |
| `app/api/proposals.py` | new `GET /proposals/{id}.json`; new `GET /p/{id}` serving the SPA shell |
| `app/main.py` | mount `app/static/proposal/` |
| `app/orchestrator.py` | the chat attachment card becomes `kind: "proposal_link"` with `page_url` |
| `widget/src/ui.ts`, `index.ts` | render the `proposal_link` card |

**Frontend (`proposal-page/`, new node project):** React + Vite + TypeScript,
Framer Motion + a scroll-reveal hook. `npm run build` → `app/static/proposal/`.

**No new DB table, no migration.** No new heavy Python dependency. No change to
the PDF path, the `.pdf`/`.png` endpoints, `render.py`, email, or retention.

## 3. The JSON contract

### 3.1 `GET /proposals/{id}.json`

`200` — the stored proposal plus a little envelope:

```jsonc
{
  "id": "<uuid>",
  "version": 2,
  "generated_on": "2026-09-02",
  "pdf_url": "/proposals/<uuid>.pdf",
  "proposal": {
    "company": "…", "person": "…", "person_role": "CTO",
    "sector": "…", "persona": "it_tech_service",
    "hero_headline": "…", "hero_subline": "…",
    "executive_summary": "…",
    "pains": [{"pain": "…", "teg_answer": "…"}],
    "sector_fit": [{"lever": "…", "weight": 5}],
    "proof": ["…"],
    "peer_companies": ["…"],
    "how_a_teg_plays_out": ["…"],
    "roi_framing": "…",
    "recommended_package": {"name": "…", "price_line": "", "includes": ["…"], "payment_plan": ""},
    "section_ctas": {"priorities": "…", "charts": "…", "investment": "…"},
    "closing_cta_headline": "…", "closing_cta_body": "…",
    "next_steps": ["…"],
    "contact": "info@techexpogujarat.com"
  }
}
```

`proposal` is exactly `ProposalRow.proposal_json` (the serialized `Proposal`).
The envelope adds `id`, `version`, `generated_on`, `pdf_url` from the row.

`404` — no row for that id: `{"detail": "not found"}`.

CORS is already permissive (`app/main.py`).

### 3.2 Field-availability rules (SPA-side fallbacks)

A proposal generated before this spec has no hero/CTA fields. The SPA falls
back:
- `hero_headline` missing/empty → `"A proposal for {company}"`
- `hero_subline` missing/empty → first sentence of `executive_summary`
- `section_ctas[k]` missing → a fixed label per section (see §5.3)
- `closing_cta_headline` missing → `"Let's make TEG 2026 count for {company}"`
- `closing_cta_body` missing → `"Reply in the chat, or reach the team directly — we'll take it from here."`

### 3.3 Pricing

`recommended_package.price_line` empty (the prospect never asked about cost)
⇒ the SPA's Ask section shows the package name + `includes` only, plus
"The team will share stall options and pricing tailored to your goals." When
`price_line` is non-empty the SPA shows it + `payment_plan`. The SPA needs no
`price_requested` flag — it checks `price_line`.

### 3.4 Chart data

The five charts need: growth numbers (TEG 2024 → 2026), the 18-industry list,
and a sector-peer count. These are **KB-static and labelled illustrative**, so
the SPA holds them as constants in `lib/chartData.ts`:

```ts
export const GROWTH = { attendees: [8000, 15000], exhibitors: [125, 250] };
export const INDUSTRIES = [
  "Manufacturing", "Automobile", "Power & Energy", "Agriculture", "Education",
  "Healthcare", "Electronics", "Pharmaceutical", "Jewellery", "Textile",
  "Retail", "Logistics", "Finance", "IT & Software", "AI & Machine Learning",
  "Fintech", "Real Estate", "Cybersecurity",
];
```

The sector-peer count is `proposal.peer_companies.length` (or a small "5+" when
that list is capped). If these ever need to be dynamic they move into the JSON
envelope later — out of scope now.

## 4. Backend

### 4.1 `Proposal` schema (`app/domain/schemas.py`)

Add to `Proposal`:

```python
    hero_headline: str = ""
    hero_subline: str = ""
    section_ctas: dict[str, str] = Field(default_factory=dict)
    closing_cta_headline: str = ""
    closing_cta_body: str = ""
```

### 4.2 `ProposalAgent.build()` (`app/agents/proposal.py`)

The `user` prompt gains:

```
Also write landing-page copy:
- hero_headline: a punchy 6-12 word line that names the outcome for {company}
  (e.g. "Turn TEG 2026 into your India-market pipeline"). No numbers, no
  guaranteed outcomes.
- hero_subline: one sentence expanding the headline.
- closing_cta_headline: a short line for the final call-to-action section.
- closing_cta_body: 1-2 sentences pushing the reader to act (reply in chat /
  reach the team). No numbers, no promises.
- section_ctas: a JSON object with short button labels for keys
  "priorities", "charts", "investment".
```

Guardrails — add to `all_violations`'s text list:
`("hero_headline", p.hero_headline)`, `("hero_subline", p.hero_subline)`,
`("closing_cta_body", p.closing_cta_body)` — run through
`check_message(price_ok=price_requested)`. `hero_headline`, `hero_subline`,
`closing_cta_body` **also** run `check_overpromise`. `check_testimonial`'s blob
gains `hero_subline` + `closing_cta_body`.

Safe fallbacks in the violation handler:
`if "hero_headline" in bad: proposal.hero_headline = PROPOSAL_SAFE_SECTIONS["hero_headline"][persona]`
— same for `hero_subline`, `closing_cta_body`.

`section_ctas`: not free-text-guardrailed (short button labels); clamp to the
three known keys, drop anything else, truncate each value to 40 chars.

### 4.3 `PROPOSAL_SAFE_SECTIONS` (`app/agents/guardrails.py`)

Add three keys, per-persona, price-free, no numbers:

```python
    "hero_headline": {
        "it_tech_service": "Put your technology in front of the buyers you want",
        "ai_startup": "Get your AI in front of buyers and investors in three days",
        "non_tech_sponsor": "Own a category at Gujarat's largest tech expo",
        "visitor": "Three days of technology you can actually use",
    },
    "hero_subline": {
        "it_tech_service": "Tech Expo Gujarat 2026 concentrates cross-industry decision-makers and pre-scheduled meetings into one focused event.",
        "ai_startup": "The Catalyst Zone and investor track give a small team a fast route to buyers and capital.",
        "non_tech_sponsor": "A category-exclusive association ties your brand to the region's innovation story across the venue, digital and press.",
        "visitor": "Meet 250+ exhibitors across every industry in one place, then follow up through the TEG app.",
    },
    "closing_cta_body": {
        "it_tech_service": "Reply in the chat, or reach the team directly — we'll tailor the stall options to your goals and take it from there.",
        "ai_startup": "Reply in the chat to ask about the Catalyst Zone or the pitch track — we'll help you pick the right fit.",
        "non_tech_sponsor": "Reply in the chat to start a sponsorship conversation — we'll map the category options with you.",
        "visitor": "Reply in the chat when you're ready and we'll send the registration link.",
    },
```

### 4.4 API (`app/api/proposals.py`)

```python
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

_SPA_INDEX = Path(__file__).resolve().parents[2] / "app" / "static" / "proposal" / "index.html"


@router.get("/proposals/{proposal_id}.json")
async def get_proposal_json(proposal_id: uuid.UUID) -> JSONResponse:
    async with SessionLocal() as s:
        row = await ProposalRepo(s).get(proposal_id)
    if row is None:
        raise HTTPException(status_code=404, detail="not found")
    return JSONResponse({
        "id": str(row.id),
        "version": row.version,
        "generated_on": row.proposal_json.get("generated_on"),
        "pdf_url": f"/proposals/{row.id}.pdf",
        "proposal": row.proposal_json,
    })


@router.get("/p/{proposal_id}")
async def get_proposal_page(proposal_id: uuid.UUID) -> HTMLResponse:
    if not _SPA_INDEX.is_file():
        raise HTTPException(status_code=503, detail="proposal page not built")
    return HTMLResponse(_SPA_INDEX.read_text("utf-8"))
```

The `{proposal_id}` in `/p/{id}` is validated as a uuid but otherwise the SPA
reads the id from `location.pathname` and fetches `.json` itself.

`app/main.py` — after the existing `/demo` mount:

```python
    proposal_static = Path(__file__).parent / "static" / "proposal"
    if proposal_static.is_dir():
        app.mount("/static/proposal", StaticFiles(directory=str(proposal_static)), name="proposal-static")
```

### 4.5 Chat handoff (`app/orchestrator.py`)

In `generate_proposal`, replace the `card` dict and the agent message:

```python
            page_url = f"/p/{row.id}"
            pdf_url = f"/proposals/{row.id}.pdf"
            card = {
                "kind": "proposal_link",
                "proposal_id": str(row.id),
                "version": version,
                "page_url": page_url,
                "pdf_url": pdf_url,
                "title": f"Your TEG 2026 proposal for {proposal.company}",
                "blurb": proposal.hero_subline or proposal.executive_summary[:160],
            }
            await mr.append(
                session_id, "agent",
                f"I've put together a proposal for {proposal.company} — open it here: {page_url}",
                turn_index=await mr.next_turn_index(session_id),
                attachment=card,
            )
```

`app/domain/schemas.py` — `ProposalCard` gains `page_url: str = ""`,
`title: str = ""`, `blurb: str = ""` (`kind` default stays `"proposal"`; the
orchestrator sets `kind="proposal_link"` on the returned card and the stored
attachment dict). `generate_proposal` builds the `ProposalCard` with these
populated and returns it. The `.pdf`/`.png` endpoints and PDF file storage are
unchanged — the PDF is still generated and still linked from the card.

### 4.6 Widget (`widget/src/`)

`ui.ts` — a `renderProposalLink(card)` that builds a card element: title,
blurb, a primary "Open your proposal" `<a href={page_url} target="_blank">`,
and a secondary "Download PDF" link. `index.ts` — the WS `attachment` handler
branches on `card.kind`: `"proposal_link"` → `renderProposalLink`, the old
`"proposal"` kind kept for back-compat.

## 5. Frontend — `proposal-page/`

### 5.1 Project

- Vite + React + TypeScript. `vite.config.ts`: `base: "/static/proposal/"`,
  `build.outDir: "../app/static/proposal"`, `build.emptyOutDir: true`.
- Deps: `react`, `react-dom`, `framer-motion`. Dev: `vite`,
  `@vitejs/plugin-react`, `typescript`, `vitest`, `@testing-library/react`,
  `@testing-library/jest-dom`, `jsdom`, `@playwright/test`.
- `VITE_API_BASE` (default `""` = same origin) — every fetch is
  `${API_BASE}/proposals/...`. Keeps the app deployable off a separate host.

### 5.2 File structure

```
proposal-page/
  index.html                 — <div id="root">, loads /src/main.tsx
  vite.config.ts
  src/
    main.tsx                 — read id from location.pathname; fetch; render <App/> or <ErrorState/>
    App.tsx                  — payload context + the section stack + footer
    lib/api.ts               — fetchProposal(id): Promise<Payload>; throws on !ok
    lib/types.ts             — Payload, Proposal, Pain, SectorFitRow (mirror §3.1)
    lib/chartData.ts         — GROWTH, INDUSTRIES (§3.4)
    lib/fallbacks.ts         — heroHeadline(p), heroSubline(p), sectionCta(p, key), closingHeadline(p), closingBody(p)
    hooks/useReveal.ts       — IntersectionObserver -> boolean (once true, stays)
    hooks/useCountUp.ts      — (target, active) -> displayed number, rAF-driven
    theme.css                — CSS custom properties (§6), base type + layout
    components/
      Section.tsx            — <section> with alt-band prop + Reveal wrapper
      Reveal.tsx             — Framer motion.div, whileInView fade-up, reduced-motion aware
      CtaButton.tsx          — <a> styled; variant primary|ghost
      StatBadge.tsx          — circular badge + useCountUp numeral + label
      charts/GrowthBars.tsx
      charts/IndustryMix.tsx
      charts/Funnel.tsx
      charts/SectorFitBars.tsx
      charts/PeerStat.tsx
    sections/
      Hero.tsx              — company, headline, subline, primary CTA; entrance animation
      Priorities.tsx        — pain -> teg_answer cards, staggered reveal + section CTA
      Charts.tsx            — the 5 chart blocks, each in a Section, reveal-animated
      Journey.tsx           — how_a_teg_plays_out as a vertical numbered timeline
      TheAsk.tsx            — recommended_package (+ conditional price) + roi_framing + closing CTA
    states/
      Loading.tsx           — branded skeleton (TEG wordmark + shimmer bands)
      ErrorState.tsx        — "This proposal link isn't valid or has expired" + link to techexpogujarat.com
  src/__fixtures__/proposal.json   — a complete Payload for tests
  src/**/*.test.tsx                — Vitest component tests
  e2e/smoke.spec.ts                — Playwright: build, serve, load, assert
```

### 5.3 Sections, top to bottom

1. **Hero** (`--teg-navy` band, white text) — `{hero}` headline (display size),
   `{subline}`, a "Talk to the team" primary CTA
   (`mailto:{contact}?subject=TEG 2026 — {company}`). Small line: "Prepared for
   {person}{, role} · {sector} · v{version} · {generated_on}". Headline +
   subline fade-up on mount, CTA 200ms later.
2. **Executive summary** (`--teg-bg`) — one paragraph, reveal-animated.
3. **Priorities** (`--teg-bg-alt`) — heading "Where TEG moves the needle for
   you"; one card per `pains[]` (`pain` bold, `teg_answer` below); staggered
   reveal. Section CTA button: `section_ctas.priorities` or `"See the plan"` →
   scrolls to Journey.
4. **The numbers** (`--teg-bg`) — heading; then five reveal blocks:
   `GrowthBars`, `IndustryMix`, `SectorFitBars` (from `sector_fit`), `Funnel`,
   `PeerStat` (`peer_companies` as a logo-less name grid + a `StatBadge` with
   the count). Each chart animates its bars/segments from zero when revealed;
   `StatBadge` counts up. Section CTA: `section_ctas.charts` or
   `"Explore the numbers"` (a no-op / scroll cue).
5. **Your three days** (`--teg-bg-alt`) — `how_a_teg_plays_out[]` as a vertical
   numbered timeline with connecting line; each step reveals in sequence.
6. **The ask** (`--teg-navy` band) — `recommended_package.name` + `includes`
   list; `{% if price_line %}` show `price_line` + `payment_plan`
   `{% else %}` "The team will share stall options and pricing tailored to your
   goals."; then `roi_framing`; then `closing_cta_headline` (display) +
   `closing_cta_body` + a primary CTA (mailto). Section CTA:
   `section_ctas.investment` or `"Get your quote"`.
7. **Footer** (`--teg-bg`) — `contact`, `next_steps[]` as links, a small
   "This is an information document, not a contract" line, "Download as PDF"
   link (`pdf_url`), TEG wordmark.

### 5.4 Data flow

`main.tsx` → parse `id` from `location.pathname` (last segment) → if not a uuid
shape, render `<ErrorState/>` → else `fetchProposal(id)` → on resolve render
`<App payload=.../>`, on reject render `<ErrorState/>`, while pending render
`<Loading/>`. `App` puts the payload in a context; sections read it; the
fallback helpers (`lib/fallbacks.ts`) are applied at the point of use, not
mutated into the payload.

### 5.5 Animation

- Framer Motion throughout. `Reveal` = `motion.div` with
  `initial={{opacity:0, y:56}}`, `whileInView={{opacity:1, y:0}}`,
  `viewport={{once:true, amount:0.3}}`, `transition={{duration:0.5}}`.
- Staggered lists: parent `variants` with `staggerChildren: 0.08`.
- `useCountUp`: rAF ease-out from 0 to target over ~1.1s once `active`.
- Charts: bar `motion.rect` / funnel `motion.path` with `scaleY` / `pathLength`
  from 0, triggered by the section's reveal.
- `prefers-reduced-motion: reduce` → a top-level flag disables `Reveal`'s
  travel + fade (renders final state), `useCountUp` snaps to target, charts
  render full. Framer's `useReducedMotion()` drives this.

### 5.6 Error / loading / empty

- **Loading:** `<Loading/>` — TEG wordmark + three shimmer bands, no spinner.
- **404 / fetch fail:** `<ErrorState/>` — centred card: "This proposal link
  isn't valid or has expired." + `<a href="https://www.techexpogujarat.com">`.
- **Partial data:** the fallback helpers cover missing hero/CTA fields. Empty
  arrays (`pains`, `sector_fit`, `peer_companies`) → that section/chart is
  skipped entirely (no empty shell).

## 6. Visual style

From `techexpogujarat.com`: light, minimalist, flat, generous whitespace,
strong type hierarchy, big bold numerals, circular badge motifs, arrow/flow
between steps.

```css
:root {
  --teg-navy:   #1b2a5b;
  --teg-ink:    #0f1729;
  --teg-cyan:   #17b3c9;
  --teg-gold:   #f3a712;
  --teg-bg:     #ffffff;
  --teg-bg-alt: #f5f7fb;
  --teg-line:   #d7dbe6;
  --font: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
```

- Navy for headings + the two dark bands (hero, the ask). Cyan for chart
  highlights + links. Gold for CTA buttons + stat emphasis. No large gradients.
- Display type: 40–56px bold for hero, 26–32px for section headers; body
  16–18px, line-height 1.6.
- CTA button: gold fill, navy text, generous padding, subtle lift on hover.
- Cards: white, 1px `--teg-line` border, ~10px radius, soft shadow.
- Fully responsive, single column, mobile-first; hero display type and chart
  widths scale down; the dark bands keep their contrast.

The exact layout rhythm, card shapes and chart proportions are worked out
during implementation with the `frontend-design` skill, anchored to this
palette and these motifs.

## 7. Testing

### 7.1 Frontend (`proposal-page/`)

**Vitest component tests** (`src/**/*.test.tsx`), against
`src/__fixtures__/proposal.json`:
- `Hero` renders the company + headline; falls back to `"A proposal for X"`
  when `hero_headline` is `""`.
- `TheAsk` shows `price_line` when present; shows the "team will share pricing"
  line when `price_line` is `""`.
- `Priorities` renders one card per `pains[]`; renders nothing when `pains` is
  `[]`.
- `SectorFitBars` renders a bar per `sector_fit[]` row; clamps a weight of 9
  to the full width.
- `<App>` with the fixture renders the hero text and at least one chart.
- `main` logic: a non-uuid path segment → `<ErrorState/>`; a rejected fetch →
  `<ErrorState/>`.
- reduced-motion: with `matchMedia` stubbed to `reduce`, `Reveal` renders its
  children immediately (no `opacity:0`).

**Playwright smoke** (`e2e/smoke.spec.ts`):
- `npm run build` (outputs to `../app/static/proposal/`); a tiny test HTTP
  server serves that directory AND a stub `GET /proposals/:id.json` returning
  `src/__fixtures__/proposal.json` AND a `GET /p/:id` route that returns
  `app/static/proposal/index.html` (mirroring the real FastAPI route);
  navigate to `/p/<fixture-id>`; assert the hero headline text, at least one
  `svg` inside a chart section, and a `a[href^="mailto:"]` are visible.

### 7.2 Backend (`tests/`)

- `tests/api/test_proposals_api.py` — `GET /proposals/{id}.json` after a
  proposal is created: `200`, body has `id`, `version`, `pdf_url`, and
  `proposal.company`; `GET /proposals/{random-uuid}.json` → `404`.
- `tests/api/test_proposals_api.py` — `GET /p/{uuid}` → `503` when the SPA
  isn't built (the default in CI), or `200 text/html` when
  `app/static/proposal/index.html` exists (guarded by a `Path.is_file()`
  skip).
- `tests/agents/test_proposal_agent.py` — built `Proposal` has non-empty
  `hero_headline`, `hero_subline`, `closing_cta_body`; an overpromising
  `hero_headline` ("you will 10x your pipeline, guaranteed") → `overpromise`
  in `flags` and the field replaced by the safe fallback; `section_ctas`
  clamped to the three known keys.
- `tests/e2e/test_proposal_flow.py` (extend) — the chat attachment card has
  `kind == "proposal_link"`, `page_url == "/p/<id>"`, keeps `pdf_url`; the
  agent message contains `/p/`.

### 7.3 What is NOT re-tested

The PDF path (`render.py`, `.pdf`/`.png` endpoints, email) — unchanged, its
existing tests stand.

## 8. Non-goals

- No intent tracking / CTA-click logging / `proposal_interest` table. CTAs are
  plain links (`mailto:` and the real techexpogujarat.com URLs).
- No SSR / per-proposal stored HTML. One static shell + live JSON fetch.
- No screenshot/thumbnail of the web page for the chat card.
- No auth on the page — the id is the capability (same as the current
  `.pdf` link).
- No change to how a proposal is *generated* or *triggered* — only what the
  data feeds and how it's delivered.
- The chart data (`GROWTH`, `INDUSTRIES`) stays a frontend constant; not moved
  into the JSON.

## 9. Success criteria

1. `GET /p/{id}` opens a single-page, animated landing page for that proposal —
   hero, priorities, the five charts (scroll-revealed, animated), the 3-day
   journey, the ask, footer.
2. The page reads live from `GET /proposals/{id}.json`; regenerating the
   proposal (new version) is reflected on the next page load.
3. The design matches the TEG brand: light, flat, navy/cyan/gold, big numerals,
   circular stat badges.
4. Animations respect `prefers-reduced-motion`.
5. Pricing shows on the page only when the prospect asked about cost (same rule
   as the PDF) — driven by whether `price_line` is empty.
6. The chat hands the prospect a `proposal_link` card: title, the hero subline
   as the blurb, an "Open your proposal" button to `/p/{id}`, and a secondary
   PDF link.
7. `hero_headline` / `hero_subline` / `closing_cta_body` never contain a
   fabricated number or a guaranteed outcome (guardrailed).
8. The WeasyPrint PDF flow is unchanged and its tests still pass.
9. Old proposals (no hero/CTA fields) still render, via SPA fallbacks.
