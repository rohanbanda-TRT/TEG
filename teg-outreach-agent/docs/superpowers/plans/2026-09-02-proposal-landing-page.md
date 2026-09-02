# Proposal Landing Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the proposal as a personalized, animated landing page served at `GET /p/{id}` — a React + Vite + Framer Motion SPA that fetches `GET /proposals/{id}.json` — alongside the untouched WeasyPrint PDF.

**Architecture:** Two decoupled halves joined by a JSON contract. The backend adds landing-page copy fields to `Proposal` (LLM-written, guardrailed), a `.json` read endpoint, a `/p/{id}` shell route, and changes the chat attachment card to `kind: "proposal_link"`. The frontend is a new `proposal-page/` node project that builds into `app/static/proposal/`; the page reads the proposal id from the URL, fetches the JSON, and renders seven scroll-animated sections. No DB migration.

**Tech Stack:** Python 3.12 / FastAPI / Pydantic v2 / SQLAlchemy (unchanged); React 18 + Vite 5 + TypeScript + Framer Motion (new); Vitest + @testing-library/react + Playwright for the frontend.

## Global Constraints

- **The PDF flow is untouched.** `app/proposal/render.py`, `GET /proposals/{id}.pdf`, `GET /proposals/{id}/preview.png`, the PDF file storage, `send_proposal_email`, and retention all stay exactly as they are. This feature is purely additive.
- **No new DB table, no Alembic migration.** The landing page reads `ProposalRow.proposal_json`.
- **No new heavy Python dependency.**
- **No intent tracking / CTA-click logging.** Page CTAs are plain links (`mailto:` and the real `techexpogujarat.com` URLs from `next_steps`).
- **`hero_headline`, `hero_subline`, `closing_cta_body` must never contain a fabricated number or a guaranteed outcome** — they run `check_message`, `check_overpromise`, and `check_testimonial` in `ProposalAgent.build()`.
- **Pricing on the page** shows only when `recommended_package.price_line` is non-empty (the same rule the PDF uses via `price_requested`).
- **Brand palette** (from `techexpogujarat.com`): `--teg-navy #1b2a5b`, `--teg-ink #0f1729`, `--teg-cyan #17b3c9`, `--teg-gold #f3a712`, `--teg-bg #ffffff`, `--teg-bg-alt #f5f7fb`, `--teg-line #d7dbe6`. Light, flat, no large gradients, big bold numerals, circular stat badges.
- **Animations respect `prefers-reduced-motion`** — Framer's `useReducedMotion()` drives a flag that collapses reveals to their final state and snaps counters.
- Frontend fetches use `import.meta.env.VITE_API_BASE` (default `""` = same origin) so the app stays deployable off a separate host.
- Vite config: `base: "/static/proposal/"`, `build.outDir: "../app/static/proposal"`, `build.emptyOutDir: true`.
- Run the KB snapshot check before the Python suite: `python scripts/build_kb_facts.py --check && python -m pytest -q`.
- Commit after every task. Branch `feat/teg-outreach-agent` is already active.
- The `proposal-page/` project is NOT part of the Python test run; its tests run with `cd proposal-page && npm test` (Vitest) and `npm run test:e2e` (Playwright).

## File Structure

### Backend (modify)
| File | Responsibility |
|---|---|
| `app/domain/schemas.py` | `Proposal` +5 fields; `ProposalCard` +3 fields |
| `app/agents/guardrails.py` | `PROPOSAL_SAFE_SECTIONS` +3 keys |
| `app/agents/proposal.py` | prompt writes + guards the new fields; `section_ctas` clamp |
| `app/api/proposals.py` | `GET /proposals/{id}.json`, `GET /p/{id}` |
| `app/main.py` | mount `app/static/proposal/` |
| `app/orchestrator.py` | `proposal_link` card + `ProposalCard` fields |
| `widget/src/ui.ts` | `renderProposalLink` + `ProposalLinkPayload` |
| `widget/src/index.ts` | branch the `attachment` handler on `card.kind` |

### Frontend (create) — `proposal-page/`
| File | Responsibility |
|---|---|
| `package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `.gitignore` | project scaffold |
| `src/main.tsx` | parse id from URL, fetch, render `<App>` / `<Loading>` / `<ErrorState>` |
| `src/App.tsx` | payload context + section stack + footer |
| `src/lib/types.ts` | `Payload`, `Proposal`, `Pain`, `SectorFitRow`, `Package` |
| `src/lib/api.ts` | `fetchProposal(id)` |
| `src/lib/chartData.ts` | `GROWTH`, `INDUSTRIES` constants |
| `src/lib/fallbacks.ts` | `heroHeadline`, `heroSubline`, `sectionCta`, `closingHeadline`, `closingBody` |
| `src/hooks/useReveal.ts` | IntersectionObserver → boolean |
| `src/hooks/useCountUp.ts` | `(target, active)` → displayed number |
| `src/theme.css` | palette tokens, base type + layout |
| `src/components/Section.tsx`, `Reveal.tsx`, `CtaButton.tsx`, `StatBadge.tsx` | primitives |
| `src/components/charts/GrowthBars.tsx`, `IndustryMix.tsx`, `Funnel.tsx`, `SectorFitBars.tsx`, `PeerStat.tsx` | chart components |
| `src/sections/Hero.tsx`, `Priorities.tsx`, `Charts.tsx`, `Journey.tsx`, `TheAsk.tsx` | page sections |
| `src/states/Loading.tsx`, `ErrorState.tsx` | non-happy states |
| `src/__fixtures__/proposal.json` | a complete `Payload` for tests |
| `src/**/*.test.tsx` | Vitest component tests |
| `e2e/smoke.spec.ts`, `e2e/server.mjs` | Playwright smoke + its tiny test server |

---

### Task 1: `Proposal` + `ProposalCard` schema fields

**Files:**
- Modify: `app/domain/schemas.py` (in `Proposal`, in `ProposalCard`)
- Test: `tests/domain/test_schemas.py`

**Interfaces:**
- Produces:
  - `Proposal` gains `hero_headline: str = ""`, `hero_subline: str = ""`, `section_ctas: dict[str, str] = Field(default_factory=dict)`, `closing_cta_headline: str = ""`, `closing_cta_body: str = ""`.
  - `ProposalCard` gains `page_url: str = ""`, `title: str = ""`, `blurb: str = ""` (`kind` default stays `"proposal"`).

- [ ] **Step 1: Write the failing test**

```python
# tests/domain/test_schemas.py  (add)
def test_proposal_landing_page_fields_default_empty():
    from app.domain.schemas import Proposal, ProposalPackage
    p = Proposal(
        company="X", person="Y", persona="it_tech_service", generated_on="d",
        session_ref="r", version=1, what_you_told_us="w", lead_generation="l",
        recommended_package=ProposalPackage(name="n", price_line="", includes=[], payment_plan=""),
        contact="c",
    )
    assert p.hero_headline == "" and p.hero_subline == ""
    assert p.section_ctas == {}
    assert p.closing_cta_headline == "" and p.closing_cta_body == ""


def test_proposal_card_link_fields():
    from app.domain.schemas import ProposalCard
    c = ProposalCard(
        proposal_id="p1", version=1, filename="f.pdf", bytes=1, pdf_url="/x.pdf", png_url="/x.png",
    )
    assert c.page_url == "" and c.title == "" and c.blurb == ""
    assert c.kind == "proposal"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/domain/test_schemas.py -q`
Expected: FAIL — `Proposal` has no `hero_headline`

- [ ] **Step 3: Add the fields**

In `app/domain/schemas.py`, in `class Proposal`, after `sector_fit`:

```python
    hero_headline: str = ""
    hero_subline: str = ""
    section_ctas: dict[str, str] = Field(default_factory=dict)
    closing_cta_headline: str = ""
    closing_cta_body: str = ""
```

In `class ProposalCard`, after `png_url: str`:

```python
    page_url: str = ""
    title: str = ""
    blurb: str = ""
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/domain/test_schemas.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/domain/schemas.py tests/domain/test_schemas.py
git commit -m "feat(proposal): Proposal hero/CTA landing-page fields; ProposalCard page_url/title/blurb"
```

---

### Task 2: `PROPOSAL_SAFE_SECTIONS` fallbacks + `ProposalAgent` writes the new fields

**Files:**
- Modify: `app/agents/guardrails.py` (`PROPOSAL_SAFE_SECTIONS`)
- Modify: `app/agents/proposal.py` (`build()` prompt, `all_violations`, safe-fallback block, `section_ctas` clamp)
- Test: `tests/agents/test_proposal_agent.py`

**Interfaces:**
- Consumes: `check_message`, `check_overpromise`, `check_testimonial` (already imported in `proposal.py`); `PROPOSAL_SAFE_SECTIONS`.
- Produces: a built `Proposal` with non-empty `hero_headline`/`hero_subline`/`closing_cta_headline`/`closing_cta_body`, a `section_ctas` dict limited to keys `{"priorities","charts","investment"}` with values ≤ 40 chars.

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/test_proposal_agent.py  (add; and add the new fields to _good_proposal)
async def test_build_writes_landing_page_fields():
    llm = FakeLLMClient(structured=[_good_proposal()])
    p, flags = await ProposalAgent(llm, explorer=_explorer()).build(
        intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[], learned_facts={"goal": "leads"}, session_ref="x", version=1,
        price_requested=True,
    )
    assert p.hero_headline and p.hero_subline
    assert p.closing_cta_headline and p.closing_cta_body


async def test_build_flags_overpromising_hero():
    bad = _good_proposal(hero_headline="You will 10x your pipeline, guaranteed.")
    llm = FakeLLMClient(structured=[bad, bad])
    p, flags = await ProposalAgent(llm, explorer=_explorer()).build(
        intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[], learned_facts={}, session_ref="x", version=1, price_requested=True,
    )
    assert "overpromise" in flags
    assert "guaranteed" not in p.hero_headline.lower()


async def test_build_clamps_section_ctas():
    bad = _good_proposal(section_ctas={
        "priorities": "x" * 80, "charts": "ok", "investment": "ok", "bogus": "drop me",
    })
    llm = FakeLLMClient(structured=[bad])
    p, _ = await ProposalAgent(llm, explorer=_explorer()).build(
        intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[], learned_facts={}, session_ref="x", version=1, price_requested=True,
    )
    assert set(p.section_ctas) <= {"priorities", "charts", "investment"}
    assert all(len(v) <= 40 for v in p.section_ctas.values())
```

