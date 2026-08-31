from __future__ import annotations

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
        model: str | None = None, max_tokens: int = 2048, temperature: float = 0.3,
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
