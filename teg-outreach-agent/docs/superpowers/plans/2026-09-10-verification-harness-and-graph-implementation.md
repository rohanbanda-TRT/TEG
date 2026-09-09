# Verification Harness & Graph — Implementation Status

Implements docs/superpowers/specs/2026-09-10-verification-harness-and-graph-design.md
(the version revised twice per review: the Rule A/Rule B split in §3.2.4, the
`pricing.json` snapshot in §3.2.1, the graph in §3.3). This note records what
shipped, what deliberately deviated from the spec and why, and what is
explicitly deferred rather than silently dropped.

## Shipped, tested, green

**Phase 1 — pricing snapshot (§3.2.1).** `scripts/build_kb_pricing.py` parses
`pricing_and_packages.md`'s stall/sponsor/payment-plan tables into
`app/kb/pricing.json` (own `--check` mode, kept as a sibling script to
`build_kb_facts.py` rather than folded in — see the docstring in
`build_kb_pricing.py` for why). `app/kb/pricing.py` exposes `load_pricing()`.
`_PRICING_BY_PERSONA` is fully deleted from `app/agents/proposal.py` — `git
grep "_PRICING_BY_PERSONA"` returns nothing outside this file and the spec
docs. `tests/kb/test_pricing.py` covers ladder shape, live KB-markdown
cross-check, and the `--check` drift guard.

**Phase 2 — ConversationSignals + tier selection (§3.2.2).**
`ConversationSignals` added to `app/domain/schemas.py`.
`_extract_conversation_signals()` (module-level in `proposal.py`) makes one
small structured-extraction LLM call from the transcript; `_select_tier()`
implements the Never-Guess gate exactly as specified. Wired into `build()` in
place of the old fixed `fallback_pkg` lookup — the first draft now targets
the right tier when the transcript signal is explicit.

Follow-up fix delivered as specified: an **inferred-only** signal
(`signal_confidence == "inferred"`) now produces a distinct, low-severity
`SECTION_INCONSISTENCY::package_tier_inferred_only` flag (`_inferred_tier_note`)
— visible in `flags`/`needs_review`, but never changes `recommended_package`.
This is a genuinely different code from the explicit-signal
`SECTION_INCONSISTENCY::package_tier`, so a human reviewer can tell "we
corrected it" from "we noticed a hint and did nothing — you may want to
look." (§3.2 of the spec file itself was updated in the prior review pass to
describe this distinction — no further spec edit was needed here.)

**Phase 3 — check_section_consistency + two-rule resolution (§3.2.3, §3.2.4).**
Implemented with the exact 3-parameter signature `(p, signals,
price_requested)` per the review's explicit instruction, superseding the
spec markdown's informal 2-parameter closure sketch. All three checks
implemented as specified. `_regenerate_sections()` and
`_resolve_by_safety_order()` are `ProposalAgent` methods (need `self._generate`).
Rule A corrects `recommended_package` toward the signal; Rule B scrubs to
`PROPOSAL_SAFE_SECTIONS` (a new `"how_a_teg_plays_out"` entry was added there,
one sentence per persona, since that field didn't have a safe-fallback
entry before). `proposal_consistency_max_loops = 1` added to
`config/settings.py`.

Follow-up fix delivered as specified: an explicit **visitor-persona guard**
in `check_section_consistency` — `p.persona != "visitor"` short-circuits the
package_tier check entirely, rather than relying on `_select_tier`'s
single-entry-ladder collapse to make a mismatch harmless implicitly.

**Phase 4 — tests/agents/test_proposal_consistency.py.** Every case from the
spec's §4, plus both review follow-ups (inferred-only case, visitor-guard
case) — 9 tests, all passing. One shared-infrastructure fix was needed and
applied: `FakeLLMClient.generate_structured`'s no-match fallback used to pop
the first queued item regardless of type (FIFO), which would have silently
fed a queued `Proposal` object to the new `ConversationSignals` call in
every existing proposal test with a non-empty transcript. Fixed by
preferring a zero-value instance of the requested schema (when the schema's
fields are all optional/defaulted) over consuming an unrelated queued item —
this is what let the new call get added without every existing test also
needing to stub it, and is itself a defensible, narrowly-scoped test-infra
improvement, not a production change.

