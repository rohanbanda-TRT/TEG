"""Exact-match KB facts for the deterministic guardrail layer.

Reads the committed ``facts.json`` snapshot produced by
``scripts/build_kb_facts.py``. Zero latency, fully deterministic, no markdown
parsing at runtime — guardrails must never depend on a live LLM call.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_PATH = Path(__file__).with_name("facts.json")


@dataclass(frozen=True)
class Testimonial:
    name: str
    role: str
    quote: str


@dataclass(frozen=True)
class Facts:
    generated_from_kb_at: str
    cleared_testimonials: tuple[Testimonial, ...]
    exhibitor_names: frozenset[str]
    exhibitor_names_lower: frozenset[str]


@lru_cache
def load() -> Facts:
    raw = json.loads(_PATH.read_text("utf-8"))
    names = frozenset(raw["exhibitor_names"])
    return Facts(
        generated_from_kb_at=raw["generated_from_kb_at"],
        cleared_testimonials=tuple(Testimonial(**t) for t in raw["cleared_testimonials"]),
        exhibitor_names=names,
        exhibitor_names_lower=frozenset(n.lower() for n in names),
    )
