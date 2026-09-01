from __future__ import annotations

import time

from app.llm.base import BaseModelT, LLMClient, LLMMessage
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
