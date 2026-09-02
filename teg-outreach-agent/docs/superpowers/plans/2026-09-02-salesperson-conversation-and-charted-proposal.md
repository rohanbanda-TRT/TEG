# Salesperson Conversation + Conditional Pricing + Charted Proposal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the outreach chatbot into a consultative TEG salesperson (discovery-first, pricing only on request, proposal offered only after enough is learned), give the proposal PDF five inline-SVG charts and price-conditional sections, and replace the inverted testimonial guardrail with an LLM check.

**Architecture:** Prompt-driven behaviour in `PersuasionAgent` — no hard gates; light session state (`price_requested`, `learned_facts`) only informs the prompt. Guardrails gain a `price_ok` flag and an async `check_testimonial()` behind a cheap regex pre-filter. The proposal grows four schema fields, a `charts.py` module of pure SVG-string functions, and a restructured Jinja template whose Investment section is `{% if price_requested %}`. One Alembic migration adds `chat_sessions.price_requested`.

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI, SQLAlchemy 2.x async + Alembic, Jinja2, WeasyPrint (inline SVG, no library), pytest (async), the existing `KBExplorer` / `FakeLLMClient`.

## Global Constraints

- **No new heavy dependency.** Charts are hand-built SVG strings — no charting library, no headless browser.
- **One migration only:** `0003_price_requested` (`down_revision="0002"`).
- **No hard turn-count or keyword gates.** The proposal-offer and pricing rules are prompt instructions; `learned_facts` and `price_requested` only inform the prompt.
- **Pricing copy rule (unchanged):** every ₹ figure is quoted "+ GST" and "indicative, confirmed at booking"; a visitor *ticket* price is never stated in an agent message.
- **`roi_framing` must never contain:** a fabricated number, a guaranteed outcome, or a deal-count promise.
- **A guardrail that cannot verify blocks:** `check_testimonial` on LLM error returns a violation.
- **TEG palette:** navy `#1b2a5b`, accent `#3b82f6`, muted `#64748b`.
- **Timeouts:** `proposal_soft_timeout_s = 15`, `proposal_hard_timeout_s = 90`.
- Commit after every task. Branch `feat/teg-outreach-agent` is already active.
- Run the KB snapshot check before the suite: `python scripts/build_kb_facts.py --check && python -m pytest -q`.
- Tests marked `integration` are deselected by default (`addopts = "-m 'not integration'"` in `pyproject.toml`).

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `app/domain/schemas.py` | `SectorFitRow`; `Proposal` +4 fields; `PersuasionTurn.asked_about_price` | 1 |
| `app/store/models.py` | `ChatSession.price_requested` column | 2 |
| `app/store/migrations/versions/0003_price_requested.py` | the migration | 2 |
| `app/store/repositories.py` | `SessionRepo.update_state(..., price_requested=None)` | 2 |
| `app/agents/guardrails.py` | `price_ok` param + `unsolicited_price`; delete regex testimonial check; add `check_testimonial()`, `_OVERPROMISE`; `PROPOSAL_SAFE_SECTIONS` +2 | 3, 4 |
| `app/agents/persuasion.py` | salesperson `_system()`; `_Analysis` +2 fields; `respond()` threading; `check_testimonial` call | 5, 6 |
| `app/proposal/charts.py` | **new** — 5 SVG-string functions + style constants | 7 |
| `app/proposal/render.py` | `render_html(p, *, price_requested)`; build charts; explorer-or-constant industry/peer data | 8 |
| `app/proposal/templates/proposal.html.j2` | ~10 sections; charts `\| safe`; Investment `{% if price_requested %}` | 8 |
| `app/agents/proposal.py` | build the 4 new fields; `price_requested` param; guardrail the new fields | 9 |
| `app/orchestrator.py` | persist + thread `price_requested`; `_state_from_row` | 10 |
| `config/settings.py`, `.env.example` | timeout bumps | 1 |
| `tests/**` | per task | all |

---

### Task 1: Schema fields + settings

**Files:**
- Modify: `app/domain/schemas.py` (after `ProposalPackage`, in `Proposal`, in `PersuasionTurn`)
- Modify: `config/settings.py:33-34` (the two `proposal_*_timeout_s` lines)
- Modify: `.env.example`
- Test: `tests/domain/test_schemas.py` (create if absent)

**Interfaces:**
- Produces:
  - `SectorFitRow(BaseModel)` with `lever: str`, `weight: int`.
  - `Proposal` gains `executive_summary: str = ""`, `how_a_teg_plays_out: list[str] = Field(default_factory=list)`, `roi_framing: str = ""`, `sector_fit: list[SectorFitRow] = Field(default_factory=list)`.
  - `PersuasionTurn` gains `asked_about_price: bool = False`.

- [ ] **Step 1: Write the failing test**

```python
# tests/domain/test_schemas.py
from app.domain.schemas import PersuasionTurn, Proposal, ProposalPackage, SectorFitRow


def _pkg():
    return ProposalPackage(name="3m x 3m stall", price_line="", includes=["2 passes"], payment_plan="")


def test_sector_fit_row():
    r = SectorFitRow(lever="India-market buyer access", weight=4)
    assert r.weight == 4


def test_proposal_new_fields_default_empty():
    p = Proposal(
        company="X", person="Y", persona="it_tech_service", generated_on="d",
        session_ref="r", version=1, what_you_told_us="w", lead_generation="l",
        recommended_package=_pkg(), contact="c",
    )
    assert p.executive_summary == ""
    assert p.how_a_teg_plays_out == []
    assert p.roi_framing == ""
    assert p.sector_fit == []


def test_persuasion_turn_asked_about_price_defaults_false():
    t = PersuasionTurn(reply_text="hi", persona="visitor")
    assert t.asked_about_price is False
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/domain/test_schemas.py -q`
Expected: FAIL — `ImportError: cannot import name 'SectorFitRow'`

- [ ] **Step 3: Add the schema code**

In `app/domain/schemas.py`, immediately before `class Proposal(BaseModel):`:

```python
class SectorFitRow(BaseModel):
    lever: str
    weight: int  # 1-5, clamped by ProposalAgent
```

Inside `Proposal`, after `contact: str`:

```python
    executive_summary: str = ""
    how_a_teg_plays_out: list[str] = Field(default_factory=list)
    roi_framing: str = ""
    sector_fit: list[SectorFitRow] = Field(default_factory=list)
```

Inside `PersuasionTurn`, after `wants_proposal: bool = False`:

```python
    asked_about_price: bool = False
```

- [ ] **Step 4: Bump the timeouts**

`config/settings.py` — change:
```python
    proposal_soft_timeout_s: int = 15
    proposal_hard_timeout_s: int = 90
```
`.env.example` — update any `PROPOSAL_SOFT_TIMEOUT_S` / `PROPOSAL_HARD_TIMEOUT_S` lines to `15` / `90` (add them if absent).

- [ ] **Step 5: Run tests**

Run: `.venv/bin/python -m pytest tests/domain/test_schemas.py tests/config/test_settings.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/domain/schemas.py config/settings.py .env.example tests/domain/test_schemas.py
git commit -m "feat(proposal): Proposal exec-summary/roi/sector-fit fields; PersuasionTurn.asked_about_price"
```

---

### Task 2: `price_requested` column + migration + repo

**Files:**
- Modify: `app/store/models.py` (in `class ChatSession`)
- Create: `app/store/migrations/versions/0003_price_requested.py`
- Modify: `app/store/repositories.py:97-108` (`SessionRepo.update_state`)
- Test: `tests/store/test_repositories.py` (add a case), `tests/store/test_migrations.py` (create if absent)

**Interfaces:**
- Consumes: none.
- Produces:
  - `ChatSession.price_requested: Mapped[bool]` default `False`.
  - `SessionRepo.update_state(self, session_id, *, cta_status, cta_type, cta_detail, learned_facts, persona, persona_remapped, needs_review, price_requested: bool | None = None)` — when `price_requested is not None`, set it on the row.

- [ ] **Step 1: Write the failing test**

```python
# tests/store/test_repositories.py  (add)
async def test_update_state_sets_price_requested(db_session):
    # db_session: an AsyncSession with the schema created — follow the file's existing fixture
    from app.store.repositories import ChatSession, SessionRepo  # or wherever ChatSession is imported
    # create a minimal session row first following the pattern already in this file, get its id -> sid
    ...
    await SessionRepo(db_session).update_state(
        sid, cta_status="none", cta_type=None, cta_detail={}, learned_facts={},
        persona="visitor", persona_remapped=False, needs_review=False,
        price_requested=True,
    )
    row = await db_session.get(ChatSession, sid)
    assert row.price_requested is True
```

If `tests/store/test_repositories.py` has no async session fixture, instead write this in `tests/store/test_migrations.py`:

