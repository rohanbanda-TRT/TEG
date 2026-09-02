"""Run a live KBExplorer.explore() and save the MODEL TURNS (not tool output).

    GEMINI_API_KEY=... python scripts/record_kb_transcript.py known_it_service \
        "Profile the company Third Rock Techkno. Return facts: sector, website, teg_history."

The transcript stores only what the model produced (its tool-call decisions and
its final answer) plus the parsed `expected` result. On replay, fs_tools run
against the live KB, so a moved/renamed KB file makes the replay test fail loud.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.kb.explorer as explorer_mod
from app.kb import fs_tools
from app.kb.explorer import KBExplorer
from app.llm.base import LLMClient, ToolTurn
from app.llm.gemini_client import GeminiClient

_DIR = Path(__file__).resolve().parents[1] / "tests" / "kb" / "transcripts"


class _Recording(LLMClient):
    """Wraps a real client, capturing every model turn for the transcript."""

    def __init__(self, inner: LLMClient) -> None:
        self._inner = inner
        self.turns: list[dict] = []
        self.final: str | None = None

    async def generate(self, **kw):
        raise NotImplementedError

    async def generate_with_tools(self, **kw) -> ToolTurn:
        turn = await self._inner.generate_with_tools(**kw)
        if turn.tool_calls:
            self.turns.append(
                {"tool_calls": [{"id": tc.id, "name": tc.name, "args": tc.args}
                                for tc in turn.tool_calls]}
            )
        else:
            self.turns.append({"final": turn.text})
            self.final = turn.text
        return turn  # keep .raw so the live loop still completes

    async def generate_structured(self, **kw):
        out = await self._inner.generate_structured(**kw)
        self.final = out.model_dump_json()
        return out


async def _main(name: str, goal: str) -> None:
    # wrap dispatch so we can record which reads actually succeeded
    reads_ok: list[str] = []
    reads_missed: list[str] = []
    real_dispatch = fs_tools.dispatch

    def _tracking_dispatch(tool: str, args: dict) -> str:
        out = real_dispatch(tool, args)
        if tool == "read_file" and "path" in args:
            (reads_missed if out.startswith("error:") else reads_ok).append(args["path"])
        return out

    explorer_mod.dispatch = _tracking_dispatch
    try:
        rec = _Recording(GeminiClient())
        result = await KBExplorer(rec).explore(goal)
    finally:
        explorer_mod.dispatch = real_dispatch

    _DIR.mkdir(parents=True, exist_ok=True)
    path = _DIR / f"{name}.json"
    path.write_text(
        json.dumps(
            {
                "goal": goal,
                "model_turns": rec.turns,
                "final": rec.final,
                "expected": result.model_dump(),
                "reads_ok": sorted(set(reads_ok)),
                "reads_missed": sorted(set(reads_missed)),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    print(f"wrote {path}  ({len(rec.turns)} turns, found={result.found}, "
          f"reads_ok={len(set(reads_ok))}, facts={list(result.facts)})")


if __name__ == "__main__":
    asyncio.run(_main(sys.argv[1], sys.argv[2]))
