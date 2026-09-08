"""Replay a recorded KBExplorer session for tests.

The transcript stores only the MODEL's outputs (tool-call decisions + the final
answer) — never tool results. On replay the real fs_tools run against the live
KB, so a moved/renamed KB file makes the test fail loudly.
"""
from __future__ import annotations

import json

from app.llm.base import BaseModelT, LLMClient, LLMMessage, ToolCall, ToolTurn


class ReplayLLMClient(LLMClient):
    def __init__(self, transcript: dict) -> None:
        self._turns: list[dict] = list(transcript.get("model_turns", []))
        self._final: str | None = transcript.get("final")
        for t in self._turns:
            if "final" in t and self._final is None:
                self._final = t["final"]

    async def generate(
        self, *, system: str, messages: list[LLMMessage],
        model: str | None = None, max_tokens: int = 2048, temperature: float = 0.3,
    ) -> str:
        raise NotImplementedError("ReplayLLMClient does not support generate()")

    async def generate_with_tools(
        self, *, system: str, messages: list, tools: list[dict],
        model: str | None = None, max_tokens: int = 2048, temperature: float = 0.2,
    ) -> ToolTurn:
        assert self._turns, "ReplayLLMClient: model_turns exhausted"
        t = self._turns.pop(0)
        if "final" in t:
            return ToolTurn(text=t["final"])
        return ToolTurn(tool_calls=[ToolCall(**c) for c in t.get("tool_calls", [])])

    async def generate_structured(
        self, *, system: str, messages: list, schema: type[BaseModelT],
        model: str | None = None,
    ) -> BaseModelT:
        assert self._final is not None, "ReplayLLMClient: no final answer in transcript"
        return schema.model_validate(json.loads(self._final))
