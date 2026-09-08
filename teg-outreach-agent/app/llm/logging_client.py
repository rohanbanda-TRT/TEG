from __future__ import annotations

import time

from app.llm.base import BaseModelT, LLMClient, LLMMessage, ToolTurn
from app.obs import body, get_logger

_log = get_logger("llm")


class LoggingLLMClient(LLMClient):
    """Wraps a real LLMClient, logging every call (and bodies when LOG_VERBOSE)."""

    def __init__(self, inner: LLMClient) -> None:
        self._inner = inner
        self._n = 0

    async def generate(
        self, *, system: str, messages: list[LLMMessage],
        model: str | None = None, max_tokens: int = 2048, temperature: float = 0.3,
    ) -> str:
        self._n += 1
        call = self._n
        _log.info("→ generate #%d  model=%s  msgs=%d  max_tokens=%d", call, model or "default",
                  len(messages), max_tokens)
        _log.debug("   #%d system: %s", call, body(system))
        _log.debug("   #%d user:   %s", call, body(messages[-1]["content"] if messages else ""))
        t0 = time.perf_counter()
        out = await self._inner.generate(
            system=system, messages=messages, model=model,
            max_tokens=max_tokens, temperature=temperature,
        )
        _log.info("← generate #%d  %.0fms  %d chars", call, (time.perf_counter() - t0) * 1000, len(out))
        _log.debug("   #%d reply:  %s", call, body(out))
        return out

    async def generate_structured(
        self, *, system: str, messages: list[LLMMessage],
        schema: type[BaseModelT], model: str | None = None,
    ) -> BaseModelT:
        self._n += 1
        call = self._n
        _log.info("→ structured #%d  schema=%s  model=%s  msgs=%d", call, schema.__name__,
                  model or "default", len(messages))
        _log.debug("   #%d system: %s", call, body(system))
        _log.debug("   #%d user:   %s", call, body(messages[-1]["content"] if messages else ""))
        t0 = time.perf_counter()
        out = await self._inner.generate_structured(
            system=system, messages=messages, schema=schema, model=model,
        )
        _log.info("← structured #%d  %.0fms  -> %s", call, (time.perf_counter() - t0) * 1000, schema.__name__)
        _log.debug("   #%d result: %s", call, body(out.model_dump_json()))
        return out

    async def generate_with_tools(
        self, *, system: str, messages: list, tools: list[dict],
        model: str | None = None, max_tokens: int = 2048, temperature: float = 0.2,
    ) -> ToolTurn:
        self._n += 1
        call = self._n
        names = [t.get("name") for t in tools]
        _log.info("→ tools #%d  model=%s  msgs=%d  tools=%s", call, model or "default",
                  len(messages), names)
        _log.debug("   #%d system: %s", call, body(system))
        _log.debug("   #%d msgs:   %s", call, body(str(messages[-1]) if messages else ""))
        t0 = time.perf_counter()
        out = await self._inner.generate_with_tools(
            system=system, messages=messages, tools=tools, model=model,
            max_tokens=max_tokens, temperature=temperature,
        )
        _log.info("← tools #%d  %.0fms  tool_calls=%s  text=%d chars", call,
                  (time.perf_counter() - t0) * 1000,
                  [c.name for c in out.tool_calls], len(out.text))
        _log.debug("   #%d out: %s", call, body(out.model_dump_json()))
        return out