**Phase 5 — verification harness (§3.1).** `app/verify/schemas.py`,
`claims.py` (4 claims, values re-confirmed against the current KB this pass,
not copied from the spec unchecked), `claude_verifier.py` (one
`ClaudeCli.generate()` call per claim, `tools=["WebSearch","WebFetch"]`,
`teg-verify` skill loaded by name via `load_skill()`/`render_skill()`, never
granted as a discoverable `Skill` tool). `.claude/skills/teg-verify/SKILL.md`
written in the same genre as `teg-research/SKILL.md`. `scripts/run_verification.py`
implements the `<claim-id>` / `--all` CLI exactly per §3.1.6.
`verify_all()`'s `resume=` usage re-confirmed via `git grep -n "resume="`
immediately before writing this code (still the first real caller) and
implements the non-resume retry fallback on a resumed call's `RuntimeError`.

**Deviation, stated plainly:** `tests/verify/test_claude_verifier.py` does
NOT use recorded live transcripts the way `tests/kb/test_explorer.py` does.
This environment has no live `claude` CLI credentials to record a real
transcript with. Instead, these tests inject a `_FakeClaude(ClaudeCli)`
subclass returning canned `ClaudeResult`s — the SAME pattern
`tests/claude/test_web_research.py` already uses for every other
`ClaudeCli`-backed caller in this repo, not an invented new pattern. All
four required cases (confirmed / conflicting / unverifiable / RuntimeError)
are covered, plus two more for the `resume` chain. A genuine
recorded-transcript suite (mirroring `test_explorer.py` exactly) is real
follow-up work once this environment has live credentials — noted in the
test file's own docstring, not hidden.

**Phase 6, items 1-2 — graph runner core (§3.3.1, §3.3.2).** `app/graph/node.py`,
`runner.py`, `errors.py` implemented exactly as specified, including the
build-time distinction between `GraphValidationError` (a key nothing in the
whole graph ever produces) and `GraphCycleError` (a mutual dependency among
otherwise-satisfiable nodes). `run_graph()` uses `asyncio.TaskGroup` (not a
bare `asyncio.gather`) specifically so a hard failure in one node of a layer
actually cancels its siblings — the spec's pseudocode used `gather`, which
does NOT cancel siblings on its own; this is a correctness fix over the
literal pseudocode, made to honor the spec's own stated requirement ("sibling
tasks in that layer are cancelled," §4) rather than its literal sketch.
`tests/graph/test_runner.py` covers every case in §4: concurrency-by-timing,
soft-failure fallback, hard-failure propagation + sibling cancellation,
unsatisfiable-reads at build time, and a cyclic graph — 7 tests, all passing.

**Phase 6, item 3 — ResearchAgent track extraction (§3.3.3's risk
mitigation).** `run_company_track(intake, *, budget=None)` /
`run_person_track(intake, *, budget=None)` added as public wrappers around
the EXISTING (unchanged) `_company_track`/`_person_track` — a pure, additive
refactor verified green against the full existing `tests/agents/test_research.py`
suite, plus three new tests for the wrappers themselves.

