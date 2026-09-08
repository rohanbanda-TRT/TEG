# TEG Outreach — Agentic KB Explorer — Design Spec

> **Status:** Approved design (2026-09-01)
> **Supersedes:** the KB-access portions of `2026-09-01-teg-conversation-and-detailed-proposal-design.md` §2.1–§2.2 (the "KB loader extracts organizer/speaker titles" work). The conversation/proposal behaviour in that spec still stands; only *how* the KB is read changes.

## 1. Problem

`app/kb/loader.py` reads the 215-file TEG knowledge base by regex-parsing markdown
into dataclasses at startup (`CompanyRecord`, `PersonRecord`, `PricingInfo`,
`GoalsAndPains`) and answering lookups from those in-memory structures.

This is brittle in the way that keeps biting us:

- `peers_in_sector()` silently returned `[]` because per-company `category`
  labels ("AI Consulting / Custom AI & Software Development") don't match the
  sector headings in `sector_wise_participation.md` ("AI & Machine Learning"),
  and because the sector blocks are markdown tables the parser didn't read.
- Organizer/speaker titles and bios aren't surfaced because the parser doesn't
  know those file shapes.
- Every new KB file format needs a new parser branch.
- Cross-references humans wrote into the prose ("also in Fintech/EdTech";
  "see `organizers_team/organizers_and_team.md`") are invisible to regex.

The KB is well-structured for a *reader*: it has an `INDEX.md` master map,
one file per company (`exhibitors/companies/<slug>.md`) and per person
(`organizers_team/<slug>.md`, `speakers/individuals/<slug>.md`), and prose
cross-references. A reader that can list directories, open files, and grep —
the way Claude Code explores a repo — navigates it naturally.

## 2. Goal

Replace `app/kb/loader.py` and `app/research/kb_retriever.py` entirely with an
**agentic KB explorer**: an LLM tool-use loop with read-only, KB-scoped
filesystem tools that navigates the knowledge base step by step to answer a
stated goal. **No regex parsing of KB markdown anywhere in the application.**

The one exception is a **build-time snapshot script** that extracts the handful
of exact-match facts the deterministic guardrail layer needs into a committed
JSON file.

## 3. Architecture

```
app/kb/
  fs_tools.py      list_dir / read_file / grep  — read-only, rooted at kb_path
  explorer.py      KBExplorer.explore(goal) -> ExploreResult   (the tool-use loop)
  facts.py         load() -> Facts   — reads the generated snapshot
  facts.json       generated snapshot (cleared testimonials + exhibitor names)

app/llm/
  base.py          + generate_with_tools(...)   (new LLMClient method)
  gemini_client.py   implements generate_with_tools
  fake.py          FakeLLMClient + ReplayLLMClient support generate_with_tools

scripts/
  build_kb_facts.py       regenerates app/kb/facts.json from the KB
  record_kb_transcript.py  runs a live explore() and saves the model turns

tests/kb/
  test_fs_tools.py    deterministic, hits the real KB on disk
  test_facts.py       deterministic; includes build_kb_facts.py --check
  test_explorer.py     record/replay: recorded model turns, live KB files
  transcripts/*.json   4 recorded exploration sessions
```

### 3.1 Deleted

- `app/kb/loader.py` — the `_norm` / `_token_set_ratio` name-similarity helpers
  it contains **move** to `app/kb/_names.py` (unchanged bodies); everything else
  in the file is removed.
- `app/research/kb_retriever.py`
- `tests/kb/test_loader.py`
- `tests/kb/test_goals_and_pains.py`

### 3.2 Consumers — before / after

| Consumer | Before | After |
|---|---|---|
| `ResearchAgent` | `KBRetriever().lookup()` per track + `kb.peers_in_sector` + `kb.canonical_sector` | two concurrent `explorer.explore(...)` calls (company goal, person goal); each goal names the facts + peers wanted |
| `ProposalAgent` | `kb.goals_and_pains()`, `kb.cleared_testimonials()`, `kb.peers_in_sector()` | `explorer.explore("TEG goals, mechanism, evidence, and the pain points for persona <P>, plus up to 5 sector peers for <sector>")`; cleared testimonials from `facts.load()` |
| `guardrails.py` | `get_kb().cleared_testimonials()`, `get_kb()._companies` | `facts.load().cleared_testimonials`, `facts.load().exhibitor_names` |
| `AnalysisAgent` | `kb._companies` name list + `_token_set_ratio` for canonicalisation | `facts.load().exhibitor_names` for the known-company list; imports `_token_set_ratio` from `app/kb/_names.py` (string similarity of two names — not markdown parsing) |
| `PersuasionAgent` | `import get_kb` (unused, "kept for test patching") | import removed |