```python
# tests/store/test_migrations.py
import pytest

pytestmark = pytest.mark.usefixtures("db_schema")


def test_chat_sessions_has_price_requested_default_false():
    import asyncio

    from sqlalchemy import text

    from app.store.db import engine

    async def _check():
        async with engine.begin() as c:
            cols = await c.run_sync(
                lambda sc: [r[0] for r in sc.execute(text(
                    "select column_name from information_schema.columns "
                    "where table_name='chat_sessions'"
                ))]
            )
        return cols

    assert "price_requested" in asyncio.run(_check())
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/store/test_migrations.py -q`
Expected: FAIL — column not present (the `db_schema` fixture builds from models; it fails only after Step 3 adds the model column and you re-run — so actually: run it AFTER Step 3 to confirm it passes, and confirm failure now by asserting the column is absent). Simplest: skip a separate "verify fail" here and rely on Step 5.

- [ ] **Step 3: Add the model column**

`app/store/models.py`, in `class ChatSession`, after `needs_review`:

```python
    price_requested: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
```

- [ ] **Step 4: Write the migration**

`app/store/migrations/versions/0003_price_requested.py`:

```python
"""add chat_sessions.price_requested

Revision ID: 0003
Revises: 0002
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_sessions",
        sa.Column("price_requested", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("chat_sessions", "price_requested")
```

- [ ] **Step 5: Extend `SessionRepo.update_state`**

`app/store/repositories.py`, change the signature and body:

```python
    async def update_state(
        self, session_id, *, cta_status, cta_type, cta_detail, learned_facts,
        persona, persona_remapped, needs_review, price_requested: bool | None = None,
    ) -> None:
        row = await self.s.get(ChatSession, session_id)
        row.cta_status = cta_status
        row.cta_type = cta_type
        row.cta_detail = cta_detail
        row.learned_facts = learned_facts
        row.persona = persona
        row.persona_remapped = persona_remapped
        row.needs_review = needs_review
        if price_requested is not None:
            row.price_requested = price_requested
```

- [ ] **Step 6: Run tests**

Run: `.venv/bin/python -m pytest tests/store/ -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/store/models.py app/store/migrations/versions/0003_price_requested.py app/store/repositories.py tests/store/
git commit -m "feat(store): chat_sessions.price_requested column + migration 0003"
```

---

### Task 3: Guardrails — conditional pricing (`price_ok`) + `unsolicited_price`

**Files:**
- Modify: `app/agents/guardrails.py` (`check_message` signature + the price branches; add `_OVERPROMISE`)
- Test: `tests/agents/test_guardrails.py` (add cases)

**Interfaces:**
- Consumes: none.
- Produces:
  - `check_message(text, *, allowed_peers, persona, price_ok: bool = False) -> list[GuardrailViolation]`
  - new violation code string `"unsolicited_price"`.
  - `check_overpromise(text: str) -> GuardrailViolation | None` — `_OVERPROMISE` regex + a ₹-figure check.

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/test_guardrails.py  (add)
from app.agents.guardrails import check_message, check_overpromise


def test_unsolicited_price_flagged_when_not_price_ok():
    v = check_message(
        "A 3m x 3m stall is around ₹1,17,000 for you.",
        allowed_peers=[], persona="it_tech_service", price_ok=False,
    )
    assert "unsolicited_price" in {x.code for x in v}


def test_price_allowed_when_price_ok_but_gst_still_enforced():
    ok = check_message(
        "A 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed at booking).",
        allowed_peers=[], persona="it_tech_service", price_ok=True,
    )
    assert "unsolicited_price" not in {x.code for x in ok}
    assert ok == []
    bad = check_message(
        "A 3m x 3m stall is ₹1,17,000 for you.",
        allowed_peers=[], persona="it_tech_service", price_ok=True,
    )
    assert "missing_gst" in {x.code for x in bad}
    assert "unsolicited_price" not in {x.code for x in bad}


def test_overpromise_patterns():
    assert check_overpromise("You will close 5 deals at TEG.") is not None
    assert check_overpromise("A guaranteed ROI of 300%.") is not None
    assert check_overpromise("Expect a return of ₹50,00,000.") is not None
    assert check_overpromise(
        "If a single partnership covers the investment several times over, it pays for itself."
    ) is None
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/agents/test_guardrails.py -k "unsolicited or overpromise or price_ok" -q`
Expected: FAIL — `check_message() got an unexpected keyword argument 'price_ok'`

- [ ] **Step 3: Implement**

In `app/agents/guardrails.py`:

Add near the other patterns:

```python
_STALL_PRICE_CTX = re.compile(r"\b(stall|sponsor|sponsorship|booth|title sponsor|partner|catalyst zone)\b", re.I)
_OVERPROMISE = re.compile(
    r"\b(guarantee[sd]?|you will (?:close|win|get|see)|"
    r"\d+\s*(?:deals|clients|leads|partnerships)\b|"
    r"\bROI of\b|\breturn of\b)",
    re.I,
)
```

Change the signature:

```python
def check_message(
    text: str, *, allowed_peers: list[str], persona: Persona, price_ok: bool = False,
) -> list[GuardrailViolation]:
```

Inside, after the existing `missing_gst` loop, add:

```python
    # unsolicited price: a stall/sponsor ₹ figure the prospect did not ask for
    if not price_ok:
        for m in _RUPEE.finditer(text):
            window = text[max(0, m.start() - 60): m.end() + 60]
            if _STALL_PRICE_CTX.search(window):
                out.append(GuardrailViolation("unsolicited_price", window.strip()))
                break
```

Add a module function:

```python
def check_overpromise(text: str) -> GuardrailViolation | None:
    if _OVERPROMISE.search(text):
        return GuardrailViolation("overpromise", _OVERPROMISE.search(text).group(0))
    for m in _RUPEE.finditer(text):
        # any rupee figure in an ROI/value paragraph is an invented number
        return GuardrailViolation("overpromise", m.group(0))
    return None
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/agents/test_guardrails.py -q`
Expected: PASS (existing guardrail tests still green — they call `check_message` without `price_ok`, which defaults False and preserves today's behaviour; if any existing test asserted a stall price with no "+ GST" passes, it now also gets `unsolicited_price` — update that test to pass `price_ok=True` or add "+ GST").

- [ ] **Step 5: Commit**

```bash
git add app/agents/guardrails.py tests/agents/test_guardrails.py
git commit -m "feat(guardrails): price_ok gate + unsolicited_price + check_overpromise"
```

---

### Task 4: Guardrails — LLM `check_testimonial()`, drop the regex

**Files:**
- Modify: `app/agents/guardrails.py` (delete `_QUOTE`, `_ATTRIB`, `_cleared_names`, the `uncleared_testimonial` branch in `check_message`; add `_QUOTE_SPAN`, `_TestimonialCheck`, `check_testimonial`; extend `PROPOSAL_SAFE_SECTIONS`)
- Test: `tests/agents/test_guardrails.py` (add cases), fix any existing test that relied on the regex path

**Interfaces:**
- Consumes: `app/kb/facts.py` `load()`; a `FakeLLMClient`/real LLM with `generate_structured`.
- Produces:
  - `async def check_testimonial(text: str, llm) -> GuardrailViolation | None`
  - `_TestimonialCheck(BaseModel)` with `quotes_testimonial: bool`, `all_cleared: bool`, `problem: str = ""`.
  - `PROPOSAL_SAFE_SECTIONS` gains `"executive_summary"` and `"roi_framing"` keys (each a `dict[Persona, str]`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/test_guardrails.py  (add)
import pytest

from app.agents.guardrails import _TestimonialCheck, check_testimonial
from app.llm.fake import FakeLLMClient


async def test_no_quote_means_no_llm_call():
    fake = FakeLLMClient()
    assert await check_testimonial("TEG has 250+ exhibitors and great matchmaking.", fake) is None
    assert fake.calls == []


async def test_cleared_quote_passes():
    fake = FakeLLMClient(structured=[_TestimonialCheck(quotes_testimonial=True, all_cleared=True)])
    v = await check_testimonial(
        'As Sonu Sharma said, "I used to think tech talent was mostly in Bangalore, but not any more."',
        fake,
    )
    assert v is None


async def test_fabricated_quote_flagged():
    fake = FakeLLMClient(structured=[
        _TestimonialCheck(quotes_testimonial=True, all_cleared=False, problem="unknown name Jane Doe")
    ])
    v = await check_testimonial('As Jane Doe said, "TEG tripled our revenue in a week."', fake)
    assert v is not None and v.code == "uncleared_testimonial"


async def test_llm_error_fails_safe():
    class _Boom:
        async def generate_structured(self, **kw):
            raise RuntimeError("down")

    v = await check_testimonial('Someone said, "a long enough quote to trip the prefilter here."', _Boom())
    assert v is not None and v.code == "uncleared_testimonial"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/agents/test_guardrails.py -k testimonial -q`
Expected: FAIL — `cannot import name '_TestimonialCheck'`

- [ ] **Step 3: Implement**

In `app/agents/guardrails.py`:

Remove `_QUOTE`, `_ATTRIB`, `_cleared_names`, and the "uncleared testimonial" block inside `check_message` (the `for qm in _QUOTE.finditer(text):` loop). Keep `_kb_company_names`.

Add:

