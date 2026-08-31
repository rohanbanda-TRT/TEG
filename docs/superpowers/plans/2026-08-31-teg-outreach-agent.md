# TEG Inquiry Outreach System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI service plus an embeddable chat widget that researches a TEG inquiry-page prospect (knowledge base first, then free web tools) and runs a persona-tuned, factually-guarded live conversation aimed at driving TEG 2026 participation, persisting a lead record and sales handoff packet.

**Architecture:** A 3-agent pipeline (Analysis → Research → Persuasion) runs on form submit and completes before the chat widget opens. Agents never call each other; an orchestrator sequences them and owns Postgres persistence. Research is frozen for the chat session. All research runs on free tools (local KB + Tavily/Brave free tier + httpx scraping); no paid LinkedIn, no browser automation.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x + Alembic, Postgres, Pydantic v2, httpx, `trafilatura` (page text extraction), `rank-bm25` (KB retrieval), `google-genai` SDK (Gemini, default) with `anthropic` SDK retained, `pytest` + `pytest-asyncio`, `respx` (httpx mocking). Widget: vanilla TypeScript, `esbuild` bundle, no framework.

**Design spec:** `docs/superpowers/specs/2026-08-31-teg-outreach-agent-design.md` — read it before starting.

## Global Constraints

- Python 3.12+. Package lives at `teg-outreach-agent/` (sibling to `teg-kb-agent/` in this repo).
- The knowledge base at `teg-kb-agent/knowledge_base/` is **read-only** to this system. Never write to it.
- Research path must run with **zero paid APIs**. `LINKEDIN_PROVIDER` defaults to `none` and its implementation is a no-op stub. No Playwright / Selenium / headless browser dependency may be added.
- Every quantitative claim a Persuasion Agent message makes must trace to a KB source file. Only the 4 cleared testimonials in `testimonials/exhibitor_testimonials.md` may be quoted. Peer-company lists come only from `sector_wise_participation.md`. Never state a visitor ticket price (amounts are unpublished).
- All prices quoted must be "+ GST" and carry the "indicative / subject to confirmation at booking" caveat (per `pricing/pricing_and_packages.md`).
- All agent I/O is typed Pydantic models defined in `app/domain/schemas.py`. Agents subclass `Agent` ABC with `async def run()`.
- LLM access only via the `LLMClient` interface (`app/llm/base.py`). No direct `google.genai` / `anthropic` imports outside their adapter files (`app/llm/gemini_client.py`, `app/llm/anthropic_client.py`). Default provider is **Gemini** (`gemini-flash-latest`).
- All external calls (LLM, web search, scraping) are `async`. Tests stub them; no test makes a real network call.
- Config via environment only (`config/settings.py`), with the defaults from spec §8.
- Conventional-commit messages. Commit at the end of every task.
- End commit messages with:
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`
  `Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ`

---

## File Structure

```
teg-outreach-agent/
├── pyproject.toml                      # package metadata, deps, pytest/ruff config
├── README.md                           # setup + run instructions
├── .env.example                        # every env var from spec §8
├── alembic.ini
├── config/
│   ├── __init__.py
│   ├── settings.py                     # Settings (pydantic-settings), get_settings()
│   └── outreach_rules.py               # parse outreach_config.md -> typed rules
├── app/
│   ├── __init__.py
│   ├── main.py                         # FastAPI app factory, router wiring, lifespan
│   ├── domain/
│   │   ├── __init__.py
│   │   └── schemas.py                  # ALL Pydantic models (I/O contracts)
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py                     # LLMClient ABC
│   │   ├── anthropic_client.py         # AnthropicClient
│   │   └── fake.py                     # FakeLLMClient for tests
│   ├── kb/
│   │   ├── __init__.py
│   │   └── loader.py                   # KnowledgeBase: find_company/find_person/peers_in_sector/pricing/cleared_testimonials
│   ├── research/
│   │   ├── __init__.py
│   │   ├── tools.py                    # ResearchTool ABC, ResearchQuery, ResearchResult
│   │   ├── kb_retriever.py             # KBRetriever(ResearchTool)
│   │   ├── web_search.py               # TavilySearch / BraveSearch (ResearchTool)
│   │   ├── page_scraper.py             # PageScraper(ResearchTool)
│   │   └── linkedin.py                 # LinkedInStub(ResearchTool) -> always unavailable
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py                     # Agent ABC
│   │   ├── analysis.py                 # AnalysisAgent
│   │   ├── research.py                 # ResearchAgent
│   │   ├── persuasion.py               # PersuasionAgent (init + respond)
│   │   └── guardrails.py               # check_message(), SAFE_TEMPLATES
│   ├── orchestrator.py                 # run_pipeline / run_turn / end_session
│   ├── store/
│   │   ├── __init__.py
│   │   ├── db.py                       # engine, session factory, get_session dep
│   │   ├── models.py                   # SQLAlchemy models (6 tables)
│   │   ├── repositories.py             # InquiryRepo, DossierRepo, SessionRepo, MessageRepo, HandoffRepo
│   │   └── migrations/                 # alembic env + versions
│   ├── api/
│   │   ├── __init__.py
│   │   ├── inquiries.py                # POST /inquiries, GET /inquiries/{id}
│   │   ├── chat.py                     # WS /chat/{session_id}
│   │   └── internal.py                 # GET /sessions/{id}
│   └── jobs/
│       ├── __init__.py
│       └── retention.py               # purge_expired()
├── widget/
│   ├── package.json
│   ├── tsconfig.json
│   ├── build.mjs                       # esbuild script
│   ├── src/
│   │   ├── index.ts                    # entry: mount(), form + chat controller
│   │   ├── api.ts                      # POST /inquiries, WS client
│   │   └── ui.ts                       # DOM rendering, ARIA live region
│   └── dist/                           # built bundle (gitignored except .gitkeep)
└── tests/
    ├── conftest.py                     # fixtures: db, fake_llm, fake_tools, kb
    ├── config/test_outreach_rules.py
    ├── kb/test_loader.py
    ├── llm/test_anthropic_client.py
    ├── research/
    │   ├── test_kb_retriever.py
    │   ├── test_web_search.py
    │   ├── test_page_scraper.py
    │   └── test_linkedin.py
    ├── agents/
    │   ├── test_analysis.py
    │   ├── test_research.py
    │   ├── test_persuasion.py
    │   └── test_guardrails.py
    ├── store/test_repositories.py
    ├── orchestrator/test_orchestrator.py
    ├── api/
    │   ├── test_inquiries.py
    │   └── test_chat.py
    ├── jobs/test_retention.py
    └── e2e/test_full_flow.py
```

---

## Task List (overview)

1. Project scaffold + settings
2. Domain schemas (all Pydantic I/O contracts)
3. `outreach_config.md` parser
4. Knowledge base loader
5. LLM client interface + Anthropic adapter + fake
6. Research tools: `ResearchTool` ABC + `KBRetriever`
7. Research tools: `PageScraper` + `LinkedInStub`
8. Research tools: `TavilySearch` / `BraveSearch`
9. `Agent` ABC + `AnalysisAgent`
10. `ResearchAgent`
11. Guardrails module
12. `PersuasionAgent` — `init`
13. `PersuasionAgent` — `respond` + persona re-map
14. Postgres models + migration
15. Repositories
16. Orchestrator: `run_pipeline`
17. Orchestrator: `run_turn` + `end_session` + handoff packet
18. API: `POST /inquiries` + internal read endpoints
19. API: `WS /chat/{session_id}`
20. Retention job
21. E2E test (happy path + handoff path)
22. Chat widget: build setup + API client
23. Chat widget: form + chat UI + mount

---

## Task 1: Project scaffold + settings

**Files:**
- Create: `teg-outreach-agent/pyproject.toml`
- Create: `teg-outreach-agent/.env.example`
- Create: `teg-outreach-agent/config/__init__.py` (empty)
- Create: `teg-outreach-agent/config/settings.py`
- Create: `teg-outreach-agent/app/__init__.py` (empty)
- Create: `teg-outreach-agent/tests/__init__.py` (empty)
- Test: `teg-outreach-agent/tests/config/test_settings.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `config.settings.Settings` — pydantic-settings `BaseSettings` with fields:
    `database_url: str`, `llm_provider: str = "anthropic"`, `llm_model_fast: str = "claude-haiku-4-5-20251001"`, `llm_model_main: str = "claude-sonnet-5"`, `anthropic_api_key: str = ""`, `web_search_provider: str = "tavily"`, `tavily_api_key: str = ""`, `brave_api_key: str = ""`, `research_max_searches_per_track: int = 2`, `research_max_scrapes: int = 3`, `pipeline_soft_timeout_s: int = 8`, `pipeline_hard_timeout_s: int = 20`, `kb_path: str = "../teg-kb-agent/knowledge_base"`, `data_retention_days: int = 180`, `linkedin_provider: str = "none"`
  - `config.settings.get_settings() -> Settings` — `@lru_cache`d accessor

- [ ] **Step 1: Write pyproject.toml**

```toml
[project]
name = "teg-outreach-agent"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "sqlalchemy>=2.0",
    "alembic>=1.14",
    "psycopg[binary]>=3.2",
    "httpx>=0.27",
    "trafilatura>=1.12",
    "rank-bm25>=0.2.2",
    "anthropic>=0.40",
    "python-multipart>=0.0.12",
    "websockets>=13",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "respx>=0.21",
    "ruff>=0.7",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["app", "config"]
```

- [ ] **Step 2: Write .env.example**

```
DATABASE_URL=postgresql+psycopg://teg:teg@localhost:5432/teg_outreach
LLM_PROVIDER=anthropic
LLM_MODEL_FAST=claude-haiku-4-5-20251001
LLM_MODEL_MAIN=claude-sonnet-5
ANTHROPIC_API_KEY=
WEB_SEARCH_PROVIDER=tavily
TAVILY_API_KEY=
BRAVE_API_KEY=
RESEARCH_MAX_SEARCHES_PER_TRACK=2
RESEARCH_MAX_SCRAPES=3
PIPELINE_SOFT_TIMEOUT_S=8
PIPELINE_HARD_TIMEOUT_S=20
KB_PATH=../teg-kb-agent/knowledge_base
DATA_RETENTION_DAYS=180
LINKEDIN_PROVIDER=none
```

- [ ] **Step 3: Write the failing test**

```python
# tests/config/test_settings.py
from config.settings import Settings, get_settings


def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    s = Settings()
    assert s.llm_provider == "anthropic"
    assert s.web_search_provider == "tavily"
    assert s.research_max_searches_per_track == 2
    assert s.linkedin_provider == "none"
    assert s.kb_path.endswith("teg-kb-agent/knowledge_base")


def test_get_settings_is_cached(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    assert get_settings() is get_settings()
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd teg-outreach-agent && python -m pytest tests/config/test_settings.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'config.settings'`

- [ ] **Step 5: Write config/settings.py**

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    llm_provider: str = "anthropic"
    llm_model_fast: str = "claude-haiku-4-5-20251001"
    llm_model_main: str = "claude-sonnet-5"
    anthropic_api_key: str = ""
    web_search_provider: str = "tavily"
    tavily_api_key: str = ""
    brave_api_key: str = ""
    research_max_searches_per_track: int = 2
    research_max_scrapes: int = 3
    pipeline_soft_timeout_s: int = 8
    pipeline_hard_timeout_s: int = 20
    kb_path: str = "../teg-kb-agent/knowledge_base"
    data_retention_days: int = 180
    linkedin_provider: str = "none"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 6: Create empty package files**

```bash
mkdir -p teg-outreach-agent/tests/config
touch teg-outreach-agent/config/__init__.py teg-outreach-agent/app/__init__.py
touch teg-outreach-agent/tests/__init__.py teg-outreach-agent/tests/config/__init__.py
```

- [ ] **Step 7: Install and run tests**

Run:
```bash
cd teg-outreach-agent && pip install -e ".[dev]" && python -m pytest tests/config/ -v
```
Expected: PASS (2 tests)

- [ ] **Step 8: Commit**

```bash
git add teg-outreach-agent/
git commit -m "feat(outreach): project scaffold and settings

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 2: Domain schemas

**Files:**
- Create: `teg-outreach-agent/app/domain/__init__.py` (empty)
- Create: `teg-outreach-agent/app/domain/schemas.py`
- Test: `teg-outreach-agent/tests/domain/test_schemas.py`

**Interfaces:**
- Consumes: nothing
- Produces (all `pydantic.BaseModel`, importable from `app.domain.schemas`):
  - `IntentHint` = `Literal["visitor","exhibitor","sponsor","startup_pitch","speaker","unknown"]`
  - `ConsentStatus` = `Literal["given","not_given","unknown"]`
  - `Relationship` = `Literal["cold","returning","insider"]`
  - `Persona` = `Literal["it_tech_service","ai_startup","non_tech_sponsor","visitor"]`
  - `CtaStatus` = `Literal["none","offered","in_progress","completed","declined"]`
  - `OutcomeStatus` = `Literal["new","contacted","qualified","lost"]`
  - `IntakePayload`: `person_name: str`, `company_name: str`, `email: str | None = None`, `phone: str | None = None`, `city: str | None = None`, `designation: str | None = None`, `participation_type: str | None = None`, `tech_category: str | None = None`, `message: str | None = None`, `preferred_contact_time: str | None = None`, `consent: bool | None = None`, `source: str = "inquiry_page"`
  - `IntakeResult`: `person_name: str`, `company_name_raw: str`, `company_name_canonical: str`, `provided_fields: list[str]`, `intent_hint: IntentHint`, `consent_status: ConsentStatus`
  - `SourceRef`: `field: str`, `url: str | None`, `tool: str`, `confidence: float`
  - `ResearchDossier`: `company_profile: dict`, `person_profile: dict`, `person_company_match: bool | None`, `relationship: Relationship`, `sector: str | None`, `peer_companies: list[str]`, `field_confidence: dict[str, float]`, `sources: list[SourceRef]`, `review_flags: list[str]`, `ask_prospect: list[str]`, `research_cost: dict[str, int]`
  - `PersuasionInit`: `persona: Persona`, `target_cta: str`, `opening_message: str`
  - `PersuasionTurn`: `reply_text: str`, `detected_cta: str | None`, `cta_status: CtaStatus`, `cta_type: str | None`, `cta_detail: dict`, `should_handoff: bool`, `updated_state: dict`, `guardrail_flags: list[str]`, `persona: Persona`
  - `HandoffPacket`: `summary: str`, `recommended_next_step: str`, `suggested_followup_message: str`, `prospect_confidence: Literal["high","medium","low"]`, `key_facts: dict`

- [ ] **Step 1: Write the failing test**

```python
# tests/domain/test_schemas.py
import pytest
from pydantic import ValidationError

from app.domain.schemas import (
    IntakePayload, IntakeResult, ResearchDossier, SourceRef,
    PersuasionInit, PersuasionTurn, HandoffPacket,
)


def test_intake_payload_minimal():
    p = IntakePayload(person_name="Rohan B", company_name="TRT")
    assert p.email is None
    assert p.source == "inquiry_page"


def test_intake_payload_requires_names():
    with pytest.raises(ValidationError):
        IntakePayload(person_name="Rohan B")


def test_intake_result_shape():
    r = IntakeResult(
        person_name="Rohan B", company_name_raw="TRT",
        company_name_canonical="Third Rock Techkno",
        provided_fields=["message"], intent_hint="exhibitor",
        consent_status="unknown",
    )
    assert r.intent_hint == "exhibitor"


def test_intent_hint_rejects_bad_value():
    with pytest.raises(ValidationError):
        IntakeResult(
            person_name="x", company_name_raw="y", company_name_canonical="y",
            provided_fields=[], intent_hint="buyer", consent_status="unknown",
        )


def test_research_dossier_defaults_and_sourceref():
    d = ResearchDossier(
        company_profile={}, person_profile={}, person_company_match=None,
        relationship="cold", sector=None, peer_companies=[],
        field_confidence={}, sources=[SourceRef(field="sector", url=None, tool="kb", confidence=0.9)],
        review_flags=[], ask_prospect=[], research_cost={},
    )
    assert d.sources[0].tool == "kb"


def test_persuasion_turn_shape():
    t = PersuasionTurn(
        reply_text="hi", detected_cta=None, cta_status="none", cta_type=None,
        cta_detail={}, should_handoff=False, updated_state={},
        guardrail_flags=[], persona="visitor",
    )
    assert t.cta_status == "none"