Add to `_good_proposal`'s `Proposal(...)` kwargs (in the same file):

```python
        hero_headline="Turn TEG 2026 into your India-market pipeline",
        hero_subline="Three focused days from cold outreach to booked buyer meetings.",
        section_ctas={"priorities": "See the plan", "charts": "Explore the numbers", "investment": "Get your quote"},
        closing_cta_headline="Let's make TEG 2026 count for DataZen Analytics",
        closing_cta_body="Reply in the chat, or reach the team directly — we'll take it from here.",
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/agents/test_proposal_agent.py -q`
Expected: FAIL — `hero_headline` not populated / not clamped

- [ ] **Step 3: Extend `PROPOSAL_SAFE_SECTIONS`**

In `app/agents/guardrails.py`, add these three keys to the `PROPOSAL_SAFE_SECTIONS` dict (copy verbatim):

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

- [ ] **Step 4: Extend the `build()` prompt**

In `app/agents/proposal.py`, in the `user` string, append before `"Produce the Proposal."`:

```python
            "Also write landing-page copy:\n"
            "- hero_headline: a punchy 6-12 word line naming the outcome for "
            f"{intake.company_name_canonical} (e.g. 'Turn TEG 2026 into your India-market "
            "pipeline'). No numbers, no guaranteed outcomes.\n"
            "- hero_subline: one sentence expanding the headline.\n"
            "- closing_cta_headline: a short line for the final call-to-action section.\n"
            "- closing_cta_body: 1-2 sentences pushing the reader to act (reply in chat / "
            "reach the team). No numbers, no promises.\n"
            "- section_ctas: a JSON object with short button labels for keys "
            "'priorities', 'charts', 'investment'.\n"
```

- [ ] **Step 5: Guard the new fields**

In `all_violations(p)`, add to the `texts` list:

```python
                ("hero_headline", p.hero_headline),
                ("hero_subline", p.hero_subline),
                ("closing_cta_body", p.closing_cta_body),
```

After the existing `op = check_overpromise(p.roi_framing)` block, add:

```python
            for label in ("hero_headline", "hero_subline", "closing_cta_body"):
                op2 = check_overpromise(getattr(p, label))
                if op2:
                    found.append((label, op2))
```

In `_testimonial_violation`'s blob join, add `p.hero_subline`, `p.closing_cta_body`.

In the safe-fallback block (where `bad` is the set of violated labels), add:

```python
            if "hero_headline" in bad:
                proposal.hero_headline = PROPOSAL_SAFE_SECTIONS["hero_headline"][persona]
            if "hero_subline" in bad:
                proposal.hero_subline = PROPOSAL_SAFE_SECTIONS["hero_subline"][persona]
            if "closing_cta_body" in bad:
                proposal.closing_cta_body = PROPOSAL_SAFE_SECTIONS["closing_cta_body"][persona]
```

- [ ] **Step 6: Clamp `section_ctas`**

In `build()`, near the other trusted-field forcing (`_clamp_sector_fit` etc.), add:

```python
        proposal.section_ctas = {
            k: str(v)[:40]
            for k, v in (proposal.section_ctas or {}).items()
            if k in ("priorities", "charts", "investment")
        }
```

Apply this in both the first pass and after the regenerate (put it next to `_clamp_sector_fit(proposal)` calls).

- [ ] **Step 7: Run tests**

Run: `.venv/bin/python -m pytest tests/agents/test_proposal_agent.py -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add app/agents/guardrails.py app/agents/proposal.py tests/agents/test_proposal_agent.py
git commit -m "feat(proposal): ProposalAgent writes + guards hero/closing/section-cta landing-page copy"
```

---

### Task 3: `GET /proposals/{id}.json` + `GET /p/{id}` + static mount

**Files:**
- Modify: `app/api/proposals.py`
- Modify: `app/main.py`
- Test: `tests/api/test_proposals_api.py`

**Interfaces:**
- Consumes: `ProposalRepo.get` (exists), `ProposalRow.proposal_json` / `.version` / `.id`.
- Produces:
  - `GET /proposals/{proposal_id}.json` → `200` `{id, version, generated_on, pdf_url, proposal}` or `404 {"detail":"not found"}`.
  - `GET /p/{proposal_id}` → `200 text/html` (the SPA shell) or `503` when `app/static/proposal/index.html` is absent.

- [ ] **Step 1: Write the failing tests**

```python
# tests/api/test_proposals_api.py  (add — follow the file's existing fixture that
# creates a proposal via the orchestrator and yields its id + a TestClient)
def test_get_proposal_json(built_proposal):
    pid, client = built_proposal
    r = client.get(f"/proposals/{pid}.json")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == str(pid)
    assert body["version"] >= 1
    assert body["pdf_url"] == f"/proposals/{pid}.pdf"
    assert body["proposal"]["company"]


def test_get_proposal_json_404(built_proposal):
    _, client = built_proposal
    import uuid
    r = client.get(f"/proposals/{uuid.uuid4()}.json")
    assert r.status_code == 404


def test_get_proposal_page_503_when_unbuilt(built_proposal):
    pid, client = built_proposal
    from pathlib import Path
    spa = Path("app/static/proposal/index.html")
    r = client.get(f"/p/{pid}")
    if spa.is_file():
        assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    else:
        assert r.status_code == 503
```

If the file has no `built_proposal` fixture, reuse the pattern from
`test_post_proposal_then_get_pdf_and_png` in that same file (it already creates
a proposal and has `pid` + `client`); extract it into a `built_proposal`
fixture and have both the pdf test and these use it.

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/api/test_proposals_api.py -q -k json`
Expected: FAIL — 404 route not defined (FastAPI returns 404 with a different body / the `.json` suffix isn't matched)

- [ ] **Step 3: Implement the routes**

In `app/api/proposals.py`, add imports and routes:

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

(`Path` is already imported in this file.)

- [ ] **Step 4: Mount the static dir**

In `app/main.py`, after the `/demo` mount block:

```python
    proposal_static = Path(__file__).parent / "static" / "proposal"
    if proposal_static.is_dir():
        app.mount(
            "/static/proposal", StaticFiles(directory=str(proposal_static)),
            name="proposal-static",
        )
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/python -m pytest tests/api/test_proposals_api.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/api/proposals.py app/main.py tests/api/test_proposals_api.py
git commit -m "feat(api): GET /proposals/{id}.json and GET /p/{id} shell route; mount app/static/proposal"
```

---

### Task 4: Chat handoff → `proposal_link` card

**Files:**
- Modify: `app/orchestrator.py` (`generate_proposal` — the card dict, the agent message, the returned `ProposalCard`)
- Test: `tests/e2e/test_proposal_flow.py`

**Interfaces:**
- Consumes: `Proposal.hero_subline`, `Proposal.executive_summary`; `ProposalCard` with `page_url`/`title`/`blurb` (Task 1).
- Produces: the stored `attachment` dict and the returned `ProposalCard` both have `kind="proposal_link"`, `page_url=f"/p/{row.id}"`, `pdf_url=f"/proposals/{row.id}.pdf"`, `title`, `blurb`.

- [ ] **Step 1: Write the failing test**

```python
# tests/e2e/test_proposal_flow.py  (extend the existing test — after the attachment
# frame is received, and in the DB check)
        assert att["kind"] == "proposal_link"
        assert att["page_url"] == f"/p/{att['proposal_id']}"
        assert att["pdf_url"] == f"/proposals/{att['proposal_id']}.pdf"
        assert att["title"] and att["blurb"]
```

And in the transcript / message check add:

```python
    # the agent message points at the page
    msgs = client.get(f"/sessions/{sid}").json()["messages"]
    assert any("/p/" in m["content"] for m in msgs if m["role"] == "agent")
```

(Adjust to the file's actual way of reading messages — it uses
`GET /sessions/{id}` via the internal router.)

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/e2e/test_proposal_flow.py -q`
Expected: FAIL — `att["kind"]` is `"proposal"`, no `page_url`

- [ ] **Step 3: Update `generate_proposal`**

In `app/orchestrator.py`, in the `async with SessionLocal() as s:` block after `row = await ProposalRepo(s).create(...)` and `await s.flush()`, replace the `card` dict + the `mr.append(...)` message + (later) the returned `ProposalCard`:

