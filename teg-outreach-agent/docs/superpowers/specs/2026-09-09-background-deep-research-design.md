# TEG Outreach — Background Deep-Research Pass — Design Spec

> **Status:** Draft (2026-09-09)
> **Related:** `2026-09-10-verification-harness-and-graph-design.md` (the `ClaudeWebSearch`/`claude_verifier.py` one-shot harness pattern this reuses), `docs/superpowers/plans/2026-09-10-verification-harness-and-graph-implementation.md`'s Company Research Brief follow-up (`app/research/brief.py`, the `company_briefs` table this extends), `docs/superpowers/plans/Teg proposal persuasion audit.md` (the persuasion gap this closes the data side of)
> **Owner:** rohanb@thirdrocktechkno.com

---

## 1. Problem

`render_company_brief()` (shipped) turns a `ResearchDossier` into a readable brief, and does that honestly — but it can only be as good as the dossier it's given, by design (no invented content). Today's dossier, built by `ResearchAgent.run()` inside `pipeline_hard_timeout_s` (90s default, has to finish before the prospect sees an opening message), carries: `sector`, `company_size`, `hq`, `founder`, `website`, `teg_history`, a short `overview`, plus a few person fields. That's genuinely thin next to what real account research looks like.

The user supplied a concrete example of the target: a Tudip Technologies account research brief compiled from Clutch, GoodFirms, Glassdoor, Tracxn, Tofler, EMIS, and LinkedIn — financial trend data (revenue growth decelerating, EBITDA down ~28% YoY), employee-review sentiment themes with mention counts (overtime, management friction), a competitive-visibility ranking (~2,624th of 130,000+ tracked competitors), named enterprise clients, certifications, a brand-ambassador/PR angle, and a table of suggested pitch angles derived from all of it. None of today's pipeline gathers this kind of data, and none of it *can* fit inside a 90-second pre-chat window without materially slowing down the very first message a prospect sees — real multi-source diligence takes real time.

## 2. Goal

Two speeds of research, not one, composed rather than replacing each other:

1. **Keep today's lightweight research exactly as it is** for the opening message — `ResearchAgent.run()`, `pipeline_hard_timeout_s`, unchanged, no regressions.
2. **Add an independent, asynchronous deep-research pass** that starts once the chat session exists, runs entirely detached from the request/response cycle, gathers the kind of multi-source diligence the Tudip brief demonstrates, and writes its result into the *same* `company_briefs` store the light pass already reuses — so anything that already reads `company_briefs` benefits automatically once a deep pass lands, with zero hard dependency on it landing in time for any particular turn.
3. **Make it observable mid-chat, never blocking.** `run_turn` can notice "has a deep brief landed for this company since this conversation started?" and fold it in if so — the same "not required behavior, just making the signal available" pattern `kb_confidence_flags` already established, not a new hard dependency any turn must wait on.

## 3. Architecture

```
app/research/
  deep.py              deep_research(intake) -> dict[str, object]  (fields merged into a dossier/brief)

.claude/skills/teg-deep-research/
  SKILL.md              much larger search budget, explicit multi-source diligence instructions,
                         explicit "directional, not exact" caveats for third-party financial/review data

app/store/
  models.py             CompanyBriefRow gains `depth: str` ("light" | "deep")
  migrations/versions/0006_company_brief_depth.py

app/api/inquiries.py     kicks off the background task (FastAPI BackgroundTasks needs the request
                          handler, not something buried inside Orchestrator)

app/orchestrator.py       run_turn gains a cheap "did a deep brief land?" check

tests/research/
  test_deep.py           fake-ClaudeCli, no network — same pattern as tests/verify/test_claude_verifier.py
tests/api/
  test_deep_research_background_task.py
```

### 3.1 `deep_research()` — one-shot harness, same shape as `ClaudeWebSearch`/`claude_verifier.py`, not `KBExplorer`

