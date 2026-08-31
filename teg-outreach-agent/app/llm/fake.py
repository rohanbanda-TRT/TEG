from __future__ import annotations

from app.llm.base import BaseModelT, LLMClient, LLMMessage


class FakeLLMClient(LLMClient):
    def __init__(
        self,
        responses: list[str] | None = None,
        structured: list | None = None,
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
