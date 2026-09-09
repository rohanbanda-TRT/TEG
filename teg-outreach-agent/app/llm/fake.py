from __future__ import annotations

from app.llm.base import BaseModelT, LLMClient, LLMMessage, ToolTurn


class FakeLLMClient(LLMClient):
    def __init__(
        self,
        responses: list[str] | None = None,
        structured: list | None = None,
        tool_turns: list[ToolTurn] | None = None,
    ) -> None:
        self._responses = list(responses or [])
        self._structured = list(structured or [])
        self._tool_turns = list(tool_turns or [])
        self.calls: list[dict] = []

    async def generate(
        self, *, system: str, messages: list[LLMMessage],
        model: str | None = None, max_tokens: int = 2048, temperature: float = 0.3,
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
        # Prefer the first queued item whose type matches the requested schema;
        # this lets a test queue e.g. a _PersonaChoice and a _Analysis in any order.
        for i, item in enumerate(self._structured):
            if isinstance(item, schema):
                return self._structured.pop(i)
        # No exact match. If the schema is fully optional (every field has a
        # default), prefer a safe zero-value instance over silently consuming
        # an unrelated queued item meant for a different schema — this is
        # what lets a new, best-effort structured call (e.g. an agent's
        # extract_conversation_signals-style extraction) get added to a
        # pipeline without every existing test needing to also stub it.
        try:
            return schema()
        except Exception:
            pass
        # Schema has required fields and nothing queued matches -> FIFO,
        # same as before.
        return self._structured.pop(0)

    async def generate_with_tools(
        self, *, system: str, messages: list, tools: list[dict],
        model: str | None = None, max_tokens: int = 2048, temperature: float = 0.2,
    ) -> ToolTurn:
        self.calls.append({"kind": "tools", "system": system, "messages": messages})
        assert self._tool_turns, "FakeLLMClient.generate_with_tools called with empty queue"
        return self._tool_turns.pop(0)