Same reasoning `claude_verifier.py` §3.1.2 already established for this codebase: `WebSearch`/`WebFetch` are native `claude` CLI tools, so the CLI subprocess runs its *own* internal agentic loop when granted them — a second Python-level loop around it would duplicate one that already exists one process down. `deep_research()` is one `ClaudeCli.generate()` call, `tools=["WebSearch", "WebFetch"]`, with:

- **A much larger search budget**, stated in `.claude/skills/teg-deep-research/SKILL.md`'s prose (the same mechanism `teg-research`/`teg-verify` already use for their own, smaller budgets) — explicitly scoped to cover firmographic depth (funding status, headcount/revenue trend if publicly findable), review-platform sentiment (aggregated themes, not raw scraped review text — matching the Tudip brief's "recurring complaint themes... approximate mention counts" shape, never a specific person's review verbatim), competitive-visibility signals, named clients, certifications/partnerships, and notable PR/leadership visibility.
- **A generous wall-clock timeout only** (`deep_research_timeout_s`, proposed default 300–600s) — no step count cap, matching `claude_verifier`'s philosophy: the skill's own prose budget plus the timeout are the two bounds, not a hand-rolled loop counter.
- **An explicit "directional, not exact" instruction** for anything sourced from third-party aggregators (Tracxn/Tofler/EMIS-style financial estimates, Glassdoor-style sentiment) — the skill must carry forward the same caveat the Tudip brief states in its own Sources section, so nothing downstream (guardrails, a future proposal use) can treat an estimated revenue band as a verified fact.

Output schema (`DeepFindings`, new in `app/research/deep.py`) is a superset addition, not a `ResearchDossier` replacement — it captures fields `ResearchDossier` doesn't have today (funding status, growth-trend narrative, review-sentiment themes, competitive positioning, named clients, certifications) and is stored as its own JSON blob in `company_briefs.dossier_json` alongside (not overwriting) the light dossier's fields, with `depth="deep"` marking that this row now carries the richer data.

### 3.2 Trigger point and background-task lifecycle

Kicked off right after `Orchestrator.run_pipeline` creates the `ChatSession` — after the opening message is already computed and about to ship, never before it. This has to be wired from `app/api/inquiries.py`'s request handler (FastAPI's `BackgroundTasks` is a dependency-injected object tied to the response cycle; `Orchestrator.run_pipeline` itself has no natural place to receive one), which is a real, separate wiring change from the previous work — flagged explicitly here rather than assumed.

**v1 uses FastAPI's `BackgroundTasks`** (runs after the response is sent, same process, same worker) — explicitly NOT a durable job queue. Non-goals stated plainly (§5): no persistence across a restart, no retry on failure, no cross-process distribution. If the process restarts mid-pass, that pass is simply lost — silently, logged, and the light dossier remains what every subsequent turn uses. This is a deliberate, stated trade-off for v1, not an oversight; a real job queue (Celery, arq, or similar) is real future work if deep research proves valuable enough to justify the operational cost.

### 3.3 Mid-chat pickup, never blocking

`run_turn` gains a cheap read (`CompanyBriefRepo.get_by_company()`, already shipped) checked once per turn: if a row exists with `depth == "deep"` and `updated_at` newer than the session's `started_at`, its findings are folded into `learned_facts` the same way `_derive_learned_facts` already flattens discovery-v2 signals — additive context for `PersuasionAgent.respond()`'s prompt, never a required input, never awaited or blocked on. If no deep row exists yet (the common case for the first several turns of any conversation), this is a no-op read, not a wait.

### 3.4 Non-duplication with the light pass