**Phase 7 — uncapping Claude's web research (a config/behavior fix raised in
review, separate from the spec file).** `claude_cli_enabled` now defaults to
`True` (`config/settings.py`) — `ClaudeWebSearch` is the default prospect-
research backend; Tavily/Brave is wired as an explicit fallback triggered
ONLY by `ClaudeCli.probe()` reporting unavailable, via a new
`ResearchAgent._ensure_web_tool()` called once at the top of `run()` (probing
needs an `await`, which `__init__` can't do — see the method's docstring).
The probe result is memoized process-wide (`_claude_probe_cache`) so only the
first `ResearchAgent.run()` call in the process ever spawns the probe
subprocess. `research_max_searches_per_track` audited and confirmed to gate
"how many times `.lookup()` is called per track," never conflated with
in-CLI-invocation search depth (that's governed entirely by the
`teg-verify`/`teg-research` skills' own prose budget + `timeout_s`, inside
the subprocess) — left unchanged at 2. `claude_cli_timeout_s` raised
180s → 240s with reasoning in a code comment (room for ~5-10 tool calls at a
realistic 15-25s each). `app/claude/cli.py`'s `run()` now counts
`WebSearch`/`WebFetch` `content_block_start` tool_use events and attaches the
total as `ClaudeResult.tool_calls`, surfaced in the existing
`"claude ok cost=... session=..."` log line as `tool_calls=%d`.
`tests/claude/test_cli.py` and `tests/agents/test_research.py` both updated
with new cases (11 new tests total across the two files).

## Explicitly deferred, not silently dropped

**Phase 6, item 5 — wiring `Orchestrator.run_pipeline` and the top of
`ProposalAgent.build()` through `run_graph()` — NOT done in this pass.**

This is flagged per the task's own instruction ("stop and ask before
deviating... if you hit a case the spec didn't anticipate, flag it rather
than improvising a resolution") rather than forced through, because the spec
genuinely doesn't resolve one real conflict:

`ResearchAgent.run()` today shares ONE `_Budget` instance across both
tracks — `web_left_company`/`web_left_person` are per-track, but
`scrapes_left`/`scrape_calls`/`web_calls` are combined, deliberately capping
total scrape spend for one research pass regardless of which track uses it.
The spec's node table (§3.3.3) gives `research_company`/`research_person`
each only `intake` as a declared input — there is no shared-budget key in
the plain-dict `GraphContext` for two independently-scheduled nodes to
coordinate through. `run_company_track`/`run_person_track` (shipped, tested)
default to a FRESH `_Budget` each when none is passed in — calling them from
two independent graph nodes with no explicit coordination would silently
double the effective scrape budget, a real behavior change from today,
not a neutral refactor.

The fix is not hard — `GraphContext` is typed `dict[str, object]`, so a
shared `_Budget` instance can legally be one of the graph's initial input
values, read by both nodes via a `reads` key like `_research_budget` — but
it's a deliberate architectural call the spec doesn't make explicitly, and
making it silently would mean *this document* is the only place recording
that a choice was made at all. Recommendation, not yet applied: add
`_research_budget` as one more layer-0 initial key both research nodes
declare in `reads`, constructed once by `Orchestrator.run_pipeline` before
calling `run_graph()`. Same open question applies, smaller in scope, to
whether `explore_kb_for_proposal`/`extract_conversation_signals` in the
proposal graph (§3.3.4) need any similar shared resource — a pass over that
table found no equivalent conflict there, only in the inquiry pipeline's
research pair.

Everything else needed to complete this wiring is ready and unblocked: the
graph runner is built and tested, `check_self_consistency`/`_select_tier`/
`extract_conversation_signals`'s logic all already exist as callable units
inside `ProposalAgent`, and `verify_relevant_teg_claims` (§3.3.3) is a small,
new, genuinely independent node (reads a cached log file, no shared state)
with no equivalent open question. The remaining work is node-object
plumbing and fixture updates to the two entrypoints' existing test suites,
not new design.

## Verification

- `pytest tests/kb/test_pricing.py tests/agents/test_proposal_agent.py
  tests/agents/test_proposal_consistency.py tests/verify tests/graph
  tests/agents/test_research.py tests/claude/test_cli.py` — all green.
