"""Claude-backed prospect research, as a drop-in `ResearchTool`.

Replaces the Tavily-search-then-scrape pair with one call that lets Claude run
its own WebSearch/WebFetch loop and return firmographic facts directly.

Unlike the other Claude-backed agents, the research method is authored as a
**discoverable skill** at ``.claude/skills/teg-research/`` rather than loaded
into the prompt. Claude finds it via the ``Skill`` tool and applies it itself
— the ``description`` in its frontmatter is what makes it fire. The `user`
prompt here is just the subject name plus the fields we need.

Tools: ``Skill``, ``WebSearch``, ``WebFetch`` — never Read, Write, Bash or
Edit. The input is a company/person name from the inquiry form, not free
prospect prose, and the skill tells Claude to treat fetched page content as
data, never as instructions.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from app.claude.cli import ClaudeCli
from app.obs import get_logger
from app.research.tools import ResearchQuery, ResearchResult, ResearchTool
from config.settings import get_settings

_log = get_logger("claude.research")

# Repo root — where `.claude/skills/` lives, so the CLI's `project` setting
# source discovers the skill.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILL_FILE = _REPO_ROOT / ".claude" / "skills" / "teg-research" / "SKILL.md"

_SYSTEM = (
    "You research a Tech Expo Gujarat 2026 prospect for our outreach team. "
    "Use the teg-research skill — it defines exactly what to look for, how to "
    "budget your searches, and how to judge what you find. Return only the "
    "JSON the schema asks for."
)


class _Findings(BaseModel):
    """Mirrors research.py's _Synthesis, plus provenance."""
    sector: str | None = None
    company_size: str | None = None
    hq: str | None = None
    founder: str | None = None
    designation: str | None = None
    seniority: str | None = None
    is_technical: bool | None = None
    person_company_match: bool | None = None
    source_url: str | None = None
    confidence: float = 0.5
    notes: str = ""


_FIELD_NAMES = (
    "sector", "company_size", "hq", "founder",
    "designation", "seniority", "is_technical", "person_company_match",
)


class ClaudeWebSearch(ResearchTool):
    name = "web"

    def __init__(self, cli: ClaudeCli | None = None) -> None:
        s = get_settings()
        self._cli = cli or ClaudeCli()
        self._model = s.claude_cli_model
        self._timeout_s = s.claude_cli_timeout_s

    async def lookup(self, query: ResearchQuery) -> ResearchResult:
        if not _SKILL_FILE.is_file():
            _log.warning("teg-research skill missing at %s", _SKILL_FILE)
            return ResearchResult(available=False, tool_name=self.name,
                                  notes="teg-research skill missing")

        subject_line = (
            f"Company to research: {query.subject}"
            if query.track == "company"
            else f"Person to research: {query.subject}"
        )
        user = (
            f"{subject_line}\n"
            f"Context we already have: {query.context or '(none)'}\n"
            f"Fields most needed this call: {', '.join(query.want) or 'sector'}\n\n"
            "Research them and return what you can actually support. Leave a "
            "field null rather than guessing it."
        )

        if not self._cli.api_key:
            from app.api.claude_conn import get_api_key

            self._cli.api_key = get_api_key() or ""

        try:
            result = await self._cli.generate(
                model=self._model,
                system_prompt=_SYSTEM,
                user_prompt=user,
                json_schema=_Findings.model_json_schema(),
                cwd=str(_REPO_ROOT),  # so `.claude/skills/` is discovered
                # `Skill` lets Claude invoke teg-research itself; the web tools
                # must be pre-approved too, or dontAsk denies them at call time.
                tools=["Skill", "WebSearch", "WebFetch"],
                allowed_tools=["Skill", "WebSearch", "WebFetch"],
                timeout_s=self._timeout_s,
            )
        except RuntimeError as exc:
            _log.warning("[%s] claude research failed: %s", query.track, exc)
            return ResearchResult(available=False, tool_name=self.name, notes=str(exc))

        found = _Findings.model_validate(result.data)

        # Drop nulls so the dossier never carries a "None" string, and render
        # booleans lowercase for the same reason.
        fields: dict[str, str] = {}
        for name in _FIELD_NAMES:
            value = getattr(found, name)
            if value is None:
                continue
            fields[name] = str(value).lower() if isinstance(value, bool) else str(value)

        conf = max(0.0, min(1.0, found.confidence))
        _log.info("[%s] claude research  subject=%r  fields=%s  conf=%.2f  cost=%s",
                  query.track, query.subject, sorted(fields), conf, result.cost_usd)

        return ResearchResult(
            available=True,
            fields=fields,
            confidence={k: conf for k in fields},
            source_url=found.source_url,
            tool_name=self.name,
            notes=found.notes,
        )