The reuse/staleness logic already shipped for `company_briefs` (`Orchestrator._reuse_company_brief`) governs the LIGHT pass. The deep pass gets its own, coarser gate: before kicking off a background deep-research task, check whether a `depth="deep"` row already exists and is fresh (same `company_brief_staleness_days` setting, or a separate, longer `deep_research_staleness_days` — deep diligence goes stale slower than a quick firmographic lookup, so a longer window is defensible, e.g. 90 days) — if so, skip kicking off a new one. This check-then-fire is not atomic (§6 risk), acceptable for v1 since `company_briefs` upserts are idempotent — worst case is duplicate work, not a correctness bug.

## 4. Testing

- `tests/research/test_deep.py` — `deep_research()` against a fake `ClaudeCli` (same `_FakeClaude(ClaudeCli)` pattern as `tests/claude/test_web_research.py`/`tests/verify/test_claude_verifier.py`, no live network): asserts `tools == {"WebSearch", "WebFetch"}`, asserts the skill is loaded/addressed correctly, asserts a `RuntimeError` from the CLI degrades to "no deep findings" rather than raising, asserts `deep_research_timeout_s` is actually passed through.
- `tests/api/test_deep_research_background_task.py` — using FastAPI's `TestClient`, which runs `BackgroundTasks` synchronously before returning in the sync client (or via explicit `await` patterns for the async client) — asserts posting an inquiry schedules exactly one background deep-research task, and that a SECOND inquiry for the same company within the staleness window does not schedule a second one.
- A test proving a failed/timed-out deep pass never raises out of the background task machinery and never touches `company_briefs` (the light-pass row, if any, is left untouched) — matching every other soft-fail convention already established in this codebase (`NodeSoftFailure`, `_ensure_web_tool`'s probe fallback, etc.).
- A `run_turn` test: a `depth="deep"` row newer than session start gets folded into `learned_facts`; a `depth="light"` row, or a `depth="deep"` row OLDER than session start (started before this conversation began), does not.

## 5. Non-goals

- No durable, cross-process job queue in v1 — FastAPI `BackgroundTasks` only, explicitly best-effort (§3.2).
- No retry logic for a failed/killed deep pass — a silent no-op, logged, light dossier remains authoritative.
- No UI/API surface exposing deep-research status to the prospect or to a human reviewer in v1 — this spec only gets the data gathered and stored; surfacing "research in progress" anywhere is separate, later work.
- No change to `render_company_brief()`'s signature or behavior in this spec — a richer, `DeepFindings`-aware rendering is real follow-up work once this pass exists and produces real data to render, not bundled in here.
- No live per-inquiry cost cap beyond the staleness-gated non-duplication in §3.4 — a hard rate limit or spend cap, if needed, is a `config/settings.py` addition to make later, once real usage data exists.

## 6. Risks

| Risk | Mitigation |
|---|---|
| A deep pass outlives the process (restart/deploy mid-run) | Explicitly best-effort in v1 (§3.2/§5) — logged, not retried, light dossier stays authoritative. A durable queue is real future work if this proves valuable. |
| Cost: an uncapped-by-step-count, wide-budget search pass run for every inquiry | Gated behind the staleness-based non-duplication check (§3.4) before firing at all; `deep_research_timeout_s` bounds worst-case duration per pass even though search count isn't capped. |
| Third-party financial/review data is directional, not verified fact — the exact caveat the Tudip brief itself states | The `teg-deep-research` skill carries this caveat into every generated field explicitly (§3.1); anything downstream that later touches this data (a future proposal use) must preserve, never strip, that framing. |
| Check-then-fire duplicate-prevention (§3.4) is not atomic | Accepted for v1 — `company_briefs` upserts are idempotent, so a race produces wasted duplicate work, not a correctness bug. Flagged, not silently assumed safe. |
| A background task silently swallowing an exception hides a real, recurring failure (e.g., a broken skill file) from anyone | Every soft-fail path logs at WARNING with enough detail to diagnose (company name, error), matching this codebase's existing "log every degraded-path decision" discipline (`NodeSoftFailure`, `_ensure_web_tool`, `_reuse_company_brief`/`_save_company_brief`'s own try/except blocks). |
