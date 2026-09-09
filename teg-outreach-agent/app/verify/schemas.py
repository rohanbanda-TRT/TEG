"""Schemas for the TEG-claim verification harness. See
docs/superpowers/specs/2026-09-10-verification-harness-and-graph-design.md §3.1.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class Claim(BaseModel):
    id: str  # stable slug, used as the CLI arg and log key
    text: str  # the claim, in TEG's own words — becomes the user prompt
    kb_source_file: str  # relpath under teg-kb-agent/knowledge_base/, for the human reviewer
    check_hint: str = ""  # optional: where to look first


class VerificationResult(BaseModel):
    claim: str
    kb_says: str
    web_says: str | None = None
    status: Literal["confirmed", "conflicting", "unverifiable"]
    sources: list[str] = Field(default_factory=list)
    checked_at: date