### 3.3 Config additions (`config/settings.py`)

```python
kb_explore_timeout_s: int = 30     # wall-clock per explore() call
kb_explore_max_steps: int = 8      # model turns before a forced answer
kb_read_file_max_bytes: int = 6144 # read_file page size
kb_grep_max_matches: int = 30      # grep result cap
```

## 4. FS tools (`app/kb/fs_tools.py`)

Three functions. All take paths relative to the KB root
(`Settings.kb_path`, resolved to an absolute path once). Every path argument is
`os.path.realpath`-resolved and checked with `os.path.commonpath([root, target])
== root`; a `..` escape, an absolute path, or a symlink out of the root returns
an error **string** (the model sees it and adapts) — it never raises out of the
loop. A missing file / directory likewise returns an error string.

| Tool | Signature | Returns | Cap |
|---|---|---|---|
| `list_dir` | `list_dir(path=".") -> str` | one entry per line; `name/` for dirs, `name  (<n> B)` for files; directories first, then files, each group sorted | 200 entries, then `… (<n> more entries)` |
| `read_file` | `read_file(path, offset=0) -> str` | UTF-8 text from byte `offset` | `kb_read_file_max_bytes`; if more remains, append `\n… (truncated at <offset+n> B; call read_file with offset=<offset+n> for more)` |
| `grep` | `grep(pattern, path=".") -> str` | for each match: `<relpath>:<lineno>: <line stripped>`; searches recursively when `path` is a dir, `*.md` only | `kb_grep_max_matches`, then `… (<n> more matches not shown; narrow the pattern or pass a path)` |

`grep` compiles `pattern` with `re.compile(pattern, re.I)`; an invalid regex
returns an error string. This is regex *searching* over file contents (like
ripgrep), not regex *parsing of document structure* — the thing being
eliminated.

Each tool call is logged via `app/obs.py` at INFO:
`[kb-explore:<track>] read_file exhibitors/companies/third_rock_techkno.md (offset=0)`.

## 5. The explorer (`app/kb/explorer.py`)

```python
class ExploreResult(BaseModel):
    found: bool                 # did the KB contain this subject at all
    summary: str                # prose answer to the goal (<= ~1500 chars)
    facts: dict[str, str]       # flat key -> value, keys taken from the goal
    sources: list[str]          # KB relpaths the answer draws on
    confidence: float           # 0.0-1.0, the model's own estimate

class KBExplorer:
    def __init__(self, llm: LLMClient, *, model: str | None = None,
                 root: Path | None = None) -> None: ...

    async def explore(self, goal: str) -> ExploreResult: ...
```

### 5.1 `_SYSTEM` prompt (fixed)

> You explore a read-only knowledge base about Tech Expo Gujarat 2026 to answer
> a research goal. You have `list_dir`, `read_file`, and `grep`. Start by
> reading `INDEX.md` to learn the layout. Then open the specific profile
> file(s) for the subject. Follow `see \`path\`` / "also in ..." references
> when they bear on the goal. Answer **only** from files you have actually
> read — never guess a fact. When you can answer, stop calling tools and give
> the final answer as JSON matching the ExploreResult schema: set `found`
> false if the KB has no profile for the subject; put every requested fact in
> `facts` (omit a key you could not find); list the files you used in
> `sources`.

### 5.2 Loop

```
messages = [user: goal + "\n\nBegin by reading INDEX.md."]
for step in range(kb_explore_max_steps):
    last = (step == kb_explore_max_steps - 1)
    sys = _SYSTEM + ("\n\nYou must give the final JSON answer now; do not call tools." if last else "")
    resp = await llm.generate_with_tools(system=sys, messages=messages,
                                         tools=_TOOL_SPECS, model=self._model)
    if resp.tool_calls and not last:
        for call in resp.tool_calls:
            out = _dispatch(call)           # runs list_dir/read_file/grep, catches errors to str
            messages.append(tool_result(call.id, out))
        continue
    # final text answer -> structured parse
    return await self._parse(messages, resp.text)
# loop fell through without a final answer (only if last turn still returned tool_calls)
return await self._parse(messages, resp.text or "")
```

