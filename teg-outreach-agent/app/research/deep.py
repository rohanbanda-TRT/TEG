"""Background deep-research pass — multi-source account diligence beyond
today's lightweight ResearchAgent pass. See
docs/superpowers/specs/2026-09-09-background-deep-research-design.md §3.1.

One `ClaudeCli.generate()` call, `tools=["WebSearch", "WebFetch"]` — the
same one-shot harness shape as `app/claude/web_research.py` and
`app/verify/claude_verifier.py`, not a hand-rolled Python loop. KBExplorer's
loop exists because ITS tools are custom in-process Python functions with no
native CLI equivalent; WebSearch/WebFetch are native `claude` CLI tools that
already run their own internal agentic loop one process down — a second
Python-level loop around them would duplicate one that already exists.

This module never raises: it always runs detached from a request/response
cycle (a FastAPI BackgroundTasks call — see Orchestrator.run_deep_research),
so no caller is ever in a position to usefully react to an exception. A
failure here just means the deep brief doesn't land; the light dossier
remains authoritative either way.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from app.claude.cli import ClaudeCli
from app.claude.prompt_builder import render_skill
from app.claude.skill_loader import load_skill
from app.obs import get_logger
from config.settings import get_settings

_log = get_logger("research.deep")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILLS_DIR = _REPO_ROOT / ".claude" / "skills"

_SYSTEM_PREFIX = (
    "You compile a deep account-research brief on a Tech Expo Gujarat "
    "prospect company, for the outreach team's internal use. Follow the "
    "teg-deep-research skill below for what to look for, how to budget "
    "your searches, and how to judge what you find. Return only the JSON "
    "the schema asks for."
)


class ReviewTheme(BaseModel):
    theme: str
    mention_count: int | None = None


class DeepFindings(BaseModel):
    """Superset of ResearchDossier — fields today's lightweight pass never
    gathers. Stored alongside (not replacing) the light dossier in
    company_briefs.deep_findings_json."""

    funding_status: str | None = None
    growth_trend: str | None = None
    competitive_position: str | None = None
    named_clients: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    review_sentiment_themes: list[ReviewTheme] = Field(default_factory=list)
    notable_visibility: str | None = None
    sources: list[str] = Field(default_factory=list)
    notes: str = ""


async def deep_research(
    company_name: str, person_name: str, *, cli: ClaudeCli | None = None,
) -> DeepFindings | None:
    """One-shot deep pass. Returns None (never raises) on any failure."""
    s = get_settings()
    cli = cli or ClaudeCli()
    if not cli.api_key:
        from app.api.claude_conn import get_api_key

        cli.api_key = get_api_key() or ""

    try:
        skill = load_skill(str(_SKILLS_DIR), "teg-deep-research")
    except FileNotFoundError:
        _log.warning("teg-deep-research skill missing; skipping deep research")
        return None
    system = _SYSTEM_PREFIX + "\n\n" + render_skill(skill)
    user = (
        f"Company: {company_name}\n"
        f"Enquirer: {person_name}\n\n"
        "Compile the deepest account-research brief you can support with "
        "real, cited sources. Leave a field null/empty rather than guessing."
    )
    try:
        result = await cli.generate(
            model=s.claude_cli_model,
            system_prompt=system,
            user_prompt=user,
            json_schema=DeepFindings.model_json_schema(),
            cwd=str(_REPO_ROOT),
            tools=["WebSearch", "WebFetch"],
            allowed_tools=["WebSearch", "WebFetch"],
            timeout_s=s.deep_research_timeout_s,
        )
    except RuntimeError as exc:
        _log.warning("[%s] deep research failed: %s", company_name, exc)
        return None

    _log.info("[%s] deep research done  cost=%s  tool_calls=%d",
              company_name, result.cost_usd, result.tool_calls)
    return DeepFindings.model_validate(result.data)