- Full suite (`pytest -q --ignore=tests/e2e`) run after every phase per the
  task's instruction: **367 passed, 2 pre-existing failures, 4 deselected**.
  - The two failures (`tests/orchestrator/test_run_turn.py::test_run_turn_persists_pair_and_state`,
    `tests/orchestrator/test_run_turn_proposal.py::test_run_turn_populates_wants_proposal_without_generating`)
    are PRE-EXISTING discovery-v2 failures from before this session's work —
    confirmed unrelated (`app/agents/persuasion.py` and the discovery-v2
    modules were not touched by this implementation).
  - **Found incidentally, unrelated to this work, worth flagging separately:**
    `tests/api/test_chat_proposal.py::test_ws_proposal_flow` and
    `::test_ws_proposal_failure_emits_failed` hang indefinitely — confirmed via
    `git diff` that this file has zero changes from this implementation pass,
    and via a stale `pytest tests/api/test_chat_proposal.py::test_ws_proposal_flow`
    process found already running (and abandoned) since September 7, i.e. this
    test was hanging before this session's work began. Root cause, not
    chased further as out of scope for this task: the test still asserts
    `att["pdf_url"].endswith(".pdf")` and fetches a real PDF — stale since the
    `2b6e9e5 feat(proposal): deliver as a link only, drop server-side PDF/PNG
    render` commit, which made `pdf_path`/`pdf_url` always `None`. Deselected
    for this verification pass; worth its own fix, separate from this spec.
- `git grep "_PRICING_BY_PERSONA"` — no hits outside spec/plan docs.
- `git grep "claude_cli_enabled"` — `app/agents/persuasion.py`,
  `app/agents/proposal.py`, `app/agents/research.py`, and `app/kb/explorer.py`
  all gate on the same setting consistently; no site disagrees.

---

## Phase 6 completion (appended, original entries above left unedited)

Follow-up pass: the graph runner was built and tested in isolation, but
`Orchestrator.run_pipeline` and `ProposalAgent.build()` had zero references
to `run_graph`/`app.graph` — confirmed via `grep -n "run_graph\|app.graph"
app/orchestrator.py` returning nothing before this pass started. This
section closes that gap.

### 1. The `_Budget` sharing decision — resolved

Decided: **share one `_Budget` instance via the graph's initial
`GraphContext`.** `Orchestrator.run_pipeline` constructs one `_Budget`
before calling `run_graph()` and puts it in the initial context under
`"_research_budget"`. `research_company` and `research_person` both declare
`_research_budget` as a `reads` key and pass it through explicitly to
`run_company_track`/`run_person_track` — neither ever falls back to the
`budget=None` (fresh-budget-per-call) default, which would have silently
doubled the combined scrape/search cap. `merge_dossier` also reads it (for
accurate `research_cost` logging — `ResearchAgent.merge_tracks()` gained a
`budget=None` parameter for this). `app/agents/research.py`'s comment block
above `run_company_track`/`run_person_track` was updated in place from
"KNOWN GAP" to "RESOLVED", pointing back here.

### 2. `Orchestrator.run_pipeline` wired through `run_graph()`

Implemented as **three separate `run_graph()` calls**, not one graph
spanning the whole pipeline — a deliberate choice, not a shortcut:

- `run_graph([analyze_intake], ...)` — un-timed, exactly matching today.
- `run_graph([research_company, research_person, verify_relevant_teg_claims,
  merge_dossier], ...)`, wrapped in the SAME `asyncio.wait_for(...,
  pipeline_hard_timeout_s)` the old sequential code used, with the SAME
  `ResearchDossier(ask_prospect=[...])` fallback on `TimeoutError`.
- `run_graph([persuasion_init], ...)` — un-timed, exactly matching today.

Why not one flat graph: a single graph-wide timeout would newly cap
`analyze_intake`/`persuasion_init` (currently un-timed) and — more
importantly — a research timeout has to let the pipeline CONTINUE to
`persuasion_init` with a substitute dossier, which a single graph's
all-or-nothing timeout semantics can't express without inventing new
node-level soft-fail behavior for `merge_dossier` that the spec never asked
for. Three scoped calls preserve the exact existing timeout/fallback
contract while still giving the research layer (the part that actually
benefits from parallelism) genuine concurrent execution.

