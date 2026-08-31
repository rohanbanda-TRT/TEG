from __future__ import annotations

from google import genai
from google.genai import types

from app.llm.base import BaseModelT, LLMClient, LLMMessage
from config.settings import get_settings


def _to_contents(messages: list[LLMMessage]) -> list[types.Content]:
    role_map = {"user": "user", "assistant": "model"}
    return [
        types.Content(
            role=role_map[m["role"]],
            parts=[types.Part.from_text(text=m["content"])],
        )
        for m in messages
    ]


class GeminiClient(LLMClient):
    def __init__(self) -> None:
        s = get_settings()
        self._client = genai.Client(api_key=s.gemini_api_key)
        self._model_main = s.llm_model_main

    async def generate(
        self, *, system: str, messages: list[LLMMessage],
        model: str | None = None, max_tokens: int = 1024, temperature: float = 0.3,
    ) -> str:
        resp = await self._client.aio.models.generate_content(
            model=model or self._model_main,
            contents=_to_contents(messages),
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        )
        return (resp.text or "").strip()

    async def generate_structured(
        self, *, system: str, messages: list[LLMMessage],
        schema: type[BaseModelT], model: str | None = None,
    ) -> BaseModelT:
        resp = await self._client.aio.models.generate_content(
            model=model or self._model_main,
            contents=_to_contents(messages),
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        parsed = getattr(resp, "parsed", None)
        if parsed is not None and not isinstance(parsed, (str, bytes)):
            if isinstance(parsed, schema):
                return parsed
            return schema.model_validate(parsed if isinstance(parsed, dict) else parsed.__dict__)
        return schema.model_validate_json(resp.text)