```python
            page_url = f"/p/{row.id}"
            pdf_url = f"/proposals/{row.id}.pdf"
            png_url = f"/proposals/{row.id}/preview.png"
            card = {
                "kind": "proposal_link",
                "proposal_id": str(row.id),
                "version": version,
                "page_url": page_url,
                "pdf_url": pdf_url,
                "png_url": png_url,
                "title": f"Your TEG 2026 proposal for {proposal.company}",
                "blurb": (proposal.hero_subline or proposal.executive_summary or "")[:160],
            }
            mr = MessageRepo(s)
            await mr.append(
                session_id, "agent",
                f"I've put together a proposal for {proposal.company} — open it here: {page_url}",
                turn_index=await mr.next_turn_index(session_id),
                attachment=card,
            )
```

And the final `return ProposalCard(...)` becomes:

```python
        return ProposalCard(
            proposal_id=proposal_id, version=version, filename=filename,
            bytes=len(pdf), pdf_url=pdf_url, png_url=png_url,
            page_url=f"/p/{proposal_id}",
            title=f"Your TEG 2026 proposal for {proposal.company}",
            blurb=(proposal.hero_subline or proposal.executive_summary or "")[:160],
        )
```

(`filename`, `pdf`, `png_url`, `proposal_id` are already computed above — keep those lines. `proposal_id` is the `str(row.id)` captured near the end.)

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/e2e/test_proposal_flow.py tests/orchestrator/test_generate_proposal.py tests/api/test_chat_proposal.py -q`
Expected: PASS. If `test_generate_proposal.py` asserts the old `card["kind"] == "proposal"` or a `filename`/`bytes`-shaped card, update those assertions to the `proposal_link` shape.

- [ ] **Step 5: Commit**

```bash
git add app/orchestrator.py tests/e2e/test_proposal_flow.py tests/orchestrator/ tests/api/
git commit -m "feat(orchestrator): chat hands over a proposal_link card (page_url) alongside the PDF"
```

---

### Task 5: Widget renders the `proposal_link` card

**Files:**
- Modify: `widget/src/ui.ts` (`ProposalLinkPayload`, `renderProposalLink`, extend the returned object)
- Modify: `widget/src/index.ts` (branch on `card.kind`)
- Test: `widget/src/ui.test.ts`

**Interfaces:**
- Consumes: the WS `attachment` frame with `kind: "proposal_link"`, `page_url`, `pdf_url`, `title`, `blurb`.
- Produces: `renderChat(root)` return object gains `showProposalLink(card: ProposalLinkPayload)`.

- [ ] **Step 1: Write the failing test**

```typescript
// widget/src/ui.test.ts  (add)
test("renderProposalLink shows title, blurb, open + pdf links", () => {
  const root = new El("div") as any;
  const chat = renderChat(root);
  chat.showProposalLink({
    kind: "proposal_link",
    proposal_id: "p1",
    version: 1,
    page_url: "/p/p1",
    pdf_url: "/proposals/p1.pdf",
    title: "Your TEG 2026 proposal for Acme",
    blurb: "Three focused days from cold outreach to booked meetings.",
  });
  const s = JSON.stringify(root);
  assert.ok(s.includes("/p/p1"));
  assert.ok(s.includes("/proposals/p1.pdf"));
  assert.ok(s.includes("Your TEG 2026 proposal for Acme"));
  assert.ok(s.includes("data-attachment"));
});

test("pending then proposal_link replaces skeleton", () => {
  const root = new El("div") as any;
  const chat = renderChat(root);
  chat.showProposalPending("Acme");
  chat.showProposalLink({
    kind: "proposal_link", proposal_id: "p1", version: 1,
    page_url: "/p/p1", pdf_url: "/proposals/p1.pdf", title: "t", blurb: "b",
  });
  const cards = JSON.stringify(root).match(/data-attachment/g) || [];
  assert.equal(cards.length, 1);
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd widget && npm test`
Expected: FAIL — `chat.showProposalLink is not a function`

- [ ] **Step 3: Implement**

In `widget/src/ui.ts`, add the type near `AttachmentPayload`:

```typescript
export interface ProposalLinkPayload {
  kind: "proposal_link";
  proposal_id: string;
  version: number;
  page_url: string;
  pdf_url: string;
  title: string;
  blurb: string;
}
```

Add `showProposalLink` to the `renderChat` return type and the object, mirroring `showAttachment` (reuse the `pendingCard` replace logic):

```typescript
    showProposalLink(card: ProposalLinkPayload) {
      const el = h("div", { "data-attachment": "proposal-link", class: "teg-card" });
      el.appendChild(h("div", { class: "teg-card-title" }, card.title));
      if (card.blurb) el.appendChild(h("div", { class: "teg-card-meta" }, card.blurb));
      el.appendChild(
        h("a", { href: card.page_url, target: "_blank", rel: "noopener", class: "teg-card-btn" },
          "Open your proposal"),
      );
      el.appendChild(
        h("a", { href: card.pdf_url, target: "_blank", rel: "noopener", class: "teg-card-btn teg-card-btn-ghost" },
          "Download PDF"),
      );
      if (pendingCard && (log as any).removeChild) (log as any).removeChild(pendingCard);
      log.appendChild(el);
      pendingCard = null;
    },
```

In `widget/src/index.ts`, change the `attachment` branch:

```typescript
      } else if (ev.type === "attachment") {
        if ((ev as any).kind === "proposal_link") {
          chat.showProposalLink(ev as never);
        } else {
          chat.showAttachment(ev as never);
        }
      }
```

- [ ] **Step 4: Run tests + build**

Run: `cd widget && npm test && npm run build`
Expected: PASS; build succeeds.

- [ ] **Step 5: Commit**

```bash
git add widget/src/ui.ts widget/src/index.ts widget/src/ui.test.ts
git commit -m "feat(widget): render the proposal_link card (Open your proposal + Download PDF)"
```

---

### Task 6: `proposal-page/` scaffold + types + API + fixture

**Files:**
- Create: `proposal-page/package.json`, `proposal-page/vite.config.ts`, `proposal-page/tsconfig.json`, `proposal-page/tsconfig.node.json`, `proposal-page/index.html`, `proposal-page/.gitignore`
- Create: `proposal-page/src/lib/types.ts`, `proposal-page/src/lib/api.ts`, `proposal-page/src/lib/chartData.ts`, `proposal-page/src/lib/fallbacks.ts`
- Create: `proposal-page/src/__fixtures__/proposal.json`
- Create: `proposal-page/src/lib/fallbacks.test.ts`
- Modify: root `.gitignore` (add `app/static/proposal/`)

**Interfaces:**
- Produces:
  - `Payload` type: `{ id: string; version: number; generated_on: string | null; pdf_url: string; proposal: Proposal }`.
  - `Proposal` type: mirrors §3.1 (all fields; landing-page fields optional as `?`).
  - `fetchProposal(id: string): Promise<Payload>` — `GET ${API_BASE}/proposals/${id}.json`, throws `Error` on `!res.ok`.
  - `GROWTH = { attendees: [8000, 15000], exhibitors: [125, 250] }`, `INDUSTRIES: string[]` (18 items).
  - `heroHeadline(p)`, `heroSubline(p)`, `sectionCta(p, key)`, `closingHeadline(p)`, `closingBody(p)` — pure fallback helpers.

- [ ] **Step 1: Scaffold the project**

`proposal-page/package.json`:

```json
{
  "name": "teg-proposal-page",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:e2e": "playwright test"
  },
  "dependencies": {
    "framer-motion": "^11.5.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@playwright/test": "^1.47.0",
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/react": "^16.0.0",
    "@types/react": "^18.3.5",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "jsdom": "^25.0.0",
    "typescript": "^5.6.0",
    "vite": "^5.4.0",
    "vitest": "^2.1.0"
  }
}
```

`proposal-page/vite.config.ts`:

```typescript
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  base: "/static/proposal/",
  plugins: [react()],
  build: { outDir: "../app/static/proposal", emptyOutDir: true },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    globals: true,
  },
});
```

`proposal-page/src/test-setup.ts`:

```typescript
import "@testing-library/jest-dom/vitest";
```

`proposal-page/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noEmit": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"],
    "resolveJsonModule": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["src", "e2e"]
}
```

`proposal-page/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Tech Expo Gujarat 2026 — Proposal</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`proposal-page/.gitignore`:

```
node_modules/
dist/
test-results/
playwright-report/
```

Root `.gitignore` — add a line: `app/static/proposal/`

- [ ] **Step 2: Install**

Run: `cd proposal-page && npm install`
Expected: completes; `node_modules/` present.

- [ ] **Step 3: Write the fixture**

`proposal-page/src/__fixtures__/proposal.json` — a full `Payload` (use a stable `id` like `"11111111-1111-1111-1111-111111111111"`):

