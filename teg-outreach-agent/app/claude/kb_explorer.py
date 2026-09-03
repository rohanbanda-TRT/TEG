"""Claude-backed KB explorer — a drop-in for `KBExplorer`.

Claude Code has real Read/Grep/Glob, so there is no hand-rolled tool loop,
no thought-signature plumbing, and no JSON-answer scraping: one `generate()`
call with the KB mounted read-only, returning an ExploreResult directly.

The KB is trusted content we ship, and the tools are read-only (Read/Grep/Glob
— never Write/Edit/Bash), so this is a safe session to give filesystem access.
The research goal is built by us from a company/person name, not free prospect
prose.
"""
from __future__ import annotations

from pathlib import Path

from app.claude.cli import ClaudeCli
from app.claude.prompt_builder import render_skill
from app.claude.skill_loader import load_skill
from app.kb.explorer import ExploreResult
from app.obs import get_logger
from config.settings import get_settings

_log = get_logger("claude.kb")


class ClaudeKBExplorer:
    """Same `explore(goal) -> ExploreResult` contract as `KBExplorer`."""

    def __init__(self, cli: ClaudeCli | None = None, *, kb_path: str | None = None) -> None:
        s = get_settings()
        self._cli = cli or ClaudeCli()
        self._model = s.claude_cli_model
        self._timeout_s = s.claude_cli_timeout_s
        self._skills_path = s.skills_path
        self._kb_path = str(Path(kb_path or s.kb_path).resolve())

    async def explore(self, goal: str) -> ExploreResult:
        _log.info("explore start  goal=%r", goal[:160])
        try:
            system = render_skill(load_skill(self._skills_path, "teg-kb-lookup"))
        except FileNotFoundError:
            _log.warning("teg-kb-lookup skill missing")
            return ExploreResult()

        if not self._cli.api_key:
            from app.api.claude_conn import get_api_key

            self._cli.api_key = get_api_key() or ""

        user = (
            f"Knowledge base is mounted at: {self._kb_path}\n\n"
            f"Research goal:\n{goal}\n\n"
            "Explore the KB and return what the files actually support."
        )

        try:
            result = await self._cli.generate(
                model=self._model,
                system_prompt=system,
                user_prompt=user,
                json_schema=ExploreResult.model_json_schema(),
                cwd=str(Path(self._skills_path).resolve().parent),
                tools=["Read", "Grep", "Glob"],
                allowed_tools=["Read", "Grep", "Glob"],
                add_dirs=[self._kb_path],
                timeout_s=self._timeout_s,
            )
        except RuntimeError as exc:
            _log.warning("claude KB explore failed: %s", exc)
            return ExploreResult()

        data = dict(result.data or {})
        # facts values must all be strings (the schema says str, but coerce
        # defensively — a model may return a bare int for a count).
        facts = {k: str(v) for k, v in (data.get("facts") or {}).items()}
        out = ExploreResult(
            found=bool(data.get("found", False)),
            summary=str(data.get("summary", "")),
            facts=facts,
            sources=[str(s) for s in (data.get("sources") or [])],
            confidence=float(data.get("confidence", 0.0) or 0.0),
        )
        _log.info(
            "explore done  found=%s  conf=%.2f  facts=%s  sources=%s  cost=%s",
            out.found, out.confidence, list(out.facts), out.sources, result.cost_usd,
        )
        return out
