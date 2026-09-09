"""Node protocol + shared types for the minimal typed execution graph. See
docs/superpowers/specs/2026-09-10-verification-harness-and-graph-design.md §3.3.1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable, Protocol

GraphContext = dict[str, object]  # accumulated state, read-only view passed to each node
PartialState = dict[str, object]  # what a node contributes back


class Node(Protocol):
    name: str
    reads: frozenset[str]  # state keys this node consumes
    writes: frozenset[str]  # state keys this node produces

    async def run(self, ctx: GraphContext) -> PartialState: ...


@dataclass
class FnNode:
    """A Node built from a plain async function — avoids a full class per
    node for simple, single-purpose graph steps like the ones in
    app/orchestrator.py's and app/agents/proposal.py's pipelines."""

    name: str
    fn: Callable[[GraphContext], Awaitable[PartialState]]
    reads: frozenset[str] = field(default_factory=frozenset)
    writes: frozenset[str] = field(default_factory=frozenset)

    async def run(self, ctx: GraphContext) -> PartialState:
        return await self.fn(ctx)
