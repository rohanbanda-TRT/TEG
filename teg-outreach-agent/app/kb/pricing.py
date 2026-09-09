"""Exact-match KB pricing for ProposalAgent — sibling to app/kb/facts.py.

Reads the committed ``pricing.json`` snapshot produced by
``scripts/build_kb_pricing.py``. Zero latency, fully deterministic, no
markdown parsing at runtime. Replaces the old hand-typed
`_PRICING_BY_PERSONA` dict in app/agents/proposal.py, which independently
duplicated numbers that already lived in
teg-kb-agent/knowledge_base/pricing/pricing_and_packages.md (see
docs/superpowers/specs/2026-09-10-verification-harness-and-graph-design.md
§3.2.1).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.domain.schemas import Persona, ProposalPackage

_PATH = Path(__file__).with_name("pricing.json")


@lru_cache
def load_pricing() -> dict[Persona, list[ProposalPackage]]:
    raw = json.loads(_PATH.read_text("utf-8"))
    return {
        persona: [ProposalPackage.model_validate(pkg) for pkg in ladder]
        for persona, ladder in raw["tier_ladders"].items()
    }