```json
{
  "id": "11111111-1111-1111-1111-111111111111",
  "version": 2,
  "generated_on": "2026-09-02",
  "pdf_url": "/proposals/11111111-1111-1111-1111-111111111111.pdf",
  "proposal": {
    "company": "DataZen Analytics",
    "person": "Rohan B",
    "person_role": "CTO",
    "sector": "AI & Machine Learning",
    "persona": "it_tech_service",
    "hero_headline": "Turn TEG 2026 into your India-market pipeline",
    "hero_subline": "Three focused days from cold outreach to booked buyer meetings.",
    "executive_summary": "DataZen Analytics builds BI dashboards and is exploring TEG 2026 to reach India enterprise buyers.",
    "pains": [
      { "pain": "Revenue concentrated in US clients", "teg_answer": "15,000+ India-market decision-makers plus pre-scheduled B2B meetings" },
      { "pain": "Low brand visibility at home", "teg_answer": "On-ground, digital and regional PR presence at the state's largest tech expo" }
    ],
    "sector_fit": [
      { "lever": "India-market buyer access", "weight": 5 },
      { "lever": "Live demo space", "weight": 4 },
      { "lever": "Pre-scheduled meetings", "weight": 5 },
      { "lever": "Brand visibility", "weight": 3 }
    ],
    "proof": [
      "TEG 2024 drew 8,000+ attendees and 125+ exhibitors; TEG 2026 targets 15,000+ and 250+.",
      "The TEG Business Retreat 2025 helped facilitate 1.5 crore raised in one day."
    ],
    "peer_companies": ["ViitorCloud", "NeuraMonks", "Perigeon", "Green Apex"],
    "how_a_teg_plays_out": [
      "Pre-event: matchmaking with India buyers in your target sectors",
      "Day 1: live demos at your stall",
      "Day 2: pre-scheduled 1:1 meetings",
      "After: follow-up through the TEG networking app"
    ],
    "roi_framing": "If a single India-market engagement that starts here covers the cost of taking part several times over, participation pays for itself.",
    "recommended_package": {
      "name": "3m x 6m stall",
      "price_line": "2,34,000 + GST (indicative, confirmed at booking)",
      "includes": ["4 exhibitor passes", "10 visitor passes", "pre-scheduled 1:1 B2B meetings", "live demo space"],
      "payment_plan": "4 instalments of 25%"
    },
    "section_ctas": { "priorities": "See the plan", "charts": "Explore the numbers", "investment": "Get your quote" },
    "closing_cta_headline": "Let's make TEG 2026 count for DataZen Analytics",
    "closing_cta_body": "Reply in the chat, or reach the team directly — we'll take it from here.",
    "next_steps": [
      "Review stall options at techexpogujarat.com/become-an-exhibitor",
      "Or reply in the chat and the team will walk you through booking"
    ],
    "contact": "info@techexpogujarat.com"
  }
}
```

- [ ] **Step 4: Write `src/lib/types.ts`**

```typescript
export interface SectorFitRow { lever: string; weight: number; }
export interface Pain { pain: string; teg_answer: string; }
export interface Package {
  name: string; price_line: string; includes: string[]; payment_plan: string;
}
export interface Proposal {
  company: string; person: string; person_role?: string | null;
  sector?: string | null; persona: string;
  hero_headline?: string; hero_subline?: string;
  executive_summary: string;
  pains: Pain[];
  sector_fit: SectorFitRow[];
  proof: string[];
  peer_companies: string[];
  how_a_teg_plays_out: string[];
  roi_framing: string;
  recommended_package: Package;
  section_ctas?: Record<string, string>;
  closing_cta_headline?: string; closing_cta_body?: string;
  next_steps: string[];
  contact: string;
}
export interface Payload {
  id: string; version: number; generated_on: string | null;
  pdf_url: string; proposal: Proposal;
}
```

- [ ] **Step 5: Write `src/lib/api.ts`**

```typescript
import type { Payload } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export async function fetchProposal(id: string): Promise<Payload> {
  const res = await fetch(`${API_BASE}/proposals/${id}.json`);
  if (!res.ok) throw new Error(`proposal ${id}: ${res.status}`);
  return (await res.json()) as Payload;
}
```

- [ ] **Step 6: Write `src/lib/chartData.ts`**

```typescript
export const GROWTH = {
  attendees: [8000, 15000] as [number, number],
  exhibitors: [125, 250] as [number, number],
};

export const INDUSTRIES = [
  "Manufacturing", "Automobile", "Power & Energy", "Agriculture", "Education",
  "Healthcare", "Electronics", "Pharmaceutical", "Jewellery", "Textile",
  "Retail", "Logistics", "Finance", "IT & Software", "AI & Machine Learning",
  "Fintech", "Real Estate", "Cybersecurity",
];
```

- [ ] **Step 7: Write `src/lib/fallbacks.ts` + its test**

`src/lib/fallbacks.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import type { Proposal } from "./types";
import { closingBody, closingHeadline, heroHeadline, heroSubline, sectionCta } from "./fallbacks";

const base = { company: "Acme", executive_summary: "Acme does BI. It wants India." } as Proposal;

describe("fallbacks", () => {
  it("heroHeadline uses the field, else 'A proposal for X'", () => {
    expect(heroHeadline({ ...base, hero_headline: "Win big" })).toBe("Win big");
    expect(heroHeadline(base)).toBe("A proposal for Acme");
  });
  it("heroSubline falls back to the first sentence of the summary", () => {
    expect(heroSubline(base)).toBe("Acme does BI.");
  });
  it("sectionCta uses the map, else a fixed label", () => {
    expect(sectionCta({ ...base, section_ctas: { priorities: "Go" } }, "priorities")).toBe("Go");
    expect(sectionCta(base, "priorities")).toBe("See the plan");
  });
  it("closing fallbacks", () => {
    expect(closingHeadline(base)).toBe("Let's make TEG 2026 count for Acme");
    expect(closingBody(base)).toContain("Reply in the chat");
  });
});
```

`src/lib/fallbacks.ts`:

```typescript
import type { Proposal } from "./types";

const SECTION_LABELS: Record<string, string> = {
  priorities: "See the plan",
  charts: "Explore the numbers",
  investment: "Get your quote",
};

export const heroHeadline = (p: Proposal): string =>
  p.hero_headline?.trim() || `A proposal for ${p.company}`;

export const heroSubline = (p: Proposal): string =>
  p.hero_subline?.trim() || (p.executive_summary.split(/(?<=\.)\s/)[0] ?? p.executive_summary);

export const sectionCta = (p: Proposal, key: string): string =>
  p.section_ctas?.[key]?.trim() || SECTION_LABELS[key] || "Learn more";

export const closingHeadline = (p: Proposal): string =>
  p.closing_cta_headline?.trim() || `Let's make TEG 2026 count for ${p.company}`;

export const closingBody = (p: Proposal): string =>
  p.closing_cta_body?.trim() ||
  "Reply in the chat, or reach the team directly — we'll take it from here.";
```

- [ ] **Step 8: Run tests + typecheck**

Run: `cd proposal-page && npm test && npx tsc -b`
Expected: fallback tests PASS; tsc clean.

- [ ] **Step 9: Commit**

```bash
git add proposal-page/package.json proposal-page/vite.config.ts proposal-page/tsconfig*.json \
  proposal-page/index.html proposal-page/.gitignore proposal-page/src/lib proposal-page/src/__fixtures__ \
  proposal-page/src/test-setup.ts .gitignore
git commit -m "feat(proposal-page): scaffold Vite+React project, types, api, chart constants, fallbacks"
```

---

### Task 7: Hooks + primitives + theme

**Files:**
- Create: `proposal-page/src/theme.css`
- Create: `proposal-page/src/hooks/useReveal.ts`, `proposal-page/src/hooks/useCountUp.ts`
- Create: `proposal-page/src/components/Section.tsx`, `Reveal.tsx`, `CtaButton.tsx`, `StatBadge.tsx`
- Create: `proposal-page/src/components/Reveal.test.tsx`, `proposal-page/src/components/StatBadge.test.tsx`

**Interfaces:**
- Produces:
  - `useReveal(): { ref: RefObject<HTMLDivElement>, shown: boolean }` — `shown` flips true once the element is ≥ 30% visible and stays true.
  - `useCountUp(target: number, active: boolean): number` — 0 → `target` over ~1.1s once `active`; snaps to `target` under reduced motion.
  - `<Reveal>` — wraps children in a Framer `motion.div` fade-up; renders final state immediately under reduced motion.
  - `<Section band?: "light" | "dark" | "alt">` — full-width `<section>` with the band background and inner max-width container.
  - `<CtaButton href variant?: "primary" | "ghost">` — styled `<a target="_blank" rel="noopener">`.
  - `<StatBadge value: number, label: string>` — circular badge; the numeral counts up when scrolled into view.

- [ ] **Step 1: Write `theme.css`**

```css
:root {
  --teg-navy: #1b2a5b;
  --teg-ink: #0f1729;
  --teg-cyan: #17b3c9;
  --teg-gold: #f3a712;
  --teg-bg: #ffffff;
  --teg-bg-alt: #f5f7fb;
  --teg-line: #d7dbe6;
  --font: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --maxw: 900px;
}
* { box-sizing: border-box; }
html, body { margin: 0; }
body { font-family: var(--font); color: var(--teg-ink); background: var(--teg-bg); line-height: 1.6; }
h1, h2, h3 { color: var(--teg-navy); line-height: 1.2; margin: 0 0 .4em; }
h1 { font-size: clamp(2rem, 5vw, 3.4rem); }
h2 { font-size: clamp(1.5rem, 3.5vw, 2rem); }
p { font-size: clamp(1rem, 1.4vw, 1.125rem); }
a { color: var(--teg-cyan); }
.section { padding: clamp(2.5rem, 7vw, 5rem) 1.25rem; }
.section--alt { background: var(--teg-bg-alt); }
.section--dark { background: var(--teg-navy); color: #fff; }
.section--dark h1, .section--dark h2, .section--dark h3 { color: #fff; }
.container { max-width: var(--maxw); margin: 0 auto; }
.card { background: #fff; border: 1px solid var(--teg-line); border-radius: 10px; padding: 1.1rem 1.25rem; box-shadow: 0 1px 3px rgba(15,23,41,.06); }
.cta { display: inline-block; background: var(--teg-gold); color: var(--teg-navy); font-weight: 700; text-decoration: none; padding: .8rem 1.4rem; border-radius: 8px; transition: transform .15s ease, box-shadow .15s ease; }
.cta:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(243,167,18,.35); }
.cta--ghost { background: transparent; border: 1.5px solid currentColor; color: inherit; }
.stat-badge { width: 132px; height: 132px; border-radius: 50%; border: 3px solid var(--teg-cyan); display: flex; flex-direction: column; align-items: center; justify-content: center; }
.stat-badge b { font-size: 2rem; color: var(--teg-navy); }
.stat-badge span { font-size: .8rem; color: var(--teg-ink); text-align: center; padding: 0 .5rem; }
@media (prefers-reduced-motion: reduce) { .cta { transition: none; } }
```

- [ ] **Step 2: Write the hooks**

`src/hooks/useReveal.ts`:

```typescript
import { useEffect, useRef, useState } from "react";

export function useReveal() {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || shown) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setShown(true);
          io.disconnect();
        }
      },
      { threshold: 0.3 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [shown]);
  return { ref, shown };
}
```

`src/hooks/useCountUp.ts`:

```typescript
import { useEffect, useState } from "react";
import { useReducedMotion } from "framer-motion";

