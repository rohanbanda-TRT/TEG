"""Lightweight structured logging for the outreach pipeline.

Enable detail with env: LOG_LEVEL=DEBUG (per-step), or LOG_VERBOSE=true
(DEBUG + logs truncated prompt/response bodies).

Usage:
    from app.obs import get_logger, step, body
    log = get_logger("agent.research")
    with step(log, "company track", company="Acme"):
        ...
    log.debug("llm ask %s", body(prompt))
"""
from __future__ import annotations

import contextlib
import logging
import time

from config.settings import get_settings

_CONFIGURED = False


def configure() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    s = get_settings()
    level = logging.DEBUG if s.log_verbose else getattr(logging, s.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-5s %(name)s | %(message)s", "%H:%M:%S"))
    root = logging.getLogger("teg")
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure()
    return logging.getLogger(f"teg.{name}")


def body(text: str | None) -> str:
    """Truncate a prompt / response for logging; empty unless LOG_VERBOSE."""
    if not get_settings().log_verbose:
        return "(set LOG_VERBOSE=true to see body)"
    if text is None:
        return "None"
    n = get_settings().log_body_chars
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n] + f" …(+{len(text) - n} chars)"


@contextlib.contextmanager
def step(log: logging.Logger, name: str, **fields):
    kv = " ".join(f"{k}={v!r}" for k, v in fields.items())
    log.info("▶ %s %s", name, kv)
    t0 = time.perf_counter()
    try:
        yield
    except Exception as exc:  # log then re-raise
        log.warning("✗ %s failed after %.0fms: %s", name, (time.perf_counter() - t0) * 1000, exc)
        raise
    else:
        log.info("✓ %s (%.0fms)", name, (time.perf_counter() - t0) * 1000)