`_parse(messages, text)` calls `llm.generate_structured(system="Return the
ExploreResult described by this transcript.", messages=messages + [assistant:
text], schema=ExploreResult)`. On any parse failure it returns
`ExploreResult(found=False, summary="", facts={}, sources=[], confidence=0.0)`.

### 5.3 Limits (all enforced)

- **Step cap** — `kb_explore_max_steps` (8). The final permitted turn forbids
  tool calls in its system message.
- **`read_file` byte cap** — `kb_read_file_max_bytes` (6144) with `offset`
  pagination. Company/person profiles are small; `INDEX.md` and
  `sector_wise_participation.md` are large and will be paged.
- **`grep` match cap** — `kb_grep_max_matches` (30).
- **Wall-clock** — `ResearchAgent` wraps each call:
  `asyncio.wait_for(explorer.explore(goal), timeout=settings.kb_explore_timeout_s)`.
  On `TimeoutError`, treat as `ExploreResult(found=False, confidence=0.0)` — the
  pipeline then behaves exactly as it does on today's research hard-timeout
  (sets `ask_prospect`).

## 6. Integration into `ResearchAgent`

`run()` keeps `asyncio.gather` over two coroutines:

The company goal makes the model read both `event_overview/event_info.md`
("Industries represented") and `sector_wise_participation.md`, then pick the ONE
best-fitting TEG sector. **TEG is not IT-only** — the sector list spans tech
verticals (AI & Machine Learning, Fintech, Cybersecurity, Cloud &
Infrastructure, Data & Analytics, Software Development & IT Services, Digital
Marketing & SEO, HR Tech, IoT & Hardware, Enterprise Software, Healthcare Tech,
EdTech) *and* broader industries (Manufacturing, Automobile, Power & Energy,
Agriculture, Education, Healthcare, Pharmaceutical, Textile, Jewellery, Retail,
Logistics, Finance). Full goal text is in the plan (Task 8). The person goal is
as before (designation, seniority, is_technical, teg_role, background;
`found=false` if no profile).

- `sector` in the dossier is `explorer facts["sector"]` when the explorer found
  it, else `synth.sector` from the web-fallback classifier (see below). No
  regex keyword map, no `canonical_sector()`.
- `peer_companies` is `facts["sector_peers"]` split on commas, stripped,
  de-duplicated, own-company removed, capped at 5.
- `relationship` logic unchanged (`teg_role == "organizer"` -> `insider`,
  etc.), reading `person facts["teg_role"]` and `company facts["teg_history"]`.
