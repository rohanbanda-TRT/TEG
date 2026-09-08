"""Agentic KB explorer — an LLM tool-use loop over the read-only KB filesystem.

Navigates the TEG knowledge base the way Claude Code explores a repo: read
INDEX.md, open the specific profile, follow cross-references. No regex parsing of
KB markdown — the model reads the files.
"""
from __future__ import annotations

import asyncio
import json

from pydantic import BaseModel, ValidationError

from app.kb.fs_tools import TOOL_SPECS, dispatch
from app.llm.base import LLMClient
from app.obs import get_logger
from config.settings import get_settings

_log = get_logger("kb.explorer")

_SYSTEM = """You explore a READ-ONLY knowledge base about Tech Expo Gujarat 2026 \
(TEG) to answer a research goal. You have the WHOLE knowledge base available \
through three tools — explore it the way an engineer explores an unfamiliar \
repository: look around, follow clues, open what matches.

  Tools:
  - list_dir(path)      — see what is in a folder
  - grep(pattern, path) — find which file mentions a name/term (locator only)
  - read_file(path)     — read a file's full contents

LAYOUT (where to look):
  knowledge_base/
  ├── INDEX.md ......................... master map, if you get lost
  ├── event_overview/event_info.md ..... dates, scale, "Industries represented"
  ├── event_goals_and_problem.md ....... TEG goals, mechanism, evidence,
  │                                      per-persona pain library
  ├── sector_wise_participation.md ..... "### Sector N: <name>" headings, each
  │                                      with that sector's company table
  │                                      (use this for sector + peers)
  ├── exhibitors/companies/ ............ one .md file per company (~133)
  ├── organizers_team/ ................. one .md file per TEG organizer (~24)
  ├── speakers/individuals/ ............ one .md file per speaker (~35)
  ├── pricing/, testimonials/, venue_logistics/, registration/, faq/,
  │   past_editions/, venture_capital/

HOW TO FIND A COMPANY:
  1. list_dir("exhibitors/companies") and scan the filenames for one that
     matches the company (files are lowercase, words joined by "_").
  2. If nothing obvious, grep the distinctive part of the name across the KB
     (e.g. grep("Itorix", ".")) to see which file, if any, mentions it.
  3. read_file the file you found. If no file mentions the company at all,
     it is not in this KB — set found=false (still return a best-guess sector
     if event_info.md / sector_wise_participation.md make one obvious).

HOW TO FIND A PERSON:
  Try list_dir("organizers_team") then list_dir("speakers/individuals") and
  scan for a matching filename; or grep their name. A founder with no file of
  their own is usually described inside their company's file.

SECTOR & PEERS: read_file sector_wise_participation.md; pick the
"### Sector N: <name>" heading whose company table best fits; the other
companies in that table are the peers.

NEVER answer from a grep snippet — grep only tells you WHICH file; then
read_file it.

When done, reply with a JSON object ONLY (no prose, no markdown fence):
{"found": bool, "summary": str, "facts": {"<key>": "<value>"}, \
"sources": ["<relpath>"], "confidence": 0.0-1.0}

Rules:
- Use only what you actually read. Never guess a fact.
- found=false only when the subject has no node in this KB at all.
- facts MUST hold every key the goal asked for that you could find; omit a key
  you could not find. Every value is a string.
- sources lists the files you actually read."""


class ExploreResult(BaseModel):
    found: bool = False
    summary: str = ""
    facts: dict[str, str] = {}
    sources: list[str] = []
    confidence: float = 0.0


def default_explorer(llm: "LLMClient"):
    """The KB explorer the pipeline should use, per config.

    Returns a ClaudeKBExplorer (real Read/Grep/Glob over the KB) when the CLI
    backend is on, else the LLM-tool-loop KBExplorer. Both expose
    ``explore(goal) -> ExploreResult``.
    """
    if get_settings().claude_cli_enabled:
        from app.claude.kb_explorer import ClaudeKBExplorer

        return ClaudeKBExplorer()
    return KBExplorer(llm)


class KBExplorer:
    def __init__(self, llm: LLMClient, *, model: str | None = None) -> None:
        self._llm = llm
        self._model = model or get_settings().kb_explore_model

    async def explore(self, goal: str) -> ExploreResult:
        max_steps = get_settings().kb_explore_max_steps
        messages: list = [{"role": "user", "content": goal}]
        _log.info("explore start  goal=%r", goal[:160])
        text = ""
        for step in range(max_steps):
            last = step == max_steps - 1
            sys = _SYSTEM + (
                "\n\nYou have used all your tool calls. Give the final JSON answer now; "
                "do NOT call tools."
                if last
                else ""
            )
            turn = await self._llm.generate_with_tools(
                system=sys, messages=messages, tools=TOOL_SPECS, model=self._model,
            )
            # A turn may carry a complete JSON answer even alongside tool calls;
            # honour the answer if it parses.
            direct = _parse_json_answer(turn.text)
            if direct is not None:
                return self._done(direct)
            if turn.tool_calls and not last:
                # echo the model's own turn back verbatim (carries thought
                # signatures on thinking models), then one tool result per call
                messages.append(
                    {"role": "assistant", "raw": turn.raw}
                    if turn.raw is not None
                    else {"role": "assistant", "tool_calls": [c.model_dump() for c in turn.tool_calls]}
                )
                for call in turn.tool_calls:
                    out = dispatch(call.name, call.args)
                    _log.info("  step %d  %s(%s) -> %d chars", step, call.name, call.args, len(out))
                    messages.append({
                        "role": "tool", "tool_call_id": call.id, "name": call.name, "content": out,
                    })
                continue
            text = turn.text
            break
        return self._done(await self._parse(messages, text))

    def _done(self, result: ExploreResult) -> ExploreResult:
        _log.info(
            "explore done  found=%s  conf=%.2f  facts=%s  sources=%s",
            result.found, result.confidence, list(result.facts), result.sources,
        )
        return result

    async def _parse(self, messages: list, text: str) -> ExploreResult:
        direct = _parse_json_answer(text)
        if direct is not None:
            return direct
        try:
            convo = messages + [
                {"role": "assistant", "content": text or "(no answer yet)"},
                {"role": "user", "content": (
                    "Give the final answer now as a JSON object with keys found, summary, "
                    "facts, sources, confidence — based only on the files read above."
                )},
            ]
            return await self._llm.generate_structured(
                system="Return the ExploreResult that this exploration arrived at.",
                messages=convo, schema=ExploreResult, model=self._model,
            )
        except Exception as exc:  # noqa: BLE001 — parse failure must not break the pipeline
            _log.warning("explore parse failed: %s", exc)
            return ExploreResult()


def _parse_json_answer(text: str) -> ExploreResult | None:
    """Parse a model turn that is (or contains) a complete ExploreResult JSON object."""
    if not text or "{" not in text:
        return None
    raw = text[text.index("{") : text.rindex("}") + 1] if "}" in text else text
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, dict) or "found" not in data:
        return None
    try:
        return ExploreResult.model_validate(data)
    except ValidationError:
        return None


async def _timed_explore(explorer: KBExplorer, goal: str) -> ExploreResult:
    """Run explore() under the wall-clock cap; return an empty result on timeout."""
    try:
        return await asyncio.wait_for(
            explorer.explore(goal), timeout=get_settings().kb_explore_timeout_s
        )
    except TimeoutError:
        _log.warning("explore timed out after %ss", get_settings().kb_explore_timeout_s)
        return ExploreResult()
