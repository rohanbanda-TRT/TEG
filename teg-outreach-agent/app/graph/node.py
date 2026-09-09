"""Node protocol + shared types for the minimal typed execution graph. See
docs/superpowers/specs/2026-09-10-verification-harness-and-graph-design.md §3.3.1.
"""
from __future__ import annotations

from typing import Protocol

GraphContext = dict[str, object]  # accumulated state, read-only view passed to each node
PartialState = dict[str, object]  # what a node contributes back


class Node(Protocol):
    name: str
    reads: frozenset[str]  # state keys this node consumes
    writes: frozenset[str]  # state keys this node produces

    async def run(self, ctx: GraphContext) -> PartialState: ...