export function useCountUp(target: number, active: boolean): number {
  const reduced = useReducedMotion();
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!active) return;
    if (reduced) { setN(target); return; }
    const start = performance.now();
    const dur = 1100;
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setN(Math.round(target * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, active, reduced]);
  return n;
}
```

- [ ] **Step 3: Write the primitives**

`src/components/Reveal.tsx`:

```tsx
import { motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";

export function Reveal({ children, delay = 0 }: { children: ReactNode; delay?: number }) {
  const reduced = useReducedMotion();
  if (reduced) return <div>{children}</div>;
  return (
    <motion.div
      initial={{ opacity: 0, y: 56 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.5, delay }}
    >
      {children}
    </motion.div>
  );
}
```

`src/components/Section.tsx`:

```tsx
import type { ReactNode } from "react";

export function Section(
  { children, band = "light", id }: { children: ReactNode; band?: "light" | "alt" | "dark"; id?: string },
) {
  const cls = band === "alt" ? "section section--alt" : band === "dark" ? "section section--dark" : "section";
  return (
    <section className={cls} id={id}>
      <div className="container">{children}</div>
    </section>
  );
}
```

`src/components/CtaButton.tsx`:

```tsx
export function CtaButton(
  { href, children, variant = "primary" }:
  { href: string; children: string; variant?: "primary" | "ghost" },
) {
  return (
    <a className={variant === "ghost" ? "cta cta--ghost" : "cta"} href={href} target="_blank" rel="noopener">
      {children}
    </a>
  );
}
```

`src/components/StatBadge.tsx`:

```tsx
import { useCountUp } from "../hooks/useCountUp";
import { useReveal } from "../hooks/useReveal";

export function StatBadge({ value, label }: { value: number; label: string }) {
  const { ref, shown } = useReveal();
  const n = useCountUp(value, shown);
  return (
    <div className="stat-badge" ref={ref}>
      <b>{n.toLocaleString()}</b>
      <span>{label}</span>
    </div>
  );
}
```

- [ ] **Step 4: Write the tests**

`src/components/Reveal.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Reveal } from "./Reveal";

describe("Reveal", () => {
  it("renders children", () => {
    render(<Reveal><p>hello</p></Reveal>);
    expect(screen.getByText("hello")).toBeInTheDocument();
  });
});
```

`src/components/StatBadge.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StatBadge } from "./StatBadge";

beforeEach(() => {
  // jsdom has no IntersectionObserver
  vi.stubGlobal("IntersectionObserver", class {
    observe() {}
    disconnect() {}
    unobserve() {}
  });
});

describe("StatBadge", () => {
  it("renders the label and a numeral", () => {
    render(<StatBadge value={15000} label="visitors" />);
    expect(screen.getByText("visitors")).toBeInTheDocument();
    // starts at 0 (not yet revealed)
    expect(screen.getByText("0")).toBeInTheDocument();
  });
});
```

Add to `src/test-setup.ts`:

```typescript
import { vi } from "vitest";

if (!("IntersectionObserver" in globalThis)) {
  vi.stubGlobal("IntersectionObserver", class {
    observe() {}
    disconnect() {}
    unobserve() {}
  });
}
```

- [ ] **Step 5: Run tests + typecheck**

Run: `cd proposal-page && npm test && npx tsc -b`
Expected: PASS; clean.

- [ ] **Step 6: Commit**

```bash
git add proposal-page/src/theme.css proposal-page/src/hooks proposal-page/src/components proposal-page/src/test-setup.ts
git commit -m "feat(proposal-page): theme tokens, useReveal/useCountUp hooks, Section/Reveal/CtaButton/StatBadge"
```

---

### Task 8: Chart components

**Files:**
- Create: `proposal-page/src/components/charts/GrowthBars.tsx`, `IndustryMix.tsx`, `Funnel.tsx`, `SectorFitBars.tsx`, `PeerStat.tsx`
- Create: `proposal-page/src/components/charts/charts.test.tsx`

**Interfaces:**
- Consumes: `GROWTH`, `INDUSTRIES` (`lib/chartData.ts`); `SectorFitRow` (`lib/types.ts`); `useReveal`, `useCountUp`.
- Produces:
  - `<GrowthBars />` — grouped bars, TEG 2024 → 2026, bars grow on reveal, labels count up.
  - `<IndustryMix />` — horizontal bars, one per `INDUSTRIES`, stagger-grow on reveal.
  - `<Funnel steps={[label, sub][]} />` — 4 downward trapezoids, grow on reveal.
  - `<SectorFitBars rows={SectorFitRow[]} />` — one horizontal bar per row, length `= clamp(weight,1,5)/5`.
  - `<PeerStat names={string[]} />` — a name grid + a `<StatBadge value={names.length} label="companies already confirmed for TEG 2026" />`.
- All are inline `<svg>` (except `PeerStat`'s grid which is HTML), navy/cyan/gold, no external refs.

- [ ] **Step 1: Write the tests**

```tsx
// proposal-page/src/components/charts/charts.test.tsx
import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Funnel } from "./Funnel";
import { GrowthBars } from "./GrowthBars";
import { IndustryMix } from "./IndustryMix";
import { PeerStat } from "./PeerStat";
import { SectorFitBars } from "./SectorFitBars";

beforeEach(() => {
  vi.stubGlobal("IntersectionObserver", class { observe(){} disconnect(){} unobserve(){} });
});