```python
from pydantic import BaseModel

_QUOTE_SPAN = re.compile(r'["“”][^"“”]{20,}["“”]')


class _TestimonialCheck(BaseModel):
    quotes_testimonial: bool
    all_cleared: bool
    problem: str = ""


async def check_testimonial(text: str, llm) -> GuardrailViolation | None:
    if not _QUOTE_SPAN.search(text):
        return None
    cleared = _load_facts().cleared_testimonials
    listing = "\n".join(f'- {t.name}: "{t.quote}"' for t in cleared)
    try:
        r = await llm.generate_structured(
            system=(
                "You verify testimonial usage. You get a MESSAGE and the ONLY "
                "testimonials that may be quoted. Decide: does the message quote a "
                "testimonial at all? If so, is every quoted testimonial one of the "
                "allowed ones word-for-word, attributed to the correct name? A "
                "paraphrase, a wrong name, or an unknown name is NOT cleared."
            ),
            messages=[{"role": "user", "content":
                       f"MESSAGE:\n{text}\n\nALLOWED TESTIMONIALS:\n{listing}"}],
            schema=_TestimonialCheck,
        )
    except Exception:  # noqa: BLE001 — a guardrail that cannot verify blocks
        return GuardrailViolation("uncleared_testimonial", "verification unavailable")
    if r.quotes_testimonial and not r.all_cleared:
        return GuardrailViolation("uncleared_testimonial", r.problem[:120])
    return None
```

Extend `PROPOSAL_SAFE_SECTIONS` with two new keys (add per-persona strings — copy this block verbatim):

```python
    "executive_summary": {
        "it_tech_service": "You run a technology services company exploring how Tech Expo Gujarat 2026 could support your business development across India-market and cross-industry buyers.",
        "ai_startup": "You run an early-stage AI/technology company exploring an affordable way to showcase it and meet buyers and investors at Tech Expo Gujarat 2026.",
        "non_tech_sponsor": "Your company is exploring a sponsorship association with Tech Expo Gujarat 2026 to build brand presence around the region's innovation story.",
        "visitor": "You are considering attending Tech Expo Gujarat 2026 to discover technology solutions relevant to your work.",
    },
    "roi_framing": {
        "it_tech_service": "TEG concentrates cross-industry decision-makers and pre-scheduled meetings into three days; if a single engagement that starts here covers the cost of taking part many times over, participation pays for itself.",
        "ai_startup": "For a small team, the Catalyst Zone and the investor track compress months of buyer and VC outreach into a few days; one partnership or raise that begins here can outweigh the cost of the stall many times over.",
        "non_tech_sponsor": "A category-exclusive association ties your brand to the region's innovation narrative across the venue, digital, and press; the value is in the sustained visibility rather than a single transaction.",
        "visitor": "Meeting 250+ exhibitors in one place compresses vendor evaluation that would otherwise take months.",
    },
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/agents/test_guardrails.py tests/agents/test_guardrails_proposal.py -q`
Expected: PASS. Any existing test that fed a quoted string to `check_message` expecting `uncleared_testimonial` in the result must move to `check_testimonial` with a `FakeLLMClient` — update it.

- [ ] **Step 5: Commit**

```bash
git add app/agents/guardrails.py tests/agents/test_guardrails.py
git commit -m "feat(guardrails): LLM-backed check_testimonial behind a quote pre-filter; drop the inverted regex"
```

---

### Task 5: PersuasionAgent — `_Analysis` fields + `_system()` salesperson rewrite

**Files:**
- Modify: `app/agents/persuasion.py` (`_Analysis`, `_system`, imports)
- Test: `tests/agents/test_persuasion_system.py` (create)

**Interfaces:**
- Consumes: `app/agents/guardrails.check_message` (now with `price_ok`), `check_testimonial`.
- Produces:
  - `_Analysis` gains `discovery: dict = {}` (replaces `learned_facts`) and `asked_about_price: bool = False`.
  - `PersuasionAgent._system(self, persona, dossier, *, learned_facts: dict, price_requested: bool) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/test_persuasion_system.py
from app.agents.persuasion import PersuasionAgent
from app.domain.schemas import ResearchDossier
from app.llm.fake import FakeLLMClient


def _agent():
    return PersuasionAgent(FakeLLMClient())


def _dossier(rel="cold", **over):
    return ResearchDossier(relationship=rel, sector="AI & Machine Learning", **over)


def test_system_lists_missing_discovery_facts():
    s = _agent()._system(
        "it_tech_service", _dossier(), learned_facts={"goal": "more India clients"},
        price_requested=False,
    )
    assert "Still missing for a proposal" in s
    assert "target_market" in s and "scale" in s
    assert "goal" not in s.split("Still missing for a proposal")[1].split("\n")[0]


def test_system_all_discovery_present_no_missing_line():
    s = _agent()._system(
        "it_tech_service", _dossier(),
        learned_facts={"goal": "x", "target_market": "y", "scale": "z"},
        price_requested=False,
    )
    assert "Still missing for a proposal: none" in s or "Still missing" not in s


def test_system_insider_forbids_pitch_and_price():
    s = _agent()._system("it_tech_service", _dossier(rel="insider"), learned_facts={}, price_requested=False)
    assert "organizing team" in s
    assert "Do NOT pitch" in s


def test_system_pricing_rule_present():
    s = _agent()._system("it_tech_service", _dossier(), learned_facts={}, price_requested=False)
    assert "Do NOT bring up cost" in s
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/agents/test_persuasion_system.py -q`
Expected: FAIL — `_system()` takes 3 positional args / missing keyword args

- [ ] **Step 3: Rewrite `_Analysis` and `_system`**

`_Analysis` — replace `learned_facts: dict = {}` with:

```python
    discovery: dict = {}          # {goal?, target_market?, scale?, timeline?, concern?} learned this turn
    asked_about_price: bool = False
```

`_system` — replace the whole method:

```python
    _REQUIRED_DISCOVERY = ("goal", "target_market", "scale")

    def _system(
        self, persona: Persona, dossier: ResearchDossier, *,
        learned_facts: dict, price_requested: bool,
    ) -> str:
        props = self._rules.persona_triggers.get(persona, {}).get("value_props", [])
        tone = {
            "insider": (
                "This person is on the Tech Expo Gujarat organizing team. Do NOT pitch "
                "them, quote prices, or push a CTA unless they explicitly ask. Talk "
                "peer-to-peer as a fellow organiser. Ask what they need sorted for their "
                "company this year (booth, a bigger presence, speaking, something else)."
            ),
            "returning": (
                "This company/person has taken part in TEG before — welcome them back "
                "and reference their specific history."
            ),
            "cold": "First contact — warm and curious, not familiar.",
        }[dossier.relationship]
        known = sorted(k for k in self._REQUIRED_DISCOVERY if learned_facts.get(k))
        missing = [k for k in self._REQUIRED_DISCOVERY if not learned_facts.get(k)]
        return (
            "You are a business-development representative for Tech Expo Gujarat 2026 "
            "(27-29 Nov 2026, GUCEC Ahmedabad), talking to a prospect who just enquired. "
            "Your goal is conversion — helping them see why participating is worth it for "
            "their business. Be consultative, not pushy: ask about their business, listen, "
            "connect what you hear to what TEG offers. Write ONLY the message to send — one "
            "warm, specific paragraph (2-4 sentences) ending in a single question. No "
            "preamble, headings, or labels.\n\n"
            f"Tone: {tone}\n\n"
            "Personalization: when you know the person's role, address them through it and "
            "reference one concrete fact about their company from the overview — not a "
            "generic line. If you do NOT know their role, ask it naturally in your first "
            "reply.\n\n"
            "Discovery: you are also gathering context for a possible tailored proposal. "
            "Naturally learn and record in `discovery`: goal (the outcome they want from "
            "TEG), target_market (who they sell to / their buyer industries), scale (rough "
            "team size or similar), and optionally timeline and concern. One light question "
            "per turn — never interrogate. Prefer questions that also move the pitch "
            f"forward.\nSo far you know: {known or 'nothing yet'}. "
            f"Still missing for a proposal: {', '.join(missing) if missing else 'none'}.\n\n"
            "Pricing: do NOT bring up cost, stall prices, sponsorship figures, or GST. Only "
            "if the prospect directly asks what something costs, or raises budget, may you "
            f"give this one indicative line: \"{_PRICING_LINE[persona]}\" — always '+ GST' "
            "and 'indicative, confirmed at booking'. Never volunteer a number they did not "
            "ask for.\n\n"
            "Proposal offer: offer to put together a tailored proposal only once you know "
            "their goal, target_market, and a rough sense of scale, AND they have shown "
            "genuine interest. Until then, keep the conversation going. If the prospect "
            "explicitly asks for a proposal or something in writing, honour that "
            "regardless.\n\n"
            f"You may draw on these benefits (paraphrase, do not list): {'; '.join(props)}.\n"
            "Hard rules: only name peer companies from the list you are given; never invent "
            "statistics or testimonials; never state a visitor ticket price."
        )
```

