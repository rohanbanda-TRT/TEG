from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ResearchQuery:
    track: Literal["company", "person"]
    subject: str
    context: str
    want: list[str]


@dataclass
class ResearchResult:
    available: bool = True
    fields: dict[str, str] = field(default_factory=dict)
    confidence: dict[str, float] = field(default_factory=dict)
    source_url: str | None = None
    tool_name: str = ""
    notes: str = ""


class ResearchTool(ABC):
    name: str = "tool"

    @abstractmethod
    async def lookup(self, query: ResearchQuery) -> ResearchResult: ...