`verify_relevant_teg_claims` (new) reads the most recent
`teg-kb-agent/knowledge_base/_verification_log/*.md`, filters to claims
relevant to `intake.intent_hint`, and returns `verification::<claim_id>`
flags for anything marked `conflicting` — read-only, no live call, wrapped
in its own try/except so a parsing problem can never block or slow the
pipeline. `ResearchDossier` gained a new `kb_confidence_flags: list[str]`
field to carry this forward (not required behavior yet, just making the
signal available).

**Test fix, not a silent loosening:**
`tests/orchestrator/test_run_pipeline.py::test_run_pipeline_research_timeout_uses_empty_dossier`
used to override `ResearchAgent.run()` to simulate a slow research call.
`run_pipeline` never calls `research.run()` on this path any more (the graph
calls `run_company_track`/`run_person_track` directly, per the spec's own
node table), so that override had gone silently dead — the test still
"passed" but for the wrong reason (`PIPELINE_HARD_TIMEOUT_S=0` times out
immediately regardless of whether the overridden method is ever invoked).
Fixed to override `run_company_track` instead — the actual entrypoint the
graph calls — so the test again genuinely exercises the
timeout-to-ask_prospect-fallback contract, not just `PipelineResult`'s
shape. No other existing test in `tests/orchestrator/` needed changes;
`tests/orchestrator/test_run_pipeline.py`,
`test_generate_proposal.py`, `test_run_turn*.py` all still pass unchanged
(the two `test_run_turn*` failures are the same pre-existing discovery-v2
failures noted in the original entries above, confirmed unrelated to this
wiring).

One small correction to the spec's literal node table, made without
ceremony: `merge_dossier`'s declared `reads` includes `intake` in addition
to `company_partial`/`person_partial`/`kb_confidence_flags` — the merge
logic genuinely needs `intake.company_name_canonical` for peer-exclusion and
the sector-peers re-fetch goal, which the original table's row omitted.

### 3. `ProposalAgent.build()` — partial graph adoption, scoped deliberately

Wired `explore_kb_for_proposal` + `extract_conversation_signals` — the one
genuinely independent pair in §3.3.4's chain — through a real 2-node
`run_graph()` call at the top of `build()`. They now run concurrently
instead of the two sequential `await`s this used to be.

**The remaining five steps in §3.3.4's table
(`build_generation_prompt` -> `generate` -> `check_field_guardrails` ->
`regenerate_on_violation` (conditional) -> `check_self_consistency` ->
`finalize`) were deliberately NOT converted into graph nodes.** Each one
needs the prior step's mutated `Proposal` object — a genuine linear
dependency chain with no real concurrency available. Wrapping a strictly
sequential chain in more graph-node ceremony wouldn't change behavior or
performance, only add indirection, so it stays as the existing direct
calls already shipped and tested in the earlier phases (§3.2's tier
selection, cross-field consistency loop, and safety-order resolution are
completely unchanged). This is a scope decision, stated here explicitly
rather than silently leaving the rest of the function looking untouched by
Phase 6 — flagged, not hidden, per the same discipline as item 1's `_Budget`
decision. `tests/agents/test_proposal_agent.py` and
`test_proposal_consistency.py` both pass unchanged (42/42 across both files
plus the Claude-backend and growth-journey suites), confirming the
concurrency change is behavior-invisible from the outside.

### 4. Concurrency proof, end to end

New `tests/orchestrator/test_pipeline_graph_concurrency.py`, one test:
overrides `run_company_track`/`run_person_track` to record a START
timestamp before each sleeps, and monkeypatches `_read_verification_flags`
to record its own timestamp — then runs a REAL `Orchestrator.run_pipeline()`
call end to end and asserts (a) all three timestamps land within a tight
window of each other (proving the graph actually scheduled them
concurrently, not that they happen to have similar durations — recording
completion time instead of start time was tried first and produced a
misleading failure, since `verify_relevant_teg_claims` has no internal
`await` and finishes near-instantly regardless of when it started; fixed by
timing starts, not completions) and (b) total pipeline wall-clock is ~1x the
per-track sleep duration, not ~2x — proving `research_company` and
`research_person` aren't serialized. This is the test that validates Phase
6's actual point was achieved for a real pipeline run, not just that
`app/graph/`'s runner works in isolation.