Leave the `_PRICING_LINE` dict as-is.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/agents/test_persuasion_system.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/agents/persuasion.py tests/agents/test_persuasion_system.py
git commit -m "feat(persuasion): salesperson _system() prompt; _Analysis discovery + asked_about_price"
```

---

### Task 6: PersuasionAgent — `init()` / `respond()` threading + testimonial check

**Files:**
- Modify: `app/agents/persuasion.py` (`init`, `respond`)
- Test: `tests/agents/test_persuasion_init.py`, `tests/agents/test_persuasion_respond.py` (update existing + add cases)

**Interfaces:**
- Consumes: `_system(persona, dossier, *, learned_facts, price_requested)` (Task 5); `check_message(..., price_ok=...)` (Task 3); `check_testimonial(text, llm)` (Task 4).
- Produces:
  - `respond()` returns a `PersuasionTurn` with `asked_about_price` set and `updated_state["price_requested"]` sticky-updated; `updated_state["learned_facts"]` merged from `analysis.discovery`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/test_persuasion_respond.py  (add; keep existing tests, adjusting _Analysis(learned_facts=...) -> discovery=...)
from app.agents.persuasion import PersuasionAgent, _Analysis
from app.domain.schemas import IntakeResult, ResearchDossier
from app.llm.fake import FakeLLMClient


def _intake():
    return IntakeResult(person_name="Rohan B", company_name_raw="Acme AI",
                        company_name_canonical="Acme AI", provided_fields=[],
                        intent_hint="exhibitor", consent_status="unknown")


def _dossier():
    return ResearchDossier(relationship="cold", sector="AI & Machine Learning",
                           peer_companies=["ViitorCloud", "NeuraMonks"])


async def test_discovery_merges_into_learned_facts():
    llm = FakeLLMClient(structured=[
        _Analysis(reply="What outcome would make TEG worth it for Acme AI?",
                  discovery={"target_market": "US banks"}),
    ])
    agent = PersuasionAgent(llm)
    turn = await agent.respond(
        intake=_intake(), dossier=_dossier(),
        state={"persona": "it_tech_service", "cta_status": "none", "learned_facts": {"goal": "leads"},
               "cta_detail": {}, "target_cta": "book_stall"},
        history=[{"role": "agent", "content": "hi"}], prospect_message="we sell to US banks",
    )
    assert turn.updated_state["learned_facts"] == {"goal": "leads", "target_market": "US banks"}


async def test_price_request_is_sticky():
    llm = FakeLLMClient(structured=[
        _Analysis(reply="A 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed at booking).",
                  asked_about_price=True),
    ])
    agent = PersuasionAgent(llm)
    turn = await agent.respond(
        intake=_intake(), dossier=_dossier(),
        state={"persona": "it_tech_service", "cta_status": "none", "learned_facts": {},
               "cta_detail": {}, "target_cta": "book_stall"},
        history=[{"role": "agent", "content": "hi"}], prospect_message="what does a stall cost?",
    )
    assert turn.asked_about_price is True
    assert turn.updated_state["price_requested"] is True
    assert turn.guardrail_flags == []   # price allowed because asked_about_price flipped price_ok


async def test_unsolicited_price_is_caught():
    llm = FakeLLMClient(
        structured=[
            _Analysis(reply="You should exhibit — a 3m x 3m stall is ₹1,17,000.", asked_about_price=False),
            _Analysis(reply="TEG brings 15,000+ buyers across every sector — worth a look?", asked_about_price=False),
        ],
    )
    agent = PersuasionAgent(llm)
    turn = await agent.respond(
        intake=_intake(), dossier=_dossier(),
        state={"persona": "it_tech_service", "cta_status": "none", "learned_facts": {},
               "cta_detail": {}, "target_cta": "book_stall"},
        history=[{"role": "agent", "content": "hi"}], prospect_message="tell me about TEG",
    )
    assert "unsolicited_price" in turn.guardrail_flags or "₹" not in turn.reply_text
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/agents/test_persuasion_respond.py -q`
Expected: FAIL — `_Analysis` has no `discovery` kwarg for the OLD tests too; and the new assertions fail

- [ ] **Step 3: Update `init()`**

In `init()`, both `_system(...)` calls (there is one, around the personalised branch) become:

```python
        system = self._system(persona, dossier, learned_facts={}, price_requested=False)
```

The guardrail calls in `init()` become:

```python
            v = check_message(text, allowed_peers=peers, persona=persona, price_ok=False)
            v_t = await check_testimonial(text, self.llm)
            if v_t:
                v = [*v, v_t]
```

(apply to both the first draft check and the post-regenerate check; keep the existing safe-template fallback).

Add the import: `from app.agents.guardrails import SAFE_TEMPLATES, check_message, check_testimonial`.

- [ ] **Step 4: Update `respond()`**

Replace the `system = self._system(...)` line:

```python
        price_requested = state.get("price_requested", False)
        system = self._system(
            persona, dossier, learned_facts=state.get("learned_facts", {}),
            price_requested=price_requested,
        ) + (
            f"\nTarget CTA: {state.get('target_cta')}. Current cta_status: {state.get('cta_status')}. "
            "Advance it naturally; set cta_status to 'completed' only if the prospect clearly commits. "
            "Set should_handoff true if they say they're just researching or repeatedly deflect. "
            "Set asked_about_price true if the prospect asked about cost or raised budget this turn. "
            "Set wants_proposal true if they ask for a proposal / PDF / 'something in writing', or "
            "accept an offer of one."
        )
```

Replace the guardrail block:

```python
        flags: list[str] = []
        v = check_message(analysis.reply, allowed_peers=peers, persona=persona, price_ok=price_requested or analysis.asked_about_price)
        v_t = await check_testimonial(analysis.reply, self.llm)
        if v_t:
            v = [*v, v_t]
        if v:
            analysis = await self.llm.generate_structured(
                system=system + f"\nPrevious draft violated {[x.code for x in v]}. Fix it.",
                messages=[{"role": "user", "content": user}], schema=_Analysis,
            )
            v = check_message(analysis.reply, allowed_peers=peers, persona=persona, price_ok=price_requested or analysis.asked_about_price)
            v_t = await check_testimonial(analysis.reply, self.llm)
            if v_t:
                v = [*v, v_t]
        if v:
            analysis.reply = SAFE_TEMPLATES[persona]
            flags = [x.code for x in v]
            state["needs_review"] = True
            _log.warning("guardrails forced safe template  flags=%s", flags)
```

Replace the state-merge block:

```python
        merged_facts = {**state.get("learned_facts", {}), **analysis.discovery}
        state["learned_facts"] = merged_facts
        state["cta_status"] = analysis.cta_status
        state["price_requested"] = price_requested or analysis.asked_about_price
        if analysis.cta_detail:
            state["cta_detail"] = {**state.get("cta_detail", {}), **analysis.cta_detail}
```

Add `asked_about_price=analysis.asked_about_price` to the returned `PersuasionTurn(...)`.

- [ ] **Step 5: Fix the existing respond/init tests**

Any `_Analysis(..., learned_facts={...})` in the existing test files → `discovery={...}`. Any `_system(persona, dossier)` call → add `learned_facts={}, price_requested=False`.

- [ ] **Step 6: Run tests**

Run: `.venv/bin/python -m pytest tests/agents/test_persuasion_init.py tests/agents/test_persuasion_respond.py tests/agents/test_persuasion_wants_proposal.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/agents/persuasion.py tests/agents/test_persuasion_init.py tests/agents/test_persuasion_respond.py tests/agents/test_persuasion_wants_proposal.py
git commit -m "feat(persuasion): thread price_requested + discovery; async testimonial check in the guarded loop"
```

---

### Task 7: `app/proposal/charts.py`

**Files:**
- Create: `app/proposal/charts.py`
- Test: `tests/proposal/test_charts.py` (create)

**Interfaces:**
- Consumes: `app/domain/schemas.SectorFitRow`.
- Produces:
  - `growth_bar(attendees: tuple[int, int], exhibitors: tuple[int, int]) -> str`
  - `industry_mix_bars(industries: list[str]) -> str`
  - `funnel(steps: list[tuple[str, str]]) -> str`
  - `sector_peer_stat(sector: str, count: int) -> str`
  - `sector_fit_bars(rows: list[SectorFitRow]) -> str`
  - module constants `NAVY`, `ACCENT`, `MUTED`, `FONT`, `W`
  - `DEFAULT_FUNNEL_STEPS: list[tuple[str, str]]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/proposal/test_charts.py
from app.domain.schemas import SectorFitRow
from app.proposal import charts


def _no_unsafe(svg: str):
    assert svg.lstrip().startswith("<svg")
    assert "<script" not in svg
    assert "http" not in svg


def test_growth_bar():
    svg = charts.growth_bar((8000, 15000), (125, 250))
    _no_unsafe(svg)
    assert ("15,000" in svg) or ("15000" in svg)
    assert "250" in svg


def test_industry_mix_bars():
    svg = charts.industry_mix_bars(["Manufacturing", "Healthcare", "Fintech"])
    _no_unsafe(svg)
    assert "Manufacturing" in svg and "Healthcare" in svg
    assert "illustrative" in svg.lower()


def test_funnel():
    svg = charts.funnel(charts.DEFAULT_FUNNEL_STEPS)
    _no_unsafe(svg)
    assert "15,000" in svg or "15000" in svg


def test_sector_peer_stat():
    svg = charts.sector_peer_stat("Fintech", 4)
    _no_unsafe(svg)
    assert ">4<" in svg or "4</text>" in svg
    assert "Fintech" in svg


def test_sector_fit_bars_4_and_6_rows_and_clamp():
    for n in (4, 6):
        rows = [SectorFitRow(lever=f"Lever {i}", weight=(i % 5) + 1) for i in range(n)]
        svg = charts.sector_fit_bars(rows)
        _no_unsafe(svg)
        assert svg.count("<rect") >= n
    # a weight above 5 must not overflow the drawing area
    svg = charts.sector_fit_bars([SectorFitRow(lever="X", weight=9)])
    _no_unsafe(svg)
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/proposal/test_charts.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.proposal.charts'`

