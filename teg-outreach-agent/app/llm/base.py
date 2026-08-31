from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal, TypedDict, TypeVar

from pydantic import BaseModel

from config.settings import get_settings

BaseModelT = TypeVar("BaseModelT", bound=BaseModel)


class LLMMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str


class LLMClient(ABC):
    @abstractmethod
    async def generate(
        self, *, system: str, messages: list[LLMMessage],
        model: str | None = None, max_tokens: int = 2048, temperature: float = 0.3,
    ) -> str: ...

    @abstractmethod
    async def generate_structured(
        self, *, system: str, messages: list[LLMMessage],
        schema: type[BaseModelT], model: str | None = None,
    ) -> BaseModelT: ...


def get_llm() -> LLMClient:
    provider = get_settings().llm_provider
    if provider == "gemini":
        from app.llm.gemini_client import GeminiClient
        return GeminiClient()
    if provider == "anthropic":
        from app.llm.anthropic_client import AnthropicClient
        return AnthropicClient()
    raise ValueError(f"unknown llm_provider: {provider!r}")