### 5. Verification harness — confirmed reachable, and a real bug found + fixed

`teg-kb-agent/knowledge_base/_verification_log/` was empty before this pass
— confirmed via `ls`, meaning every real inquiry today would have gotten
`verify_relevant_teg_claims`'s empty fallback silently. Ran
`scripts/run_verification.py --all` for real, against the live KB and the
live web, twice:

- **First run surfaced two real bugs**, not test-only issues:
  1. `run_verification.py`'s `_LOG_DIR` (and `app/orchestrator.py`'s
     `_latest_verification_log()`) computed
     `Path(kb_path).resolve().parent / "_verification_log"` — an off-by-one
     that wrote to `teg-kb-agent/_verification_log/` (sibling of the whole
     `teg-kb-agent` checkout) instead of the spec's
     `teg-kb-agent/knowledge_base/_verification_log/` (sibling of the other
     KB topic directories), because `kb_path` already points AT
     `knowledge_base` — `.parent` was one level too many. Fixed in both
     files to `Path(kb_path).resolve() / "_verification_log"`; the
     wrongly-placed directory from the first run was deleted before
     re-running.
  2. `ClaudeCli.generate()` never declared or forwarded a `resume` parameter
     to `run()` — `app/verify/claude_verifier.py` is the first real caller
     of `resume=` (§3.1.5), and it calls `generate()`, not `run()`, directly.
     This was invisible to every Phase 5 unit test because they all inject a
     `_FakeClaude(ClaudeCli)` subclass overriding `generate()` entirely
     (matching `tests/claude/test_web_research.py`'s existing pattern), so
     none of them exercised the real `generate()` implementation's argument
     list. Fixed by adding `resume: str | None = None` to `generate()`'s
     signature and forwarding it to `run()`. A regression test
     (`test_generate_forwards_resume_to_run`) was added to
     `tests/claude/test_cli.py` — this is exactly the class of bug real
     end-to-end verification is supposed to catch, so it's recorded here
     rather than folded in as if it were part of the original Phase 5 work.
- **Second run succeeded**, live, real cost, `resume` genuinely reused one
  session across all four claims (same `session_id` on all four log lines):
  `dates_venue`: confirmed · `scale_targets`: confirmed ·
  `visitor_pricing_published`: confirmed · `payment_plan_dates`:
  **unverifiable** (the model's own notes flag that the first three of the
  claimed installment dates are already in the past as of today, 9 Sep 2026
  — worth a human's attention on the next KB pass, even though the harness
  correctly declined to call it "conflicting" without web evidence either
  way). Written to
  `teg-kb-agent/knowledge_base/_verification_log/2026-09-09.md`. Confirmed
  `_read_verification_flags()` now finds and parses this file correctly
  (returns `[]` for this inquiry's intent, correctly — nothing is flagged
  `conflicting` this pass).

### Verification (this pass)

- `grep -n "run_graph" app/orchestrator.py app/agents/proposal.py` — real
  call sites in both (not zero).
- Targeted: `tests/orchestrator/`, `tests/agents/test_proposal_agent.py`,
  `tests/agents/test_proposal_consistency.py`,
  `tests/agents/test_proposal_claude_backend.py`,
  `tests/agents/test_growth_journey.py`, `tests/claude/test_cli.py`,
  `tests/verify/`, `tests/agents/test_research.py` — all green (including
  the new concurrency-proof and `resume`-forwarding regression tests).
- Full suite (`pytest -q --ignore=tests/e2e`, same two pre-existing
  `test_ws_proposal_*` deselections as before): **369 passed, 2 pre-existing
  discovery-v2 failures, 4 deselected** — one more passing test than the
  previous full-suite count, accounting for the new concurrency-proof test.