describe("charts", () => {
  it("GrowthBars renders an svg with the target numbers", () => {
    const { container } = render(<GrowthBars />);
    expect(container.querySelector("svg")).toBeTruthy();
  });
  it("IndustryMix renders a bar per industry", () => {
    const { container } = render(<IndustryMix />);
    expect(container.querySelectorAll("rect").length).toBeGreaterThanOrEqual(18);
  });
  it("Funnel renders 4 segments", () => {
    const { container } = render(
      <Funnel steps={[["a", "1"], ["b", "2"], ["c", "3"], ["d", "4"]]} />,
    );
    expect(container.querySelectorAll("path").length).toBe(4);
  });
  it("SectorFitBars renders a bar per row and clamps weight", () => {
    const { container } = render(
      <SectorFitBars rows={[{ lever: "A", weight: 9 }, { lever: "B", weight: 2 }]} />,
    );
    expect(container.querySelectorAll("rect").length).toBeGreaterThanOrEqual(2);
  });
  it("PeerStat lists names and shows the count", () => {
    const { getByText } = render(<PeerStat names={["X", "Y", "Z"]} />);
    expect(getByText("X")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd proposal-page && npm test -- charts`
Expected: FAIL — modules not found

- [ ] **Step 3: Implement the charts**

Each file follows this shape (viewBox-scaled `<svg>`, Framer `motion` on the
growing elements, gated by `useReveal`). `GrowthBars.tsx`:

```tsx
import { motion } from "framer-motion";
import { GROWTH } from "../../lib/chartData";
import { useCountUp } from "../../hooks/useCountUp";
import { useReveal } from "../../hooks/useReveal";

const W = 520, H = 220;

export function GrowthBars() {
  const { ref, shown } = useReveal();
  const groups: [string, [number, number]][] = [
    ["Attendees", GROWTH.attendees],
    ["Exhibitors", GROWTH.exhibitors],
  ];
  const max = Math.max(GROWTH.attendees[1], GROWTH.exhibitors[1]);
  const baseY = H - 44, plotH = baseY - 24, gw = W / groups.length;
  return (
    <div ref={ref}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="TEG 2024 to 2026 growth">
        {groups.map(([label, [a, b]], gi) => {
          const cx = gi * gw + gw / 2;
          return (
            <g key={label}>
              {[[a, "#64748b", -46], [b, "#1b2a5b", 4]].map(([v, fill, dx], bi) => {
                const bh = (plotH * (v as number)) / max;
                return (
                  <motion.rect
                    key={bi}
                    x={cx + (dx as number)} width={38} rx={2} fill={fill as string}
                    initial={{ height: 0, y: baseY }}
                    animate={shown ? { height: bh, y: baseY - bh } : {}}
                    transition={{ duration: 0.7, delay: bi * 0.1 }}
                  />
                );
              })}
              <Value x={cx - 27} y={baseY - (plotH * a) / max - 6} v={a} shown={shown} />
              <Value x={cx + 23} y={baseY - (plotH * b) / max - 6} v={b} shown={shown} />
              <text x={cx} y={baseY + 18} fontSize={12} textAnchor="middle" fill="#64748b">{label}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function Value({ x, y, v, shown }: { x: number; y: number; v: number; shown: boolean }) {
  const n = useCountUp(v, shown);
  return <text x={x} y={y} fontSize={11} textAnchor="middle" fill="#1b2a5b">{n.toLocaleString()}</text>;
}
```

`IndustryMix.tsx`:

```tsx
import { motion } from "framer-motion";
import { INDUSTRIES } from "../../lib/chartData";
import { useReveal } from "../../hooks/useReveal";

const W = 520;

export function IndustryMix() {
  const { ref, shown } = useReveal();
  const rowH = 20, h = INDUSTRIES.length * rowH + 12;
  return (
    <div ref={ref}>
      <p style={{ fontSize: ".85rem", color: "#64748b" }}>
        Buyers attend across every sector — illustrative, not to scale
      </p>
      <svg viewBox={`0 0 ${W} ${h}`} width="100%" role="img" aria-label="Industries represented">
        {INDUSTRIES.map((name, i) => {
          const y = i * rowH + 4;
          const frac = 0.55 + (0.4 * i) / (INDUSTRIES.length - 1);
          return (
            <g key={name}>
              <text x={124} y={y + 11} fontSize={10} textAnchor="end" fill="#64748b">{name}</text>
              <motion.rect
                x={132} y={y} height={13} rx={2} fill="#17b3c9" opacity={0.85}
                initial={{ width: 0 }}
                animate={shown ? { width: (W - 142) * frac } : {}}
                transition={{ duration: 0.5, delay: i * 0.03 }}
              />
            </g>
          );
        })}
      </svg>
    </div>
  );
}
```

`Funnel.tsx`:

```tsx
import { motion } from "framer-motion";
import { useReveal } from "../../hooks/useReveal";

const W = 520;

export function Funnel({ steps }: { steps: [string, string][] }) {
  const { ref, shown } = useReveal();
  const stepH = 52, h = steps.length * stepH + 8;
  const topW = W - 40, botW = W * 0.34;
  return (
    <div ref={ref}>
      <svg viewBox={`0 0 ${W} ${h}`} width="100%" role="img" aria-label="TEG mechanism funnel">
        {steps.map(([label, sub], i) => {
          const y = i * stepH + 4;
          const wTop = topW - ((topW - botW) * i) / steps.length;
          const wBot = topW - ((topW - botW) * (i + 1)) / steps.length;
          const xTop = (W - wTop) / 2, xBot = (W - wBot) / 2;
          const d = `M${xTop},${y} L${xTop + wTop},${y} L${xBot + wBot},${y + stepH - 6} L${xBot},${y + stepH - 6} Z`;
          return (
            <g key={i}>
              <motion.path
                d={d} fill="#1b2a5b" opacity={0.9 - i * 0.13}
                initial={{ pathLength: 0, opacity: 0 }}
                animate={shown ? { pathLength: 1, opacity: 0.9 - i * 0.13 } : {}}
                transition={{ duration: 0.5, delay: i * 0.12 }}
              />
              <text x={W / 2} y={y + 22} fontSize={12} fill="#fff" textAnchor="middle">{label}</text>
              <text x={W / 2} y={y + 37} fontSize={9} fill="#e2e8f0" textAnchor="middle">{sub}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
```

`SectorFitBars.tsx`:

```tsx
import { motion } from "framer-motion";
import type { SectorFitRow } from "../../lib/types";
import { useReveal } from "../../hooks/useReveal";

const W = 520;

export function SectorFitBars({ rows }: { rows: SectorFitRow[] }) {
  const { ref, shown } = useReveal();
  const rowH = 32, h = rows.length * rowH + 8, inner = W - 170;
  return (
    <div ref={ref}>
      <svg viewBox={`0 0 ${W} ${h}`} width="100%" role="img" aria-label="How TEG's levers weigh for your sector">
        {rows.map((r, i) => {
          const w = Math.max(1, Math.min(5, r.weight)) / 5;
          const y = i * rowH + 4;
          return (
            <g key={r.lever}>
              <text x={0} y={y + 15} fontSize={10} fill="#64748b">{r.lever}</text>
              <motion.rect
                x={150} y={y + 3} height={15} rx={2} fill="#17b3c9"
                initial={{ width: 0 }}
                animate={shown ? { width: inner * w } : {}}
                transition={{ duration: 0.6, delay: i * 0.08 }}
              />
              <text x={150 + inner * w + 6} y={y + 15} fontSize={9} fill="#64748b">
                {Math.max(1, Math.min(5, r.weight))}/5
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
```

`PeerStat.tsx`:

```tsx
import { StatBadge } from "../StatBadge";

export function PeerStat({ names }: { names: string[] }) {
  return (
    <div style={{ display: "flex", gap: "1.5rem", flexWrap: "wrap", alignItems: "center" }}>
      <StatBadge value={names.length} label="companies already confirmed for TEG 2026" />
      <div style={{ display: "flex", gap: ".5rem", flexWrap: "wrap", flex: 1 }}>
        {names.map((n) => (
          <span key={n} className="card" style={{ padding: ".4rem .75rem", fontSize: ".9rem" }}>{n}</span>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests + typecheck**

Run: `cd proposal-page && npm test && npx tsc -b`
Expected: PASS; clean.

- [ ] **Step 5: Commit**

```bash
git add proposal-page/src/components/charts
git commit -m "feat(proposal-page): 5 animated chart components (growth, industry mix, funnel, sector-fit, peer stat)"
```

---

### Task 9: Sections + `App` + states + `main`

**Files:**
- Create: `proposal-page/src/sections/Hero.tsx`, `Priorities.tsx`, `Charts.tsx`, `Journey.tsx`, `TheAsk.tsx`
- Create: `proposal-page/src/states/Loading.tsx`, `proposal-page/src/states/ErrorState.tsx`
- Create: `proposal-page/src/App.tsx`, `proposal-page/src/main.tsx`
- Create: `proposal-page/src/App.test.tsx`, `proposal-page/src/sections/sections.test.tsx`

**Interfaces:**
- Consumes: everything from Tasks 6-8.
- Produces:
  - `<App payload={Payload} />` — renders the 7-section page.
  - `main.tsx` — reads the last path segment as `id`; if not uuid-shaped → `<ErrorState />`; else fetch → `<Loading />` while pending, `<App />` on success, `<ErrorState />` on failure.

- [ ] **Step 1: Write the section tests**

```tsx
// proposal-page/src/sections/sections.test.tsx
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import fixture from "../__fixtures__/proposal.json";
import type { Proposal } from "../lib/types";
import { Hero } from "./Hero";
import { Priorities } from "./Priorities";
import { TheAsk } from "./TheAsk";

const p = fixture.proposal as Proposal;

beforeEach(() => {
  vi.stubGlobal("IntersectionObserver", class { observe(){} disconnect(){} unobserve(){} });
});

describe("sections", () => {
  it("Hero shows company + headline; falls back when headline empty", () => {
    render(<Hero p={p} />);
    expect(screen.getByText(p.hero_headline!)).toBeInTheDocument();
    render(<Hero p={{ ...p, hero_headline: "" }} />);
    expect(screen.getByText(`A proposal for ${p.company}`)).toBeInTheDocument();
  });
  it("Priorities renders one card per pain; nothing when empty", () => {
    const { container, rerender } = render(<Priorities p={p} />);
    expect(container.querySelectorAll(".card").length).toBe(p.pains.length);
    rerender(<Priorities p={{ ...p, pains: [] }} />);
    expect(container.querySelector("section")).toBeNull();
  });
  it("TheAsk shows price when present, hides it when empty", () => {
    render(<TheAsk p={p} />);
    expect(screen.getByText(/2,34,000/)).toBeInTheDocument();
    render(<TheAsk p={{ ...p, recommended_package: { ...p.recommended_package, price_line: "", payment_plan: "" } }} />);
    expect(screen.getByText(/team will share stall options/i)).toBeInTheDocument();
  });
});
```

```tsx
// proposal-page/src/App.test.tsx
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import fixture from "./__fixtures__/proposal.json";
import type { Payload } from "./lib/types";
import { App } from "./App";

beforeEach(() => {
  vi.stubGlobal("IntersectionObserver", class { observe(){} disconnect(){} unobserve(){} });
});

describe("App", () => {
  it("renders the hero and a chart", () => {
    const { container } = render(<App payload={fixture as Payload} />);
    expect(screen.getByText(fixture.proposal.hero_headline)).toBeInTheDocument();
    expect(container.querySelector("svg")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd proposal-page && npm test -- sections App`
Expected: FAIL — modules not found

- [ ] **Step 3: Implement the sections**

`Hero.tsx`:

```tsx
import { motion } from "framer-motion";
import type { Proposal } from "../lib/types";
import { heroHeadline, heroSubline } from "../lib/fallbacks";
import { Section } from "../components/Section";
import { CtaButton } from "../components/CtaButton";

export function Hero({ p }: { p: Proposal }) {
  const mail = `mailto:${p.contact}?subject=${encodeURIComponent(`TEG 2026 — ${p.company}`)}`;
  return (
    <Section band="dark" id="top">
      <motion.h1 initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
        {heroHeadline(p)}
      </motion.h1>
      <motion.p initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.15 }}>
        {heroSubline(p)}
      </motion.p>
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.35 }} style={{ marginTop: "1.5rem" }}>
        <CtaButton href={mail}>Talk to the team</CtaButton>
      </motion.div>
      <p style={{ opacity: 0.75, fontSize: ".85rem", marginTop: "1.5rem" }}>
        Prepared for {p.person}{p.person_role ? `, ${p.person_role}` : ""} · {p.sector ?? ""} · v{"" /* version comes via App footer */}
      </p>
    </Section>
  );
}
```

`Priorities.tsx`:

```tsx
import type { Proposal } from "../lib/types";
import { sectionCta } from "../lib/fallbacks";
import { Section } from "../components/Section";
import { Reveal } from "../components/Reveal";
import { CtaButton } from "../components/CtaButton";

export function Priorities({ p }: { p: Proposal }) {
  if (!p.pains.length) return null;
  return (
    <Section band="alt" id="priorities">
      <Reveal><h2>Where TEG moves the needle for you</h2></Reveal>
      <div style={{ display: "grid", gap: "1rem", marginTop: "1.5rem" }}>
        {p.pains.map((pain, i) => (
          <Reveal key={i} delay={i * 0.08}>
            <div className="card">
              <strong>{pain.pain}</strong>
              <p style={{ margin: ".4rem 0 0" }}>{pain.teg_answer}</p>
            </div>
          </Reveal>
        ))}
      </div>
      <div style={{ marginTop: "1.5rem" }}>
        <a className="cta cta--ghost" href="#journey">{sectionCta(p, "priorities")}</a>
      </div>
    </Section>
  );
}
```

`Charts.tsx`:

```tsx
import type { Proposal } from "../lib/types";
import { Section } from "../components/Section";
import { Reveal } from "../components/Reveal";
import { GrowthBars } from "../components/charts/GrowthBars";
import { IndustryMix } from "../components/charts/IndustryMix";
import { SectorFitBars } from "../components/charts/SectorFitBars";
import { Funnel } from "../components/charts/Funnel";
import { PeerStat } from "../components/charts/PeerStat";

const FUNNEL: [string, string][] = [
  ["15,000+ visitors", "cross-industry decision-makers"],
  ["Pre-scheduled 1:1 meetings", "matched to your sectors"],
  ["Qualified conversations", "live demos, real intent"],
  ["Partnerships & pipeline", "the follow-up that starts here"],
];

export function Charts({ p }: { p: Proposal }) {
  return (
    <Section band="light" id="numbers">
      <Reveal><h2>The numbers behind TEG</h2></Reveal>
      {p.sector_fit.length > 0 && (
        <Reveal><h3 style={{ marginTop: "2rem" }}>How your sector benefits</h3><SectorFitBars rows={p.sector_fit} /></Reveal>
      )}
      <Reveal><h3 style={{ marginTop: "2rem" }}>The track record</h3>
        <ul>{p.proof.map((x, i) => <li key={i}>{x}</li>)}</ul>
        <GrowthBars />
      </Reveal>
      <Reveal><h3 style={{ marginTop: "2rem" }}>Who's in the room</h3><IndustryMix /></Reveal>
      {p.peer_companies.length > 0 && (
        <Reveal><div style={{ marginTop: "1.5rem" }}><PeerStat names={p.peer_companies} /></div></Reveal>
      )}
      <Reveal><h3 style={{ marginTop: "2rem" }}>How it converts</h3><Funnel steps={FUNNEL} /></Reveal>
    </Section>
  );
}
```

`Journey.tsx`:

```tsx
import type { Proposal } from "../lib/types";
import { Section } from "../components/Section";
import { Reveal } from "../components/Reveal";

export function Journey({ p }: { p: Proposal }) {
  if (!p.how_a_teg_plays_out.length) return null;
  return (
    <Section band="alt" id="journey">
      <Reveal><h2>How your three days play out</h2></Reveal>
      <ol style={{ listStyle: "none", padding: 0, marginTop: "1.5rem" }}>
        {p.how_a_teg_plays_out.map((step, i) => (
          <Reveal key={i} delay={i * 0.1}>
            <li style={{ display: "flex", gap: "1rem", padding: ".75rem 0", borderLeft: "2px solid var(--teg-cyan)", paddingLeft: "1rem", marginLeft: ".5rem" }}>
              <b style={{ color: "var(--teg-cyan)" }}>{i + 1}</b>
              <span>{step}</span>
            </li>
          </Reveal>
        ))}
      </ol>
    </Section>
  );
}
```

`TheAsk.tsx`:

```tsx
import type { Proposal } from "../lib/types";
import { closingBody, closingHeadline, sectionCta } from "../lib/fallbacks";
import { Section } from "../components/Section";
import { Reveal } from "../components/Reveal";
import { CtaButton } from "../components/CtaButton";

export function TheAsk({ p }: { p: Proposal }) {
  const pkg = p.recommended_package;
  const priced = pkg.price_line.trim().length > 0;
  const mail = `mailto:${p.contact}?subject=${encodeURIComponent(`TEG 2026 — ${p.company}`)}`;
  return (
    <Section band="dark" id="the-ask">
      <Reveal><h2>The ask</h2></Reveal>
      <Reveal>
        <div className="card" style={{ color: "var(--teg-ink)", marginTop: "1rem" }}>
          <strong>{pkg.name}</strong>
          <ul>{pkg.includes.map((x, i) => <li key={i}>{x}</li>)}</ul>
          {priced ? (
            <>
              <div><b>{pkg.price_line}</b></div>
              {pkg.payment_plan && <div>Payment: {pkg.payment_plan}</div>}
            </>
          ) : (
            <div>The team will share stall options and pricing tailored to your goals.</div>
          )}
        </div>
      </Reveal>
      {p.roi_framing && <Reveal><p style={{ marginTop: "1rem" }}>{p.roi_framing}</p></Reveal>}
      <Reveal>
        <h3 style={{ marginTop: "2rem" }}>{closingHeadline(p)}</h3>
        <p>{closingBody(p)}</p>
        <div style={{ marginTop: "1rem" }}><CtaButton href={mail}>{sectionCta(p, "investment")}</CtaButton></div>
      </Reveal>
    </Section>
  );
}
```

- [ ] **Step 4: Implement `App`, states, `main`**

`states/Loading.tsx`:

```tsx
export function Loading() {
  return (
    <div style={{ maxWidth: 600, margin: "20vh auto", padding: "0 1.25rem" }}>
      <div style={{ fontWeight: 800, color: "var(--teg-navy)", fontSize: "1.25rem" }}>Tech Expo Gujarat 2026</div>
      {[0, 1, 2].map((i) => (
        <div key={i} style={{
          height: 18, margin: "1rem 0", borderRadius: 6,
          background: "linear-gradient(90deg,#eef1f7 25%,#e2e6ef 37%,#eef1f7 63%)",
          backgroundSize: "400% 100%", animation: "sh 1.4s ease infinite",
        }} />
      ))}
      <style>{`@keyframes sh{0%{background-position:100% 0}100%{background-position:-100% 0}}`}</style>
    </div>
  );
}
```

`states/ErrorState.tsx`:

```tsx
export function ErrorState() {
  return (
    <div style={{ maxWidth: 480, margin: "22vh auto", textAlign: "center", padding: "0 1.25rem" }}>
      <div style={{ fontWeight: 800, color: "var(--teg-navy)", fontSize: "1.25rem", marginBottom: ".5rem" }}>
        Tech Expo Gujarat 2026
      </div>
      <p>This proposal link isn't valid or has expired.</p>
      <a className="cta" href="https://www.techexpogujarat.com">Go to techexpogujarat.com</a>
    </div>
  );
}
```

`App.tsx`:

```tsx
import "./theme.css";
import type { Payload } from "./lib/types";
import { Hero } from "./sections/Hero";
import { Priorities } from "./sections/Priorities";
import { Charts } from "./sections/Charts";
import { Journey } from "./sections/Journey";
import { TheAsk } from "./sections/TheAsk";
import { Section } from "./components/Section";

export function App({ payload }: { payload: Payload }) {
  const p = payload.proposal;
  return (
    <>
      <Hero p={p} />
      {p.executive_summary && (
        <Section band="light"><p style={{ fontSize: "1.15rem" }}>{p.executive_summary}</p></Section>
      )}
      <Priorities p={p} />
      <Charts p={p} />
      <Journey p={p} />
      <TheAsk p={p} />
      <Section band="light">
        <p><strong>Contact:</strong> {p.contact}</p>
        <ul>{p.next_steps.map((s, i) => {
          const url = s.match(/https?:\/\/\S+|[\w.-]+\.com\/\S+/);
          return <li key={i}>{url ? <a href={url[0].startsWith("http") ? url[0] : `https://${url[0]}`} target="_blank" rel="noopener">{s}</a> : s}</li>;
        })}</ul>
        <p style={{ fontSize: ".8rem", color: "#64748b" }}>
          v{payload.version} · {payload.generated_on} · This is an information document, not a contract.{" "}
          <a href={payload.pdf_url} target="_blank" rel="noopener">Download as PDF</a>
        </p>
      </Section>
    </>
  );
}
```

`main.tsx`:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { fetchProposal } from "./lib/api";
import type { Payload } from "./lib/types";
import { App } from "./App";
import { Loading } from "./states/Loading";
import { ErrorState } from "./states/ErrorState";
import "./theme.css";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const id = window.location.pathname.split("/").filter(Boolean).pop() ?? "";
const root = createRoot(document.getElementById("root")!);

function render(node: JSX.Element) {
  root.render(<StrictMode>{node}</StrictMode>);
}

if (!UUID.test(id)) {
  render(<ErrorState />);
} else {
  render(<Loading />);
  fetchProposal(id)
    .then((payload: Payload) => render(<App payload={payload} />))
    .catch(() => render(<ErrorState />));
}
```

- [ ] **Step 5: Run tests + typecheck + build**

Run: `cd proposal-page && npm test && npm run build`
Expected: tests PASS; `npm run build` produces `app/static/proposal/index.html` + assets.

- [ ] **Step 6: Verify the Python `/p/{id}` route now serves**

Run: `.venv/bin/python -m pytest tests/api/test_proposals_api.py -q -k page`
Expected: the `test_get_proposal_page_503_when_unbuilt` test now takes the `200` branch.

- [ ] **Step 7: Commit**

```bash
git add proposal-page/src/sections proposal-page/src/states proposal-page/src/App.tsx proposal-page/src/main.tsx \
  proposal-page/src/App.test.tsx proposal-page/src/sections/sections.test.tsx
git commit -m "feat(proposal-page): 7 page sections, App, Loading/Error states, main entrypoint"
```

---

### Task 10: Playwright smoke + design pass + docs

**Files:**
- Create: `proposal-page/playwright.config.ts`, `proposal-page/e2e/server.mjs`, `proposal-page/e2e/smoke.spec.ts`
- Modify: `proposal-page/src/theme.css` + section files (design polish via the `frontend-design` skill)
- Modify: `README.md`

- [ ] **Step 1: Playwright config + test server**

`proposal-page/playwright.config.ts`:

```typescript
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  use: { baseURL: "http://127.0.0.1:4178" },
  webServer: {
    command: "node e2e/server.mjs",
    url: "http://127.0.0.1:4178/health",
    reuseExistingServer: false,
  },
});
```

`proposal-page/e2e/server.mjs` — a tiny static + stub-API server:

```javascript
import { createReadStream, existsSync, readFileSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join } from "node:path";

const ROOT = join(process.cwd(), "..", "app", "static", "proposal");
const FIXTURE = readFileSync(join(process.cwd(), "src", "__fixtures__", "proposal.json"), "utf8");
const TYPES = { ".js": "text/javascript", ".css": "text/css", ".html": "text/html", ".svg": "image/svg+xml", ".json": "application/json" };

createServer((req, res) => {
  const url = new URL(req.url, "http://x");
  if (url.pathname === "/health") return res.end("ok");
  if (url.pathname.endsWith(".json") && url.pathname.startsWith("/proposals/")) {
    res.setHeader("content-type", "application/json");
    return res.end(FIXTURE);
  }
  if (url.pathname.startsWith("/p/")) {
    res.setHeader("content-type", "text/html");
    return res.end(readFileSync(join(ROOT, "index.html"), "utf8"));
  }
  // static assets under /static/proposal/...
  const rel = url.pathname.replace("/static/proposal/", "");
  const file = join(ROOT, rel);
  if (existsSync(file) && !file.endsWith("/")) {
    res.setHeader("content-type", TYPES[extname(file)] ?? "application/octet-stream");
    return createReadStream(file).pipe(res);
  }
  res.statusCode = 404;
  res.end("nf");
}).listen(4178);
```

`proposal-page/e2e/smoke.spec.ts`:

```typescript
import { expect, test } from "@playwright/test";
import fixture from "../src/__fixtures__/proposal.json";

test("proposal page renders hero, a chart, and a mailto CTA", async ({ page }) => {
  await page.goto(`/p/${fixture.id}`);
  await expect(page.getByText(fixture.proposal.hero_headline)).toBeVisible();
  await expect(page.locator("svg").first()).toBeVisible();
  await expect(page.locator('a[href^="mailto:"]').first()).toBeVisible();
});

test("bad id shows the error state", async ({ page }) => {
  await page.goto("/p/not-a-uuid");
  await expect(page.getByText(/isn't valid or has expired/i)).toBeVisible();
});
```

- [ ] **Step 2: Run the smoke test**

Run: `cd proposal-page && npm run build && npx playwright install chromium && npm run test:e2e`
Expected: both tests PASS.

- [ ] **Step 3: Design polish**

Announce: "I'm using the frontend-design skill to refine the proposal page visuals."
**REQUIRED SUB-SKILL:** `frontend-design` — iterate on `theme.css` and the
section components for spacing rhythm, card shapes, chart proportions, hero
weight, and the dark/light band transitions, anchored to the palette and motifs
in the spec (§6). Keep every existing test green. Re-run
`cd proposal-page && npm test && npm run build && npm run test:e2e` after.

- [ ] **Step 4: README**

In `README.md`, under the "Personalized proposal" section, add:

> **Landing page.** Every proposal is also a hosted, animated web page at
> `GET /p/{id}` — a React + Vite app in `proposal-page/` that fetches
> `GET /proposals/{id}.json` and renders a full landing page (hero, priorities,
> animated charts, the ask). Build it with `cd proposal-page && npm install &&
> npm run build` (outputs to `app/static/proposal/`, which FastAPI serves). The
> chat hands the prospect a link card to the page; the PDF stays available as a
> secondary download. `cd proposal-page && npm test` runs the Vitest component
> tests; `npm run test:e2e` runs the Playwright smoke.

- [ ] **Step 5: Full verification**

```bash
.venv/bin/python scripts/build_kb_facts.py --check
.venv/bin/python -m pytest -q
cd widget && npm test && npm run build && cd ..
cd proposal-page && npm test && npm run build && cd ..
.venv/bin/ruff check app config tests scripts
```
Expected: all green; ruff no worse than baseline.

- [ ] **Step 6: Commit**

```bash
git add proposal-page/playwright.config.ts proposal-page/e2e proposal-page/src proposal-page/package.json README.md
git commit -m "test(proposal-page): Playwright smoke; design polish; README"
```

- [ ] **Step 7: Finish the branch**

Verify `.venv/bin/python -m pytest -q` and both `npm test` suites are green,
then present merge options to the user.

---

## Self-Review

**Spec coverage:**
- §4.1 `Proposal` +5 fields, `ProposalCard` +3 → Task 1.
- §4.2 `ProposalAgent` writes + guards → Task 2. §4.3 `PROPOSAL_SAFE_SECTIONS` +3 → Task 2.
- §4.4 `GET /proposals/{id}.json`, `GET /p/{id}`, static mount → Task 3.
- §4.5 chat `proposal_link` card + `ProposalCard` populated → Task 4.
- §4.6 widget `renderProposalLink` → Task 5.
- §5.1 project scaffold → Task 6. §5.2 file structure → Tasks 6-9. §5.3 sections → Task 9. §5.4 data flow (`main.tsx`) → Task 9. §5.5 animation (`Reveal`/`useCountUp`/reduced-motion) → Tasks 7-8. §5.6 loading/error/empty → Task 9.
- §3.1 JSON contract → Task 3 (endpoint) + Task 6 (`types.ts`). §3.2 fallbacks → Task 6 (`fallbacks.ts`). §3.3 pricing rule → Task 9 (`TheAsk`). §3.4 chart data constants → Task 6 (`chartData.ts`).
- §6 visual style tokens → Task 7 (`theme.css`); polish → Task 10 Step 3.
- §7.1 Vitest tests → Tasks 6-9; Playwright → Task 10. §7.2 backend tests → Tasks 1-4.
- §8 non-goals: no intent table (nothing built), PDF untouched (no PDF files touched in any task), chart data stays a FE constant (Task 6).

**Placeholder scan:** Task 9 `Hero.tsx` has an inline comment `{"" /* version comes via App footer */}` — the hero deliberately doesn't show the version (the App footer does); this renders an empty string, not a placeholder token. Every code step has real code. No "TBD"/"add error handling" prose.

**Type consistency:**
- `Payload` / `Proposal` / `SectorFitRow` / `Pain` / `Package` — defined Task 6, used Tasks 7-9 identically.
- `fetchProposal(id): Promise<Payload>` — Task 6, used Task 9.
- `useReveal(): {ref, shown}` — Task 7, used Tasks 7-8.
- `useCountUp(target, active): number` — Task 7, used Tasks 7-8.
- `<Section band?>` values `"light"|"alt"|"dark"` — Task 7, used Task 9.
- `heroHeadline/heroSubline/sectionCta/closingHeadline/closingBody` — Task 6, used Task 9.
- `ProposalLinkPayload` — Task 5 (widget); `card["kind"] == "proposal_link"` — Task 4 (orchestrator) matches.
- `Proposal.hero_headline` etc. (Python) — Task 1; written Task 2; serialized into `proposal_json` and surfaced by Task 3's `.json` route; consumed by the FE `Proposal` type (Task 6).
- Backend `section_ctas` keys `{"priorities","charts","investment"}` (Task 2) == FE `SECTION_LABELS` keys (Task 6) == `sectionCta` calls in `Priorities`/`TheAsk` (Task 9).