- [ ] **Step 3: Implement `app/proposal/charts.py`**

```python
"""Hand-built inline SVG charts for the proposal PDF.

Each function returns a complete <svg> string: viewBox-scaled, system-font
labels, no external references, no <script>. WeasyPrint renders inline SVG
natively. All charts are decorative/illustrative — labelled as such where they
are not to scale.
"""
from __future__ import annotations

from html import escape

from app.domain.schemas import SectorFitRow

NAVY = "#1b2a5b"
ACCENT = "#3b82f6"
MUTED = "#64748b"
FONT = "-apple-system, 'Segoe UI', Roboto, 'DejaVu Sans', sans-serif"
W = 520

DEFAULT_FUNNEL_STEPS: list[tuple[str, str]] = [
    ("15,000+ visitors", "cross-industry decision-makers over 3 days"),
    ("Pre-scheduled 1:1 B2B meetings", "matched to your target sectors"),
    ("Qualified conversations", "live demos, real buying intent"),
    ("Partnerships & pipeline", "the follow-up that starts here"),
]


def _fmt(n: int) -> str:
    return f"{n:,}"


def _svg(body: str, height: int) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height}" '
        f'width="{W}" height="{height}" font-family="{FONT}">{body}</svg>'
    )


def growth_bar(attendees: tuple[int, int], exhibitors: tuple[int, int]) -> str:
    h = 210
    groups = [("Attendees", attendees), ("Exhibitors", exhibitors)]
    max_v = max(attendees[1], exhibitors[1])
    base_y = h - 40
    plot_h = base_y - 30
    parts = [f'<text x="0" y="16" font-size="12" fill="{NAVY}">TEG 2024 → TEG 2026</text>']
    gw = W / len(groups)
    for gi, (label, (v24, v26)) in enumerate(groups):
        cx = gi * gw + gw / 2
        for bi, (v, colour) in enumerate(((v24, MUTED), (v26, NAVY))):
            bh = plot_h * (v / max_v)
            bx = cx - 46 + bi * 44
            parts.append(
                f'<rect x="{bx:.0f}" y="{base_y - bh:.0f}" width="38" height="{bh:.0f}" fill="{colour}" rx="2"/>'
            )
            parts.append(
                f'<text x="{bx + 19:.0f}" y="{base_y - bh - 5:.0f}" font-size="10" '
                f'text-anchor="middle" fill="{NAVY}">{_fmt(v)}</text>'
            )
        parts.append(
            f'<text x="{cx:.0f}" y="{base_y + 16:.0f}" font-size="11" text-anchor="middle" fill="{MUTED}">{escape(label)}</text>'
        )
    parts.append(
        f'<rect x="0" y="{h - 14}" width="10" height="10" fill="{MUTED}"/>'
        f'<text x="14" y="{h - 5}" font-size="9" fill="{MUTED}">2024 (actual)</text>'
        f'<rect x="110" y="{h - 14}" width="10" height="10" fill="{NAVY}"/>'
        f'<text x="124" y="{h - 5}" font-size="9" fill="{MUTED}">2026 (target)</text>'
    )
    return _svg("".join(parts), h)


def industry_mix_bars(industries: list[str]) -> str:
    rows = industries[:20]
    row_h = 18
    h = 30 + row_h * len(rows) + 16
    parts = [f'<text x="0" y="14" font-size="11" fill="{NAVY}">Buyers attend across every sector — illustrative, not to scale</text>']
    for i, name in enumerate(rows):
        y = 28 + i * row_h
        frac = 0.55 + 0.4 * (i / max(1, len(rows) - 1))
        parts.append(f'<rect x="130" y="{y}" width="{(W - 140) * frac:.0f}" height="12" fill="{ACCENT}" opacity="0.85" rx="2"/>')
        parts.append(f'<text x="124" y="{y + 10}" font-size="10" text-anchor="end" fill="{MUTED}">{escape(name)}</text>')
    return _svg("".join(parts), h)


def funnel(steps: list[tuple[str, str]]) -> str:
    n = len(steps)
    step_h = 46
    h = 24 + n * step_h + 18
    top_w, bot_w = W - 40, W * 0.34
    parts = []
    for i, (label, sub) in enumerate(steps):
        y = 16 + i * step_h
        w_top = top_w - (top_w - bot_w) * (i / n)
        w_bot = top_w - (top_w - bot_w) * ((i + 1) / n)
        x_top = (W - w_top) / 2
        x_bot = (W - w_bot) / 2
        parts.append(
            f'<path d="M{x_top:.0f},{y} L{x_top + w_top:.0f},{y} '
            f'L{x_bot + w_bot:.0f},{y + step_h - 6} L{x_bot:.0f},{y + step_h - 6} Z" '
            f'fill="{NAVY}" opacity="{0.9 - i * 0.13:.2f}"/>'
        )
        parts.append(f'<text x="{W/2:.0f}" y="{y + 19}" font-size="11" fill="#fff" text-anchor="middle">{escape(label)}</text>')
        parts.append(f'<text x="{W/2:.0f}" y="{y + 33}" font-size="8.5" fill="#e2e8f0" text-anchor="middle">{escape(sub)}</text>')
    parts.append(f'<text x="0" y="{h - 4}" font-size="9" fill="{MUTED}">Illustrative of the TEG mechanism</text>')
    return _svg("".join(parts), h)


def sector_peer_stat(sector: str, count: int) -> str:
    h = 96
    body = (
        f'<rect x="0" y="0" width="{W}" height="{h}" fill="#f1f5f9" rx="6"/>'
        f'<text x="24" y="62" font-size="44" font-weight="bold" fill="{NAVY}">{int(count)}</text>'
        f'<text x="{24 + 22 + len(str(int(count))) * 26}" y="40" font-size="12" fill="{MUTED}">companies in</text>'
        f'<text x="{24 + 22 + len(str(int(count))) * 26}" y="58" font-size="12" fill="{NAVY}">{escape(sector)}</text>'
        f'<text x="{24 + 22 + len(str(int(count))) * 26}" y="76" font-size="12" fill="{MUTED}">already on the TEG 2026 list</text>'
    )
    return _svg(body, h)


def sector_fit_bars(rows: list[SectorFitRow]) -> str:
    rows = rows[:6]
    row_h = 30
    h = 28 + row_h * len(rows) + 14
    inner = W - 170
    parts = [f'<text x="0" y="14" font-size="11" fill="{NAVY}">How TEG\'s levers weigh for your sector — illustrative</text>']
    for i, r in enumerate(rows):
        y = 26 + i * row_h
        w = max(1, min(5, r.weight)) / 5
        parts.append(f'<text x="0" y="{y + 13}" font-size="10" fill="{MUTED}">{escape(r.lever)}</text>')
        parts.append(f'<rect x="150" y="{y + 2}" width="{inner * w:.0f}" height="14" fill="{ACCENT}" rx="2"/>')
        parts.append(f'<text x="{150 + inner * w + 6:.0f}" y="{y + 13}" font-size="9" fill="{MUTED}">{max(1, min(5, r.weight))}/5</text>')
    return _svg("".join(parts), h)
```

Note: the `_svg` wrapper's `xmlns` attribute contains `http` — the test's
`assert "http" not in svg` will trip on it. Change the test's check to
`assert "http://" not in svg.replace('xmlns="http://www.w3.org/2000/svg"', "")`
OR drop the `xmlns` (WeasyPrint does not require it for inline SVG). **Drop the
`xmlns`** — simpler; update `_svg` to omit it, and the test stays as written.

- [ ] **Step 4: Adjust `_svg` per the note**

`_svg` becomes:

```python
def _svg(body: str, height: int) -> str:
    return (
        f'<svg viewBox="0 0 {W} {height}" width="{W}" height="{height}" '
        f'font-family="{FONT}">{body}</svg>'
    )
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/python -m pytest tests/proposal/test_charts.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/proposal/charts.py tests/proposal/test_charts.py
git commit -m "feat(proposal): charts.py — 5 hand-built inline-SVG chart functions"
```

---

### Task 8: Renderer + template — sections, charts, conditional Investment