- **Web fallback**: if a company/person `explore()` returns `found=False` or
  `confidence < 0.5`, the existing Tavily -> scrape -> `_Synthesis` cascade runs
  for that track. **`_Synthesis` now also classifies the sector**: its prompt
  passes the same broad TEG-sector list and instructs the model, when the web
  text describes the business but names no formal industry, to pick the closest
  TEG sector (fixes the observed `sector=None` for a non-KB company like "Itorix
  Infotech LLP", an SEO firm -> "Digital Marketing & SEO"). `ask_prospect` is
  set from the post-fallback id-confidence, same thresholds.
- If a sector is known but `peer_companies` is empty (typical for a web-fallback
  company that is not itself a TEG exhibitor), the ResearchAgent makes ONE small
  bounded `explore("List up to 5 TEG exhibitors in the '<sector>' sector from
  sector_wise_participation.md")` to populate peers — keeping all KB reading
  inside the explorer.

`_track()` loses its KB branch entirely — it becomes the web-only cascade,
invoked only when the explorer missed.

## 7. Guardrail snapshot

### 7.1 `scripts/build_kb_facts.py`

Standalone script, **not imported by the app**. The *only* place regex-parsing
of KB markdown remains — it is a build tool whose output is reviewed in the git
diff.

Reads:
- `testimonials/exhibitor_testimonials.md` — the "✅ Attributed Testimonials"
  section only -> `cleared_testimonials: [{name, role, quote}]` (quote text and
  attributed name verbatim).
- every `exhibitors/companies/*.md` first `# ` heading, plus the company names
  in `sector_wise_participation.md` tables -> `exhibitor_names: [str]`, union,
  de-duplicated, canonical spelling preserved.

Writes `app/kb/facts.json`:

```json
{
  "generated_from_kb_at": "2026-09-01",
  "cleared_testimonials": [
    {"name": "...", "role": "...", "quote": "..."}
  ],
  "exhibitor_names": ["Third Rock Techkno", "ViitorCloud", "..."]
}
```

`--check` mode: rebuild in memory, compare to the committed file, exit non-zero
if they differ (wired into CI so a KB edit that forgets to regenerate fails).

### 7.2 `app/kb/facts.py`

```python
@dataclass(frozen=True)
class Testimonial:
    name: str
    role: str
    quote: str

@dataclass(frozen=True)
class Facts:
    generated_from_kb_at: str
    cleared_testimonials: tuple[Testimonial, ...]
    exhibitor_names: frozenset[str]
    exhibitor_names_lower: frozenset[str]

@lru_cache
def load() -> Facts: ...     # reads app/kb/facts.json
```

Zero latency, fully deterministic, no markdown at runtime.
`guardrails.py` `_cleared_names()` / `_kb_company_names()` become one-liners over
`facts.load()`.

## 8. LLM abstraction (`app/llm/`)

### 8.1 `LLMClient.generate_with_tools`

```python
class ToolSpec(TypedDict):
    name: str
    description: str
    parameters: dict          # JSON schema

class ToolCall(BaseModel):
    id: str
    name: str
    args: dict

class ToolTurn(BaseModel):
    tool_calls: list[ToolCall] = []
    text: str = ""            # set when the model answers instead of calling tools

async def generate_with_tools(
    self, *, system: str, messages: list[LLMMessage | ToolResultMessage],
    tools: list[ToolSpec], model: str | None = None,
    max_tokens: int = 2048, temperature: float = 0.2,
) -> ToolTurn: ...
```

`ToolResultMessage` is `{"role": "tool", "tool_call_id": str, "content": str}`.

### 8.2 `GeminiClient.generate_with_tools`

Maps `tools` to `google.genai` `FunctionDeclaration`s, sends the running
`contents` list, reads `response.function_calls` (-> `ToolTurn.tool_calls`) or
`response.text` (-> `ToolTurn.text`). Reuses the existing `_prepare_schema`
sanitiser for the tool `parameters` (strip `additionalProperties`, resolve
`$ref`). Reuses the retry-with-doubled-headroom already in `generate()`.

Automatic function calling is **not** used — the loop stays in `KBExplorer` so
it is provider-agnostic and interceptable for record/replay.

### 8.3 `FakeLLMClient` / `ReplayLLMClient`

- `FakeLLMClient.generate_with_tools` — pops the next queued item; if it is a
  `ToolTurn`, returns it; existing schema-aware matching for `generate_structured`
  unchanged.
- `ReplayLLMClient` (new, `app/llm/replay.py`) — constructed from a transcript
  dict; `generate_with_tools` pops the next `model_turns` entry and returns it
  as a `ToolTurn`; `generate_structured` returns the transcript's `final`
  parsed into the requested schema. Raises if the queue is exhausted or the
  requested schema doesn't match.

## 9. Testing

### 9.1 `tests/kb/test_fs_tools.py` — deterministic, real KB on disk

- `list_dir(".")` contains `INDEX.md` and `exhibitors/`; dirs sort before files.
- `read_file("exhibitors/companies/third_rock_techkno.md")` contains
  `"Third Rock Techkno"`.
- `read_file` of a > 6 KB file (`INDEX.md`) truncates at 6144 and appends the
  offset notice; `read_file(..., offset=6144)` returns the continuation.
- `grep("Third Rock Techkno")` yields a line from
  `exhibitors/companies/third_rock_techkno.md`.
- `grep` of a common token caps at 30 matches with the "more matches" line.
- `grep("(")` (invalid regex) returns an error string, no exception.
- Escape attempts — `read_file("../../../etc/passwd")`, `list_dir("/")`,
  `read_file("exhibitors/../../secrets")` — each returns an error string, no
  exception, nothing read outside the root.

### 9.2 `tests/kb/test_facts.py` — deterministic

- `load()` is cached (`load() is load()`).
- every `cleared_testimonials` entry has non-empty `name` and `quote`.
- `exhibitor_names` contains `"Third Rock Techkno"` and `"ViitorCloud"`.
- `subprocess` run of `python scripts/build_kb_facts.py --check` exits 0
  against the committed `facts.json`.

### 9.3 `tests/kb/test_explorer.py` — record / replay

**Recording.** `scripts/record_kb_transcript.py <name> "<goal>"` runs
`KBExplorer(get_llm()).explore(goal)` against **live Gemini + live KB files**
and writes `tests/kb/transcripts/<name>.json`:

```json
{
  "goal": "Profile the company Third Rock Techkno. Return facts: sector, ...",
  "model_turns": [
    {"tool_calls": [{"id": "c1", "name": "read_file", "args": {"path": "INDEX.md"}}]},
    {"tool_calls": [{"id": "c2", "name": "read_file",
                     "args": {"path": "exhibitors/companies/third_rock_techkno.md"}}]},
    {"tool_calls": [{"id": "c3", "name": "grep",
                     "args": {"pattern": "Third Rock", "path": "sector_wise_participation.md"}}]},
    {"final": "{\"found\": true, \"summary\": \"...\", \"facts\": {\"sector\": \"AI & Machine Learning\", \"sector_peers\": \"ViitorCloud, Green Apex, ZeroThreat, Bytes Technolabs, Eternal Web\"}, \"sources\": [\"exhibitors/companies/third_rock_techkno.md\", \"sector_wise_participation.md\"], \"confidence\": 0.9}"}
  ]
}
```

**Only the model's outputs are stored — never tool results.**

**Replay.** A `ReplayLLMClient` seeded from the transcript drives the loop; the
FS tools hit the **real KB on disk**. Assertions per transcript:
- `result.found` is as expected.
- named keys in `result.facts` have the expected values (e.g.
  `facts["sector"] == "AI & Machine Learning"`, `"ViitorCloud" in facts["sector_peers"]`).
- `result.sources` includes the expected profile path.
- **Every path the transcript reads still resolves.** If a KB file named in a
  transcript has moved or been deleted, `read_file` returns an error, the
  assertions fail, and the failure message says "re-record `<name>`". Staleness
  is loud, not silent.

**Coverage — 4 transcripts, one per pipeline shape:**

1. `known_it_service.json` — TRT / Tapan Patel (organizer -> `insider`).
2. `known_company_unknown_person.json` — TRT / "Rohan" (`person found=false`).
3. `ai_startup.json` — an AI-startup-persona company profile.
4. `company_not_in_kb.json` — a made-up company; explorer returns `found=false`
   within a couple of steps.

### 9.4 Existing pipeline tests

`tests/agents/test_research.py`, `test_proposal.py`, `test_persuasion.py` inject
a `ReplayLLMClient` (seeded with the relevant transcript) or a hand-built
`FakeLLMClient` queue where a full transcript is overkill. The live-Gemini E2E
test (`tests/test_e2e_*`) stays as the one non-hermetic integration check and
gains a KB-exploration assertion (dossier has a real sector + non-empty
`peer_companies` for TRT).

## 10. Non-goals

- No write access to the KB, ever.
- No general-purpose filesystem tool — the tools are KB-root-locked. A future
  need to point them at `trt-kb-agent/` is a separate change.
- No caching of `explore()` results across inquiries in this iteration
  (the wall-clock + step caps keep a single call bounded; per-inquiry caching
  can come later if latency demands it).
- `pricing()` — the proposal's `_PRICING_BY_PERSONA` table is already
  hard-coded in `app/agents/proposal.py` from the pricing KB; that stays as is.
  The explorer is not asked for pricing.

## 11. Risks

| Risk | Mitigation |
|---|---|
| Added latency: 3–8 LLM round-trips per track, ~15–40k tokens/inquiry | Step cap 8, `read_file` 6 KB pages, `grep` 30-match cap, 30 s wall-clock; web-fallback path unchanged so a slow/empty explore still yields a usable dossier |
| Non-determinism in the pipeline | Guardrail-critical facts are in the deterministic `facts.json`; pipeline tests use `ReplayLLMClient`; only the CI E2E test calls live Gemini |
| Transcript staleness when the KB is reorganised | Replay uses live files -> a moved file fails the test loudly with a "re-record" message |
| `generate_with_tools` is new surface on every client | Gemini implementation reuses existing schema sanitiser + retry; Fake/Replay are thin; one integration test exercises the real Gemini tool loop |
| `build_kb_facts.py` drift | `--check` mode in CI fails the build if `facts.json` is stale |