def test_handoff_packet_confidence_enum():
    with pytest.raises(ValidationError):
        HandoffPacket(
            summary="s", recommended_next_step="n", suggested_followup_message="m",
            prospect_confidence="maybe", key_facts={},
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd teg-outreach-agent && python -m pytest tests/domain/ -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.domain.schemas'`

- [ ] **Step 3: Write app/domain/schemas.py**

```python
from typing import Literal

from pydantic import BaseModel, Field

IntentHint = Literal["visitor", "exhibitor", "sponsor", "startup_pitch", "speaker", "unknown"]
ConsentStatus = Literal["given", "not_given", "unknown"]
Relationship = Literal["cold", "returning", "insider"]
Persona = Literal["it_tech_service", "ai_startup", "non_tech_sponsor", "visitor"]
CtaStatus = Literal["none", "offered", "in_progress", "completed", "declined"]
OutcomeStatus = Literal["new", "contacted", "qualified", "lost"]


class IntakePayload(BaseModel):
    person_name: str
    company_name: str
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    designation: str | None = None
    participation_type: str | None = None
    tech_category: str | None = None
    message: str | None = None
    preferred_contact_time: str | None = None
    consent: bool | None = None
    source: str = "inquiry_page"


class IntakeResult(BaseModel):
    person_name: str
    company_name_raw: str
    company_name_canonical: str
    provided_fields: list[str]
    intent_hint: IntentHint
    consent_status: ConsentStatus


class SourceRef(BaseModel):
    field: str
    url: str | None
    tool: str
    confidence: float


class ResearchDossier(BaseModel):
    company_profile: dict = Field(default_factory=dict)
    person_profile: dict = Field(default_factory=dict)
    person_company_match: bool | None = None
    relationship: Relationship = "cold"
    sector: str | None = None
    peer_companies: list[str] = Field(default_factory=list)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    sources: list[SourceRef] = Field(default_factory=list)
    review_flags: list[str] = Field(default_factory=list)
    ask_prospect: list[str] = Field(default_factory=list)
    research_cost: dict[str, int] = Field(default_factory=dict)


class PersuasionInit(BaseModel):
    persona: Persona
    target_cta: str
    opening_message: str


class PersuasionTurn(BaseModel):
    reply_text: str
    detected_cta: str | None = None
    cta_status: CtaStatus = "none"
    cta_type: str | None = None
    cta_detail: dict = Field(default_factory=dict)
    should_handoff: bool = False
    updated_state: dict = Field(default_factory=dict)
    guardrail_flags: list[str] = Field(default_factory=list)
    persona: Persona


class HandoffPacket(BaseModel):
    summary: str
    recommended_next_step: str
    suggested_followup_message: str
    prospect_confidence: Literal["high", "medium", "low"]
    key_facts: dict = Field(default_factory=dict)
```

- [ ] **Step 4: Create package files, run tests**

```bash
mkdir -p teg-outreach-agent/tests/domain
touch teg-outreach-agent/app/domain/__init__.py teg-outreach-agent/tests/domain/__init__.py
cd teg-outreach-agent && python -m pytest tests/domain/ -v
```
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add teg-outreach-agent/
git commit -m "feat(outreach): domain schemas for agent I/O contracts

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 3: `outreach_config.md` parser

**Files:**
- Create: `teg-outreach-agent/config/outreach_rules.py`
- Test: `teg-outreach-agent/tests/config/test_outreach_rules.py`

**Interfaces:**
- Consumes: `config.settings.get_settings` (for `kb_path`)
- Produces (`config.outreach_rules`):
  - `HARD_REQUIREMENTS: frozenset[str]` = `{"email", "phone", "consent"}` (the "Never Enrich" set)
  - `ENRICHABLE_FIELDS: frozenset[str]` = `{"designation", "linkedin_url", "sector", "company_size", "website", "prior_teg_involvement"}`
  - `PERSONA_TRIGGERS: dict[str, dict]` — parsed persona mapping, keys `it_tech_service`, `ai_startup`, `non_tech_sponsor`, `visitor`, each `{"sectors": list[str], "size_max": int | None, "intent": str | None, "value_props": list[str]}`
  - `CONFIDENCE_THRESHOLDS: dict[str, dict[str, float]]` — keys `company_name`, `linkedin`, `sector`; each `{"auto_accept": float, "review_low": float}` (auto-accept ≥, review band between)
  - `GUARDRAILS: list[str]` — the guardrail bullet strings, verbatim
  - `load_rules() -> OutreachRules` — dataclass bundling all of the above; reads `{kb_path}/outreach_config.md`
  - `OutreachRules` dataclass with attributes: `hard_requirements`, `enrichable_fields`, `persona_triggers`, `confidence_thresholds`, `guardrails`

**Note for implementer:** `outreach_config.md` is a hand-maintained markdown doc. This parser reads specific sections by heading. It must **fail loudly** (raise `OutreachConfigError`) if an expected heading or table is missing — that is the "structural drift" guard from spec §4.8. Do NOT make the parser tolerant; a silent empty result would let the agents run ungoverned.

- [ ] **Step 1: Read the source file to confirm structure**

Run: `sed -n '1,60p' teg-kb-agent/knowledge_base/outreach_config.md`
Confirm these headings exist: `## Confidence Thresholds`, `### Company Name Matching`, `### Sector Classification`, `## Field Classification`, `### Hard Requirements (Never Enrich)`, `### Enrichable Fields (Can be researched)`, `## Persona Mapping Rules`, `## Guardrails`.

- [ ] **Step 2: Write the failing test**

```python
# tests/config/test_outreach_rules.py
import pytest

from config.outreach_rules import (
    load_rules, OutreachRules, OutreachConfigError,
    HARD_REQUIREMENTS, ENRICHABLE_FIELDS,
)


def test_hard_requirements_constant():
    assert HARD_REQUIREMENTS == frozenset({"email", "phone", "consent"})


def test_enrichable_includes_sector_and_linkedin():
    assert "sector" in ENRICHABLE_FIELDS
    assert "linkedin_url" in ENRICHABLE_FIELDS


def test_load_rules_from_real_kb():
    rules = load_rules()
    assert isinstance(rules, OutreachRules)
    # personas
    assert set(rules.persona_triggers) == {
        "it_tech_service", "ai_startup", "non_tech_sponsor", "visitor"
    }
    assert "AI & Machine Learning" in rules.persona_triggers["ai_startup"]["sectors"]
    assert rules.persona_triggers["ai_startup"]["size_max"] == 50
    # thresholds
    assert rules.confidence_thresholds["company_name"]["auto_accept"] == 0.95
    assert rules.confidence_thresholds["sector"]["auto_accept"] == 0.95
    # guardrails carried verbatim
    assert any("fabricated testimonials" in g.lower() for g in rules.guardrails)


def test_load_rules_raises_on_missing_heading(tmp_path, monkeypatch):
    bad = tmp_path / "outreach_config.md"
    bad.write_text("# Outreach Configuration\n\nNo useful sections here.\n")
    monkeypatch.setattr("config.outreach_rules._config_path", lambda: bad)
    with pytest.raises(OutreachConfigError):
        load_rules()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd teg-outreach-agent && python -m pytest tests/config/test_outreach_rules.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'config.outreach_rules'`

- [ ] **Step 4: Write config/outreach_rules.py**

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from config.settings import get_settings

HARD_REQUIREMENTS = frozenset({"email", "phone", "consent"})
ENRICHABLE_FIELDS = frozenset({
    "designation", "linkedin_url", "sector", "company_size", "website",
    "prior_teg_involvement",
})


class OutreachConfigError(RuntimeError):
    """Raised when outreach_config.md is missing an expected section/table."""


@dataclass(frozen=True)
class OutreachRules:
    hard_requirements: frozenset[str]
    enrichable_fields: frozenset[str]
    persona_triggers: dict[str, dict]
    confidence_thresholds: dict[str, dict[str, float]]
    guardrails: list[str]


def _config_path() -> Path:
    return Path(get_settings().kb_path).resolve() / "outreach_config.md"


def _require(text: str, heading: str) -> None:
    if heading not in text:
        raise OutreachConfigError(f"outreach_config.md missing expected heading: {heading!r}")


def _percent(cell: str) -> float:
    m = re.search(r"(\d+)\s*%", cell)
    if not m:
        raise OutreachConfigError(f"expected a percentage in {cell!r}")
    return int(m.group(1)) / 100.0


def _parse_thresholds(text: str) -> dict[str, dict[str, float]]:
    # Each subsection's first data row is the auto-accept tier ("95%+"),
    # the second is the review-band lower bound ("70-94%").
    out: dict[str, dict[str, float]] = {}
    blocks = {
        "company_name": "### Company Name Matching",
        "linkedin": "### LinkedIn Profile Matching",
        "sector": "### Sector Classification",
    }
    for key, heading in blocks.items():
        _require(text, heading)
        seg = text.split(heading, 1)[1].split("\n###", 1)[0].split("\n##", 1)[0]
        rows = [r for r in seg.splitlines() if r.strip().startswith("|") and "%" in r]
        if len(rows) < 2:
            raise OutreachConfigError(f"{heading}: expected >=2 data rows with percentages")
        auto = _percent(rows[0])
        review_low = _percent(rows[1])
        out[key] = {"auto_accept": auto, "review_low": review_low}
    return out


def _parse_personas(text: str) -> dict[str, dict]:
    _require(text, "## Persona Mapping Rules")
    seg = text.split("## Persona Mapping Rules", 1)[1].split("\n## ", 1)[0]
    mapping = {
        "it_tech_service": "### IT/Tech Service Company",
        "ai_startup": "### AI/Deep-Tech Startup",
        "non_tech_sponsor": "### Non-Tech Sponsor",
        "visitor": "### Visitor",
    }
    out: dict[str, dict] = {}
    for key, heading in mapping.items():
        if heading not in seg:
            raise OutreachConfigError(f"persona section missing: {heading!r}")
        body = seg.split(heading, 1)[1].split("\n###", 1)[0]
        trigger_line = next(
            (l for l in body.splitlines() if "**Trigger:**" in l), ""
        )
        sectors = re.findall(r"\[([^\]]+)\]", trigger_line)
        sector_list: list[str] = []
        for grp in sectors:
            sector_list.extend(s.strip() for s in grp.split(","))
        size_max = None
        m = re.search(r"size\s*<\s*(\d+)", trigger_line)
        if m:
            size_max = int(m.group(1))
        intent = None
        m = re.search(r'Intent\s*=\s*"(\w+)"', trigger_line)
        if m:
            intent = m.group(1)
        props = [
            l.strip("- ").strip()
            for l in body.splitlines()
            if l.strip().startswith("- ")
        ]
        out[key] = {
            "sectors": sector_list,
            "size_max": size_max,
            "intent": intent,
            "value_props": props,
        }
    return out


def _parse_guardrails(text: str) -> list[str]:
    _require(text, "## Guardrails")
    seg = text.split("## Guardrails", 1)[1].split("\n## ", 1)[0]
    bullets = [
        l.strip("- ").strip()
        for l in seg.splitlines()
        if l.strip().startswith("- ")
    ]
    if not bullets:
        raise OutreachConfigError("## Guardrails section has no bullet points")
    return bullets


def load_rules() -> OutreachRules:
    path = _config_path()
    if not path.is_file():
        raise OutreachConfigError(f"outreach_config.md not found at {path}")
    text = path.read_text(encoding="utf-8")
    for heading in (
        "## Confidence Thresholds",
        "## Field Classification",
        "### Hard Requirements (Never Enrich)",
        "### Enrichable Fields (Can be researched)",
        "## Persona Mapping Rules",
        "## Guardrails",
    ):
        _require(text, heading)
    return OutreachRules(
        hard_requirements=HARD_REQUIREMENTS,
        enrichable_fields=ENRICHABLE_FIELDS,
        persona_triggers=_parse_personas(text),
        confidence_thresholds=_parse_thresholds(text),
        guardrails=_parse_guardrails(text),
    )
```

- [ ] **Step 5: Run tests**

Run: `cd teg-outreach-agent && python -m pytest tests/config/test_outreach_rules.py -v`
Expected: PASS (4 tests). If `test_load_rules_from_real_kb` fails on a specific assertion, inspect the real `outreach_config.md` section and adjust the parser regex — do NOT relax the "raise on missing" behaviour.

- [ ] **Step 6: Commit**

```bash
git add teg-outreach-agent/
git commit -m "feat(outreach): typed parser for outreach_config.md rules

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 4: Knowledge base loader

**Files:**
- Create: `teg-outreach-agent/app/kb/__init__.py` (empty)
- Create: `teg-outreach-agent/app/kb/loader.py`
- Test: `teg-outreach-agent/tests/kb/test_loader.py`

**Interfaces:**
- Consumes: `config.settings.get_settings` (for `kb_path`)
- Produces (`app.kb.loader`):
  - `CompanyRecord` dataclass: `name: str`, `slug: str`, `category: str | None`, `website: str | None`, `teg_participation: str | None`, `confidence: str | None`, `overview: str`, `raw: str`
  - `PersonRecord` dataclass: `name: str`, `slug: str`, `role: str | None`, `kind: Literal["organizer","speaker","founder"]`, `company: str | None`, `overview: str`, `raw: str`
  - `PricingInfo` dataclass: `stalls: list[dict]` (each `{"size","area","price_inr","exhibitor_passes","visitor_passes"}`), `title_sponsor_inr: int`, `payment_plan: str`, `refund_policy: str`, `raw: str`
  - `KnowledgeBase` class:
    - `__init__(self, root: Path | None = None)` — defaults to `get_settings().kb_path`
    - `find_company(self, name: str) -> tuple[CompanyRecord | None, float]` — returns best match + score 0..1 (exact filename/title = 1.0; token-set fuzzy otherwise)
    - `find_person(self, name: str) -> tuple[PersonRecord | None, float]`
    - `peers_in_sector(self, sector: str, limit: int = 5) -> list[str]` — from `sector_wise_participation.md` only
    - `pricing(self) -> PricingInfo`
    - `cleared_testimonials(self) -> list[dict]` — each `{"name","role","quote"}`, only the 4 in `testimonials/exhibitor_testimonials.md`
  - `get_kb() -> KnowledgeBase` — `@lru_cache`d singleton

**Shared helper:** `app.kb.loader` also exposes `_token_set_ratio(a: str, b: str) -> float` (token-set similarity, 0..1) and `_norm(s: str) -> str` — used by `AnalysisAgent` (Task 9) and tests. Keep both importable (leading underscore is fine; they are internal-shared, not private-to-class).

**Implementer note:** company profile files are at `exhibitors/companies/*.md` (exclude `companies_index.md`). Organizer files at `organizers_team/*.md` (exclude `organizers_and_team.md`, `co_organizers.md`). Speaker files at `speakers/individuals/*.md`. Each company file's blockquote header lines look like `> **Category:** ...`, `> **Website:** ...`, `> **TEG participation:** ...`, `> **Confidence:** ...`. The Overview section follows a `## Overview` heading. Founder names appear under `## Company Details` as `- **Founder(s)...:** Name`.

- [ ] **Step 1: Write the failing test**

```python
# tests/kb/test_loader.py
from app.kb.loader import KnowledgeBase, get_kb, CompanyRecord, PersonRecord


def test_find_company_exact():
    kb = KnowledgeBase()
    rec, score = kb.find_company("Third Rock Techkno")
    assert isinstance(rec, CompanyRecord)
    assert score == 1.0
    assert "AI" in (rec.category or "")
    assert rec.website == "https://www.thirdrocktechkno.com/"
    assert "2024" in (rec.teg_participation or "")


def test_find_company_abbreviation_is_fuzzy_or_miss():
    kb = KnowledgeBase()
    rec, score = kb.find_company("TRT")
    # "TRT" is not the file title; loader must NOT hallucinate a 1.0 match.
    assert score < 0.95


def test_find_company_miss_returns_none():
    kb = KnowledgeBase()
    rec, score = kb.find_company("Zzxqwerty Nonexistent Ltd")
    assert rec is None
    assert score < 0.5


def test_find_person_organizer_and_founder():
    kb = KnowledgeBase()
    rec, score = kb.find_person("Tejas Shah")
    assert isinstance(rec, PersonRecord)
    assert score >= 0.9
    assert rec.kind in {"organizer", "founder"}


def test_peers_in_sector_from_file_only():
    kb = KnowledgeBase()
    peers = kb.peers_in_sector("AI & Machine Learning", limit=5)
    assert "Third Rock Techkno" in peers
    assert "NeuraMonks" in peers
    assert len(peers) <= 5
    # must not include a company absent from that section
    assert "GTPL" not in peers


def test_pricing_has_confirmed_stall_numbers():
    kb = KnowledgeBase()
    p = kb.pricing()
    sizes = {s["size"] for s in p.stalls}
    assert "3m × 3m" in sizes or "3m x 3m" in sizes
    prices = {s["price_inr"] for s in p.stalls}
    assert 117000 in prices
    assert 468000 in prices
    assert p.title_sponsor_inr == 3500000


def test_cleared_testimonials_exactly_four():
    kb = KnowledgeBase()
    t = kb.cleared_testimonials()
    assert len(t) == 4
    names = {x["name"] for x in t}
    assert "Sonu Sharma" in names
    assert "Kanaksinh Rana" in names
    assert all(x["quote"] for x in t)


def test_get_kb_cached():
    assert get_kb() is get_kb()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd teg-outreach-agent && mkdir -p tests/kb && touch tests/kb/__init__.py app/kb/__init__.py && python -m pytest tests/kb/ -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.kb.loader'`

- [ ] **Step 3: Write app/kb/loader.py**

```python
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal

from config.settings import get_settings

_HEADER_RE = re.compile(r"^>\s*\*\*(?P<key>[^:*]+):\*\*\s*(?P<val>.+?)\s*$", re.M)


def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\b(pvt\.?|private|ltd\.?|limited|llp|inc\.?|technologies|technolabs|solutions|software|it)\b", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(s.split())


def _token_set_ratio(a: str, b: str) -> float:
    ta, tb = set(_norm(a).split()), set(_norm(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


@dataclass
class CompanyRecord:
    name: str
    slug: str
    category: str | None
    website: str | None
    teg_participation: str | None
    confidence: str | None
    overview: str
    raw: str


@dataclass
class PersonRecord:
    name: str
    slug: str
    role: str | None
    kind: Literal["organizer", "speaker", "founder"]
    company: str | None
    overview: str
    raw: str


@dataclass
class PricingInfo:
    stalls: list[dict] = field(default_factory=list)
    title_sponsor_inr: int = 0
    payment_plan: str = ""
    refund_policy: str = ""
    raw: str = ""


def _title_of(md: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+?)\s*$", md, re.M)
    if not m:
        return fallback
    # strip a parenthetical legal-name suffix for the display name
    return m.group(1).strip()


def _section(md: str, heading: str) -> str:
    if heading not in md:
        return ""
    seg = md.split(heading, 1)[1]
    return seg.split("\n## ", 1)[0].split("\n#", 1)[0].strip()


def _headers(md: str) -> dict[str, str]:
    return {m.group("key").strip().lower(): m.group("val").strip() for m in _HEADER_RE.finditer(md)}


class KnowledgeBase:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root or get_settings().kb_path).resolve()
        self._companies: list[CompanyRecord] = []
        self._people: list[PersonRecord] = []
        self._load_companies()
        self._load_people()

    # ---- loading ----
    def _load_companies(self) -> None:
        cdir = self.root / "exhibitors" / "companies"
        for f in sorted(cdir.glob("*.md")):
            if f.stem == "companies_index":
                continue
            md = f.read_text(encoding="utf-8")
            h = _headers(md)
            self._companies.append(CompanyRecord(
                name=_title_of(md, f.stem),
                slug=f.stem,
                category=h.get("category"),
                website=h.get("website"),
                teg_participation=h.get("teg participation"),
                confidence=h.get("confidence"),
                overview=_section(md, "## Overview"),
                raw=md,
            ))

    def _load_people(self) -> None:
        odir = self.root / "organizers_team"
        for f in sorted(odir.glob("*.md")):
            if f.stem in {"organizers_and_team", "co_organizers"}:
                continue
            md = f.read_text(encoding="utf-8")
            self._people.append(PersonRecord(
                name=_title_of(md, f.stem), slug=f.stem, role=_headers(md).get("role"),
                kind="organizer", company=None,
                overview=_section(md, "## Overview") or _section(md, "## Profile"),
                raw=md,
            ))
        sdir = self.root / "speakers" / "individuals"
        for f in sorted(sdir.glob("*.md")):
            md = f.read_text(encoding="utf-8")
            self._people.append(PersonRecord(
                name=_title_of(md, f.stem), slug=f.stem, role=_headers(md).get("affiliation"),
                kind="speaker", company=None,
                overview=_section(md, "## Overview") or _section(md, "## Bio"),
                raw=md,
            ))
        # founder names inside company files
        for c in self._companies:
            for m in re.finditer(r"-\s*\*\*Founder[^:*]*:\*\*\s*([A-Z][A-Za-z.\- ]+)", c.raw):
                fname = m.group(1).strip().rstrip(".")
                if len(fname.split()) >= 2:
                    self._people.append(PersonRecord(
                        name=fname, slug=f"{c.slug}:{_norm(fname).replace(' ', '_')}",
                        role="Founder", kind="founder", company=c.name,
                        overview=c.overview, raw=c.raw,
                    ))

    # ---- queries ----
    def find_company(self, name: str) -> tuple[CompanyRecord | None, float]:
        n = _norm(name)
        best: CompanyRecord | None = None
        best_score = 0.0
        for c in self._companies:
            if _norm(c.name) == n or c.slug == _norm(name).replace(" ", "_"):
                return c, 1.0
            score = _token_set_ratio(name, c.name)
            if score > best_score:
                best, best_score = c, score
        return (best, best_score) if best_score >= 0.5 else (None, best_score)

    def find_person(self, name: str) -> tuple[PersonRecord | None, float]:
        n = _norm(name)
        best: PersonRecord | None = None
        best_score = 0.0
        for p in self._people:
            if _norm(p.name) == n:
                return p, 1.0
            score = _token_set_ratio(name, p.name)
            if score > best_score:
                best, best_score = p, score
        return (best, best_score) if best_score >= 0.6 else (None, best_score)

    def peers_in_sector(self, sector: str, limit: int = 5) -> list[str]:
        f = self.root / "sector_wise_participation.md"
        md = f.read_text(encoding="utf-8")
        want = sector.strip().lower()
        for block in re.split(r"\n### ", md):
            head, _, body = block.partition("\n")
            if head.strip().lower().startswith(want) or want in head.strip().lower():
                line = body.splitlines()[0] if body.strip() else ""
                names = [x.strip() for x in re.split(r"·|\|", line) if x.strip()]
                names = [re.sub(r"\s*\(.*?\)", "", x).strip().strip("*") for x in names]
                names = [x for x in names if x and not x.startswith("_")]
                return names[:limit]
        return []

    def pricing(self) -> PricingInfo:
        f = self.root / "pricing" / "pricing_and_packages.md"
        md = f.read_text(encoding="utf-8")
        stalls: list[dict] = []
        for row in re.finditer(
            r"\|\s*\*\*(?P<size>[\dm×x ]+)\*\*\s*\|\s*(?P<area>[\d ]*sqm)?\s*\|.*?₹(?P<price>[\d,]+)",
            md,
        ):
            price = int(row.group("price").replace(",", ""))
            stalls.append({
                "size": row.group("size").strip(),
                "area": (row.group("area") or "").strip(),
                "price_inr": price,
                "exhibitor_passes": None,
                "visitor_passes": None,
            })
        ts = re.search(r"Title Sponsor.*?₹\s*([\d,]+)", md, re.S)
        title_inr = int(ts.group(1).replace(",", "")) if ts else 0
        return PricingInfo(
            stalls=stalls,
            title_sponsor_inr=title_inr,
            payment_plan=_section(md, "## 7. Flexible Payment Plan"),
            refund_policy=_section(md, "## 8. Refund"),
            raw=md,
        )

    def cleared_testimonials(self) -> list[dict]:
        f = self.root / "testimonials" / "exhibitor_testimonials.md"
        md = f.read_text(encoding="utf-8")
        block = md.split("## ✅ Attributed Testimonials", 1)[-1].split("\n## ", 1)[0]
        out: list[dict] = []
        for part in re.split(r"\n### ", block)[1:]:
            name = part.splitlines()[0].strip()
            role_m = re.search(r"\*\*Role:\*\*\s*(.+)", part)
            quote_m = re.search(r">\s*\"(.+?)\"", part, re.S)
            if quote_m:
                out.append({
                    "name": name,
                    "role": role_m.group(1).strip() if role_m else "",
                    "quote": " ".join(quote_m.group(1).split()),
                })
        return out


@lru_cache
def get_kb() -> KnowledgeBase:
    return KnowledgeBase()
```

- [ ] **Step 4: Run tests, iterate on regexes**

Run: `cd teg-outreach-agent && python -m pytest tests/kb/ -v`
Expected: PASS (8 tests). If a parse assertion fails, run `sed -n '1,40p' teg-kb-agent/knowledge_base/pricing/pricing_and_packages.md` (or the relevant file) and adjust the regex to the actual formatting. Keep the public method signatures unchanged.

- [ ] **Step 5: Commit**

```bash
git add teg-outreach-agent/
git commit -m "feat(outreach): knowledge base loader with company/person/pricing/peers queries

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 5: LLM client interface + Anthropic adapter + fake

**Files:**
- Create: `teg-outreach-agent/app/llm/__init__.py` (empty)
- Create: `teg-outreach-agent/app/llm/base.py`
- Create: `teg-outreach-agent/app/llm/anthropic_client.py`
- Create: `teg-outreach-agent/app/llm/fake.py`
- Test: `teg-outreach-agent/tests/llm/test_fake.py`
- Test: `teg-outreach-agent/tests/llm/test_anthropic_client.py`

**Interfaces:**
- Consumes: `config.settings.get_settings`
- Produces (`app.llm.base`):
  - `LLMMessage` TypedDict: `{"role": Literal["user","assistant"], "content": str}`
  - `LLMClient` ABC:
    - `async def generate(self, *, system: str, messages: list[LLMMessage], model: str | None = None, max_tokens: int = 1024, temperature: float = 0.3) -> str`
    - `async def generate_structured(self, *, system: str, messages: list[LLMMessage], schema: type[BaseModelT], model: str | None = None) -> BaseModelT`
  - `get_llm() -> LLMClient` — factory keyed on `settings.llm_provider`; raises `ValueError` for unknown provider
- Produces (`app.llm.fake`):
  - `FakeLLMClient(LLMClient)` — constructor takes `responses: list[str] | None` and `structured: list[BaseModel] | None`; pops from these queues; records `.calls: list[dict]`. If a queue is empty it returns a deterministic echo (`generate`) or raises `AssertionError` (`generate_structured`).

- [ ] **Step 1: Write the failing test for the fake**

```python
# tests/llm/test_fake.py
import pytest
from pydantic import BaseModel

from app.llm.fake import FakeLLMClient


class Out(BaseModel):
    x: int


async def test_fake_generate_returns_queued():
    c = FakeLLMClient(responses=["hello"])
    r = await c.generate(system="s", messages=[{"role": "user", "content": "hi"}])
    assert r == "hello"
    assert c.calls[0]["system"] == "s"


async def test_fake_generate_structured_returns_queued():
    c = FakeLLMClient(structured=[Out(x=5)])
    r = await c.generate_structured(
        system="s", messages=[{"role": "user", "content": "hi"}], schema=Out
    )
    assert r.x == 5


async def test_fake_structured_without_queue_raises():
    c = FakeLLMClient()
    with pytest.raises(AssertionError):
        await c.generate_structured(
            system="s", messages=[{"role": "user", "content": "hi"}], schema=Out
        )
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent && mkdir -p tests/llm && touch tests/llm/__init__.py app/llm/__init__.py && python -m pytest tests/llm/test_fake.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.llm.fake'`

- [ ] **Step 3: Write app/llm/base.py**

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal, TypedDict, TypeVar

from pydantic import BaseModel

from config.settings import get_settings

BaseModelT = TypeVar("BaseModelT", bound=BaseModel)


class LLMMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str


class LLMClient(ABC):
    @abstractmethod
    async def generate(
        self, *, system: str, messages: list[LLMMessage],
        model: str | None = None, max_tokens: int = 1024, temperature: float = 0.3,
    ) -> str: ...

    @abstractmethod
    async def generate_structured(
        self, *, system: str, messages: list[LLMMessage],
        schema: type[BaseModelT], model: str | None = None,
    ) -> BaseModelT: ...


def get_llm() -> LLMClient:
    provider = get_settings().llm_provider
    if provider == "anthropic":
        from app.llm.anthropic_client import AnthropicClient
        return AnthropicClient()
    raise ValueError(f"unknown llm_provider: {provider!r}")
```

- [ ] **Step 4: Write app/llm/fake.py**

```python
from __future__ import annotations

from app.llm.base import BaseModelT, LLMClient, LLMMessage


class FakeLLMClient(LLMClient):
    def __init__(
        self,
        responses: list[str] | None = None,
        structured: list = None,
    ) -> None:
        self._responses = list(responses or [])
        self._structured = list(structured or [])
        self.calls: list[dict] = []

    async def generate(
        self, *, system: str, messages: list[LLMMessage],
        model: str | None = None, max_tokens: int = 1024, temperature: float = 0.3,
    ) -> str:
        self.calls.append({"kind": "generate", "system": system, "messages": messages, "model": model})
        if self._responses:
            return self._responses.pop(0)
        return f"[echo] {messages[-1]['content']}"

    async def generate_structured(
        self, *, system: str, messages: list[LLMMessage],
        schema: type[BaseModelT], model: str | None = None,
    ) -> BaseModelT:
        self.calls.append({"kind": "structured", "system": system, "messages": messages, "schema": schema.__name__})
        assert self._structured, "FakeLLMClient.generate_structured called with empty queue"
        return self._structured.pop(0)
```

- [ ] **Step 5: Write app/llm/anthropic_client.py**

```python
from __future__ import annotations

import json

from anthropic import AsyncAnthropic

from app.llm.base import BaseModelT, LLMClient, LLMMessage
from config.settings import get_settings


class AnthropicClient(LLMClient):
    def __init__(self) -> None:
        s = get_settings()
        self._client = AsyncAnthropic(api_key=s.anthropic_api_key)
        self._model_main = s.llm_model_main

    async def generate(
        self, *, system: str, messages: list[LLMMessage],
        model: str | None = None, max_tokens: int = 1024, temperature: float = 0.3,
    ) -> str:
        resp = await self._client.messages.create(
            model=model or self._model_main,
            system=system,
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return "".join(block.text for block in resp.content if block.type == "text")

    async def generate_structured(
        self, *, system: str, messages: list[LLMMessage],
        schema: type[BaseModelT], model: str | None = None,
    ) -> BaseModelT:
        tool = {
            "name": "emit",
            "description": f"Return a {schema.__name__} object.",
            "input_schema": schema.model_json_schema(),
        }
        resp = await self._client.messages.create(
            model=model or self._model_main,
            system=system,
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
            max_tokens=2048,
            tools=[tool],
            tool_choice={"type": "tool", "name": "emit"},
        )
        for block in resp.content:
            if block.type == "tool_use" and block.name == "emit":
                return schema.model_validate(block.input)
        raise RuntimeError("model did not return the expected tool call")
```

- [ ] **Step 6: Write app/llm/test_anthropic_client.py (mock the SDK)**

```python
# tests/llm/test_anthropic_client.py
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel


class Out(BaseModel):
    name: str


@pytest.fixture
def anthropic_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")


async def test_generate_extracts_text(anthropic_env):
    from app.llm.anthropic_client import AnthropicClient

    fake_resp = SimpleNamespace(content=[SimpleNamespace(type="text", text="hi there")])
    with patch("app.llm.anthropic_client.AsyncAnthropic") as m:
        m.return_value.messages.create = AsyncMock(return_value=fake_resp)
        c = AnthropicClient()
        out = await c.generate(system="s", messages=[{"role": "user", "content": "x"}])
    assert out == "hi there"


async def test_generate_structured_parses_tool_input(anthropic_env):
    from app.llm.anthropic_client import AnthropicClient

    fake_resp = SimpleNamespace(content=[
        SimpleNamespace(type="tool_use", name="emit", input={"name": "Rohan"})
    ])
    with patch("app.llm.anthropic_client.AsyncAnthropic") as m:
        m.return_value.messages.create = AsyncMock(return_value=fake_resp)
        c = AnthropicClient()
        out = await c.generate_structured(
            system="s", messages=[{"role": "user", "content": "x"}], schema=Out
        )
    assert out.name == "Rohan"
```

- [ ] **Step 7: Run all llm tests**

Run: `cd teg-outreach-agent && python -m pytest tests/llm/ -v`
Expected: PASS (5 tests)

- [ ] **Step 8: Commit**

```bash
git add teg-outreach-agent/
git commit -m "feat(outreach): provider-agnostic LLM client with Anthropic adapter and fake

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 5b: Gemini LLM adapter (default provider)

> **Added mid-execution:** the user chose Google Gemini (`gemini-flash-latest` / "Gemini 3.6 Flash") as the LLM provider instead of Anthropic. The `LLMClient` interface from Task 5 makes this a pure adapter add.

**Files:**
- Create: `teg-outreach-agent/app/llm/gemini_client.py`
- Modify: `teg-outreach-agent/app/llm/base.py` (add `gemini` branch to `get_llm()`)
- Modify: `teg-outreach-agent/config/settings.py` (provider default + Gemini fields)
- Modify: `teg-outreach-agent/.env.example`
- Modify: `teg-outreach-agent/pyproject.toml` (add `google-genai` dep)
- Test: `teg-outreach-agent/tests/llm/test_gemini_client.py`

**Interfaces:**
- Produces `app.llm.gemini_client.GeminiClient(LLMClient)`:
  - `generate(*, system, messages, model=None, max_tokens=1024, temperature=0.3) -> str` — via `google.genai` `client.aio.models.generate_content(model=..., contents=[...], config=GenerateContentConfig(system_instruction=system, max_output_tokens=max_tokens, temperature=temperature))`; return `resp.text`.
  - `generate_structured(*, system, messages, schema, model=None) -> BaseModelT` — set `config.response_mime_type = "application/json"` and `config.response_schema = schema`; parse `resp.text` with `schema.model_validate_json(...)` (fallback: `schema.model_validate(resp.parsed)` if the SDK returns a parsed object).
- `config.settings.Settings` new/changed fields:
  - `llm_provider: str = "gemini"` (was "anthropic")
  - `llm_model_fast: str = "gemini-flash-latest"`
  - `llm_model_main: str = "gemini-flash-latest"`
  - `gemini_api_key: str = ""`
  - keep `anthropic_api_key: str = ""` (Anthropic adapter stays available)
- `get_llm()` adds: `if provider == "gemini": from app.llm.gemini_client import GeminiClient; return GeminiClient()`

- [ ] **Step 1: Add the dependency and install**

Edit `pyproject.toml` `dependencies`: add `"google-genai>=0.8"`. Then:
```bash
cd teg-outreach-agent && .venv/bin/pip install -e ".[dev]"
```
Check the installed version and the exact import path:
```bash
.venv/bin/python -c "import google.genai as g; from google.genai import types; print(g.__version__ if hasattr(g,'__version__') else 'ok'); print([x for x in dir(types) if 'Config' in x])"
```

- [ ] **Step 2: Write the failing test**

```python
# tests/llm/test_gemini_client.py
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel


class Out(BaseModel):
    name: str


@pytest.fixture
def gemini_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    from config.settings import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_generate_returns_text(gemini_env):
    from app.llm.gemini_client import GeminiClient

    fake_resp = SimpleNamespace(text="hi there", parsed=None)
    with patch("app.llm.gemini_client.genai.Client") as m:
        m.return_value.aio.models.generate_content = AsyncMock(return_value=fake_resp)
        c = GeminiClient()
        out = await c.generate(system="s", messages=[{"role": "user", "content": "x"}])
    assert out == "hi there"


async def test_generate_structured_parses_json(gemini_env):
    from app.llm.gemini_client import GeminiClient

    fake_resp = SimpleNamespace(text='{"name": "Rohan"}', parsed=None)
    with patch("app.llm.gemini_client.genai.Client") as m:
        m.return_value.aio.models.generate_content = AsyncMock(return_value=fake_resp)
        c = GeminiClient()
        out = await c.generate_structured(
            system="s", messages=[{"role": "user", "content": "x"}], schema=Out
        )
    assert out.name == "Rohan"


def test_get_llm_selects_gemini(gemini_env):
    from app.llm.base import get_llm
    from app.llm.gemini_client import GeminiClient
    assert isinstance(get_llm(), GeminiClient)
```

- [ ] **Step 3: Run to verify fail**

Run: `cd teg-outreach-agent && .venv/bin/python -m pytest tests/llm/test_gemini_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.llm.gemini_client'`

- [ ] **Step 4: Write app/llm/gemini_client.py**

```python
from __future__ import annotations

from google import genai
from google.genai import types

from app.llm.base import BaseModelT, LLMClient, LLMMessage
from config.settings import get_settings


def _to_contents(messages: list[LLMMessage]) -> list[types.Content]:
    role_map = {"user": "user", "assistant": "model"}
    return [
        types.Content(
            role=role_map[m["role"]],
            parts=[types.Part.from_text(text=m["content"])],
        )
        for m in messages
    ]


class GeminiClient(LLMClient):
    def __init__(self) -> None:
        s = get_settings()
        self._client = genai.Client(api_key=s.gemini_api_key)
        self._model_main = s.llm_model_main

    async def generate(
        self, *, system: str, messages: list[LLMMessage],
        model: str | None = None, max_tokens: int = 1024, temperature: float = 0.3,
    ) -> str:
        resp = await self._client.aio.models.generate_content(
            model=model or self._model_main,
            contents=_to_contents(messages),
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        )
        return (resp.text or "").strip()

    async def generate_structured(
        self, *, system: str, messages: list[LLMMessage],
        schema: type[BaseModelT], model: str | None = None,
    ) -> BaseModelT:
        resp = await self._client.aio.models.generate_content(
            model=model or self._model_main,
            contents=_to_contents(messages),
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        parsed = getattr(resp, "parsed", None)
        if parsed is not None and not isinstance(parsed, (str, bytes)):
            return schema.model_validate(parsed if isinstance(parsed, dict) else parsed.__dict__)
        return schema.model_validate_json(resp.text)
```

**Note:** if `.venv/bin/python -c "import google.genai"` in Step 1 revealed a different API surface (e.g. `genai.Client` lives elsewhere, or `aio` is spelled differently, or `Part.from_text` takes a positional arg), adapt this file to the installed SDK. Keep the `LLMClient` interface and the 3 test assertions (mock `app.llm.gemini_client.genai.Client`, `.aio.models.generate_content` AsyncMock returning an object with `.text` and `.parsed`) unchanged.

- [ ] **Step 5: Update base.py get_llm()**

In `app/llm/base.py`, extend `get_llm()`:
```python
def get_llm() -> LLMClient:
    provider = get_settings().llm_provider
    if provider == "gemini":
        from app.llm.gemini_client import GeminiClient
        return GeminiClient()
    if provider == "anthropic":
        from app.llm.anthropic_client import AnthropicClient
        return AnthropicClient()
    raise ValueError(f"unknown llm_provider: {provider!r}")
```

- [ ] **Step 6: Update settings.py**

```python
    llm_provider: str = "gemini"
    llm_model_fast: str = "gemini-flash-latest"
    llm_model_main: str = "gemini-flash-latest"
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
```
(keep every other field unchanged)

- [ ] **Step 7: Update .env.example**

Change the LLM block to:
```
LLM_PROVIDER=gemini
LLM_MODEL_FAST=gemini-flash-latest
LLM_MODEL_MAIN=gemini-flash-latest
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
```

- [ ] **Step 8: Fix the Anthropic test's provider assumption**

`tests/llm/test_anthropic_client.py` sets `ANTHROPIC_API_KEY` but relies on `AnthropicClient` being constructible directly (it is — it doesn't check `llm_provider`). No change needed there. But `tests/config/test_settings.py::test_settings_defaults` asserts `s.llm_provider == "anthropic"` — update that assertion to `== "gemini"`, and `test_web_search`/others that call `get_settings()` are unaffected. Grep for `"anthropic"` in `tests/` and fix only the provider-default assertion.

- [ ] **Step 9: Run tests + commit**

Run:
```bash
cd teg-outreach-agent && .venv/bin/python -m pytest -q
```
Expected: full suite green (Gemini's 3 new tests + existing, with the one settings assertion updated).

```bash
cd /home/com-028/Desktop/TRT/PROJ/TECHEXPO
git add teg-outreach-agent/
git commit -m "feat(outreach): Gemini LLM adapter, set as default provider

User chose Google Gemini (gemini-flash-latest) over Anthropic. Adds
GeminiClient behind the existing LLMClient interface; get_llm() routes on
llm_provider='gemini' (now the default). Anthropic adapter retained.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 6: Research tools — `ResearchTool` ABC + `KBRetriever`

**Files:**
- Create: `teg-outreach-agent/app/research/__init__.py` (empty)
- Create: `teg-outreach-agent/app/research/tools.py`
- Create: `teg-outreach-agent/app/research/kb_retriever.py`
- Test: `teg-outreach-agent/tests/research/test_kb_retriever.py`

**Interfaces:**
- Consumes: `app.kb.loader.get_kb`, `CompanyRecord`, `PersonRecord`
- Produces (`app.research.tools`):
  - `ResearchQuery` dataclass: `track: Literal["company","person"]`, `subject: str` (the name), `context: str` (e.g. the other name), `want: list[str]` (target field names)
  - `ResearchResult` dataclass: `available: bool = True`, `fields: dict[str, str] = {}`, `confidence: dict[str, float] = {}`, `source_url: str | None = None`, `tool_name: str = ""`, `notes: str = ""`
  - `ResearchTool` ABC: `name: str` (class attr), `async def lookup(self, query: ResearchQuery) -> ResearchResult`
- Produces (`app.research.kb_retriever`):
  - `KBRetriever(ResearchTool)` — `name = "kb"`. On a `company` query: `find_company`, and if score ≥ 0.5 populate `fields` (`sector` from category, `website`, `teg_history` from teg_participation, `overview`), `confidence` per field = the match score, `notes` = slug. On a `person` query: `find_person`, populate `role`, `teg_role` (= `kind`), `overview`.

- [ ] **Step 1: Write the failing test**

```python
# tests/research/test_kb_retriever.py
from app.research.tools import ResearchQuery
from app.research.kb_retriever import KBRetriever


async def test_company_hit_populates_fields():
    r = await KBRetriever().lookup(ResearchQuery(
        track="company", subject="Third Rock Techkno", context="Rohan B",
        want=["sector", "website", "teg_history"],
    ))
    assert r.available is True
    assert r.tool_name == "kb"
    assert "AI" in r.fields["sector"]
    assert r.fields["website"].startswith("https://")
    assert "2024" in r.fields["teg_history"]
    assert r.confidence["sector"] == 1.0


async def test_company_miss_returns_unavailable():
    r = await KBRetriever().lookup(ResearchQuery(
        track="company", subject="Zzxqwerty Nonexistent Ltd", context="",
        want=["sector"],
    ))
    assert r.available is False


async def test_person_hit_sets_teg_role():
    r = await KBRetriever().lookup(ResearchQuery(
        track="person", subject="Tejas Shah", context="MagnusMinds",
        want=["role", "teg_role"],
    ))
    assert r.available is True
    assert r.fields["teg_role"] in {"organizer", "founder", "speaker"}
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent && mkdir -p tests/research && touch tests/research/__init__.py app/research/__init__.py && python -m pytest tests/research/test_kb_retriever.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.research.tools'`

- [ ] **Step 3: Write app/research/tools.py**

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ResearchQuery:
    track: Literal["company", "person"]
    subject: str
    context: str
    want: list[str]


@dataclass
class ResearchResult:
    available: bool = True
    fields: dict[str, str] = field(default_factory=dict)
    confidence: dict[str, float] = field(default_factory=dict)
    source_url: str | None = None
    tool_name: str = ""
    notes: str = ""


class ResearchTool(ABC):
    name: str = "tool"

    @abstractmethod
    async def lookup(self, query: ResearchQuery) -> ResearchResult: ...
```

- [ ] **Step 4: Write app/research/kb_retriever.py**

```python
from __future__ import annotations

from app.kb.loader import get_kb
from app.research.tools import ResearchQuery, ResearchResult, ResearchTool


class KBRetriever(ResearchTool):
    name = "kb"

    async def lookup(self, query: ResearchQuery) -> ResearchResult:
        kb = get_kb()
        if query.track == "company":
            rec, score = kb.find_company(query.subject)
            if rec is None or score < 0.5:
                return ResearchResult(available=False, tool_name=self.name)
            fields: dict[str, str] = {}
            if rec.category:
                fields["sector"] = rec.category
            if rec.website:
                fields["website"] = rec.website
            if rec.teg_participation:
                fields["teg_history"] = rec.teg_participation
            if rec.overview:
                fields["overview"] = rec.overview
            return ResearchResult(
                available=True, fields=fields,
                confidence={k: score for k in fields},
                tool_name=self.name, notes=rec.slug,
            )
        rec_p, score_p = kb.find_person(query.subject)
        if rec_p is None or score_p < 0.6:
            return ResearchResult(available=False, tool_name=self.name)
        fields = {"teg_role": rec_p.kind}
        if rec_p.role:
            fields["role"] = rec_p.role
        if rec_p.overview:
            fields["overview"] = rec_p.overview
        if rec_p.company:
            fields["company"] = rec_p.company
        return ResearchResult(
            available=True, fields=fields,
            confidence={k: score_p for k in fields},
            tool_name=self.name, notes=rec_p.slug,
        )
```

- [ ] **Step 5: Run tests**

Run: `cd teg-outreach-agent && python -m pytest tests/research/test_kb_retriever.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add teg-outreach-agent/
git commit -m "feat(outreach): ResearchTool interface and KB retriever

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 7: Research tools — `PageScraper` + `LinkedInStub`

**Files:**
- Create: `teg-outreach-agent/app/research/page_scraper.py`
- Create: `teg-outreach-agent/app/research/linkedin.py`
- Test: `teg-outreach-agent/tests/research/test_page_scraper.py`
- Test: `teg-outreach-agent/tests/research/test_linkedin.py`

**Interfaces:**
- Consumes: `app.research.tools`, `config.settings.get_settings`
- Produces:
  - `app.research.page_scraper.PageScraper(ResearchTool)` — `name = "scrape"`. `lookup` treats `query.subject` as a URL (skip if it doesn't look like `http`). GET via `httpx.AsyncClient` (timeout 8s, one retry, `follow_redirects=True`, a normal browser UA). Extract main text with `trafilatura.extract`. Returns the first ~4000 chars in `fields["page_text"]`, `source_url` set, `confidence={"page_text": 0.6}`. On HTTP error or empty extraction → `available=False`.
  - `app.research.linkedin.LinkedInStub(ResearchTool)` — `name = "linkedin"`. Always returns `ResearchResult(available=False, tool_name="linkedin", notes="linkedin provider disabled")`. Reads `settings.linkedin_provider`; only `none` is supported — any other value raises `NotImplementedError` at construction (documents the slot without silently no-op-ing a misconfiguration).

- [ ] **Step 1: Write the failing tests**

```python
# tests/research/test_page_scraper.py
import httpx
import respx

from app.research.tools import ResearchQuery
from app.research.page_scraper import PageScraper

HTML = """<html><body><article>
<h1>Acme Corp</h1>
<p>Acme Corp is a 40-person software company in Ahmedabad building ERP tools.</p>
</article></body></html>"""


@respx.mock
async def test_scrape_extracts_text():
    respx.get("https://acme.example/about").mock(
        return_value=httpx.Response(200, html=HTML)
    )
    r = await PageScraper().lookup(ResearchQuery(
        track="company", subject="https://acme.example/about", context="", want=["page_text"],
    ))
    assert r.available is True
    assert "Ahmedabad" in r.fields["page_text"]
    assert r.source_url == "https://acme.example/about"


@respx.mock
async def test_scrape_http_error_unavailable():
    respx.get("https://acme.example/404").mock(return_value=httpx.Response(404))
    r = await PageScraper().lookup(ResearchQuery(
        track="company", subject="https://acme.example/404", context="", want=["page_text"],
    ))
    assert r.available is False


async def test_scrape_non_url_unavailable():
    r = await PageScraper().lookup(ResearchQuery(
        track="company", subject="Acme Corp", context="", want=["page_text"],
    ))
    assert r.available is False
```

```python
# tests/research/test_linkedin.py
import pytest

from app.research.tools import ResearchQuery
from app.research.linkedin import LinkedInStub


async def test_linkedin_stub_always_unavailable(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("LINKEDIN_PROVIDER", "none")
    r = await LinkedInStub().lookup(ResearchQuery(
        track="person", subject="Someone", context="Acme", want=["linkedin_url"],
    ))
    assert r.available is False
    assert r.tool_name == "linkedin"


def test_linkedin_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("LINKEDIN_PROVIDER", "apify")
    from config.settings import get_settings
    get_settings.cache_clear()
    with pytest.raises(NotImplementedError):
        LinkedInStub()
    get_settings.cache_clear()
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent && python -m pytest tests/research/test_page_scraper.py tests/research/test_linkedin.py -v`
Expected: FAIL — modules not found

- [ ] **Step 3: Write app/research/page_scraper.py**

```python
from __future__ import annotations

import httpx
import trafilatura

from app.research.tools import ResearchQuery, ResearchResult, ResearchTool

_UA = "Mozilla/5.0 (compatible; TEG-Outreach/0.1; +https://techexpogujarat.com)"


class PageScraper(ResearchTool):
    name = "scrape"

    async def lookup(self, query: ResearchQuery) -> ResearchResult:
        url = query.subject.strip()
        if not url.lower().startswith("http"):
            return ResearchResult(available=False, tool_name=self.name)
        text: str | None = None
        async with httpx.AsyncClient(
            timeout=8.0, follow_redirects=True, headers={"User-Agent": _UA}
        ) as client:
            for attempt in range(2):
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    text = trafilatura.extract(resp.text)
                    break
                except (httpx.HTTPError,) as exc:  # noqa: PERF203
                    if attempt == 1:
                        return ResearchResult(
                            available=False, tool_name=self.name, notes=str(exc)
                        )
        if not text:
            return ResearchResult(available=False, tool_name=self.name)
        return ResearchResult(
            available=True,
            fields={"page_text": text[:4000]},
            confidence={"page_text": 0.6},
            source_url=url,
            tool_name=self.name,
        )
```

- [ ] **Step 4: Write app/research/linkedin.py**

```python
from __future__ import annotations

from app.research.tools import ResearchQuery, ResearchResult, ResearchTool
from config.settings import get_settings


class LinkedInStub(ResearchTool):
    name = "linkedin"

    def __init__(self) -> None:
        provider = get_settings().linkedin_provider
        if provider != "none":
            raise NotImplementedError(
                f"linkedin_provider={provider!r} is not implemented. "
                "This system ships with no paid LinkedIn enrichment."
            )

    async def lookup(self, query: ResearchQuery) -> ResearchResult:
        return ResearchResult(
            available=False, tool_name=self.name, notes="linkedin provider disabled"
        )
```

- [ ] **Step 5: Run tests**

Run: `cd teg-outreach-agent && python -m pytest tests/research/test_page_scraper.py tests/research/test_linkedin.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add teg-outreach-agent/
git commit -m "feat(outreach): page scraper and no-op LinkedIn stub research tools

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 8: Research tools — `TavilySearch` / `BraveSearch`

**Files:**
- Create: `teg-outreach-agent/app/research/web_search.py`
- Test: `teg-outreach-agent/tests/research/test_web_search.py`

**Interfaces:**
- Consumes: `app.research.tools`, `config.settings.get_settings`
- Produces (`app.research.web_search`):
  - `TavilySearch(ResearchTool)` — `name = "web"`. POSTs `https://api.tavily.com/search` with `{"api_key", "query", "max_results": 5, "search_depth": "basic"}`. Builds `query.subject + " " + query.context`. Returns concatenated result snippets in `fields["web_context"]`, any LinkedIn URL found in results in `fields["linkedin_url"]` (URL only, never fetched), `source_url` = first result url, `confidence={"web_context": 0.5, "linkedin_url": 0.5}`. Missing key or HTTP error → `available=False`.
  - `BraveSearch(ResearchTool)` — `name = "web"`. GET `https://api.search.brave.com/res/v1/web/search?q=...` with header `X-Subscription-Token`. Same output shape.
  - `get_web_search() -> ResearchTool | None` — returns `TavilySearch()` / `BraveSearch()` / `None` per `settings.web_search_provider` (`tavily`/`brave`/`none`).

- [ ] **Step 1: Write the failing test**

```python
# tests/research/test_web_search.py
import httpx
import respx

from app.research.tools import ResearchQuery
from app.research.web_search import TavilySearch, BraveSearch, get_web_search


@respx.mock
async def test_tavily_returns_context_and_linkedin(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    respx.post("https://api.tavily.com/search").mock(return_value=httpx.Response(200, json={
        "results": [
            {"title": "Acme", "url": "https://acme.example", "content": "Acme builds ERP in Ahmedabad."},
            {"title": "Rohan on LinkedIn", "url": "https://in.linkedin.com/in/rohanb", "content": "CTO at Acme"},
        ]
    }))
    r = await TavilySearch().lookup(ResearchQuery(
        track="company", subject="Acme", context="Rohan B", want=["web_context", "linkedin_url"],
    ))
    assert r.available is True
    assert "Ahmedabad" in r.fields["web_context"]
    assert r.fields["linkedin_url"] == "https://in.linkedin.com/in/rohanb"


@respx.mock
async def test_tavily_http_error_unavailable(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    respx.post("https://api.tavily.com/search").mock(return_value=httpx.Response(500))
    r = await TavilySearch().lookup(ResearchQuery(
        track="company", subject="Acme", context="", want=["web_context"],
    ))
    assert r.available is False


async def test_tavily_missing_key_unavailable(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("TAVILY_API_KEY", "")
    from config.settings import get_settings
    get_settings.cache_clear()
    r = await TavilySearch().lookup(ResearchQuery(
        track="company", subject="Acme", context="", want=["web_context"],
    ))
    assert r.available is False
    get_settings.cache_clear()


async def test_get_web_search_selects_provider(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "none")
    from config.settings import get_settings
    get_settings.cache_clear()
    assert get_web_search() is None
    get_settings.cache_clear()
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent && python -m pytest tests/research/test_web_search.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write app/research/web_search.py**

```python
from __future__ import annotations

import re

import httpx

from app.research.tools import ResearchQuery, ResearchResult, ResearchTool
from config.settings import get_settings

_LINKEDIN_RE = re.compile(r"https?://[a-z]{0,3}\.?linkedin\.com/\S+", re.I)


def _pack(results: list[dict]) -> ResearchResult:
    if not results:
        return ResearchResult(available=False, tool_name="web")
    snippets = " ".join(
        f"{r.get('title', '')}: {r.get('content', r.get('description', ''))}".strip()
        for r in results
    )
    linkedin = ""
    for r in results:
        m = _LINKEDIN_RE.search(r.get("url", ""))
        if m:
            linkedin = m.group(0).rstrip(".,)")
            break
    fields = {"web_context": snippets[:4000]}
    conf = {"web_context": 0.5}
    if linkedin:
        fields["linkedin_url"] = linkedin
        conf["linkedin_url"] = 0.5
    return ResearchResult(
        available=True, fields=fields, confidence=conf,
        source_url=results[0].get("url"), tool_name="web",
    )


class TavilySearch(ResearchTool):
    name = "web"

    async def lookup(self, query: ResearchQuery) -> ResearchResult:
        key = get_settings().tavily_api_key
        if not key:
            return ResearchResult(available=False, tool_name=self.name)
        q = f"{query.subject} {query.context}".strip()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post("https://api.tavily.com/search", json={
                    "api_key": key, "query": q, "max_results": 5, "search_depth": "basic",
                })
                resp.raise_for_status()
                return _pack(resp.json().get("results", []))
        except httpx.HTTPError:
            return ResearchResult(available=False, tool_name=self.name)


class BraveSearch(ResearchTool):
    name = "web"

    async def lookup(self, query: ResearchQuery) -> ResearchResult:
        key = get_settings().brave_api_key
        if not key:
            return ResearchResult(available=False, tool_name=self.name)
        q = f"{query.subject} {query.context}".strip()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": q, "count": 5},
                    headers={"X-Subscription-Token": key, "Accept": "application/json"},
                )
                resp.raise_for_status()
                web = resp.json().get("web", {}).get("results", [])
                return _pack(web)
        except httpx.HTTPError:
            return ResearchResult(available=False, tool_name=self.name)


def get_web_search() -> ResearchTool | None:
    provider = get_settings().web_search_provider
    if provider == "tavily":
        return TavilySearch()
    if provider == "brave":
        return BraveSearch()
    return None
```

- [ ] **Step 4: Run tests**

Run: `cd teg-outreach-agent && python -m pytest tests/research/ -v`
Expected: PASS (all research tests)

- [ ] **Step 5: Commit**

```bash
git add teg-outreach-agent/
git commit -m "feat(outreach): Tavily and Brave web-search research tools

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 9: `Agent` ABC + `AnalysisAgent`

**Files:**
- Create: `teg-outreach-agent/app/agents/__init__.py` (empty)
- Create: `teg-outreach-agent/app/agents/base.py`
- Create: `teg-outreach-agent/app/agents/analysis.py`
- Test: `teg-outreach-agent/tests/agents/test_analysis.py`

**Interfaces:**
- Consumes: `app.llm.base.LLMClient`, `app.domain.schemas.IntakePayload`/`IntakeResult`, `app.kb.loader.get_kb`
- Produces:
  - `app.agents.base.Agent` — generic ABC: `class Agent(ABC): def __init__(self, llm: LLMClient) -> None; @abstractmethod async def run(self, data): ...`
  - `app.agents.analysis.AnalysisAgent(Agent)` — `async def run(self, payload: IntakePayload) -> IntakeResult`
    - Strips honorifics (`Mr Mr. Ms Ms. Mrs Dr Dr. Shri Smt Prof`) and title-cases `person_name`.
    - Canonicalizes `company_name`: calls one `llm.generate_structured` with `_CanonResult` schema (`{"canonical": str, "intent_hint": IntentHint}`), passing the KB company-name list as context so it only expands abbreviations that match a real KB company. Falls back to the raw name if the LLM canonical doesn't fuzzy-match either the raw input or a KB company at ≥0.5.
    - `provided_fields`: names of non-None optional fields.
    - `consent_status`: `given`/`not_given`/`unknown` from `payload.consent`.
  - `_CanonResult(BaseModel)` — internal, in `analysis.py`: `canonical: str`, `intent_hint: IntentHint`

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/test_analysis.py
from app.agents.analysis import AnalysisAgent, _CanonResult
from app.domain.schemas import IntakePayload
from app.llm.fake import FakeLLMClient


async def test_strips_honorific_and_titlecases():
    llm = FakeLLMClient(structured=[_CanonResult(canonical="Acme Corp", intent_hint="unknown")])
    out = await AnalysisAgent(llm).run(IntakePayload(person_name="dr. rohan  b", company_name="acme corp"))
    assert out.person_name == "Rohan B"


async def test_canonical_from_llm_when_matches_kb():
    llm = FakeLLMClient(structured=[_CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor")])
    out = await AnalysisAgent(llm).run(IntakePayload(person_name="Rohan B", company_name="TRT"))
    assert out.company_name_canonical == "Third Rock Techkno"
    assert out.company_name_raw == "TRT"
    assert out.intent_hint == "exhibitor"


async def test_canonical_falls_back_when_llm_hallucinates():
    # LLM returns something unrelated to input and not in KB -> keep raw
    llm = FakeLLMClient(structured=[_CanonResult(canonical="Completely Different Co", intent_hint="unknown")])
    out = await AnalysisAgent(llm).run(IntakePayload(person_name="X", company_name="Acme Corp"))
    assert out.company_name_canonical == "Acme Corp"


async def test_provided_fields_and_consent():
    llm = FakeLLMClient(structured=[_CanonResult(canonical="Acme", intent_hint="visitor")])
    out = await AnalysisAgent(llm).run(IntakePayload(
        person_name="X", company_name="Acme", email="x@y.com", message="want to attend", consent=False,
    ))
    assert set(out.provided_fields) == {"email", "message"}
    assert out.consent_status == "not_given"


async def test_intent_hint_from_participation_type_overrides_llm():
    llm = FakeLLMClient(structured=[_CanonResult(canonical="Acme", intent_hint="unknown")])
    out = await AnalysisAgent(llm).run(IntakePayload(
        person_name="X", company_name="Acme", participation_type="sponsor",
    ))
    assert out.intent_hint == "sponsor"
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent && mkdir -p tests/agents && touch tests/agents/__init__.py app/agents/__init__.py && python -m pytest tests/agents/test_analysis.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write app/agents/base.py**

```python
from __future__ import annotations

from abc import ABC, abstractmethod

from app.llm.base import LLMClient


class Agent(ABC):
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    @abstractmethod
    async def run(self, data):  # noqa: ANN001, ANN201
        ...
```

- [ ] **Step 4: Write app/agents/analysis.py**

```python
from __future__ import annotations

import re

from pydantic import BaseModel

from app.agents.base import Agent
from app.domain.schemas import IntakePayload, IntakeResult, IntentHint
from app.kb.loader import _token_set_ratio, get_kb

_HONORIFICS = re.compile(r"^\s*(mr|mrs|ms|dr|shri|smt|prof)\.?\s+", re.I)

_PARTICIPATION_MAP = {
    "visitor": "visitor", "exhibitor": "exhibitor", "sponsor": "sponsor",
    "startup_pitch": "startup_pitch", "startup pitch": "startup_pitch",
    "speaker": "speaker",
}

_MESSAGE_HINTS = [
    (re.compile(r"\b(exhibit|stall|booth)\b", re.I), "exhibitor"),
    (re.compile(r"\b(sponsor|partner)\b", re.I), "sponsor"),
    (re.compile(r"\b(pitch|funding|investor)\b", re.I), "startup_pitch"),
    (re.compile(r"\b(visit|attend|ticket|pass)\b", re.I), "visitor"),
]


class _CanonResult(BaseModel):
    canonical: str
    intent_hint: IntentHint


def _clean_name(raw: str) -> str:
    name = _HONORIFICS.sub("", raw or "").strip()
    name = " ".join(name.split())
    return name.title()


def _guess_intent(payload: IntakePayload) -> IntentHint:
    pt = (payload.participation_type or "").strip().lower()
    if pt in _PARTICIPATION_MAP:
        return _PARTICIPATION_MAP[pt]  # type: ignore[return-value]
    msg = payload.message or ""
    for rx, hint in _MESSAGE_HINTS:
        if rx.search(msg):
            return hint  # type: ignore[return-value]
    return "unknown"


class AnalysisAgent(Agent):
    async def run(self, payload: IntakePayload) -> IntakeResult:
        person = _clean_name(payload.person_name)
        raw_company = payload.company_name.strip()

        kb = get_kb()
        kb_names = [c.name for c in kb._companies]  # noqa: SLF001  (read-only helper access)
        system = (
            "You normalise a company name for an event CRM. Only expand an abbreviation "
            "or partial name if it clearly matches one of the known companies provided. "
            "Otherwise return the input unchanged. Also give a best-guess intent_hint."
        )
        user = (
            f"Company as entered: {raw_company!r}\n"
            f"Message (may be empty): {payload.message or ''!r}\n"
            f"Known companies: {', '.join(kb_names[:400])}"
        )
        canon = await self.llm.generate_structured(
            system=system,
            messages=[{"role": "user", "content": user}],
            schema=_CanonResult,
        )

        canonical = canon.canonical.strip() or raw_company
        matches_input = _token_set_ratio(canonical, raw_company) >= 0.5
        matches_kb = any(_token_set_ratio(canonical, n) >= 0.9 for n in kb_names)
        if not (matches_input or matches_kb):
            canonical = raw_company

        provided = [
            f for f in (
                "email", "phone", "city", "designation", "participation_type",
                "tech_category", "message", "preferred_contact_time",
            )
            if getattr(payload, f) not in (None, "")
        ]

        if payload.consent is True:
            consent = "given"
        elif payload.consent is False:
            consent = "not_given"
        else:
            consent = "unknown"

        explicit_intent = _guess_intent(payload)
        intent = explicit_intent if explicit_intent != "unknown" else canon.intent_hint

        return IntakeResult(
            person_name=person,
            company_name_raw=raw_company,
            company_name_canonical=canonical,
            provided_fields=provided,
            intent_hint=intent,
            consent_status=consent,
        )
```

- [ ] **Step 5: Run tests**

Run: `cd teg-outreach-agent && python -m pytest tests/agents/test_analysis.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add teg-outreach-agent/
git commit -m "feat(outreach): Agent ABC and AnalysisAgent

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 10: `ResearchAgent`

**Files:**
- Create: `teg-outreach-agent/app/agents/research.py`
- Test: `teg-outreach-agent/tests/agents/test_research.py`

**Interfaces:**
- Consumes: `app.agents.base.Agent`, `app.domain.schemas.IntakeResult`/`ResearchDossier`/`SourceRef`, `app.research.tools.*`, `app.research.kb_retriever.KBRetriever`, `app.research.page_scraper.PageScraper`, `app.research.linkedin.LinkedInStub`, `app.research.web_search.get_web_search`, `config.settings.get_settings`, `config.outreach_rules.load_rules`, `app.kb.loader.get_kb`
- Produces:
  - `app.agents.research.ResearchAgent(Agent)`:
    - `__init__(self, llm, tools: list[ResearchTool] | None = None)` — default tools: `[KBRetriever(), get_web_search(), PageScraper(), LinkedInStub()]` (drop `None`).
    - `async def run(self, intake: IntakeResult) -> ResearchDossier`
    - Runs a **company track** and a **person track** concurrently (`asyncio.gather`), each a bounded cascade:
      - company `want = ["sector","company_size","hq","founder","website","teg_history","booth_number"]`
      - person `want = ["designation","seniority","is_technical","linkedin_url","teg_role","background"]`
      - Step 1: `KBRetriever`. If it fills the identity field (`sector` for company / `teg_role` or `role` for person) at conf ≥ `thresholds.auto_accept`, that's high-confidence.
      - Step 2: web search — up to `settings.research_max_searches_per_track` calls — if KB missed identity OR `want` fields remain empty.
      - Step 3: `PageScraper` — only on URLs surfaced by web search (company site / directory), capped by `settings.research_max_scrapes` **shared across both tracks**.
      - `LinkedInStub` is always tried and always returns unavailable (keeps the call path honest).
    - After both tracks: one `llm.generate_structured` call with `_Synthesis` schema to fold raw `web_context`/`page_text` into clean fields (`sector`, `company_size`, `hq`, `founder`, `designation`, `seniority`, `is_technical`) and to judge `person_company_match`.
    - Derived:
      - `relationship`: `insider` if person KB match kind == "organizer"; `returning` if company `teg_history` mentions "2024"/"2026"/"sponsor" or person kind == "speaker"; else `cold`.
      - `sector`: resolved sector string (KB category preferred, else synthesis).
      - `peer_companies`: `get_kb().peers_in_sector(sector, 5)` minus the prospect's own company.
      - `field_confidence`: merged per-field max confidence seen.
      - `sources`: one `SourceRef` per (field, tool) that contributed.
      - `ask_prospect`: if company identity confidence < 0.5 → append `"company_description"`; if person identity confidence < 0.5 → append `"role"`.
      - `research_cost`: `{"web_calls": n, "scrape_calls": n, "llm_calls": n}`.
  - `_Synthesis(BaseModel)` in `research.py`: `sector: str | None`, `company_size: str | None`, `hq: str | None`, `founder: str | None`, `designation: str | None`, `seniority: str | None`, `is_technical: bool | None`, `person_company_match: bool | None`

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/test_research.py
from app.agents.research import ResearchAgent, _Synthesis
from app.domain.schemas import IntakeResult
from app.llm.fake import FakeLLMClient
from app.research.tools import ResearchQuery, ResearchResult, ResearchTool


class StubTool(ResearchTool):
    def __init__(self, name, result):
        self.name = name
        self._result = result
        self.queries: list[ResearchQuery] = []

    async def lookup(self, query):
        self.queries.append(query)
        return self._result


def _intake(company="Third Rock Techkno", person="Rohan B", intent="exhibitor"):
    return IntakeResult(
        person_name=person, company_name_raw=company, company_name_canonical=company,
        provided_fields=[], intent_hint=intent, consent_status="unknown",
    )


async def test_kb_hit_company_fills_dossier_without_web():
    from app.research.kb_retriever import KBRetriever
    web = StubTool("web", ResearchResult(available=False, tool_name="web"))
    llm = FakeLLMClient(structured=[_Synthesis(
        sector="AI Consulting", company_size=None, hq=None, founder=None,
        designation=None, seniority=None, is_technical=None, person_company_match=None,
    )])
    agent = ResearchAgent(llm, tools=[KBRetriever(), web])
    d = await agent.run(_intake())
    assert "AI" in (d.sector or "")
    assert d.relationship in {"returning", "insider"}
    assert "Third Rock Techkno" not in d.peer_companies
    assert web.queries == [] or all(q for q in web.queries)  # web may be skipped


async def test_unknown_company_sets_ask_prospect():
    from app.research.kb_retriever import KBRetriever
    web = StubTool("web", ResearchResult(available=False, tool_name="web"))
    llm = FakeLLMClient(structured=[_Synthesis(
        sector=None, company_size=None, hq=None, founder=None,
        designation=None, seniority=None, is_technical=None, person_company_match=None,
    )])
    agent = ResearchAgent(llm, tools=[KBRetriever(), web])
    d = await agent.run(_intake(company="Zzxqwerty Nonexistent Ltd", person="Nobody Atall"))
    assert "company_description" in d.ask_prospect
    assert d.relationship == "cold"


async def test_web_context_is_synthesised_into_fields():
    from app.research.kb_retriever import KBRetriever
    web = StubTool("web", ResearchResult(
        available=True, tool_name="web",
        fields={"web_context": "Acme is a 30-person ERP firm in Surat. Rohan is CTO."},
        confidence={"web_context": 0.5},
        source_url="https://acme.example",
    ))
    scraper = StubTool("scrape", ResearchResult(available=False, tool_name="scrape"))
    llm = FakeLLMClient(structured=[_Synthesis(
        sector="Enterprise Software", company_size="30", hq="Surat", founder=None,
        designation="CTO", seniority="exec", is_technical=True, person_company_match=True,
    )])
    agent = ResearchAgent(llm, tools=[KBRetriever(), web, scraper])
    d = await agent.run(_intake(company="Acme Corp", person="Rohan B", intent="unknown"))
    assert d.company_profile["hq"] == "Surat"
    assert d.person_profile["designation"] == "CTO"
    assert d.person_company_match is True
    assert d.research_cost["web_calls"] >= 1
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent && python -m pytest tests/agents/test_research.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write app/agents/research.py**

```python
from __future__ import annotations

import asyncio

from pydantic import BaseModel

from app.agents.base import Agent
from app.domain.schemas import IntakeResult, ResearchDossier, SourceRef
from app.kb.loader import get_kb
from app.research.kb_retriever import KBRetriever
from app.research.linkedin import LinkedInStub
from app.research.page_scraper import PageScraper
from app.research.tools import ResearchQuery, ResearchResult, ResearchTool
from app.research.web_search import get_web_search
from config.outreach_rules import load_rules
from config.settings import get_settings

_COMPANY_WANT = ["sector", "company_size", "hq", "founder", "website", "teg_history", "booth_number"]
_PERSON_WANT = ["designation", "seniority", "is_technical", "linkedin_url", "teg_role", "background"]


class _Synthesis(BaseModel):
    sector: str | None = None
    company_size: str | None = None
    hq: str | None = None
    founder: str | None = None
    designation: str | None = None
    seniority: str | None = None
    is_technical: bool | None = None
    person_company_match: bool | None = None


class _Budget:
    def __init__(self, max_web_per_track: int, max_scrapes: int) -> None:
        self.web_left_company = max_web_per_track
        self.web_left_person = max_web_per_track
        self.scrapes_left = max_scrapes
        self.web_calls = 0
        self.scrape_calls = 0


class ResearchAgent(Agent):
    def __init__(self, llm, tools: list[ResearchTool] | None = None) -> None:
        super().__init__(llm)
        if tools is None:
            tools = [KBRetriever(), get_web_search(), PageScraper(), LinkedInStub()]
        tools = [t for t in tools if t is not None]
        self._kb = next((t for t in tools if t.name == "kb"), KBRetriever())
        self._web = next((t for t in tools if t.name == "web"), None)
        self._scraper = next((t for t in tools if t.name == "scrape"), None)
        self._linkedin = next((t for t in tools if t.name == "linkedin"), None)
        self._rules = load_rules()
        self._auto = self._rules.confidence_thresholds["company_name"]["auto_accept"]

    async def run(self, intake: IntakeResult) -> ResearchDossier:
        s = get_settings()
        budget = _Budget(s.research_max_searches_per_track, s.research_max_scrapes)

        company_task = self._track(
            "company", intake.company_name_canonical, intake.person_name, _COMPANY_WANT, budget,
        )
        person_task = self._track(
            "person", intake.person_name, intake.company_name_canonical, _PERSON_WANT, budget,
        )
        (c_fields, c_conf, c_sources, c_id_conf, c_kb_notes), \
        (p_fields, p_conf, p_sources, p_id_conf, p_kb_notes) = await asyncio.gather(
            company_task, person_task
        )

        raw_ctx = " ".join(
            v for v in (
                c_fields.get("web_context", ""), c_fields.get("page_text", ""),
                p_fields.get("web_context", ""), p_fields.get("page_text", ""),
            ) if v
        )
        synth = _Synthesis()
        llm_calls = 0
        if raw_ctx.strip():
            synth = await self.llm.generate_structured(
                system=(
                    "Extract firmographic and role facts from research text. "
                    "Only state a field if the text supports it; else leave it null. "
                    "person_company_match: does the text place this person at this company?"
                ),
                messages=[{"role": "user", "content": (
                    f"Person: {intake.person_name}\nCompany: {intake.company_name_canonical}\n\n"
                    f"Research text:\n{raw_ctx[:6000]}"
                )}],
                schema=_Synthesis,
            )
            llm_calls = 1

        company_profile = {
            "sector": c_fields.get("sector") or synth.sector,
            "company_size": synth.company_size,
            "hq": synth.hq,
            "founder": synth.founder,
            "website": c_fields.get("website"),
            "teg_history": c_fields.get("teg_history"),
            "overview": c_fields.get("overview"),
        }
        person_profile = {
            "designation": p_fields.get("role") or synth.designation,
            "seniority": synth.seniority,
            "is_technical": synth.is_technical,
            "linkedin_url": p_fields.get("linkedin_url"),
            "teg_role": p_fields.get("teg_role"),
            "background": p_fields.get("overview"),
        }

        # relationship
        relationship = "cold"
        teg_hist = (company_profile.get("teg_history") or "").lower()
        if p_fields.get("teg_role") == "organizer":
            relationship = "insider"
        elif any(k in teg_hist for k in ("2024", "2026", "sponsor")) or p_fields.get("teg_role") == "speaker":
            relationship = "returning"

        sector = company_profile.get("sector")
        peers: list[str] = []
        if sector:
            own = intake.company_name_canonical.lower()
            peers = [p for p in get_kb().peers_in_sector(sector, 6) if p.lower() != own][:5]

        field_confidence: dict[str, float] = {}
        for k, v in list(c_conf.items()) + list(p_conf.items()):
            field_confidence[k] = max(field_confidence.get(k, 0.0), v)

        sources = c_sources + p_sources

        ask_prospect: list[str] = []
        if c_id_conf < 0.5:
            ask_prospect.append("company_description")
        if p_id_conf < 0.5:
            ask_prospect.append("role")

        return ResearchDossier(
            company_profile={k: v for k, v in company_profile.items() if v is not None},
            person_profile={k: v for k, v in person_profile.items() if v is not None},
            person_company_match=synth.person_company_match,
            relationship=relationship,
            sector=sector,
            peer_companies=peers,
            field_confidence=field_confidence,
            sources=sources,
            review_flags=(["person_company_mismatch"] if synth.person_company_match is False else []),
            ask_prospect=ask_prospect,
            research_cost={
                "web_calls": budget.web_calls,
                "scrape_calls": budget.scrape_calls,
                "llm_calls": llm_calls,
            },
        )

    async def _track(self, track, subject, context, want, budget):
        fields: dict[str, str] = {}
        conf: dict[str, float] = {}
        sources: list[SourceRef] = []

        kb_res = await self._kb.lookup(ResearchQuery(track=track, subject=subject, context=context, want=want))
        id_field = "sector" if track == "company" else "teg_role"
        id_conf = 0.0
        if kb_res.available:
            fields.update(kb_res.fields)
            conf.update(kb_res.confidence)
            id_conf = max(id_conf, kb_res.confidence.get(id_field, 0.0), kb_res.confidence.get("role", 0.0))
            for f in kb_res.fields:
                sources.append(SourceRef(field=f, url=None, tool="kb", confidence=kb_res.confidence.get(f, 0.0)))

        need_web = (not kb_res.available) or id_conf < self._auto or any(w not in fields for w in ("sector", "role", "designation"))
        web_left = budget.web_left_company if track == "company" else budget.web_left_person
        if need_web and self._web is not None and web_left > 0:
            res = await self._web.lookup(ResearchQuery(track=track, subject=subject, context=context, want=want))
            budget.web_calls += 1
            if track == "company":
                budget.web_left_company -= 1
            else:
                budget.web_left_person -= 1
            if res.available:
                fields.update(res.fields)
                conf.update({k: max(conf.get(k, 0.0), v) for k, v in res.confidence.items()})
                for f in res.fields:
                    sources.append(SourceRef(field=f, url=res.source_url, tool="web", confidence=res.confidence.get(f, 0.0)))
                # id_conf is not raised by web for company identity (weak signal), but a hit means "found something"
                id_conf = max(id_conf, 0.5 if res.fields.get("web_context") else id_conf)
                # try a scrape on the surfaced url
                if self._scraper is not None and res.source_url and budget.scrapes_left > 0:
                    sc = await self._scraper.lookup(ResearchQuery(track=track, subject=res.source_url, context=context, want=["page_text"]))
                    budget.scrape_calls += 1
                    budget.scrapes_left -= 1
                    if sc.available:
                        fields.update(sc.fields)
                        conf.update(sc.confidence)
                        sources.append(SourceRef(field="page_text", url=sc.source_url, tool="scrape", confidence=0.6))

        if self._linkedin is not None:
            await self._linkedin.lookup(ResearchQuery(track=track, subject=subject, context=context, want=["linkedin_url"]))

        return fields, conf, sources, id_conf, kb_res.notes
```

- [ ] **Step 4: Run tests**

Run: `cd teg-outreach-agent && python -m pytest tests/agents/test_research.py -v`
Expected: PASS (3 tests). If a peer/relationship assertion fails, inspect what `KBRetriever` returns for `third_rock_techkno` and adjust the `relationship`/`peers` derivation — not the test.

- [ ] **Step 5: Commit**

```bash
git add teg-outreach-agent/
git commit -m "feat(outreach): ResearchAgent with bounded KB-first company+person cascade

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 11: Guardrails module

**Files:**
- Create: `teg-outreach-agent/app/agents/guardrails.py`
- Test: `teg-outreach-agent/tests/agents/test_guardrails.py`

**Interfaces:**
- Consumes: `app.kb.loader.get_kb`, `app.domain.schemas.Persona`
- Produces (`app.agents.guardrails`):
  - `GuardrailViolation` dataclass: `code: str`, `detail: str`
  - `check_message(text: str, *, allowed_peers: list[str], persona: "Persona") -> list[GuardrailViolation]` — deterministic checks:
    - `visitor_price`: text mentions a rupee amount within ~30 chars of "visitor" / "ticket" / "pass" and the words "visitor"/"golden ticket" → violation (visitor prices are unpublished). Stall/sponsor prices are fine.
    - `uncleared_testimonial`: text contains a quoted sentence (`"..."` ≥ 12 words) whose attribution name is not among `get_kb().cleared_testimonials()` names → violation.
    - `invented_peer`: any capitalized multi-word company-like token in a "companies like X, Y, Z" / "peers such as" context that is not in `allowed_peers` and not in the KB company list → violation.
    - `missing_gst`: a rupee amount for a stall/sponsorship with no "GST" within 40 chars → violation.
    - `awaiting_as_confirmed`: phrases like "the ticket price is", "tickets cost ₹", "confirmed sponsors include" (for 2026) → violation.
  - `SAFE_TEMPLATES: dict[Persona, str]` — a fully KB-sourced, CTA-bearing fallback reply per persona (literal strings; no f-strings — peer names are added by the caller if available).

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/test_guardrails.py
from app.agents.guardrails import check_message, SAFE_TEMPLATES


def test_flags_visitor_price():
    v = check_message(
        "A visitor pass costs around ₹500 for early birds.",
        allowed_peers=[], persona="visitor",
    )
    assert any(x.code == "visitor_price" for x in v)


def test_allows_stall_price_with_gst():
    v = check_message(
        "A 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed at booking).",
        allowed_peers=[], persona="it_tech_service",
    )
    assert v == []


def test_flags_stall_price_missing_gst():
    v = check_message(
        "A 3m x 3m stall is ₹1,17,000.",
        allowed_peers=[], persona="it_tech_service",
    )
    assert any(x.code == "missing_gst" for x in v)


def test_flags_uncleared_testimonial():
    v = check_message(
        'As Jane Doe said, "This event completely transformed our pipeline and we closed ten deals in a week."',
        allowed_peers=[], persona="it_tech_service",
    )
    assert any(x.code == "uncleared_testimonial" for x in v)


def test_allows_cleared_testimonial():
    # Sonu Sharma is one of the 4 cleared names
    v = check_message(
        'Sonu Sharma noted that Gujarat "has an amazing force of tech people" after visiting.',
        allowed_peers=[], persona="visitor",
    )
    assert not any(x.code == "uncleared_testimonial" for x in v)


def test_flags_invented_peer():
    v = check_message(
        "Companies like Globex Corp and Initech are already exhibiting alongside you.",
        allowed_peers=["Third Rock Techkno", "NeuraMonks"], persona="ai_startup",
    )
    assert any(x.code == "invented_peer" for x in v)


def test_allows_listed_peer():
    v = check_message(
        "Companies like Third Rock Techkno and NeuraMonks are already exhibiting.",
        allowed_peers=["Third Rock Techkno", "NeuraMonks"], persona="ai_startup",
    )
    assert not any(x.code == "invented_peer" for x in v)


def test_safe_templates_cover_all_personas():
    for p in ("it_tech_service", "ai_startup", "non_tech_sponsor", "visitor"):
        assert p in SAFE_TEMPLATES and SAFE_TEMPLATES[p].strip()
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent && python -m pytest tests/agents/test_guardrails.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write app/agents/guardrails.py**

```python
from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.schemas import Persona
from app.kb.loader import get_kb

_RUPEE = re.compile(r"₹\s?[\d,]+(?:\.\d+)?\s*(?:crore|cr|lakh|lac|k)?", re.I)
_VISITOR_CTX = re.compile(r"\b(visitor|golden ticket)\b", re.I)
_TICKETY = re.compile(r"\b(ticket|pass|entry)\b", re.I)
_QUOTE = re.compile(r"[\"“]([^\"”]{20,})[\"”]")
_ATTRIB = re.compile(r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b(?=[^.]{0,40}(?:said|noted|shared|according to|remarked))|"
                     r"(?:said|noted|according to|as)\s+([A-Z][a-z]+ [A-Z][a-z]+)", re.I)
_PEER_CTX = re.compile(r"(companies like|peers such as|alongside|exhibiting with|joined by)\s+(.+?)(?:\.|$)", re.I)
_CAP_ORG = re.compile(r"\b([A-Z][A-Za-z0-9&.]+(?:\s+[A-Z][A-Za-z0-9&.]+){0,3})\b")
_AWAITING = re.compile(r"(the ticket price is|tickets cost ₹|confirmed sponsors include|the 2026 sponsors are)", re.I)


@dataclass
class GuardrailViolation:
    code: str
    detail: str


def _cleared_names() -> set[str]:
    return {t["name"] for t in get_kb().cleared_testimonials()}


def _kb_company_names() -> set[str]:
    return {c.name for c in get_kb()._companies}  # noqa: SLF001


def check_message(text: str, *, allowed_peers: list[str], persona: Persona) -> list[GuardrailViolation]:
    out: list[GuardrailViolation] = []

    # visitor price
    for m in _RUPEE.finditer(text):
        window = text[max(0, m.start() - 40): m.end() + 40]
        if _VISITOR_CTX.search(window) or (_TICKETY.search(window) and "stall" not in window.lower()
                                           and "sponsor" not in window.lower()):
            out.append(GuardrailViolation("visitor_price", window.strip()))
            break

    # missing GST on stall/sponsor price
    for m in _RUPEE.finditer(text):
        window = text[max(0, m.start() - 60): m.end() + 60]
        if re.search(r"\b(stall|sponsor|sponsorship|booth|title sponsor|partner)\b", window, re.I):
            if "gst" not in window.lower():
                out.append(GuardrailViolation("missing_gst", window.strip()))
                break

    # uncleared testimonial
    cleared = _cleared_names()
    for qm in _QUOTE.finditer(text):
        if len(qm.group(1).split()) < 12:
            continue
        span = text[max(0, qm.start() - 80): qm.end() + 80]
        names = [g for pair in _ATTRIB.findall(span) for g in pair if g]
        if names and not any(n in cleared for n in names):
            out.append(GuardrailViolation("uncleared_testimonial", qm.group(1)[:80]))
            break

    # invented peer
    kb_names_lower = {n.lower() for n in _kb_company_names()}
    allowed_lower = {p.lower() for p in allowed_peers}
    pm = _PEER_CTX.search(text)
    if pm:
        chunk = pm.group(2)
        for om in _CAP_ORG.finditer(chunk):
            cand = om.group(1).strip()
            if cand.lower() in {"and", "the"} or len(cand) < 3:
                continue
            if cand.lower() in allowed_lower or cand.lower() in kb_names_lower:
                continue
            # ignore obvious non-org words
            if cand.lower() in {"companies like", "peers such"}:
                continue
            out.append(GuardrailViolation("invented_peer", cand))
            break

    # awaiting-as-confirmed
    if _AWAITING.search(text):
        out.append(GuardrailViolation("awaiting_as_confirmed", _AWAITING.search(text).group(0)))

    return out


SAFE_TEMPLATES: dict[Persona, str] = {
    "it_tech_service": (
        "Tech Expo Gujarat 2026 runs 27–29 November 2026 at GUCEC, Ahmedabad, targeting "
        "250+ exhibitors and 15,000+ business visitors across manufacturing, healthcare, "
        "finance and more. Stall packages start at ₹1,17,000 + GST for a 3m x 3m stall "
        "(indicative, confirmed at booking), with pre-scheduled 1:1 buyer meetings and "
        "live demo space included. Would you like me to walk you through the stall options "
        "for your team?"
    ),
    "ai_startup": (
        "Tech Expo Gujarat 2026 (27–29 Nov 2026, GUCEC Ahmedabad) has a startup-focused "
        "Catalyst Zone at ₹35,000 + GST (indicative, confirmed at booking), plus an AI demo "
        "area and investor-matchmaking that came out of the TEG ecosystem. Want the Catalyst "
        "Zone details, or information on submitting a pitch?"
    ),
    "non_tech_sponsor": (
        "Tech Expo Gujarat 2026 (27–29 Nov 2026, GUCEC Ahmedabad) offers category-exclusive "
        "sponsorships — once a brand locks a category, direct competitors are excluded. "
        "Tiers run from the Title Sponsor at ₹35,00,000 + GST down to focused partner slots "
        "(all + GST, indicative and confirmed at booking). Shall I arrange a sponsorship call "
        "with the TEG team?"
    ),
    "visitor": (
        "Tech Expo Gujarat 2026 runs 27–29 November 2026 at GUCEC, Ahmedabad — three days of "
        "AI, SaaS, cloud, cybersecurity and industry tech with 250+ exhibitors. Entry is "
        "ticketed (there is no free entry); current pricing is on the official ticketing "
        "portal. Would you like the registration link?"
    ),
}
```

- [ ] **Step 4: Run tests, iterate on regexes**

Run: `cd teg-outreach-agent && python -m pytest tests/agents/test_guardrails.py -v`
Expected: PASS (8 tests). Regex tuning is expected here — adjust patterns to pass all 8 without weakening the intent (a false negative on `invented_peer` or `visitor_price` is a plan failure).

- [ ] **Step 5: Commit**

```bash
git add teg-outreach-agent/
git commit -m "feat(outreach): deterministic message guardrails and safe fallback templates

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 12: `PersuasionAgent` — `init`

**Files:**
- Create: `teg-outreach-agent/app/agents/persuasion.py`
- Test: `teg-outreach-agent/tests/agents/test_persuasion_init.py`

**Interfaces:**
- Consumes: `app.agents.base.Agent`, `app.domain.schemas.*`, `app.kb.loader.get_kb`, `config.outreach_rules.load_rules`, `app.agents.guardrails.check_message`/`SAFE_TEMPLATES`
- Produces (`app.agents.persuasion`):
  - `map_persona(intake: IntakeResult, dossier: ResearchDossier) -> Persona` — pure function implementing spec §5.3 mapping + the 3-step fallback order:
    1. sector in it-tech set → `it_tech_service`
    2. sector == AI set AND (company_size parses to < 50 OR unknown) AND matches → `ai_startup`
    3. intent_hint == "sponsor" and sector not in tech sets → `non_tech_sponsor`
    4. intent_hint == "visitor" → `visitor`
    5. fallback: tech sector → `it_tech_service`; non-tech + unknown intent → `visitor`; nothing resolved → `visitor`
  - `target_cta_for(persona: Persona) -> str` — `it_tech_service`→`"book_stall"`, `ai_startup`→`"catalyst_zone_or_pitch"`, `non_tech_sponsor`→`"request_sponsor_call"`, `visitor`→`"register_visitor"`
  - `PersuasionAgent(Agent)`:
    - `async def init(self, intake: IntakeResult, dossier: ResearchDossier) -> PersuasionInit`
      - persona = `map_persona`; if `dossier.ask_prospect` non-empty → persona used only for tone, opening_message = a qualifying question (not a pitch).
      - else: one `llm.generate` call with a system prompt built from persona value props (`load_rules().persona_triggers[persona]["value_props"]` + `exhibitor_benefits_analysis.md` section text via KB), the dossier, `dossier.peer_companies` (max 3), the relevant pricing line, tone from `dossier.relationship`. Post-check the opening with `check_message`; on violation regenerate once, then fall back to `SAFE_TEMPLATES[persona]` (+ peers appended if any).
      - returns `PersuasionInit(persona, target_cta, opening_message)`

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/test_persuasion_init.py
from app.agents.persuasion import PersuasionAgent, map_persona, target_cta_for
from app.domain.schemas import IntakeResult, ResearchDossier
from app.llm.fake import FakeLLMClient


def _intake(intent="exhibitor", company="Third Rock Techkno"):
    return IntakeResult(
        person_name="Rohan B", company_name_raw=company, company_name_canonical=company,
        provided_fields=[], intent_hint=intent, consent_status="unknown",
    )


def test_map_persona_it_tech():
    d = ResearchDossier(sector="Software Development", relationship="cold")
    assert map_persona(_intake(), d) == "it_tech_service"


def test_map_persona_ai_startup_small():
    d = ResearchDossier(sector="AI & Machine Learning", company_profile={"company_size": "20"}, relationship="cold")
    assert map_persona(_intake(), d) == "ai_startup"


def test_map_persona_non_tech_sponsor():
    d = ResearchDossier(sector="Real Estate", relationship="cold")
    assert map_persona(_intake(intent="sponsor"), d) == "non_tech_sponsor"


def test_map_persona_fallback_unresolved_is_visitor():
    d = ResearchDossier(sector=None, relationship="cold", ask_prospect=["company_description"])
    assert map_persona(_intake(intent="unknown"), d) == "visitor"


def test_target_cta_mapping():
    assert target_cta_for("it_tech_service") == "book_stall"
    assert target_cta_for("non_tech_sponsor") == "request_sponsor_call"


async def test_init_unresolved_opens_with_question():
    llm = FakeLLMClient(responses=["So I can tailor this — what does your company do, and what's your role there?"])
    d = ResearchDossier(sector=None, relationship="cold", ask_prospect=["company_description", "role"])
    out = await PersuasionAgent(llm).init(_intake(intent="unknown", company="Zzxqwerty Ltd"), d)
    assert "?" in out.opening_message
    assert out.persona == "visitor"


async def test_init_pitch_uses_peers_and_passes_guardrails():
    llm = FakeLLMClient(responses=[
        "Great to see Third Rock Techkno here. Companies like NeuraMonks and ViitorCloud "
        "are already exhibiting. A 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed "
        "at booking). Want the stall options?"
    ])
    d = ResearchDossier(
        sector="AI & Machine Learning", company_profile={"company_size": "200"},
        relationship="returning", peer_companies=["NeuraMonks", "ViitorCloud", "Perigeon"],
    )
    out = await PersuasionAgent(llm).init(_intake(company="Third Rock Techkno"), d)
    assert out.persona in {"it_tech_service", "ai_startup"}
    assert "NeuraMonks" in out.opening_message


async def test_init_falls_back_to_safe_template_on_repeated_violation():
    # both generations mention a visitor price -> must fall back
    bad = "Visitor tickets are just ₹500 — grab one now."
    llm = FakeLLMClient(responses=[bad, bad])
    d = ResearchDossier(sector="Software Development", relationship="cold", peer_companies=["NeuraMonks"])
    out = await PersuasionAgent(llm).init(_intake(intent="visitor"), d)
    assert "₹500" not in out.opening_message
    assert "GUCEC" in out.opening_message  # came from SAFE_TEMPLATES
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent && python -m pytest tests/agents/test_persuasion_init.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write app/agents/persuasion.py (init half)**

```python
from __future__ import annotations

import re

from app.agents.base import Agent
from app.agents.guardrails import SAFE_TEMPLATES, check_message
from app.domain.schemas import IntakeResult, Persona, PersuasionInit, ResearchDossier
from app.kb.loader import get_kb
from config.outreach_rules import load_rules

_IT_SECTORS = {
    "software development", "software development & it services", "it services",
    "cloud & infrastructure", "enterprise software", "data & analytics",
    "devops / cloud / hosting", "saas / productivity / messaging",
}
_AI_SECTORS = {"ai & machine learning", "ai / ml", "ai solutions", "ai consulting"}


def _size_lt_50(profile: dict) -> bool:
    raw = str(profile.get("company_size") or "")
    m = re.search(r"\d+", raw)
    if not m:
        return True  # unknown -> allow startup classification
    return int(m.group()) < 50


def map_persona(intake: IntakeResult, dossier: ResearchDossier) -> Persona:
    sector = (dossier.sector or "").strip().lower()
    if dossier.ask_prospect:
        return "visitor"
    if any(s in sector for s in _AI_SECTORS) and _size_lt_50(dossier.company_profile):
        return "ai_startup"
    if any(s in sector for s in _IT_SECTORS) or "software" in sector:
        return "it_tech_service"
    if intake.intent_hint == "sponsor":
        return "non_tech_sponsor"
    if intake.intent_hint == "visitor":
        return "visitor"
    if sector and any(s in sector for s in _IT_SECTORS | _AI_SECTORS):
        return "it_tech_service"
    return "visitor"


def target_cta_for(persona: Persona) -> str:
    return {
        "it_tech_service": "book_stall",
        "ai_startup": "catalyst_zone_or_pitch",
        "non_tech_sponsor": "request_sponsor_call",
        "visitor": "register_visitor",
    }[persona]


_PRICING_LINE = {
    "it_tech_service": "A 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed at booking); larger stalls scale up to ₹4,68,000 + GST for 6m x 6m.",
    "ai_startup": "The startup-focused Catalyst Zone is ₹35,000 + GST (indicative, confirmed at booking).",
    "non_tech_sponsor": "Sponsorship runs from the Title Sponsor at ₹35,00,000 + GST down to focused partner slots (all + GST, indicative, confirmed at booking).",
    "visitor": "Entry is ticketed (no free entry); current visitor pricing is on the official ticketing portal.",
}


class PersuasionAgent(Agent):
    def __init__(self, llm) -> None:
        super().__init__(llm)
        self._rules = load_rules()

    async def run(self, data):  # PersuasionAgent uses init()/respond(), not run()
        raise NotImplementedError("PersuasionAgent has no run(); call init() or respond()")

    def _system(self, persona: Persona, dossier: ResearchDossier) -> str:
        props = self._rules.persona_triggers.get(persona, {}).get("value_props", [])
        tone = {
            "insider": "This person is a TEG organiser — warm, peer-to-peer, no hard sell.",
            "returning": "This company/person has been part of TEG before — acknowledge that, welcome them back.",
            "cold": "First contact — warm and helpful, not familiar.",
        }[dossier.relationship]
        return (
            "You are a helpful TEG 2026 outreach assistant on the inquiry page. "
            "Be encouraging and specific, never pushy. One short paragraph, end with one soft ask.\n"
            f"Tone: {tone}\n"
            f"Persona value props to draw on: {'; '.join(props)}\n"
            f"Pricing you may quote: {_PRICING_LINE[persona]}\n"
            "Rules: never state a visitor ticket price; every price is '+ GST' and 'indicative, "
            "confirmed at booking'; only mention peer companies from the provided list; "
            "no invented statistics or testimonials."
        )

    async def init(self, intake: IntakeResult, dossier: ResearchDossier) -> PersuasionInit:
        persona = map_persona(intake, dossier)
        cta = target_cta_for(persona)

        if dossier.ask_prospect:
            q = await self.llm.generate(
                system=(
                    "You are a TEG 2026 assistant. The prospect just submitted an inquiry but we "
                    "could not identify their company or role. Ask ONE friendly question to learn "
                    "what their company does and their role, so you can tailor the conversation."
                ),
                messages=[{"role": "user", "content": (
                    f"Name: {intake.person_name}\nCompany as entered: {intake.company_name_raw}"
                )}],
                max_tokens=120,
            )
            return PersuasionInit(persona=persona, target_cta=cta, opening_message=q.strip())

        peers = dossier.peer_companies[:3]
        user = (
            f"Person: {intake.person_name}\nCompany: {intake.company_name_canonical}\n"
            f"Sector: {dossier.sector}\nRelationship: {dossier.relationship}\n"
            f"Company facts: {dossier.company_profile}\n"
            f"Peer companies you may name (only these): {peers}\n"
            f"Their stated intent: {intake.intent_hint}\n"
            "Write the opening message."
        )
        system = self._system(persona, dossier)
        text = await self.llm.generate(system=system, messages=[{"role": "user", "content": user}], max_tokens=300)
        for _ in range(1):
            v = check_message(text, allowed_peers=peers, persona=persona)
            if not v:
                break
            text = await self.llm.generate(
                system=system + f"\nYour previous draft violated: {[x.code for x in v]}. Fix it.",
                messages=[{"role": "user", "content": user}], max_tokens=300,
            )
        if check_message(text, allowed_peers=peers, persona=persona):
            text = SAFE_TEMPLATES[persona]
            if peers:
                text += f" Companies like {' and '.join(peers[:2])} are already taking part."
        return PersuasionInit(persona=persona, target_cta=cta, opening_message=text.strip())
```

- [ ] **Step 4: Run tests**

Run: `cd teg-outreach-agent && python -m pytest tests/agents/test_persuasion_init.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add teg-outreach-agent/
git commit -m "feat(outreach): PersuasionAgent.init with persona mapping and guarded opening

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 13: `PersuasionAgent` — `respond` + persona re-map

**Files:**
- Modify: `teg-outreach-agent/app/agents/persuasion.py` (add `respond`, `_Analysis` schema, re-map logic)
- Test: `teg-outreach-agent/tests/agents/test_persuasion_respond.py`

**Interfaces:**
- Consumes: everything from Task 12 plus `app.domain.schemas.PersuasionTurn`, `CtaStatus`
- Produces (added to `app.agents.persuasion`):
  - `_Analysis(BaseModel)`: `reply: str`, `detected_cta: str | None`, `cta_status: CtaStatus`, `cta_type: str | None`, `cta_detail: dict`, `should_handoff: bool`, `learned_facts: dict`
  - `PersuasionAgent.respond(self, *, intake: IntakeResult, dossier: ResearchDossier, state: dict, history: list[dict], prospect_message: str) -> PersuasionTurn`
    - `state` carries: `persona`, `target_cta`, `cta_status`, `cta_detail`, `learned_facts`, `persona_remapped` (bool), `needs_review` (bool)
    - **Persona re-map:** if `state.get("persona_remapped") is not True` AND the original `dossier.ask_prospect` was non-empty AND this is the first prospect turn — infer sector/role from `prospect_message` via one `llm.generate_structured(_RemapHint)` (`{"sector": str|None, "role": str|None, "size": str|None}`), build a patched dossier, re-run `map_persona`, set `state["persona"]`, `state["persona_remapped"] = True`.
    - Generate the reply via one `llm.generate_structured(_Analysis)` — system prompt = persona system (Task 12 `_system`) + CTA guidance + "extract detected_cta / cta_status / learned_facts".
    - Post-check `_Analysis.reply` with `check_message`; regenerate once; then `SAFE_TEMPLATES[persona]`, set `state["needs_review"] = True`, `guardrail_flags` populated.
    - `should_handoff`: `_Analysis.should_handoff` OR (turn count ≥ 6 AND `cta_status` in `{"none","offered"}`).
    - Merge `learned_facts` into `state["learned_facts"]`.
  - `_RemapHint(BaseModel)`: `sector: str | None`, `role: str | None`, `size: str | None`

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/test_persuasion_respond.py
from app.agents.persuasion import PersuasionAgent, _Analysis, _RemapHint
from app.domain.schemas import IntakeResult, ResearchDossier
from app.llm.fake import FakeLLMClient


def _intake(intent="unknown", company="Acme Corp"):
    return IntakeResult(
        person_name="Rohan B", company_name_raw=company, company_name_canonical=company,
        provided_fields=[], intent_hint=intent, consent_status="unknown",
    )


def _state(persona="visitor", **kw):
    base = {
        "persona": persona, "target_cta": "register_visitor", "cta_status": "none",
        "cta_detail": {}, "learned_facts": {}, "persona_remapped": False, "needs_review": False,
    }
    base.update(kw)
    return base


async def test_respond_basic_turn_updates_cta():
    llm = FakeLLMClient(structured=[_Analysis(
        reply="Happy to help — shall I send the registration link?",
        detected_cta="register_visitor", cta_status="offered", cta_type=None,
        cta_detail={}, should_handoff=False, learned_facts={},
    )])
    d = ResearchDossier(sector="Software Development", relationship="cold", peer_companies=["NeuraMonks"])
    turn = await PersuasionAgent(llm).respond(
        intake=_intake(), dossier=d, state=_state("it_tech_service"),
        history=[{"role": "agent", "content": "hi"}], prospect_message="tell me more",
    )
    assert turn.cta_status == "offered"
    assert turn.persona == "it_tech_service"


async def test_respond_remaps_persona_on_first_reply_after_unresolved():
    llm = FakeLLMClient(
        structured=[
            _RemapHint(sector="Real Estate", role="Marketing Head", size="500"),
            _Analysis(
                reply="A category-exclusive sponsorship could work well. Shall I set up a call?",
                detected_cta="request_sponsor_call", cta_status="offered", cta_type=None,
                cta_detail={}, should_handoff=False, learned_facts={"sector": "Real Estate"},
            ),
        ],
    )
    d = ResearchDossier(sector=None, relationship="cold", ask_prospect=["company_description", "role"])
    turn = await PersuasionAgent(llm).respond(
        intake=_intake(intent="sponsor"), dossier=d, state=_state("visitor"),
        history=[{"role": "agent", "content": "what does your company do?"}],
        prospect_message="We're a real estate developer, I run marketing.",
    )
    assert turn.persona == "non_tech_sponsor"
    assert turn.updated_state["persona_remapped"] is True


async def test_respond_handoff_after_repeated_deflection():
    llm = FakeLLMClient(structured=[_Analysis(
        reply="No problem — I'll have the team follow up when you're ready.",
        detected_cta=None, cta_status="none", cta_type=None, cta_detail={},
        should_handoff=True, learned_facts={},
    )])
    d = ResearchDossier(sector="Software Development", relationship="cold")
    turn = await PersuasionAgent(llm).respond(
        intake=_intake(), dossier=d, state=_state("it_tech_service"),
        history=[{"role": "agent", "content": "x"}] * 7, prospect_message="just researching for now",
    )
    assert turn.should_handoff is True


async def test_respond_guardrail_fallback_sets_needs_review():
    bad = _Analysis(
        reply="Visitor tickets are ₹400, super cheap!", detected_cta=None,
        cta_status="none", cta_type=None, cta_detail={}, should_handoff=False, learned_facts={},
    )
    llm = FakeLLMClient(structured=[bad, bad])
    d = ResearchDossier(sector="Software Development", relationship="cold", peer_companies=["NeuraMonks"])
    turn = await PersuasionAgent(llm).respond(
        intake=_intake(intent="visitor"), dossier=d, state=_state("visitor"),
        history=[{"role": "agent", "content": "x"}], prospect_message="how much is a ticket?",
    )
    assert "₹400" not in turn.reply_text
    assert turn.updated_state["needs_review"] is True
    assert turn.guardrail_flags
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent && python -m pytest tests/agents/test_persuasion_respond.py -v`
Expected: FAIL — `_Analysis` / `_RemapHint` not defined

- [ ] **Step 3: Add to app/agents/persuasion.py**

```python
# --- append these imports at top ---
from app.domain.schemas import CtaStatus, PersuasionTurn
from pydantic import BaseModel

# --- append these classes at module level ---
class _Analysis(BaseModel):
    reply: str
    detected_cta: str | None = None
    cta_status: CtaStatus = "none"
    cta_type: str | None = None
    cta_detail: dict = {}
    should_handoff: bool = False
    learned_facts: dict = {}


class _RemapHint(BaseModel):
    sector: str | None = None
    role: str | None = None
    size: str | None = None


# --- add this method to PersuasionAgent ---
    async def respond(
        self, *, intake: IntakeResult, dossier: ResearchDossier, state: dict,
        history: list[dict], prospect_message: str,
    ) -> PersuasionTurn:
        persona: Persona = state.get("persona", "visitor")

        # one-time persona re-map for the unresolved-identity case
        first_prospect_turn = sum(1 for m in history if m.get("role") == "prospect") == 0
        if (
            dossier.ask_prospect
            and not state.get("persona_remapped")
            and first_prospect_turn
        ):
            hint = await self.llm.generate_structured(
                system=(
                    "From the prospect's message, infer their company's sector, the person's "
                    "role, and any headcount mentioned. Null if not stated."
                ),
                messages=[{"role": "user", "content": prospect_message}],
                schema=_RemapHint,
            )
            patched = dossier.model_copy(update={
                "sector": hint.sector or dossier.sector,
                "company_profile": {**dossier.company_profile, "company_size": hint.size or dossier.company_profile.get("company_size")},
                "ask_prospect": [],
            })
            intake_patched = intake.model_copy(update={
                "intent_hint": intake.intent_hint,
            })
            persona = map_persona(intake_patched, patched)
            state["persona"] = persona
            state["target_cta"] = target_cta_for(persona)
            state["persona_remapped"] = True
            dossier = patched

        peers = dossier.peer_companies[:3]
        system = self._system(persona, dossier) + (
            f"\nTarget CTA: {state.get('target_cta')}. Current cta_status: {state.get('cta_status')}. "
            "Advance it naturally; set cta_status to 'completed' only if the prospect clearly commits. "
            "Set should_handoff true if they say they're just researching or repeatedly deflect. "
            "Return learned_facts for anything new they told you."
        )
        convo = "\n".join(f"{m['role']}: {m['content']}" for m in history[-8:])
        user = (
            f"Person: {intake.person_name}\nCompany: {intake.company_name_canonical}\n"
            f"Peer companies you may name (only these): {peers}\n\n"
            f"Conversation so far:\n{convo}\n\nprospect: {prospect_message}\n\n"
            "Produce the next reply."
        )

        analysis = await self.llm.generate_structured(
            system=system, messages=[{"role": "user", "content": user}], schema=_Analysis,
        )
        flags: list[str] = []
        v = check_message(analysis.reply, allowed_peers=peers, persona=persona)
        if v:
            analysis = await self.llm.generate_structured(
                system=system + f"\nPrevious draft violated {[x.code for x in v]}. Fix it.",
                messages=[{"role": "user", "content": user}], schema=_Analysis,
            )
            v = check_message(analysis.reply, allowed_peers=peers, persona=persona)
        if v:
            analysis.reply = SAFE_TEMPLATES[persona]
            flags = [x.code for x in v]
            state["needs_review"] = True

        turn_count = sum(1 for m in history if m.get("role") == "agent")
        should_handoff = analysis.should_handoff or (
            turn_count >= 6 and analysis.cta_status in ("none", "offered")
        )

        merged_facts = {**state.get("learned_facts", {}), **analysis.learned_facts}
        state["learned_facts"] = merged_facts
        state["cta_status"] = analysis.cta_status
        if analysis.cta_detail:
            state["cta_detail"] = {**state.get("cta_detail", {}), **analysis.cta_detail}

        return PersuasionTurn(
            reply_text=analysis.reply.strip(),
            detected_cta=analysis.detected_cta,
            cta_status=analysis.cta_status,
            cta_type=analysis.cta_type,
            cta_detail=state["cta_detail"],
            should_handoff=should_handoff,
            updated_state=state,
            guardrail_flags=flags,
            persona=persona,
        )
```

- [ ] **Step 4: Run tests**

Run: `cd teg-outreach-agent && python -m pytest tests/agents/test_persuasion_respond.py tests/agents/test_persuasion_init.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add teg-outreach-agent/
git commit -m "feat(outreach): PersuasionAgent.respond with turn loop, CTA tracking, persona re-map

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 14: Postgres models + migration

**Files:**
- Create: `teg-outreach-agent/app/store/__init__.py` (empty)
- Create: `teg-outreach-agent/app/store/db.py`
- Create: `teg-outreach-agent/app/store/models.py`
- Create: `teg-outreach-agent/alembic.ini`
- Create: `teg-outreach-agent/app/store/migrations/env.py`
- Create: `teg-outreach-agent/app/store/migrations/script.py.mako`
- Create: `teg-outreach-agent/app/store/migrations/versions/0001_initial.py`
- Test: `teg-outreach-agent/tests/store/test_models.py`

**Interfaces:**
- Consumes: `config.settings.get_settings`
- Produces (`app.store.db`):
  - `Base` — SQLAlchemy `DeclarativeBase`
  - `engine` — created from `settings.database_url`
  - `SessionLocal` — `async_sessionmaker`
  - `async def get_session() -> AsyncIterator[AsyncSession]` — FastAPI dependency
- Produces (`app.store.models`): SQLAlchemy models `Inquiry`, `ResearchDossierRow`, `ChatSession`, `ChatMessage`, `HandoffPacketRow` — columns exactly per spec §6 (uuid PKs `default=uuid4`, `created_at` server_default now, jsonb via `sqlalchemy.dialects.postgresql.JSONB`).

**Implementer note:** tests need a Postgres. Use the local one: `createdb teg_outreach_test 2>/dev/null; export DATABASE_URL=postgresql+psycopg://$USER@localhost:5432/teg_outreach_test`. If `psycopg` async needs it, driver string is `postgresql+psycopg`. The test fixture creates all tables with `Base.metadata.create_all` against a fresh schema and drops them after.

- [ ] **Step 1: Write the failing test**

```python
# tests/store/test_models.py
import pytest
from sqlalchemy import select

from app.store.db import Base, SessionLocal, engine
from app.store.models import ChatMessage, ChatSession, Inquiry, ResearchDossierRow


@pytest.fixture(autouse=True)
async def _schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def test_insert_inquiry_and_related_rows():
    async with SessionLocal() as s:
        inq = Inquiry(
            person_name="Rohan B", company_name_raw="TRT",
            company_name_canonical="Third Rock Techkno",
            consent_status="unknown", intent_hint="exhibitor", source="inquiry_page",
        )
        s.add(inq)
        await s.flush()
        d = ResearchDossierRow(
            inquiry_id=inq.id, company_profile={"sector": "AI"}, person_profile={},
            relationship="returning", sector="AI", peer_companies=["NeuraMonks"],
            field_confidence={}, sources=[], review_flags=[], ask_prospect=[], research_cost={},
        )
        s.add(d)
        await s.flush()
        cs = ChatSession(
            inquiry_id=inq.id, dossier_id=d.id, persona="ai_startup",
            target_cta="catalyst_zone_or_pitch", cta_status="none",
        )
        s.add(cs)
        await s.flush()
        s.add(ChatMessage(session_id=cs.id, turn_index=0, role="agent", content="hi"))
        await s.commit()

        rows = (await s.execute(select(Inquiry))).scalars().all()
        assert len(rows) == 1
        assert rows[0].company_name_canonical == "Third Rock Techkno"
```

- [ ] **Step 2: Run to verify fail**

Run:
```bash
cd teg-outreach-agent && mkdir -p tests/store app/store/migrations/versions && touch tests/store/__init__.py app/store/__init__.py
createdb teg_outreach_test 2>/dev/null || true
DATABASE_URL="postgresql+psycopg://$USER@localhost:5432/teg_outreach_test" python -m pytest tests/store/ -v
```
Expected: FAIL — module not found

- [ ] **Step 3: Write app/store/db.py**

```python
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config.settings import get_settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(get_settings().database_url, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
```

- [ ] **Step 4: Write app/store/models.py**

```python
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.store.db import Base


def _uuid_col(**kw):
    return mapped_column(UUID(as_uuid=True), default=uuid.uuid4, **kw)


class Inquiry(Base):
    __tablename__ = "inquiries"
    id: Mapped[uuid.UUID] = _uuid_col(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    person_name: Mapped[str] = mapped_column(Text, nullable=False)
    company_name_raw: Mapped[str] = mapped_column(Text, nullable=False)
    company_name_canonical: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)
    designation: Mapped[str | None] = mapped_column(Text)
    participation_type: Mapped[str | None] = mapped_column(Text)
    tech_category: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    preferred_contact_time: Mapped[str | None] = mapped_column(Text)
    consent_status: Mapped[str] = mapped_column(String(16), nullable=False)
    intent_hint: Mapped[str] = mapped_column(String(24), nullable=False)
    source: Mapped[str | None] = mapped_column(Text)


class ResearchDossierRow(Base):
    __tablename__ = "research_dossiers"
    id: Mapped[uuid.UUID] = _uuid_col(primary_key=True)
    inquiry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inquiries.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    company_profile: Mapped[dict] = mapped_column(JSONB, default=dict)
    person_profile: Mapped[dict] = mapped_column(JSONB, default=dict)
    person_company_match: Mapped[bool | None] = mapped_column(Boolean)
    relationship: Mapped[str] = mapped_column(String(16), nullable=False)
    sector: Mapped[str | None] = mapped_column(Text)
    peer_companies: Mapped[list] = mapped_column(JSONB, default=list)
    field_confidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    sources: Mapped[list] = mapped_column(JSONB, default=list)
    review_flags: Mapped[list] = mapped_column(JSONB, default=list)
    ask_prospect: Mapped[list] = mapped_column(JSONB, default=list)
    research_cost: Mapped[dict] = mapped_column(JSONB, default=dict)


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[uuid.UUID] = _uuid_col(primary_key=True)
    inquiry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inquiries.id"), nullable=False)
    dossier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_dossiers.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    persona: Mapped[str | None] = mapped_column(String(24))
    target_cta: Mapped[str | None] = mapped_column(String(32))
    cta_status: Mapped[str] = mapped_column(String(16), nullable=False, default="none")
    cta_type: Mapped[str | None] = mapped_column(String(32))
    cta_detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    outcome_status: Mapped[str | None] = mapped_column(String(16))
    handoff_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    learned_facts: Mapped[dict] = mapped_column(JSONB, default=dict)
    persona_remapped: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[uuid.UUID] = _uuid_col(primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(12), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    guardrail_flags: Mapped[list] = mapped_column(JSONB, default=list)
    detected_intent: Mapped[dict] = mapped_column(JSONB, default=dict)


class HandoffPacketRow(Base):
    __tablename__ = "handoff_packets"
    id: Mapped[uuid.UUID] = _uuid_col(primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    summary: Mapped[str | None] = mapped_column(Text)
    recommended_next_step: Mapped[str | None] = mapped_column(Text)
    suggested_followup_message: Mapped[str | None] = mapped_column(Text)
    prospect_confidence: Mapped[str | None] = mapped_column(String(8))
    key_facts: Mapped[dict] = mapped_column(JSONB, default=dict)
    delivered_to: Mapped[str | None] = mapped_column(Text)
```

- [ ] **Step 5: Write alembic scaffold**

`alembic.ini` (minimal):
```ini
[alembic]
script_location = app/store/migrations
sqlalchemy.url = driver://user:pass@localhost/dbname

[loggers]
keys = root
[handlers]
keys = console
[formatters]
keys = generic
[logger_root]
level = WARN
handlers = console
[handler_console]
class = StreamHandler
args = (sys.stderr,)
formatter = generic
[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

`app/store/migrations/env.py`:
```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.store.db import Base
from app.store import models  # noqa: F401  (register models)
from config.settings import get_settings

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=get_settings().database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _do_run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(get_settings().database_url)
    async with engine.connect() as connection:
        await connection.run_sync(_do_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

`app/store/migrations/script.py.mako`:
```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 6: Generate the initial migration**

Run:
```bash
cd teg-outreach-agent
DATABASE_URL="postgresql+psycopg://$USER@localhost:5432/teg_outreach_test" alembic revision --autogenerate -m "initial"
```
Rename the generated file in `versions/` to `0001_initial.py` and set `revision = "0001"`, `down_revision = None`. Verify it creates all 5 tables.

- [ ] **Step 7: Run model test**

Run:
```bash
cd teg-outreach-agent && DATABASE_URL="postgresql+psycopg://$USER@localhost:5432/teg_outreach_test" python -m pytest tests/store/test_models.py -v
```
Expected: PASS (1 test)

- [ ] **Step 8: Add conftest with DATABASE_URL and a schema fixture**

Create `teg-outreach-agent/tests/conftest.py`:
```python
import asyncio
import os

os.environ.setdefault(
    "DATABASE_URL",
    f"postgresql+psycopg://{os.environ.get('USER', 'postgres')}@localhost:5432/teg_outreach_test",
)

import pytest

from app.store.db import Base, engine


@pytest.fixture
def db_schema():
    """Sync fixture: create all tables, drop after. Use in SYNC tests (WS / TestClient)."""
    async def _create():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    async def _drop():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    asyncio.get_event_loop().run_until_complete(_create()) if False else asyncio.run(_create())
    yield
    asyncio.run(_drop())
```

**Convention:** async tests use their own local `async def _schema()` autouse fixture (shown per task).
Sync tests (`TestClient` / `websocket_connect` in Tasks 19, 21) take the `db_schema` fixture argument
instead — replace the local async `_schema` fixture in those two tasks' test files with
`@pytest.mark.usefixtures("db_schema")` on the test class or `def test_...(db_schema, ...)`.

- [ ] **Step 9: Commit**

```bash
git add teg-outreach-agent/
git commit -m "feat(outreach): Postgres models and initial Alembic migration

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 15: Repositories

**Files:**
- Create: `teg-outreach-agent/app/store/repositories.py`
- Test: `teg-outreach-agent/tests/store/test_repositories.py`

**Interfaces:**
- Consumes: `app.store.models.*`, `app.domain.schemas.*`
- Produces (`app.store.repositories`), each constructed with an `AsyncSession`:
  - `InquiryRepo`:
    - `async def create(self, payload: IntakePayload, intake: IntakeResult) -> Inquiry`
    - `async def get(self, inquiry_id: uuid.UUID) -> Inquiry | None`
  - `DossierRepo`:
    - `async def create(self, inquiry_id: uuid.UUID, dossier: ResearchDossier) -> ResearchDossierRow`
    - `async def get(self, dossier_id: uuid.UUID) -> ResearchDossierRow | None`
    - `async def to_domain(row: ResearchDossierRow) -> ResearchDossier` (staticmethod)
  - `SessionRepo`:
    - `async def create(self, inquiry_id, dossier_id, init: PersuasionInit) -> ChatSession`
    - `async def get(self, session_id) -> ChatSession | None`
    - `async def update_state(self, session_id, *, cta_status, cta_type, cta_detail, learned_facts, persona, persona_remapped, needs_review) -> None`
    - `async def finalize(self, session_id, *, outcome_status: OutcomeStatus, handoff_generated: bool) -> None`
  - `MessageRepo`:
    - `async def append(self, session_id, role, content, *, turn_index: int, guardrail_flags=None, detected_intent=None) -> ChatMessage`
    - `async def history(self, session_id) -> list[dict]` — `[{"role","content"}]` ordered by `turn_index`
    - `async def next_turn_index(self, session_id) -> int`
  - `HandoffRepo`:
    - `async def create(self, session_id, packet: HandoffPacket) -> HandoffPacketRow`
    - `async def get_by_session(self, session_id) -> HandoffPacketRow | None`

- [ ] **Step 1: Write the failing test**

```python
# tests/store/test_repositories.py
import pytest

from app.domain.schemas import (
    HandoffPacket, IntakePayload, IntakeResult, PersuasionInit, ResearchDossier,
)
from app.store.db import Base, SessionLocal, engine
from app.store.repositories import (
    DossierRepo, HandoffRepo, InquiryRepo, MessageRepo, SessionRepo,
)


@pytest.fixture(autouse=True)
async def _schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def _intake():
    return IntakeResult(
        person_name="Rohan B", company_name_raw="TRT",
        company_name_canonical="Third Rock Techkno",
        provided_fields=["email"], intent_hint="exhibitor", consent_status="given",
    )


async def test_full_persistence_roundtrip():
    async with SessionLocal() as s:
        inq = await InquiryRepo(s).create(
            IntakePayload(person_name="Rohan B", company_name="TRT", email="r@x.com", consent=True),
            _intake(),
        )
        await s.flush()
        dossier = ResearchDossier(sector="AI", relationship="returning", peer_companies=["NeuraMonks"])
        drow = await DossierRepo(s).create(inq.id, dossier)
        await s.flush()
        cs = await SessionRepo(s).create(
            inq.id, drow.id,
            PersuasionInit(persona="it_tech_service", target_cta="book_stall", opening_message="hi"),
        )
        await s.flush()
        mr = MessageRepo(s)
        await mr.append(cs.id, "agent", "hi", turn_index=await mr.next_turn_index(cs.id))
        await mr.append(cs.id, "prospect", "tell me more", turn_index=await mr.next_turn_index(cs.id))
        await SessionRepo(s).update_state(
            cs.id, cta_status="offered", cta_type=None, cta_detail={}, learned_facts={"x": 1},
            persona="it_tech_service", persona_remapped=False, needs_review=False,
        )
        await HandoffRepo(s).create(cs.id, HandoffPacket(
            summary="s", recommended_next_step="n", suggested_followup_message="m",
            prospect_confidence="high", key_facts={},
        ))
        await SessionRepo(s).finalize(cs.id, outcome_status="contacted", handoff_generated=True)
        await s.commit()

        hist = await MessageRepo(s).history(cs.id)
        assert [m["role"] for m in hist] == ["agent", "prospect"]
        got = await SessionRepo(s).get(cs.id)
        assert got.cta_status == "offered"
        assert got.outcome_status == "contacted"
        assert got.learned_facts == {"x": 1}
        h = await HandoffRepo(s).get_by_session(cs.id)
        assert h.prospect_confidence == "high"
        dom = DossierRepo.to_domain(await DossierRepo(s).get(drow.id))
        assert dom.sector == "AI"
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent && python -m pytest tests/store/test_repositories.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write app/store/repositories.py**

```python
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.schemas import (
    HandoffPacket, IntakePayload, IntakeResult, OutcomeStatus, PersuasionInit,
    ResearchDossier, SourceRef,
)
from app.store.models import (
    ChatMessage, ChatSession, HandoffPacketRow, Inquiry, ResearchDossierRow,
)


class InquiryRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def create(self, payload: IntakePayload, intake: IntakeResult) -> Inquiry:
        row = Inquiry(
            person_name=intake.person_name,
            company_name_raw=intake.company_name_raw,
            company_name_canonical=intake.company_name_canonical,
            email=payload.email, phone=payload.phone, city=payload.city,
            designation=payload.designation, participation_type=payload.participation_type,
            tech_category=payload.tech_category, message=payload.message,
            preferred_contact_time=payload.preferred_contact_time,
            consent_status=intake.consent_status, intent_hint=intake.intent_hint,
            source=payload.source,
        )
        self.s.add(row)
        return row

    async def get(self, inquiry_id: uuid.UUID) -> Inquiry | None:
        return await self.s.get(Inquiry, inquiry_id)


class DossierRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def create(self, inquiry_id: uuid.UUID, dossier: ResearchDossier) -> ResearchDossierRow:
        row = ResearchDossierRow(
            inquiry_id=inquiry_id,
            company_profile=dossier.company_profile,
            person_profile=dossier.person_profile,
            person_company_match=dossier.person_company_match,
            relationship=dossier.relationship,
            sector=dossier.sector,
            peer_companies=dossier.peer_companies,
            field_confidence=dossier.field_confidence,
            sources=[s.model_dump() for s in dossier.sources],
            review_flags=dossier.review_flags,
            ask_prospect=dossier.ask_prospect,
            research_cost=dossier.research_cost,
        )
        self.s.add(row)
        return row

    async def get(self, dossier_id: uuid.UUID) -> ResearchDossierRow | None:
        return await self.s.get(ResearchDossierRow, dossier_id)

    @staticmethod
    def to_domain(row: ResearchDossierRow) -> ResearchDossier:
        return ResearchDossier(
            company_profile=row.company_profile or {},
            person_profile=row.person_profile or {},
            person_company_match=row.person_company_match,
            relationship=row.relationship,
            sector=row.sector,
            peer_companies=row.peer_companies or [],
            field_confidence=row.field_confidence or {},
            sources=[SourceRef(**s) for s in (row.sources or [])],
            review_flags=row.review_flags or [],
            ask_prospect=row.ask_prospect or [],
            research_cost=row.research_cost or {},
        )


class SessionRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def create(self, inquiry_id, dossier_id, init: PersuasionInit) -> ChatSession:
        row = ChatSession(
            inquiry_id=inquiry_id, dossier_id=dossier_id,
            persona=init.persona, target_cta=init.target_cta, cta_status="none",
        )
        self.s.add(row)
        return row

    async def get(self, session_id) -> ChatSession | None:
        return await self.s.get(ChatSession, session_id)

    async def update_state(
        self, session_id, *, cta_status, cta_type, cta_detail, learned_facts,
        persona, persona_remapped, needs_review,
    ) -> None:
        row = await self.s.get(ChatSession, session_id)
        row.cta_status = cta_status
        row.cta_type = cta_type
        row.cta_detail = cta_detail
        row.learned_facts = learned_facts
        row.persona = persona
        row.persona_remapped = persona_remapped
        row.needs_review = needs_review

    async def finalize(self, session_id, *, outcome_status: OutcomeStatus, handoff_generated: bool) -> None:
        from sqlalchemy import func as _f
        row = await self.s.get(ChatSession, session_id)
        row.outcome_status = outcome_status
        row.handoff_generated = handoff_generated
        row.ended_at = _f.now()


class MessageRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def next_turn_index(self, session_id) -> int:
        rows = (await self.s.execute(
            select(ChatMessage.turn_index).where(ChatMessage.session_id == session_id)
        )).scalars().all()
        return (max(rows) + 1) if rows else 0

    async def append(
        self, session_id, role, content, *, turn_index: int,
        guardrail_flags=None, detected_intent=None,
    ) -> ChatMessage:
        row = ChatMessage(
            session_id=session_id, turn_index=turn_index, role=role, content=content,
            guardrail_flags=guardrail_flags or [], detected_intent=detected_intent or {},
        )
        self.s.add(row)
        return row

    async def history(self, session_id) -> list[dict]:
        rows = (await self.s.execute(
            select(ChatMessage).where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.turn_index)
        )).scalars().all()
        return [{"role": r.role, "content": r.content} for r in rows]


class HandoffRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def create(self, session_id, packet: HandoffPacket) -> HandoffPacketRow:
        row = HandoffPacketRow(
            session_id=session_id, summary=packet.summary,
            recommended_next_step=packet.recommended_next_step,
            suggested_followup_message=packet.suggested_followup_message,
            prospect_confidence=packet.prospect_confidence, key_facts=packet.key_facts,
        )
        self.s.add(row)
        return row

    async def get_by_session(self, session_id) -> HandoffPacketRow | None:
        return (await self.s.execute(
            select(HandoffPacketRow).where(HandoffPacketRow.session_id == session_id)
        )).scalars().first()
```

- [ ] **Step 4: Run tests**

Run: `cd teg-outreach-agent && python -m pytest tests/store/ -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add teg-outreach-agent/
git commit -m "feat(outreach): repository layer for all aggregates

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 16: Orchestrator — `run_pipeline`

**Files:**
- Create: `teg-outreach-agent/app/orchestrator.py`
- Test: `teg-outreach-agent/tests/orchestrator/test_run_pipeline.py`

**Interfaces:**
- Consumes: `app.agents.*`, `app.store.repositories.*`, `app.store.db.SessionLocal`, `app.llm.base.get_llm`, `config.settings.get_settings`
- Produces (`app.orchestrator`):
  - `@dataclass PipelineResult: inquiry_id: uuid.UUID`, `session_id: uuid.UUID`, `opening_message: str`, `persona: str`
  - `class Orchestrator:`
    - `__init__(self, *, analysis: AnalysisAgent | None = None, research: ResearchAgent | None = None, persuasion: PersuasionAgent | None = None)` — defaults build each with `get_llm()`
    - `async def run_pipeline(self, payload: IntakePayload) -> PipelineResult`:
      1. `intake = await analysis.run(payload)`
      2. `dossier = await asyncio.wait_for(research.run(intake), timeout=settings.pipeline_hard_timeout_s)` — on `TimeoutError`, use an empty `ResearchDossier(ask_prospect=["company_description","role"])`
      3. `init = await persuasion.init(intake, dossier)`
      4. in one DB transaction: create inquiry, dossier, session; append the opening message as turn 0 (role `agent`)
      5. return `PipelineResult`

- [ ] **Step 1: Write the failing test**

```python
# tests/orchestrator/test_run_pipeline.py
import pytest

from app.agents.analysis import AnalysisAgent, _CanonResult
from app.agents.persuasion import PersuasionAgent
from app.agents.research import ResearchAgent, _Synthesis
from app.domain.schemas import IntakePayload
from app.llm.fake import FakeLLMClient
from app.orchestrator import Orchestrator
from app.research.kb_retriever import KBRetriever
from app.research.tools import ResearchResult, ResearchTool
from app.store.db import Base, SessionLocal, engine
from app.store.models import ChatMessage, ChatSession, Inquiry
from sqlalchemy import select


@pytest.fixture(autouse=True)
async def _schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


class _DeadWeb(ResearchTool):
    name = "web"
    async def lookup(self, query):
        return ResearchResult(available=False, tool_name="web")


async def test_run_pipeline_persists_and_returns_opening():
    analysis = AnalysisAgent(FakeLLMClient(structured=[
        _CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor"),
    ]))
    research = ResearchAgent(
        FakeLLMClient(structured=[_Synthesis(
            sector="AI Consulting", company_size="200", hq=None, founder=None,
            designation=None, seniority=None, is_technical=None, person_company_match=None,
        )]),
        tools=[KBRetriever(), _DeadWeb()],
    )
    persuasion = PersuasionAgent(FakeLLMClient(responses=[
        "Welcome back, Third Rock Techkno. Companies like NeuraMonks and ViitorCloud are "
        "exhibiting. A 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed at booking). "
        "Want the stall options?"
    ]))
    orch = Orchestrator(analysis=analysis, research=research, persuasion=persuasion)
    res = await orch.run_pipeline(IntakePayload(person_name="Rohan B", company_name="TRT"))

    assert res.opening_message
    async with SessionLocal() as s:
        assert (await s.execute(select(Inquiry))).scalars().first().company_name_canonical == "Third Rock Techkno"
        cs = (await s.execute(select(ChatSession))).scalars().first()
        assert cs.id == res.session_id
        msgs = (await s.execute(select(ChatMessage))).scalars().all()
        assert len(msgs) == 1 and msgs[0].role == "agent"


async def test_run_pipeline_research_timeout_uses_empty_dossier(monkeypatch):
    monkeypatch.setenv("PIPELINE_HARD_TIMEOUT_S", "0")
    from config.settings import get_settings
    get_settings.cache_clear()

    class _SlowResearch(ResearchAgent):
        async def run(self, intake):
            import asyncio
            await asyncio.sleep(1)
            raise AssertionError("should have timed out")

    analysis = AnalysisAgent(FakeLLMClient(structured=[_CanonResult(canonical="Acme", intent_hint="unknown")]))
    research = _SlowResearch(FakeLLMClient(), tools=[KBRetriever(), _DeadWeb()])
    persuasion = PersuasionAgent(FakeLLMClient(responses=["What does your company do, and what's your role?"]))
    orch = Orchestrator(analysis=analysis, research=research, persuasion=persuasion)
    res = await orch.run_pipeline(IntakePayload(person_name="X", company_name="Acme"))
    assert "?" in res.opening_message
    get_settings.cache_clear()
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent && mkdir -p tests/orchestrator && touch tests/orchestrator/__init__.py && python -m pytest tests/orchestrator/test_run_pipeline.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write app/orchestrator.py (run_pipeline only)**

```python
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

from app.agents.analysis import AnalysisAgent
from app.agents.persuasion import PersuasionAgent
from app.agents.research import ResearchAgent
from app.domain.schemas import IntakePayload, ResearchDossier
from app.llm.base import get_llm
from app.store.db import SessionLocal
from app.store.repositories import DossierRepo, InquiryRepo, MessageRepo, SessionRepo
from config.settings import get_settings


@dataclass
class PipelineResult:
    inquiry_id: uuid.UUID
    session_id: uuid.UUID
    opening_message: str
    persona: str


class Orchestrator:
    def __init__(
        self, *,
        analysis: AnalysisAgent | None = None,
        research: ResearchAgent | None = None,
        persuasion: PersuasionAgent | None = None,
    ) -> None:
        self.analysis = analysis or AnalysisAgent(get_llm())
        self.research = research or ResearchAgent(get_llm())
        self.persuasion = persuasion or PersuasionAgent(get_llm())

    async def run_pipeline(self, payload: IntakePayload) -> PipelineResult:
        settings = get_settings()
        intake = await self.analysis.run(payload)

        try:
            dossier = await asyncio.wait_for(
                self.research.run(intake), timeout=settings.pipeline_hard_timeout_s,
            )
        except (TimeoutError, asyncio.TimeoutError):
            dossier = ResearchDossier(ask_prospect=["company_description", "role"])

        init = await self.persuasion.init(intake, dossier)

        async with SessionLocal() as s:
            inq = await InquiryRepo(s).create(payload, intake)
            await s.flush()
            drow = await DossierRepo(s).create(inq.id, dossier)
            await s.flush()
            cs = await SessionRepo(s).create(inq.id, drow.id, init)
            await s.flush()
            mr = MessageRepo(s)
            await mr.append(cs.id, "agent", init.opening_message, turn_index=0)
            await s.commit()
            return PipelineResult(
                inquiry_id=inq.id, session_id=cs.id,
                opening_message=init.opening_message, persona=init.persona,
            )
```

- [ ] **Step 4: Run tests**

Run: `cd teg-outreach-agent && python -m pytest tests/orchestrator/test_run_pipeline.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add teg-outreach-agent/
git commit -m "feat(outreach): orchestrator run_pipeline sequencing the 3 agents

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 17: Orchestrator — `run_turn` + `end_session` + handoff packet

**Files:**
- Modify: `teg-outreach-agent/app/orchestrator.py`
- Test: `teg-outreach-agent/tests/orchestrator/test_run_turn.py`

**Interfaces:**
- Consumes: everything from Task 16 plus `app.domain.schemas.HandoffPacket`, `PersuasionTurn`
- Produces (added to `app.orchestrator.Orchestrator`):
  - `async def run_turn(self, session_id: uuid.UUID, prospect_message: str) -> PersuasionTurn`:
    - load session + inquiry + dossier; rebuild `state` dict from the session row
    - `history = await MessageRepo.history`
    - `turn = await persuasion.respond(intake=..., dossier=..., state=state, history=history, prospect_message=prospect_message)`
      (intake reconstructed from the inquiry row: person_name, company_name_raw/canonical, provided_fields not needed → pass `[]`, intent_hint from row, consent_status from row)
    - persist: append prospect message, append agent reply (with `guardrail_flags`), `SessionRepo.update_state`
    - return `turn`
  - `async def end_session(self, session_id: uuid.UUID, reason: str) -> HandoffPacket | None`:
    - load session; compute `outcome_status`:
      - `qualified` if `cta_status == "completed"` or (`cta_status in {"in_progress","offered"}` and `cta_detail` has a callback)
      - `lost` if `reason == "bounced"` or `cta_status == "declined"`
      - else `contacted`
    - if `cta_status != "completed"`: generate a handoff packet via one `persuasion.llm.generate_structured(HandoffPacket)` using a summary prompt built from the transcript + dossier + `learned_facts`; `prospect_confidence` from dossier identity confidence (`high` if company+person both in KB, `low` if `ask_prospect` was set, else `medium`); persist via `HandoffRepo`
    - `SessionRepo.finalize(outcome_status, handoff_generated=bool(packet))`
    - return the packet (or `None` if CTA completed cleanly)

- [ ] **Step 1: Write the failing test**

```python
# tests/orchestrator/test_run_turn.py
import pytest

from app.agents.analysis import AnalysisAgent, _CanonResult
from app.agents.persuasion import PersuasionAgent, _Analysis
from app.agents.research import ResearchAgent, _Synthesis
from app.domain.schemas import HandoffPacket, IntakePayload
from app.llm.fake import FakeLLMClient
from app.orchestrator import Orchestrator
from app.research.kb_retriever import KBRetriever
from app.research.tools import ResearchResult, ResearchTool
from app.store.db import Base, SessionLocal, engine
from app.store.models import ChatMessage, ChatSession, HandoffPacketRow
from sqlalchemy import select


@pytest.fixture(autouse=True)
async def _schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


class _DeadWeb(ResearchTool):
    name = "web"
    async def lookup(self, q):
        return ResearchResult(available=False, tool_name="web")


async def _seed_session(persuasion_llm) -> tuple[Orchestrator, "uuid.UUID"]:
    analysis = AnalysisAgent(FakeLLMClient(structured=[_CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor")]))
    research = ResearchAgent(FakeLLMClient(structured=[_Synthesis(
        sector="AI Consulting", company_size="200", hq=None, founder=None,
        designation=None, seniority=None, is_technical=None, person_company_match=None,
    )]), tools=[KBRetriever(), _DeadWeb()])
    persuasion = PersuasionAgent(persuasion_llm)
    orch = Orchestrator(analysis=analysis, research=research, persuasion=persuasion)
    res = await orch.run_pipeline(IntakePayload(person_name="Rohan B", company_name="TRT"))
    return orch, res.session_id


async def test_run_turn_persists_pair_and_state():
    persuasion_llm = FakeLLMClient(
        responses=["opening line ok"],
        structured=[_Analysis(
            reply="Shall I send the stall booking link?", detected_cta="book_stall",
            cta_status="offered", cta_type=None, cta_detail={}, should_handoff=False,
            learned_facts={"budget_mentioned": False},
        )],
    )
    orch, sid = await _seed_session(persuasion_llm)
    turn = await orch.run_turn(sid, "tell me about stalls")
    assert turn.cta_status == "offered"
    async with SessionLocal() as s:
        msgs = (await s.execute(select(ChatMessage).order_by(ChatMessage.turn_index))).scalars().all()
        assert [m.role for m in msgs] == ["agent", "prospect", "agent"]
        cs = (await s.execute(select(ChatSession))).scalars().first()
        assert cs.cta_status == "offered"
        assert cs.learned_facts == {"budget_mentioned": False}


async def test_end_session_generates_handoff_when_cta_incomplete():
    persuasion_llm = FakeLLMClient(
        responses=["opening line ok"],
        structured=[
            _Analysis(reply="No worries, I'll pass you to the team.", detected_cta=None,
                      cta_status="none", cta_type=None, cta_detail={}, should_handoff=True,
                      learned_facts={}),
            HandoffPacket(summary="Rohan from TRT, exploring exhibiting, not ready to commit.",
                          recommended_next_step="Sales rep to email stall deck.",
                          suggested_followup_message="Hi Rohan, following up on TEG 2026...",
                          prospect_confidence="high", key_facts={"company": "Third Rock Techkno"}),
        ],
    )
    orch, sid = await _seed_session(persuasion_llm)
    await orch.run_turn(sid, "just researching for now")
    packet = await orch.end_session(sid, reason="left")
    assert packet is not None
    async with SessionLocal() as s:
        cs = (await s.execute(select(ChatSession))).scalars().first()
        assert cs.outcome_status in {"contacted", "lost"}
        assert cs.handoff_generated is True
        h = (await s.execute(select(HandoffPacketRow))).scalars().first()
        assert "TRT" in h.summary
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent && python -m pytest tests/orchestrator/test_run_turn.py -v`
Expected: FAIL — `run_turn` / `end_session` not defined

- [ ] **Step 3: Add to app/orchestrator.py**

```python
# --- add imports ---
from app.domain.schemas import HandoffPacket, IntakeResult, PersuasionTurn
from app.store.repositories import DossierRepo, HandoffRepo

# --- add methods to Orchestrator ---
    def _state_from_row(self, cs) -> dict:
        return {
            "persona": cs.persona,
            "target_cta": cs.target_cta,
            "cta_status": cs.cta_status,
            "cta_detail": cs.cta_detail or {},
            "learned_facts": cs.learned_facts or {},
            "persona_remapped": cs.persona_remapped,
            "needs_review": cs.needs_review,
        }

    async def run_turn(self, session_id: uuid.UUID, prospect_message: str) -> PersuasionTurn:
        async with SessionLocal() as s:
            cs = await SessionRepo(s).get(session_id)
            inq = await InquiryRepo(s).get(cs.inquiry_id)
            drow = await DossierRepo(s).get(cs.dossier_id)
            dossier = DossierRepo.to_domain(drow)
            intake = IntakeResult(
                person_name=inq.person_name,
                company_name_raw=inq.company_name_raw,
                company_name_canonical=inq.company_name_canonical or inq.company_name_raw,
                provided_fields=[],
                intent_hint=inq.intent_hint,
                consent_status=inq.consent_status,
            )
            history = await MessageRepo(s).history(session_id)
            state = self._state_from_row(cs)

            turn = await self.persuasion.respond(
                intake=intake, dossier=dossier, state=state,
                history=history, prospect_message=prospect_message,
            )

            mr = MessageRepo(s)
            await mr.append(session_id, "prospect", prospect_message,
                            turn_index=await mr.next_turn_index(session_id))
            await mr.append(session_id, "agent", turn.reply_text,
                            turn_index=await mr.next_turn_index(session_id),
                            guardrail_flags=turn.guardrail_flags,
                            detected_intent={"detected_cta": turn.detected_cta})
            await SessionRepo(s).update_state(
                session_id,
                cta_status=turn.cta_status, cta_type=turn.cta_type,
                cta_detail=turn.cta_detail,
                learned_facts=turn.updated_state.get("learned_facts", {}),
                persona=turn.persona,
                persona_remapped=turn.updated_state.get("persona_remapped", False),
                needs_review=turn.updated_state.get("needs_review", False),
            )
            await s.commit()
            return turn

    async def end_session(self, session_id: uuid.UUID, reason: str) -> HandoffPacket | None:
        async with SessionLocal() as s:
            cs = await SessionRepo(s).get(session_id)
            drow = await DossierRepo(s).get(cs.dossier_id)
            dossier = DossierRepo.to_domain(drow)
            history = await MessageRepo(s).history(session_id)

            if cs.cta_status == "completed":
                outcome = "qualified"
            elif cs.cta_status in ("in_progress", "offered") and (cs.cta_detail or {}).get("callback"):
                outcome = "qualified"
            elif reason == "bounced" or cs.cta_status == "declined":
                outcome = "lost"
            else:
                outcome = "contacted"

            packet: HandoffPacket | None = None
            if cs.cta_status != "completed":
                if dossier.ask_prospect:
                    confidence = "low"
                elif dossier.sector and dossier.person_profile.get("teg_role"):
                    confidence = "high"
                else:
                    confidence = "medium"
                convo = "\n".join(f"{m['role']}: {m['content']}" for m in history)
                packet = await self.persuasion.llm.generate_structured(
                    system=(
                        "Write a concise sales handoff for the TEG team. Summarise who this is, "
                        "what they want, where the conversation landed, and the best next step. "
                        "suggested_followup_message: a short draft the rep can send."
                    ),
                    messages=[{"role": "user", "content": (
                        f"Dossier: company={dossier.company_profile} person={dossier.person_profile} "
                        f"sector={dossier.sector} relationship={dossier.relationship}\n"
                        f"Learned in chat: {cs.learned_facts}\n\nTranscript:\n{convo}"
                    )}],
                    schema=HandoffPacket,
                )
                packet = packet.model_copy(update={"prospect_confidence": confidence})
                await HandoffRepo(s).create(session_id, packet)

            await SessionRepo(s).finalize(
                session_id, outcome_status=outcome, handoff_generated=packet is not None,
            )
            await s.commit()
            return packet
```

- [ ] **Step 4: Run tests**

Run: `cd teg-outreach-agent && python -m pytest tests/orchestrator/ -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add teg-outreach-agent/
git commit -m "feat(outreach): orchestrator run_turn, end_session, handoff packet generation

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 18: API — `POST /inquiries` + internal read endpoints

**Files:**
- Create: `teg-outreach-agent/app/api/__init__.py` (empty)
- Create: `teg-outreach-agent/app/api/inquiries.py`
- Create: `teg-outreach-agent/app/api/internal.py`
- Create: `teg-outreach-agent/app/main.py`
- Test: `teg-outreach-agent/tests/api/test_inquiries.py`

**Interfaces:**
- Consumes: `app.orchestrator.Orchestrator`, `app.store.db`, `app.store.repositories.*`, `app.domain.schemas.IntakePayload`
- Produces:
  - `app.api.inquiries.router` (`APIRouter`):
    - `POST /inquiries` body `IntakePayload` → `202` `{"session_id": str, "opening_message": str, "persona": str}`. Uses a module-level `Orchestrator()` unless overridden via `app.dependency_overrides`.
    - `GET /inquiries/{inquiry_id}` → the inquiry row as JSON (internal)
  - `app.api.internal.router`:
    - `GET /sessions/{session_id}` → `{"session": {...}, "dossier": {...}, "transcript": [...], "handoff": {...} | null}`
  - `app.main.create_app() -> FastAPI` — wires both routers + the chat router (Task 19) + a `/healthz`
  - `app.main.app` — `create_app()` instance
  - `app.api.inquiries.get_orchestrator() -> Orchestrator` — dependency, overridable in tests

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_inquiries.py
import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.analysis import AnalysisAgent, _CanonResult
from app.agents.persuasion import PersuasionAgent
from app.agents.research import ResearchAgent, _Synthesis
from app.api.inquiries import get_orchestrator
from app.llm.fake import FakeLLMClient
from app.main import create_app
from app.orchestrator import Orchestrator
from app.research.kb_retriever import KBRetriever
from app.research.tools import ResearchResult, ResearchTool
from app.store.db import Base, engine


@pytest.fixture(autouse=True)
async def _schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


class _DeadWeb(ResearchTool):
    name = "web"
    async def lookup(self, q):
        return ResearchResult(available=False, tool_name="web")


def _fake_orchestrator() -> Orchestrator:
    # Tapan Patel (TEG organizer + Third Rock Techkno co-founder) and Third Rock
    # Techkno both resolve in the KB, so the person track resolves and the dossier
    # does NOT set ask_prospect -> persona is a real tech persona, not the fallback.
    # NOTE: get_orchestrator() lazily constructs Orchestrator() so importing the API
    # module does not require an LLM API key.
    return Orchestrator(
        analysis=AnalysisAgent(FakeLLMClient(structured=[_CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor")])),
        research=ResearchAgent(
            FakeLLMClient(structured=[_Synthesis(
                sector="AI Consulting", company_size="200", hq=None, founder=None,
                designation=None, seniority=None, is_technical=None, person_company_match=None,
            )]),
            tools=[KBRetriever(), _DeadWeb()],
        ),
        persuasion=PersuasionAgent(FakeLLMClient(responses=[
            "Welcome back. A 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed at booking). Want details?"
        ])),
    )


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_orchestrator] = _fake_orchestrator
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def test_post_inquiry_returns_session_and_opening(client):
    async with client as c:
        r = await c.post("/inquiries", json={"person_name": "Tapan Patel", "company_name": "Third Rock Techkno"})
    assert r.status_code == 202
    body = r.json()
    assert body["session_id"]
    assert "1,17,000" in body["opening_message"]
    assert body["persona"] in {"it_tech_service", "ai_startup"}


async def test_post_inquiry_requires_company(client):
    async with client as c:
        r = await c.post("/inquiries", json={"person_name": "Rohan B"})
    assert r.status_code == 422


async def test_get_session_returns_transcript(client):
    async with client as c:
        posted = (await c.post("/inquiries", json={"person_name": "Tapan Patel", "company_name": "Third Rock Techkno"})).json()
        r = await c.get(f"/sessions/{posted['session_id']}")
    assert r.status_code == 200
    data = r.json()
    assert data["transcript"][0]["role"] == "agent"
    assert data["dossier"]["sector"]
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent && mkdir -p tests/api && touch tests/api/__init__.py app/api/__init__.py && python -m pytest tests/api/test_inquiries.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write app/api/inquiries.py**

```python
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.domain.schemas import IntakePayload
from app.orchestrator import Orchestrator
from app.store.db import SessionLocal
from app.store.repositories import InquiryRepo

router = APIRouter()
_orchestrator = Orchestrator()


def get_orchestrator() -> Orchestrator:
    return _orchestrator


@router.post("/inquiries", status_code=status.HTTP_202_ACCEPTED)
async def create_inquiry(
    payload: IntakePayload, orch: Orchestrator = Depends(get_orchestrator)
) -> dict:
    result = await orch.run_pipeline(payload)
    return {
        "session_id": str(result.session_id),
        "opening_message": result.opening_message,
        "persona": result.persona,
    }


@router.get("/inquiries/{inquiry_id}")
async def get_inquiry(inquiry_id: uuid.UUID) -> dict:
    async with SessionLocal() as s:
        row = await InquiryRepo(s).get(inquiry_id)
        if row is None:
            raise HTTPException(404)
        return {
            "id": str(row.id), "person_name": row.person_name,
            "company_name_canonical": row.company_name_canonical,
            "intent_hint": row.intent_hint, "consent_status": row.consent_status,
        }
```

- [ ] **Step 4: Write app/api/internal.py**

```python
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.store.db import SessionLocal
from app.store.repositories import DossierRepo, HandoffRepo, MessageRepo, SessionRepo

router = APIRouter()


@router.get("/sessions/{session_id}")
async def get_session(session_id: uuid.UUID) -> dict:
    async with SessionLocal() as s:
        cs = await SessionRepo(s).get(session_id)
        if cs is None:
            raise HTTPException(404)
        drow = await DossierRepo(s).get(cs.dossier_id)
        transcript = await MessageRepo(s).history(session_id)
        h = await HandoffRepo(s).get_by_session(session_id)
        return {
            "session": {
                "id": str(cs.id), "persona": cs.persona, "target_cta": cs.target_cta,
                "cta_status": cs.cta_status, "outcome_status": cs.outcome_status,
                "needs_review": cs.needs_review, "learned_facts": cs.learned_facts,
            },
            "dossier": {
                "company_profile": drow.company_profile, "person_profile": drow.person_profile,
                "relationship": drow.relationship, "sector": drow.sector,
                "peer_companies": drow.peer_companies, "review_flags": drow.review_flags,
                "ask_prospect": drow.ask_prospect,
            },
            "transcript": transcript,
            "handoff": None if h is None else {
                "summary": h.summary, "recommended_next_step": h.recommended_next_step,
                "suggested_followup_message": h.suggested_followup_message,
                "prospect_confidence": h.prospect_confidence, "key_facts": h.key_facts,
            },
        }
```

- [ ] **Step 5: Write app/main.py**

```python
from __future__ import annotations

from fastapi import FastAPI

from app.api import inquiries, internal


def create_app() -> FastAPI:
    app = FastAPI(title="TEG Outreach Agent")
    app.include_router(inquiries.router)
    app.include_router(internal.router)

    from app.api import chat  # imported here to avoid circulars
    app.include_router(chat.router)

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"ok": True}

    return app


app = create_app()
```

**Note:** `app/api/chat.py` doesn't exist until Task 19. For this task, create a stub `app/api/chat.py` containing just `from fastapi import APIRouter; router = APIRouter()` and replace it in Task 19.

- [ ] **Step 6: Run tests**

Run: `cd teg-outreach-agent && python -m pytest tests/api/test_inquiries.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add teg-outreach-agent/
git commit -m "feat(outreach): POST /inquiries endpoint and internal session read API

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 19: API — `WS /chat/{session_id}`

**Files:**
- Modify (replace stub): `teg-outreach-agent/app/api/chat.py`
- Test: `teg-outreach-agent/tests/api/test_chat.py`

**Interfaces:**
- Consumes: `app.orchestrator.Orchestrator`, `app.api.inquiries.get_orchestrator`, `app.store.db`, `app.store.repositories.MessageRepo`/`SessionRepo`
- Produces:
  - `app.api.chat.router` with `WEBSOCKET /chat/{session_id}`:
    - On connect: accept, load session; if missing → close code `4404`. Send `{"type":"opening","text": <turn 0 agent message>}`.
    - Loop: receive `{"type":"message","text":...}` → `orch.run_turn(session_id, text)` → send `{"type":"reply","text": turn.reply_text, "cta_status": turn.cta_status, "should_handoff": turn.should_handoff}`. If `turn.should_handoff` → send `{"type":"handoff"}` and continue (client may still chat).
    - On `{"type":"end"}` or disconnect → `orch.end_session(session_id, reason)` (`reason="left"` on explicit end, `"bounced"` if disconnect with < 1 prospect message, else `"left"`), then close.
  - Chat uses `get_orchestrator()` so tests can override.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_chat.py
import pytest
from fastapi.testclient import TestClient

from app.agents.analysis import AnalysisAgent, _CanonResult
from app.agents.persuasion import PersuasionAgent, _Analysis
from app.agents.research import ResearchAgent, _Synthesis
from app.api.inquiries import get_orchestrator
from app.llm.fake import FakeLLMClient
from app.main import create_app
from app.orchestrator import Orchestrator
from app.research.kb_retriever import KBRetriever
from app.research.tools import ResearchResult, ResearchTool
from app.store.db import Base, engine


pytestmark = pytest.mark.usefixtures("db_schema")


class _DeadWeb(ResearchTool):
    name = "web"
    async def lookup(self, q):
        return ResearchResult(available=False, tool_name="web")


def _orch():
    return Orchestrator(
        analysis=AnalysisAgent(FakeLLMClient(structured=[_CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor")])),
        research=ResearchAgent(FakeLLMClient(structured=[_Synthesis(
            sector="AI Consulting", company_size="200", hq=None, founder=None,
            designation=None, seniority=None, is_technical=None, person_company_match=None,
        )]), tools=[KBRetriever(), _DeadWeb()]),
        persuasion=PersuasionAgent(FakeLLMClient(
            responses=["opening: a 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed at booking)."],
            structured=[_Analysis(
                reply="Shall I send the booking link?", detected_cta="book_stall",
                cta_status="offered", cta_type=None, cta_detail={}, should_handoff=False,
                learned_facts={},
            )],
        )),
    )


def test_ws_chat_roundtrip():
    app = create_app()
    shared = _orch()
    app.dependency_overrides[get_orchestrator] = lambda: shared
    client = TestClient(app)

    posted = client.post("/inquiries", json={"person_name": "Rohan B", "company_name": "TRT"}).json()
    sid = posted["session_id"]

    with client.websocket_connect(f"/chat/{sid}") as ws:
        opening = ws.receive_json()
        assert opening["type"] == "opening"
        assert "1,17,000" in opening["text"]
        ws.send_json({"type": "message", "text": "tell me about stalls"})
        reply = ws.receive_json()
        assert reply["type"] == "reply"
        assert reply["cta_status"] == "offered"
        ws.send_json({"type": "end"})


def test_ws_unknown_session_closes():
    app = create_app()
    app.dependency_overrides[get_orchestrator] = lambda: _orch()
    client = TestClient(app)
    with pytest.raises(Exception):
        with client.websocket_connect("/chat/00000000-0000-0000-0000-000000000000") as ws:
            ws.receive_json()
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent && python -m pytest tests/api/test_chat.py -v`
Expected: FAIL — router has no websocket route

- [ ] **Step 3: Write app/api/chat.py**

```python
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.api.inquiries import get_orchestrator
from app.orchestrator import Orchestrator
from app.store.db import SessionLocal
from app.store.repositories import MessageRepo, SessionRepo

router = APIRouter()


@router.websocket("/chat/{session_id}")
async def chat(
    websocket: WebSocket,
    session_id: uuid.UUID,
    orch: Orchestrator = Depends(get_orchestrator),
) -> None:
    await websocket.accept()

    async with SessionLocal() as s:
        cs = await SessionRepo(s).get(session_id)
        if cs is None:
            await websocket.close(code=4404)
            return
        history = await MessageRepo(s).history(session_id)

    opening = next((m["content"] for m in history if m["role"] == "agent"), "")
    await websocket.send_json({"type": "opening", "text": opening})

    prospect_turns = 0
    try:
        while True:
            msg = await websocket.receive_json()
            if msg.get("type") == "end":
                await orch.end_session(session_id, reason="left")
                await websocket.close()
                return
            if msg.get("type") != "message":
                continue
            prospect_turns += 1
            turn = await orch.run_turn(session_id, msg.get("text", ""))
            await websocket.send_json({
                "type": "reply",
                "text": turn.reply_text,
                "cta_status": turn.cta_status,
                "should_handoff": turn.should_handoff,
            })
            if turn.should_handoff:
                await websocket.send_json({"type": "handoff"})
    except WebSocketDisconnect:
        reason = "bounced" if prospect_turns == 0 else "left"
        await orch.end_session(session_id, reason=reason)
```

- [ ] **Step 4: Run tests**

Run: `cd teg-outreach-agent && python -m pytest tests/api/ -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add teg-outreach-agent/
git commit -m "feat(outreach): WebSocket chat endpoint driving the turn loop

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 20: Retention job

**Files:**
- Create: `teg-outreach-agent/app/jobs/__init__.py` (empty)
- Create: `teg-outreach-agent/app/jobs/retention.py`
- Test: `teg-outreach-agent/tests/jobs/test_retention.py`

**Interfaces:**
- Consumes: `app.store.db.SessionLocal`, `app.store.models.*`, `config.settings.get_settings`
- Produces (`app.jobs.retention`):
  - `async def purge_expired(now: datetime | None = None) -> dict[str, int]` — deletes `chat_messages` and `research_dossiers` (and their `handoff_packets`, `chat_sessions`) whose parent `inquiries.created_at` is older than `settings.data_retention_days`. Keeps the `inquiries` row itself (name/company/consent kept as a minimal record; message content and research purged). Returns counts deleted per table.
  - `if __name__ == "__main__": asyncio.run(purge_expired())` — runnable as `python -m app.jobs.retention` from cron.

- [ ] **Step 1: Write the failing test**

```python
# tests/jobs/test_retention.py
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text

from app.jobs.retention import purge_expired
from app.store.db import Base, SessionLocal, engine
from app.store.models import ChatMessage, ChatSession, Inquiry, ResearchDossierRow


@pytest.fixture(autouse=True)
async def _schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _make_inquiry(s, *, old: bool) -> Inquiry:
    inq = Inquiry(
        person_name="X", company_name_raw="Y", company_name_canonical="Y",
        consent_status="unknown", intent_hint="unknown", source="t",
    )
    s.add(inq)
    await s.flush()
    d = ResearchDossierRow(inquiry_id=inq.id, company_profile={}, person_profile={},
                           relationship="cold", peer_companies=[], field_confidence={},
                           sources=[], review_flags=[], ask_prospect=[], research_cost={})
    s.add(d)
    await s.flush()
    cs = ChatSession(inquiry_id=inq.id, dossier_id=d.id, cta_status="none")
    s.add(cs)
    await s.flush()
    s.add(ChatMessage(session_id=cs.id, turn_index=0, role="agent", content="hi"))
    await s.flush()
    if old:
        await s.execute(
            text("UPDATE inquiries SET created_at = :ts WHERE id = :id"),
            {"ts": datetime.now(timezone.utc) - timedelta(days=400), "id": inq.id},
        )
    return inq


async def test_purge_removes_old_messages_keeps_inquiry_row():
    async with SessionLocal() as s:
        old = await _make_inquiry(s, old=True)
        fresh = await _make_inquiry(s, old=False)
        await s.commit()

    counts = await purge_expired()
    assert counts["chat_messages"] >= 1

    async with SessionLocal() as s:
        inquiries = (await s.execute(select(Inquiry))).scalars().all()
        assert {i.id for i in inquiries} == {old.id, fresh.id}  # both inquiry rows kept
        msgs = (await s.execute(select(ChatMessage))).scalars().all()
        remaining_sessions = {m.session_id for m in msgs}
        # only the fresh inquiry's messages remain
        fresh_sessions = (await s.execute(
            select(ChatSession.id).where(ChatSession.inquiry_id == fresh.id)
        )).scalars().all()
        assert remaining_sessions <= set(fresh_sessions)
        dossiers = (await s.execute(select(ResearchDossierRow))).scalars().all()
        assert all(d.inquiry_id == fresh.id for d in dossiers)
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent && mkdir -p tests/jobs && touch tests/jobs/__init__.py app/jobs/__init__.py && python -m pytest tests/jobs/test_retention.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write app/jobs/retention.py**

```python
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.store.db import SessionLocal
from app.store.models import (
    ChatMessage, ChatSession, HandoffPacketRow, Inquiry, ResearchDossierRow,
)
from config.settings import get_settings


async def purge_expired(now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=get_settings().data_retention_days)
    counts = {
        "chat_messages": 0, "handoff_packets": 0,
        "chat_sessions": 0, "research_dossiers": 0,
    }
    async with SessionLocal() as s:
        old_inq_ids = (await s.execute(
            select(Inquiry.id).where(Inquiry.created_at < cutoff)
        )).scalars().all()
        if not old_inq_ids:
            return counts

        session_ids = (await s.execute(
            select(ChatSession.id).where(ChatSession.inquiry_id.in_(old_inq_ids))
        )).scalars().all()

        if session_ids:
            counts["chat_messages"] = (await s.execute(
                delete(ChatMessage).where(ChatMessage.session_id.in_(session_ids))
            )).rowcount or 0
            counts["handoff_packets"] = (await s.execute(
                delete(HandoffPacketRow).where(HandoffPacketRow.session_id.in_(session_ids))
            )).rowcount or 0
            counts["chat_sessions"] = (await s.execute(
                delete(ChatSession).where(ChatSession.id.in_(session_ids))
            )).rowcount or 0

        counts["research_dossiers"] = (await s.execute(
            delete(ResearchDossierRow).where(ResearchDossierRow.inquiry_id.in_(old_inq_ids))
        )).rowcount or 0

        await s.commit()
    return counts


if __name__ == "__main__":
    print(asyncio.run(purge_expired()))
```

- [ ] **Step 4: Run tests**

Run: `cd teg-outreach-agent && python -m pytest tests/jobs/ -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add teg-outreach-agent/
git commit -m "feat(outreach): data-retention purge job

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 21: E2E test (happy path + handoff path)

**Files:**
- Create: `teg-outreach-agent/tests/e2e/__init__.py` (empty)
- Create: `teg-outreach-agent/tests/e2e/test_full_flow.py`
- Create: `teg-outreach-agent/README.md`

**Interfaces:**
- Consumes: the whole app via `create_app()` + `TestClient`; `FakeLLMClient` scripted for a multi-turn conversation.
- Produces: no new production code. This task proves spec §11 success criteria 1, 2, 3, 5.

- [ ] **Step 1: Write the E2E test**

```python
# tests/e2e/test_full_flow.py
import pytest
from fastapi.testclient import TestClient

from app.agents.analysis import AnalysisAgent, _CanonResult
from app.agents.persuasion import PersuasionAgent, _Analysis
from app.agents.research import ResearchAgent, _Synthesis
from app.api.inquiries import get_orchestrator
from app.domain.schemas import HandoffPacket
from app.llm.fake import FakeLLMClient
from app.main import create_app
from app.orchestrator import Orchestrator
from app.research.kb_retriever import KBRetriever
from app.research.tools import ResearchResult, ResearchTool
from app.store.db import Base, SessionLocal, engine
from app.store.models import ChatSession, HandoffPacketRow
from sqlalchemy import select


pytestmark = pytest.mark.usefixtures("db_schema")


class _DeadWeb(ResearchTool):
    name = "web"
    async def lookup(self, q):
        return ResearchResult(available=False, tool_name="web")


def test_happy_path_kb_company_completes_cta():
    """Criteria 1, 2, 5: name+company -> persona-correct opening w/ real peers -> CTA completed -> record."""
    orch = Orchestrator(
        analysis=AnalysisAgent(FakeLLMClient(structured=[_CanonResult(canonical="Third Rock Techkno", intent_hint="exhibitor")])),
        research=ResearchAgent(FakeLLMClient(structured=[_Synthesis(
            sector="AI Consulting", company_size="200", hq="Ahmedabad", founder=None,
            designation=None, seniority=None, is_technical=None, person_company_match=None,
        )]), tools=[KBRetriever(), _DeadWeb()]),
        persuasion=PersuasionAgent(FakeLLMClient(
            responses=[
                "Welcome back, Third Rock Techkno. Companies like NeuraMonks and ViitorCloud "
                "are exhibiting. A 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed at "
                "booking). Want the stall options?"
            ],
            structured=[
                _Analysis(reply="A 3m x 6m at ₹2,34,000 + GST (indicative) would fit a team of 4. "
                                "Shall I lock a 3m x 6m stall for you?",
                          detected_cta="book_stall", cta_status="in_progress", cta_type="stall",
                          cta_detail={"stall_size": "3x6"}, should_handoff=False, learned_facts={}),
                _Analysis(reply="Done — I've noted a 3m x 6m stall booking. The team will confirm the invoice.",
                          detected_cta="book_stall", cta_status="completed", cta_type="stall",
                          cta_detail={"stall_size": "3x6"}, should_handoff=False, learned_facts={}),
            ],
        )),
    )
    app = create_app()
    app.dependency_overrides[get_orchestrator] = lambda: orch
    client = TestClient(app)

    posted = client.post("/inquiries", json={"person_name": "Rohan B", "company_name": "TRT"}).json()
    assert posted["persona"] in {"it_tech_service", "ai_startup"}
    assert "NeuraMonks" in posted["opening_message"]
    assert "₹1,17,000 + GST" in posted["opening_message"]

    sid = posted["session_id"]
    with client.websocket_connect(f"/chat/{sid}") as ws:
        assert ws.receive_json()["type"] == "opening"
        ws.send_json({"type": "message", "text": "we're a team of 4"})
        assert ws.receive_json()["cta_status"] == "in_progress"
        ws.send_json({"type": "message", "text": "yes book it"})
        assert ws.receive_json()["cta_status"] == "completed"
        ws.send_json({"type": "end"})

    import asyncio
    async def _check():
        async with SessionLocal() as s:
            cs = (await s.execute(select(ChatSession))).scalars().first()
            assert cs.cta_status == "completed"
            assert cs.outcome_status == "qualified"
            assert cs.cta_detail.get("stall_size") == "3x6"
            assert (await s.execute(select(HandoffPacketRow))).scalars().first() is None
    asyncio.run(_check())


def test_handoff_path_unknown_company_deflect():
    """Criteria 3, 5: unknown identity -> qualifying question -> deflection -> handoff packet."""
    orch = Orchestrator(
        analysis=AnalysisAgent(FakeLLMClient(structured=[_CanonResult(canonical="Obscure Local Co", intent_hint="unknown")])),
        research=ResearchAgent(FakeLLMClient(structured=[]), tools=[KBRetriever(), _DeadWeb()]),
        persuasion=PersuasionAgent(FakeLLMClient(
            responses=["So I can tailor this — what does your company do, and what's your role there?"],
            structured=[
                _Analysis(reply="Thanks! TEG has a lot for services firms. Are you thinking of exhibiting or visiting?",
                          detected_cta=None, cta_status="none", cta_type=None, cta_detail={},
                          should_handoff=False, learned_facts={"sector": "IT services"}),
                _Analysis(reply="No problem — I'll have the team send details when you're ready.",
                          detected_cta=None, cta_status="none", cta_type=None, cta_detail={},
                          should_handoff=True, learned_facts={}),
                HandoffPacket(summary="Person from Obscure Local Co, an IT services firm, just researching.",
                              recommended_next_step="Email the exhibitor brochure.",
                              suggested_followup_message="Hi, thanks for your interest in TEG 2026...",
                              prospect_confidence="low", key_facts={}),
            ],
        )),
    )
    app = create_app()
    app.dependency_overrides[get_orchestrator] = lambda: orch
    client = TestClient(app)

    posted = client.post("/inquiries", json={"person_name": "Someone New", "company_name": "Obscure Local Co"}).json()
    assert posted["opening_message"].endswith("?")

    sid = posted["session_id"]
    with client.websocket_connect(f"/chat/{sid}") as ws:
        ws.receive_json()
        ws.send_json({"type": "message", "text": "we do IT staffing, I'm the founder"})
        ws.receive_json()
        ws.send_json({"type": "message", "text": "just researching for now"})
        r = ws.receive_json()
        assert r["should_handoff"] is True
        ws.send_json({"type": "end"})

    r2 = client.get(f"/sessions/{sid}").json()
    assert r2["handoff"] is not None
    assert r2["handoff"]["prospect_confidence"] == "low"
    assert r2["session"]["outcome_status"] in {"contacted", "lost"}
```

- [ ] **Step 2: Run the E2E tests**

Run: `cd teg-outreach-agent && python -m pytest tests/e2e/ -v`
Expected: PASS (2 tests). The e2e tests are sync (`TestClient`/`websocket_connect`) and use the `db_schema` fixture from `conftest.py`; the async DB check inside uses `asyncio.run`.

- [ ] **Step 3: Run the full suite**

Run: `cd teg-outreach-agent && python -m pytest -q`
Expected: ALL PASS. Fix any cross-task regressions before continuing.

- [ ] **Step 4: Write README.md**

```markdown
# TEG Inquiry Outreach Agent

FastAPI service + chat widget that researches a TEG 2026 inquiry-page prospect
(knowledge base first, then free web tools) and runs a persona-tuned,
factually-guarded conversation to drive participation.

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
- `GET /sessions/{session_id}` -> transcript + dossier + handoff (internal)

## Tests

```bash
createdb teg_outreach_test
python -m pytest -q
```

## Retention

```bash
python -m app.jobs.retention   # run from cron
```

## Design docs

- Spec: `../docs/superpowers/specs/2026-08-31-teg-outreach-agent-design.md`
- Plan: `../docs/superpowers/plans/2026-08-31-teg-outreach-agent.md`
```

- [ ] **Step 5: Commit**

```bash
git add teg-outreach-agent/
git commit -m "test(outreach): end-to-end happy-path and handoff-path coverage; README

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 22: Chat widget — build setup + API client

**Files:**
- Create: `teg-outreach-agent/widget/package.json`
- Create: `teg-outreach-agent/widget/tsconfig.json`
- Create: `teg-outreach-agent/widget/build.mjs`
- Create: `teg-outreach-agent/widget/src/api.ts`
- Create: `teg-outreach-agent/widget/src/api.test.ts`
- Create: `teg-outreach-agent/widget/.gitignore` (`dist/` except `.gitkeep`)

**Interfaces:**
- Produces (`widget/src/api.ts`):
  - `interface InquiryInput { person_name: string; company_name: string; email?: string; phone?: string; message?: string; participation_type?: string; consent?: boolean }`
  - `interface InquiryResponse { session_id: string; opening_message: string; persona: string }`
  - `async function submitInquiry(baseUrl: string, input: InquiryInput): Promise<InquiryResponse>` — `POST {baseUrl}/inquiries`, throws `Error` on non-202
  - `type ChatEvent = { type: 'opening' | 'reply' | 'handoff'; text?: string; cta_status?: string; should_handoff?: boolean }`
  - `class ChatSocket` — `constructor(wsUrl: string, sessionId: string)`; `onEvent(cb: (e: ChatEvent) => void)`; `send(text: string)`; `end()`; `close()`. Wraps a `WebSocket` to `{wsUrl}/chat/{sessionId}`.
- Test runner: `node --test` with the built-in test runner (no extra deps); `api.test.ts` compiled on the fly via `tsx` (add to devDeps) OR write `api.test.mjs` importing the compiled `dist`. Use `tsx`.

- [ ] **Step 1: Write package.json**

```json
{
  "name": "teg-outreach-widget",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "build": "node build.mjs",
    "test": "tsx --test src/*.test.ts"
  },
  "devDependencies": {
    "esbuild": "^0.24.0",
    "tsx": "^4.19.0",
    "typescript": "^5.6.0"
  }
}
```

- [ ] **Step 2: Write tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "bundler",
    "strict": true,
    "lib": ["ES2022", "DOM"],
    "types": ["node"],
    "noEmit": true,
    "skipLibCheck": true
  },
  "include": ["src"]
}
```

- [ ] **Step 3: Write build.mjs**

```javascript
import * as esbuild from "esbuild";

await esbuild.build({
  entryPoints: ["src/index.ts"],
  bundle: true,
  format: "iife",
  globalName: "TegOutreach",
  outfile: "dist/teg-outreach-widget.js",
  minify: true,
  target: ["es2019"],
});
console.log("built dist/teg-outreach-widget.js");
```

- [ ] **Step 4: Write the failing test**

```typescript
// src/api.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { submitInquiry, ChatSocket } from "./api.ts";

test("submitInquiry posts and parses", async () => {
  const calls: any[] = [];
  globalThis.fetch = (async (url: string, init: any) => {
    calls.push({ url, init });
    return {
      status: 202,
      json: async () => ({ session_id: "s1", opening_message: "hi", persona: "visitor" }),
    };
  }) as any;

  const res = await submitInquiry("http://api", { person_name: "Rohan B", company_name: "TRT" });
  assert.equal(res.session_id, "s1");
  assert.equal(calls[0].url, "http://api/inquiries");
  assert.equal(JSON.parse(calls[0].init.body).company_name, "TRT");
});

test("submitInquiry throws on non-202", async () => {
  globalThis.fetch = (async () => ({ status: 422, json: async () => ({}) })) as any;
  await assert.rejects(() =>
    submitInquiry("http://api", { person_name: "x", company_name: "y" })
  );
});

test("ChatSocket wires url and forwards events", () => {
  const sent: string[] = [];
  let handler: ((e: any) => void) | null = null;
  class FakeWS {
    onmessage: ((e: any) => void) | null = null;
    onopen: (() => void) | null = null;
    constructor(public url: string) {}
    send(s: string) { sent.push(s); }
    close() {}
  }
  (globalThis as any).WebSocket = FakeWS;

  const cs = new ChatSocket("ws://api", "s1");
  cs.onEvent((e) => { handler = () => {}; assert.equal(e.type, "reply"); });
  const raw: any = (cs as any).ws;
  assert.equal(raw.url, "ws://api/chat/s1");
  raw.onmessage({ data: JSON.stringify({ type: "reply", text: "ok", cta_status: "offered" }) });
  cs.send("hello");
  assert.equal(JSON.parse(sent[0]).text, "hello");
});
```

- [ ] **Step 5: Run to verify fail**

Run: `cd teg-outreach-agent/widget && npm install && npm test`
Expected: FAIL — `./api.ts` not found

- [ ] **Step 6: Write src/api.ts**

```typescript
export interface InquiryInput {
  person_name: string;
  company_name: string;
  email?: string;
  phone?: string;
  message?: string;
  participation_type?: string;
  consent?: boolean;
}

export interface InquiryResponse {
  session_id: string;
  opening_message: string;
  persona: string;
}

export type ChatEvent = {
  type: "opening" | "reply" | "handoff";
  text?: string;
  cta_status?: string;
  should_handoff?: boolean;
};

export async function submitInquiry(
  baseUrl: string,
  input: InquiryInput,
): Promise<InquiryResponse> {
  const resp = await fetch(`${baseUrl}/inquiries`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (resp.status !== 202) {
    throw new Error(`inquiry failed: ${resp.status}`);
  }
  return (await resp.json()) as InquiryResponse;
}

export class ChatSocket {
  private ws: WebSocket;
  private cb: ((e: ChatEvent) => void) | null = null;

  constructor(wsUrl: string, sessionId: string) {
    this.ws = new WebSocket(`${wsUrl}/chat/${sessionId}`);
    this.ws.onmessage = (ev: MessageEvent) => {
      if (this.cb) this.cb(JSON.parse(ev.data) as ChatEvent);
    };
  }

  onEvent(cb: (e: ChatEvent) => void): void {
    this.cb = cb;
  }

  send(text: string): void {
    this.ws.send(JSON.stringify({ type: "message", text }));
  }

  end(): void {
    this.ws.send(JSON.stringify({ type: "end" }));
  }

  close(): void {
    this.ws.close();
  }
}
```

- [ ] **Step 7: Run tests**

Run: `cd teg-outreach-agent/widget && npm test`
Expected: PASS (3 tests)

- [ ] **Step 8: Commit**

```bash
git add teg-outreach-agent/widget/
git commit -m "feat(outreach): chat widget build setup and API client

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Task 23: Chat widget — form + chat UI + mount

**Files:**
- Create: `teg-outreach-agent/widget/src/ui.ts`
- Create: `teg-outreach-agent/widget/src/index.ts`
- Create: `teg-outreach-agent/widget/src/ui.test.ts`
- Create: `teg-outreach-agent/widget/demo.html` (manual test page)

**Interfaces:**
- Consumes: `widget/src/api.ts` (`submitInquiry`, `ChatSocket`, types)
- Produces (`widget/src/ui.ts`):
  - `function renderForm(root: HTMLElement, onSubmit: (input: InquiryInput) => void): void` — builds a minimal form: person_name (required), company_name (required), email, message, participation_type `<select>`, consent checkbox, submit button. On submit, prevents default, validates the two required fields, calls `onSubmit`.
  - `function renderChat(root: HTMLElement): { addMessage: (role: "agent" | "you", text: string) => void; setStatus: (s: string) => void; onSend: (cb: (text: string) => void) => void }` — a message list with `role="log" aria-live="polite"`, an input + send button, a status line. `addMessage` appends a bubble; `setStatus` updates the status line.
- Produces (`widget/src/index.ts`):
  - `export function mount(el: HTMLElement, opts: { apiBaseUrl: string; wsBaseUrl: string }): void` — renders the form; on submit → `submitInquiry` → swap to chat view → show `opening_message` → open `ChatSocket` → wire send/receive; show "Preparing your session…" between submit and opening.
  - Auto-mount: if a `<div id="teg-outreach" data-api="..." data-ws="...">` exists, call `mount` on `DOMContentLoaded`.

- [ ] **Step 1: Write the failing test**

```typescript
// src/ui.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";

// minimal DOM shim
class El {
  children: El[] = [];
  attrs: Record<string, string> = {};
  listeners: Record<string, ((e: any) => void)[]> = {};
  value = "";
  textContent = "";
  tagName: string;
  constructor(tag: string) { this.tagName = tag.toUpperCase(); }
  appendChild(c: El) { this.children.push(c); return c; }
  setAttribute(k: string, v: string) { this.attrs[k] = v; }
  getAttribute(k: string) { return this.attrs[k] ?? null; }
  addEventListener(k: string, cb: (e: any) => void) { (this.listeners[k] ||= []).push(cb); }
  querySelector(sel: string): El | null {
    const want = sel.replace(/[#.\[\]]/g, "");
    const walk = (n: El): El | null => {
      if (n.attrs.name === want || n.attrs.id === want || n.tagName === sel.toUpperCase()) return n;
      for (const c of n.children) { const r = walk(c); if (r) return r; }
      return null;
    };
    return walk(this);
  }
  fire(k: string, e: any = { preventDefault() {} }) { (this.listeners[k] || []).forEach((f) => f(e)); }
}
(globalThis as any).document = {
  createElement: (t: string) => new El(t),
};

const { renderForm, renderChat } = await import("./ui.ts");

test("renderForm calls onSubmit with required fields", () => {
  const root = new El("div") as any;
  let got: any = null;
  renderForm(root, (input) => { got = input; });
  root.querySelector("[name=person_name]").value = "Rohan B";
  root.querySelector("[name=company_name]").value = "TRT";
  root.querySelector("form").fire("submit");
  assert.equal(got.person_name, "Rohan B");
  assert.equal(got.company_name, "TRT");
});

test("renderForm blocks submit when company missing", () => {
  const root = new El("div") as any;
  let calls = 0;
  renderForm(root, () => { calls++; });
  root.querySelector("[name=person_name]").value = "Rohan B";
  root.querySelector("form").fire("submit");
  assert.equal(calls, 0);
});

test("renderChat addMessage and aria-live log", () => {
  const root = new El("div") as any;
  const chat = renderChat(root);
  chat.addMessage("agent", "hello");
  const log = root.querySelector("[role=log]") ?? root.querySelector("log");
  assert.ok(log);
  assert.equal(log.getAttribute("aria-live"), "polite");
});

test("renderChat onSend fires with input value", () => {
  const root = new El("div") as any;
  const chat = renderChat(root);
  let sent = "";
  chat.onSend((t) => { sent = t; });
  root.querySelector("[name=chat_input]").value = "how much is a stall?";
  root.querySelector("[name=chat_send]").fire("click");
  assert.equal(sent, "how much is a stall?");
});
```

- [ ] **Step 2: Run to verify fail**

Run: `cd teg-outreach-agent/widget && npm test`
Expected: FAIL — `./ui.ts` not found

- [ ] **Step 3: Write src/ui.ts**

```typescript
import type { InquiryInput } from "./api.ts";

function h(tag: string, attrs: Record<string, string> = {}, text = ""): HTMLElement {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (text) el.textContent = text;
  return el;
}

export function renderForm(
  root: HTMLElement,
  onSubmit: (input: InquiryInput) => void,
): void {
  const form = h("form");
  const mk = (name: string, type: string, ph: string, required = false) => {
    const i = h("input", { name, type, placeholder: ph });
    if (required) i.setAttribute("required", "required");
    return i;
  };
  form.appendChild(mk("person_name", "text", "Your name", true));
  form.appendChild(mk("company_name", "text", "Company name", true));
  form.appendChild(mk("email", "email", "Work email (optional)"));
  form.appendChild(mk("message", "text", "What are you interested in? (optional)"));

  const sel = h("select", { name: "participation_type" });
  for (const v of ["", "visitor", "exhibitor", "sponsor", "startup_pitch", "speaker"]) {
    sel.appendChild(h("option", { value: v }, v || "I'm not sure yet"));
  }
  form.appendChild(sel);

  const consent = h("input", { name: "consent", type: "checkbox" });
  form.appendChild(consent);
  form.appendChild(h("label", {}, "You may contact me about TEG 2026"));

  form.appendChild(h("button", { type: "submit" }, "Start"));

  form.addEventListener("submit", (e: Event) => {
    e.preventDefault();
    const val = (n: string) =>
      (form.querySelector(`[name=${n}]`) as HTMLInputElement | null)?.value?.trim() || "";
    const person = val("person_name");
    const company = val("company_name");
    if (!person || !company) return;
    onSubmit({
      person_name: person,
      company_name: company,
      email: val("email") || undefined,
      message: val("message") || undefined,
      participation_type: val("participation_type") || undefined,
      consent: (form.querySelector("[name=consent]") as HTMLInputElement | null)?.checked,
    });
  });

  root.appendChild(form);
}

export function renderChat(root: HTMLElement): {
  addMessage: (role: "agent" | "you", text: string) => void;
  setStatus: (s: string) => void;
  onSend: (cb: (text: string) => void) => void;
} {
  const wrap = h("div", { class: "teg-chat" });
  const log = h("div", { role: "log", "aria-live": "polite", class: "teg-log" });
  const status = h("div", { class: "teg-status" });
  const input = h("input", { name: "chat_input", type: "text", placeholder: "Type a message" });
  const send = h("button", { name: "chat_send", type: "button" }, "Send");

  wrap.appendChild(log);
  wrap.appendChild(status);
  wrap.appendChild(input);
  wrap.appendChild(send);
  root.appendChild(wrap);

  let sendCb: ((t: string) => void) | null = null;
  send.addEventListener("click", () => {
    const v = (input as HTMLInputElement).value.trim();
    if (v && sendCb) {
      sendCb(v);
      (input as HTMLInputElement).value = "";
    }
  });

  return {
    addMessage(role, text) {
      log.appendChild(h("div", { class: `teg-msg teg-${role}` }, `${role === "agent" ? "TEG" : "You"}: ${text}`));
    },
    setStatus(s) {
      status.textContent = s;
    },
    onSend(cb) {
      sendCb = cb;
    },
  };
}
```

- [ ] **Step 4: Write src/index.ts**

```typescript
import { ChatSocket, submitInquiry, type InquiryInput } from "./api.ts";
import { renderChat, renderForm } from "./ui.ts";

export function mount(
  el: HTMLElement,
  opts: { apiBaseUrl: string; wsBaseUrl: string },
): void {
  renderForm(el, async (input: InquiryInput) => {
    el.textContent = "";
    const status = document.createElement("div");
    status.textContent = "Preparing your session…";
    el.appendChild(status);

    let res;
    try {
      res = await submitInquiry(opts.apiBaseUrl, input);
    } catch {
      status.textContent = "Something went wrong. Please try again.";
      return;
    }

    el.textContent = "";
    const chat = renderChat(el);
    chat.addMessage("agent", res.opening_message);

    const sock = new ChatSocket(opts.wsBaseUrl, res.session_id);
    sock.onEvent((ev) => {
      if (ev.type === "reply" && ev.text) {
        chat.addMessage("agent", ev.text);
        if (ev.cta_status) chat.setStatus(`Status: ${ev.cta_status}`);
      } else if (ev.type === "handoff") {
        chat.setStatus("Our team will follow up with you.");
      }
    });
    chat.onSend((text) => {
      chat.addMessage("you", text);
      sock.send(text);
    });
  });
}

const auto = typeof document !== "undefined" ? document.getElementById?.("teg-outreach") : null;
if (auto) {
  const el = auto as HTMLElement;
  mount(el, {
    apiBaseUrl: el.getAttribute("data-api") || "",
    wsBaseUrl: el.getAttribute("data-ws") || "",
  });
}
```

- [ ] **Step 5: Write demo.html**

```html
<!doctype html>
<html>
  <head><meta charset="utf-8" /><title>TEG Outreach widget demo</title></head>
  <body>
    <h1>TEG 2026 — Get in touch</h1>
    <div id="teg-outreach" data-api="http://localhost:8000" data-ws="ws://localhost:8000"></div>
    <script src="./dist/teg-outreach-widget.js"></script>
  </body>
</html>
```

- [ ] **Step 6: Run tests + build**

Run:
```bash
cd teg-outreach-agent/widget && npm test && npm run build
```
Expected: 4 UI tests + 3 api tests PASS; `dist/teg-outreach-widget.js` produced.

- [ ] **Step 7: Manual smoke test (optional, needs running backend)**

Run: start the backend (`uvicorn app.main:app` with a real DB + keys), then open `widget/demo.html` in a browser, submit a form with a real KB company, confirm the chat opens with a sourced opening message.

- [ ] **Step 8: Commit**

```bash
git add teg-outreach-agent/widget/
git commit -m "feat(outreach): chat widget form, chat UI, and mount entrypoint

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01S8jnLgnabikNB11qaetwtQ"
```

---

## Final verification

- [ ] **Run the full backend suite:** `cd teg-outreach-agent && python -m pytest -q` — ALL PASS
- [ ] **Run the widget suite:** `cd teg-outreach-agent/widget && npm test` — ALL PASS
- [ ] **Lint:** `cd teg-outreach-agent && ruff check .` — clean
- [ ] **Migration round-trips:** `alembic downgrade base && alembic upgrade head` on a scratch DB — clean
- [ ] **Confirm no paid deps / no browser automation:** `grep -RniE "playwright|selenium|apify|proxycurl|peopledatalabs" teg-outreach-agent/` returns nothing in source (only allowed in comments/docs referencing what is NOT used)