**Files:**
- Modify: `app/proposal/render.py` (`render_html` signature, chart building, industry/peer data)
- Rewrite: `app/proposal/templates/proposal.html.j2`
- Test: `tests/proposal/test_render.py` (update + add)

**Interfaces:**
- Consumes: `app/proposal/charts.py` (Task 7); `app/domain/schemas.Proposal` with the new fields (Task 1); `app/kb/explorer.KBExplorer` (optional).
- Produces: `render_html(proposal: Proposal, *, price_requested: bool = False) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/proposal/test_render.py  (add; keep existing render_pdf / png tests)
from app.domain.schemas import Proposal, ProposalPackage, SectorFitRow
from app.proposal.render import render_html, render_pdf


def _proposal(**over):
    base = dict(
        company="Acme AI", person="Rohan B", person_role="CTO",
        sector="AI & Machine Learning", persona="it_tech_service",
        generated_on="2026-09-02", session_ref="abcd1234", version=1,
        what_you_told_us="You build AI tooling and want India enterprise clients.",
        lead_generation="Pre-scheduled B2B meetings with India-market buyers.",
        proof=["TEG 2024 drew 8,000+ attendees and 125+ exhibitors."],
        recommended_package=ProposalPackage(
            name="3m x 3m stall",
            price_line="₹1,17,000 + GST (indicative, confirmed at booking)",
            includes=["2 exhibitor passes", "5 visitor passes"],
            payment_plan="25% x 4",
        ),
        peer_companies=["ViitorCloud", "NeuraMonks"],
        next_steps=["Reply here to lock a slot."],
        contact="info@techexpogujarat.com",
        executive_summary="Acme AI, an AI tooling company, is exploring TEG 2026 to reach India enterprise buyers.",
        how_a_teg_plays_out=["Pre-event: matchmaking", "Day 1: demos", "Day 2: meetings", "After: follow-up"],
        roi_framing="If a single enterprise engagement that starts here covers the cost many times over, it pays for itself.",
        sector_fit=[SectorFitRow(lever="India-market buyer access", weight=5),
                    SectorFitRow(lever="Live demo space", weight=4),
                    SectorFitRow(lever="Pre-scheduled meetings", weight=5),
                    SectorFitRow(lever="Brand visibility", weight=3)],
    )
    base.update(over)
    return Proposal(**base)


def test_render_html_has_new_sections_and_charts():
    html = render_html(_proposal(), price_requested=True)
    assert "Executive summary" in html
    assert "Acme AI, an AI tooling company" in html
    assert "Investment" in html
    assert "₹1,17,000 + GST" in html
    assert html.count("<svg") >= 4


def test_render_html_omits_price_when_not_requested():
    html = render_html(_proposal(), price_requested=False)
    assert "Investment" in html            # section still present
    assert "₹" not in html                 # but no figures anywhere
    assert "pricing tailored to your goals" in html


def test_render_pdf_still_multipage():
    html = render_html(_proposal(), price_requested=True)
    pdf = render_pdf(html)
    assert pdf[:4] == b"%PDF"
    assert pdf.count(b"/Type /Page") >= 2 or pdf.count(b"/Type/Page") >= 2
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/proposal/test_render.py -q`
Expected: FAIL — `render_html() got an unexpected keyword argument 'price_requested'`

- [ ] **Step 3: Rewrite `render.py`**

```python
from __future__ import annotations

from pathlib import Path

import pymupdf
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from app.domain.schemas import Proposal
from app.proposal import charts

TEMPLATE_DIR = Path(__file__).parent / "templates"

# Sourced from event_overview/event_info.md (TEG 2024 actual → TEG 2026 target).
_ATTENDEES = (8000, 15000)
_EXHIBITORS = (125, 250)

_DEFAULT_INDUSTRIES = [
    "Manufacturing", "Automobile", "Power & Energy", "Agriculture", "Education",
    "Healthcare", "Electronics", "Pharmaceutical", "Jewellery", "Textile",
    "Retail", "Logistics", "Finance", "IT & Software", "AI & Machine Learning",
    "Fintech", "Real Estate", "Cybersecurity",
]

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def _chart_data(proposal: Proposal) -> tuple[list[str], int]:
    """Industries + sector peer count. Constants unless the explorer is handy."""
    try:
        import asyncio

        from app.kb.explorer import KBExplorer
        from app.llm.base import get_llm

        ex = asyncio.get_event_loop().run_until_complete(
            KBExplorer(get_llm()).explore(
                "From event_overview/event_info.md list the TEG target industries, and from "
                f"sector_wise_participation.md count the companies under the '{proposal.sector}' "
                "sector. Return facts: industries (comma-separated), sector_peer_count (integer)."
            )
        )
        industries = [s.strip() for s in ex.facts.get("industries", "").split(",") if s.strip()]
        count = int(ex.facts.get("sector_peer_count") or 0)
    except Exception:  # noqa: BLE001 — charts are illustrative; constants are fine
        industries, count = [], 0
    return (industries or _DEFAULT_INDUSTRIES), (count or len(proposal.peer_companies))


def render_html(proposal: Proposal, *, price_requested: bool = False) -> str:
    industries, peer_count = _chart_data(proposal)
    ch = {
        "growth": charts.growth_bar(_ATTENDEES, _EXHIBITORS),
        "industry": charts.industry_mix_bars(industries),
        "funnel": charts.funnel(charts.DEFAULT_FUNNEL_STEPS),
        "peer_stat": charts.sector_peer_stat(proposal.sector or "your sector", peer_count),
        "sector_fit": charts.sector_fit_bars(proposal.sector_fit),
    }
    return _env.get_template("proposal.html.j2").render(
        p=proposal, price_requested=price_requested, charts=ch,
    )


def render_pdf(html: str) -> bytes:
    return HTML(string=html).write_pdf()


def render_first_page_png(html: str, width: int = 600) -> bytes:
    pdf = render_pdf(html)
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    try:
        page = doc[0]
        zoom = width / page.rect.width
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        return pix.tobytes("png")
    finally:
        doc.close()
```

Note on `_chart_data`: `asyncio.get_event_loop().run_until_complete` fails if
called from inside a running loop (it is — `generate_proposal` is async). Since
the orchestrator already runs `render_pdf` via `asyncio.to_thread`, and
`render_html` is called on the main loop, **do not call the explorer here** —
just use the constants. Simplify `_chart_data` to:

```python
def _chart_data(proposal: Proposal) -> tuple[list[str], int]:
    return _DEFAULT_INDUSTRIES, len(proposal.peer_companies)
```

Delete the `try` block and the explorer imports. (The spec marks the explorer
call as optional polish; the constants keep the charts correct.)

- [ ] **Step 4: Rewrite `proposal.html.j2`**

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
  section { break-inside: avoid; }
  table { width: 100%; border-collapse: collapse; margin: 6px 0; }
  th, td { text-align: left; vertical-align: top; padding: 5px 8px; border: 1px solid #d7dbe6; font-size: 9.5pt; }
  th { background: #eef1f7; }
  ul { margin: 4px 0 4px 18px; padding: 0; }
  .pkg { background: #f6f8fc; border: 1px solid #d7dbe6; border-radius: 6px; padding: 10px 12px; }
  .pkg .name { font-weight: bold; color: #1b2a5b; }
  .peers { font-size: 9.5pt; }
  .chart { margin: 10px 0; }
  .footer { margin-top: 18px; padding-top: 8px; border-top: 1px solid #d7dbe6; font-size: 8pt; color: #6a7180; }
</style>
</head>
<body>
  <div class="cover">
    <h1>Tech Expo Gujarat 2026 &mdash; Proposal for {{ p.company }}</h1>
    <div class="sub">
      Prepared for {{ p.person }}{% if p.person_role %}, {{ p.person_role }}{% endif %}
      &nbsp;&middot;&nbsp; {{ p.sector or "&mdash;" }}
      &nbsp;&middot;&nbsp; {{ p.generated_on }} &nbsp;&middot;&nbsp; Version {{ p.version }} &nbsp;&middot;&nbsp; Ref {{ p.session_ref }}
    </div>
  </div>
  <div class="accent"></div>

  <section>
    <h2>Executive summary</h2>
    <p>{{ p.executive_summary or p.what_you_told_us }}</p>
  </section>

  <section>
    <h2>Your priorities</h2>
    <table>
      <tr><th>Your challenge</th><th>How Tech Expo Gujarat 2026 addresses it</th></tr>
      {% for pain in p.pains %}
      <tr><td>{{ pain.pain }}</td><td>{{ pain.teg_answer }}</td></tr>
      {% endfor %}
    </table>
  </section>

  {% if p.sector_fit %}
  <section>
    <h2>How your sector benefits</h2>
    <p>Which of TEG's levers matter most for a company in {{ p.sector or "your sector" }}:</p>
    <div class="chart">{{ charts.sector_fit | safe }}</div>
  </section>
  {% endif %}

  <section>
    <h2>The track record</h2>
    <ul>{% for pr in p.proof %}<li>{{ pr }}</li>{% endfor %}</ul>
    <div class="chart">{{ charts.growth | safe }}</div>
  </section>

  <section>
    <h2>Who's in the room</h2>
    <div class="chart">{{ charts.industry | safe }}</div>
    {% if p.peer_companies %}<p class="peers">Companies like yours taking part: {{ p.peer_companies | join(" &middot; ") }}</p>{% endif %}
    <div class="chart">{{ charts.peer_stat | safe }}</div>
  </section>

  {% if p.how_a_teg_plays_out %}
  <section>
    <h2>How a TEG plays out for you</h2>
    <ul>{% for step in p.how_a_teg_plays_out %}<li>{{ step }}</li>{% endfor %}</ul>
    <div class="chart">{{ charts.funnel | safe }}</div>
  </section>
  {% endif %}

  <section>
    <h2>Investment</h2>
    <div class="pkg">
      <div class="name">{{ p.recommended_package.name }}</div>
      <ul>{% for inc in p.recommended_package.includes %}<li>{{ inc }}</li>{% endfor %}</ul>
      {% if price_requested and p.recommended_package.price_line %}
      <div><strong>{{ p.recommended_package.price_line }}</strong></div>
      {% if p.recommended_package.payment_plan %}<div>Payment: {{ p.recommended_package.payment_plan }}</div>{% endif %}
      {% else %}
      <div>The team will share stall options and pricing tailored to your goals &mdash; just ask.</div>
      {% endif %}
    </div>
    {% if p.roi_framing %}<p>{{ p.roi_framing }}</p>{% endif %}
  </section>

  <section>
    <h2>Next steps</h2>
    <ul>{% for ns in p.next_steps %}<li>{{ ns }}</li>{% endfor %}</ul>
    <p><strong>Contact:</strong> {{ p.contact }}</p>
  </section>

  <div class="footer">
    Generated {{ p.generated_on }} &middot; Version {{ p.version }} &middot; Session ref {{ p.session_ref }}.
    {% if price_requested %}All figures are indicative and subject to confirmation at booking.{% endif %}
    This document is for information only &mdash; it is not a contract, a binding quote, or an offer requiring signature.
  </div>
</body>
</html>
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/python -m pytest tests/proposal/ -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/proposal/render.py app/proposal/templates/proposal.html.j2 tests/proposal/test_render.py
git commit -m "feat(proposal): charted 10-section template; price-conditional Investment section"
```

---

### Task 9: ProposalAgent — build the new fields, price-conditional, guardrailed

**Files:**
- Modify: `app/agents/proposal.py` (`build` signature, prompt, guardrail loop, trusted-field forcing)
- Test: `tests/agents/test_proposal_agent.py` (update + add)

**Interfaces:**
- Consumes: `check_message(..., price_ok=...)` (Task 3), `check_testimonial`, `check_overpromise` (Tasks 3/4); `Proposal` with new fields; `SectorFitRow`; `PROPOSAL_SAFE_SECTIONS["executive_summary"|"roi_framing"]` (Task 4).
- Produces: `ProposalAgent.build(self, *, intake, dossier, persona, transcript, learned_facts, session_ref, version, price_requested: bool = False) -> tuple[Proposal, list[str]]`.

- [ ] **Step 1: Update the tests**

```python
# tests/agents/test_proposal_agent.py  (add + adjust _good_proposal to include new fields)
from app.domain.schemas import SectorFitRow


def _good_proposal(**over):
    base = _EXISTING_GOOD_PROPOSAL_KWARGS  # keep the current dict, add:
    base.update(dict(
        executive_summary="DataZen Analytics builds BI dashboards and wants India-market clients.",
        how_a_teg_plays_out=["Pre-event matchmaking", "Day 1 demos", "Day 2 buyer meetings"],
        roi_framing="If one India-market engagement covers the cost several times over, it pays for itself.",
        sector_fit=[SectorFitRow(lever="Buyer access", weight=5), SectorFitRow(lever="Demos", weight=4),
                    SectorFitRow(lever="Meetings", weight=5), SectorFitRow(lever="Visibility", weight=3)],
    ))
    base.update(over)
    return Proposal(**base)


async def test_build_populates_new_fields():
    llm = FakeLLMClient(structured=[_good_proposal()])
    p, flags = await ProposalAgent(llm, explorer=_explorer()).build(
        intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[], learned_facts={"goal": "India clients"}, session_ref="x", version=1,
        price_requested=True,
    )
    assert p.executive_summary
    assert len(p.how_a_teg_plays_out) >= 3
    assert p.roi_framing
    assert 4 <= len(p.sector_fit) <= 6
    assert all(1 <= r.weight <= 5 for r in p.sector_fit)


async def test_build_omits_price_when_not_requested():
    llm = FakeLLMClient(structured=[_good_proposal()])
    p, _ = await ProposalAgent(llm, explorer=_explorer()).build(
        intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[], learned_facts={}, session_ref="x", version=1, price_requested=False,
    )
    assert p.recommended_package.price_line == ""
    assert p.recommended_package.payment_plan == ""


async def test_build_flags_overpromising_roi():
    bad = _good_proposal(roi_framing="You will close 5 deals and see a guaranteed ROI of 400%.")
    llm = FakeLLMClient(structured=[bad, bad])
    p, flags = await ProposalAgent(llm, explorer=_explorer()).build(
        intake=_intake(), dossier=_dossier(), persona="it_tech_service",
        transcript=[], learned_facts={}, session_ref="x", version=1, price_requested=True,
    )
    assert "overpromise" in flags
    assert "guaranteed" not in p.roi_framing.lower()
```

Keep `test_build_returns_clean_proposal`, `test_build_falls_back_on_repeated_violation`,
`test_build_survives_explorer_miss`, `test_pricing_fallback_table_has_all_personas`
— add `price_requested=True` to their `build(...)` calls.

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/agents/test_proposal_agent.py -q`
Expected: FAIL — `build() got an unexpected keyword argument 'price_requested'`

- [ ] **Step 3: Modify `build()`**

Signature: add `price_requested: bool = False`.

After computing `fallback_pkg`:

```python
        if price_requested:
            pkg_line = f"Recommended package: {fallback_pkg.model_dump()} — include its price_line and payment_plan."
        else:
            pkg_line = (
                f"Recommended package name: '{fallback_pkg.name}' with includes {fallback_pkg.includes}. "
                "Set recommended_package.price_line and payment_plan to EMPTY strings — state NO figures."
            )
```

Extend the `user` prompt (append before "Produce the Proposal."):

```python
            f"{pkg_line}\n"
            "Also produce:\n"
            "- executive_summary: 3-4 sentences (their role + company, their goal, why TEG fits, "
            "the headline recommendation)\n"
            "- how_a_teg_plays_out: 3-6 bullets walking the 3 days, tuned to their goal\n"
            "- roi_framing: a value paragraph with NO numbers and NO promised outcomes — phrase it "
            "'if a single engagement covers the investment many times over'\n"
            "- sector_fit: 4-6 {lever, weight} rows; weight 1-5 = how much each TEG lever matters "
            f"for the '{dossier.sector}' sector (use the pain library)\n"
```

After the LLM call, before the violation scan, force the sector_fit shape:

```python
        proposal.sector_fit = [
            SectorFitRow(lever=r.lever, weight=max(1, min(5, r.weight)))
            for r in proposal.sector_fit[:6]
        ]
        if not price_requested:
            proposal.recommended_package.price_line = ""
            proposal.recommended_package.payment_plan = ""
```

Extend `all_violations(p)` — add these text tuples:

```python
            texts.append(("executive_summary", p.executive_summary))
            texts.append(("roi_framing", p.roi_framing))
            for i, st in enumerate(p.how_a_teg_plays_out):
                texts.append((f"walkthrough::{i}", st))
```

Change the `check_message` calls in `all_violations` to pass `price_ok=price_requested`.
Add, after the `check_message` loop inside `all_violations`:

```python
            op = check_overpromise(p.roi_framing)
            if op:
                found.append(("roi_framing", op))
```

Make `all_violations` also run `check_testimonial` — since `build` is async and
`all_violations` is a nested sync def, hoist a one-shot check before the scan:

```python
        t_v = await check_testimonial(
            " ".join([proposal.what_you_told_us, proposal.lead_generation,
                      proposal.executive_summary, proposal.roi_framing,
                      *(pn.teg_answer for pn in proposal.pains)]),
            self.llm,
        )
```
and after `violations = all_violations(proposal)`:
```python
        if t_v:
            violations.append(("proof::0", t_v))
```
(re-run `t_v` after the regenerate too.)

In the safe-fallback section, add:

```python
            if "executive_summary" in bad:
                proposal.executive_summary = PROPOSAL_SAFE_SECTIONS["executive_summary"][persona]
            if "roi_framing" in bad:
                proposal.roi_framing = PROPOSAL_SAFE_SECTIONS["roi_framing"][persona]
```

Import: `from app.agents.guardrails import (PROPOSAL_SAFE_SECTIONS, check_message, check_overpromise, check_testimonial)` and `from app.domain.schemas import SectorFitRow`.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/agents/test_proposal_agent.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/agents/proposal.py tests/agents/test_proposal_agent.py
git commit -m "feat(proposal): build exec-summary/roi/walkthrough/sector-fit; price-conditional; overpromise + testimonial guards"
```

---

### Task 10: Orchestrator threading

**Files:**
- Modify: `app/orchestrator.py` (`_state_from_row`, `run_turn`, `generate_proposal`)
- Test: `tests/orchestrator/test_run_turn.py`, `tests/orchestrator/test_generate_proposal.py` (add assertions)

**Interfaces:**
- Consumes: `SessionRepo.update_state(..., price_requested=...)` (Task 2); `PersuasionTurn.asked_about_price` (Task 1); `ProposalAgent.build(..., price_requested=...)` (Task 9); `render_html(..., price_requested=...)` (Task 8).

- [ ] **Step 1: Write the failing tests**

```python
# tests/orchestrator/test_run_turn.py  (add)
async def test_run_turn_persists_price_requested(...):
    # seed a session (existing helper), then run a turn whose FakeLLM _Analysis has asked_about_price=True
    ...
    turn = await orch.run_turn(sid, "what does a stall cost?")
    async with SessionLocal() as s:
        cs = await SessionRepo(s).get(sid)
        assert cs.price_requested is True


# tests/orchestrator/test_generate_proposal.py  (add)
async def test_generate_proposal_passes_price_requested(...):
    # seed a session with price_requested=True on the row (SessionRepo.update_state), then:
    card = await orch.generate_proposal(sid)
    # assert the persisted proposal_json has a non-empty recommended_package.price_line
    ...
```

(Fill the `...` following the seeding helpers already in each file.)

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/orchestrator/test_run_turn.py tests/orchestrator/test_generate_proposal.py -q`
Expected: FAIL — `price_requested` not persisted / not passed

- [ ] **Step 3: Modify `_state_from_row`**

```python
            "needs_review": cs.needs_review,
            "price_requested": cs.price_requested,
```

- [ ] **Step 4: Modify `run_turn`**

In the `SessionRepo(s).update_state(...)` call add:

```python
                price_requested=turn.updated_state.get("price_requested", False),
```

- [ ] **Step 5: Modify `generate_proposal`**

After `learned = cs.learned_facts or {}`:

```python
            price_requested = bool(cs.price_requested)
```

The `self.proposal.build(...)` call gains `price_requested=price_requested`.
The `render_html(proposal)` call becomes `render_html(proposal, price_requested=price_requested)`.

- [ ] **Step 6: Run tests**

Run: `.venv/bin/python -m pytest tests/orchestrator/ -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/orchestrator.py tests/orchestrator/
git commit -m "feat(orchestrator): persist + thread price_requested through run_turn and generate_proposal"
```

---

### Task 11: Full verification + E2E + docs

**Files:**
- Modify: `tests/e2e/test_proposal_flow.py` (assert new fields + page count)
- Create: `tests/e2e/test_conversation_no_price.py` (`integration`)
- Modify: `README.md` (note the salesperson behaviour + price-conditional proposal)

- [ ] **Step 1: Extend the proposal E2E**

In `tests/e2e/test_proposal_flow.py`, after the proposal is generated, load
`proposal_json` from the DB and assert:

```python
    assert pj["executive_summary"]
    assert pj["sector_fit"] and 4 <= len(pj["sector_fit"]) <= 6
    assert len(pj["how_a_teg_plays_out"]) >= 3
    from app.proposal.render import render_pdf, render_html
    # the FakeLLM path already produced the Proposal; re-render to check pages
```
And bump the FakeLLM `Proposal` stub used in that file to include the four new
fields (mirror `_good_proposal` from `test_proposal_agent.py`).

- [ ] **Step 2: Write the no-price integration test**

```python
# tests/e2e/test_conversation_no_price.py
import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="needs GEMINI_API_KEY"),
]


async def test_agent_never_volunteers_price(tmp_path):
    from app.agents.persuasion import PersuasionAgent
    from app.domain.schemas import IntakeResult, ResearchDossier
    from app.llm.base import get_llm

    agent = PersuasionAgent(get_llm())
    dossier = ResearchDossier(relationship="cold", sector="AI & Machine Learning",
                              peer_companies=["ViitorCloud", "NeuraMonks"],
                              company_profile={"overview": "an AI tooling startup"})
    intake = IntakeResult(person_name="Sam", company_name_raw="Nova AI",
                          company_name_canonical="Nova AI", provided_fields=[],
                          intent_hint="exhibitor", consent_status="unknown")
    state = {"persona": "it_tech_service", "cta_status": "none", "learned_facts": {},
             "cta_detail": {}, "target_cta": "book_stall"}
    history = []
    for msg in ["tell me about tech expo gujarat",
                "who usually exhibits there?",
                "what would we get out of it?"]:
        turn = await agent.respond(intake=intake, dossier=dossier, state=state,
                                   history=history, prospect_message=msg)
        assert "₹" not in turn.reply_text, f"volunteered price: {turn.reply_text}"
        history += [{"role": "prospect", "content": msg},
                    {"role": "agent", "content": turn.reply_text}]
        state = turn.updated_state
```

- [ ] **Step 3: Run everything**

```bash
.venv/bin/python scripts/build_kb_facts.py --check
.venv/bin/python -m pytest -q
cd widget && npm test && cd ..
.venv/bin/ruff check app config tests scripts
```
Expected: all green; ruff no worse than baseline.

- [ ] **Step 4: Run the integration suite once**

```bash
GEMINI_API_KEY=... TAVILY_API_KEY=... .venv/bin/python -m pytest -q -m integration
```
Expected: the no-price conversation test + the earlier explorer/gemini tests pass. Record the outcome in the commit message.

- [ ] **Step 5: README**

Under a "Conversation behaviour" subsection: the chatbot acts as a consultative
TEG salesperson — discovery-first, never volunteers pricing (only on a direct
ask), offers a proposal only after learning the prospect's goal, target market
and rough scale. The proposal PDF shows pricing only when the prospect asked
about cost.

- [ ] **Step 6: Commit**

```bash
git add tests/e2e/ README.md
git commit -m "test(e2e): proposal has charts+new fields; live no-price conversation check; README"
```

- [ ] **Step 7: Finish the branch**

The full agentic-KB-explorer + salesperson work is now on `feat/teg-outreach-agent`.
Verify `python -m pytest -q` is green, then present merge options to the user
(merge to main / open a PR / keep iterating).

---

## Self-Review

**Spec coverage:**
- §3.1 salesperson `_system()` → Task 5. §3.2 `_Analysis` fields → Task 5. §3.3 `respond()` threading → Task 6. §3.4 `init()` → Task 6.
- §4.1 `price_ok` + `unsolicited_price` → Task 3. §4.2 `check_testimonial` → Task 4. §4.3 `overpromise` → Task 3 (`check_overpromise`), applied in Task 9. §4.4 fallbacks → Task 4 (safe sections) + Task 9 (loop).
- §5.1 schema → Task 1. §5.2 `build()` → Task 9. §5.3 `charts.py` → Task 7. §5.4 `render.py` → Task 8. §5.5 template → Task 8. §5.6 orchestrator → Task 10. §5.7 migration/model/repo → Task 2. §5.8 settings → Task 1.
- §6 tests → distributed across every task; §6.6 E2E → Task 11; §6.7 migration test → Task 2.
- §8 success criteria: 1–3 (Tasks 5–6), 4 (Tasks 8–9), 5 (Tasks 7–8), 6 (Tasks 3, 9), 7 (Task 4), 8 (Task 5), 9 (Task 11).

**Placeholder scan:** Task 2 Step 1 and Task 10 Step 1 leave `...` where the engineer must follow the file's existing seeding fixtures — these reference concrete helpers that exist in those test files; acceptable but flagged. Task 9 Step 1 `_EXISTING_GOOD_PROPOSAL_KWARGS` is a pointer to the current `_good_proposal` dict in that file. No "add error handling" / "TBD" placeholders in implementation steps.

**Type consistency:**
- `_system(persona, dossier, *, learned_facts, price_requested)` — same in Tasks 5, 6.
- `check_message(..., price_ok=False)` — Tasks 3, 6, 9.
- `check_testimonial(text, llm) -> GuardrailViolation | None` — Tasks 4, 6, 9.
- `check_overpromise(text) -> GuardrailViolation | None` — Task 3, used Task 9.
- `_Analysis.discovery` / `.asked_about_price` — Tasks 5, 6.
- `PersuasionTurn.asked_about_price` — Tasks 1, 6, 10.
- `SectorFitRow(lever, weight)` — Tasks 1, 7, 9.
- `Proposal` new fields — Tasks 1, 7 (chart input), 8 (template), 9 (build).
- `render_html(proposal, *, price_requested=False)` — Tasks 8, 10.
- `ProposalAgent.build(..., price_requested=False)` — Tasks 9, 10.
- `SessionRepo.update_state(..., price_requested=None)` — Tasks 2, 10.
- `ChatSession.price_requested` — Tasks 2, 10.
