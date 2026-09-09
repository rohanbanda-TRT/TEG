"""Topological layering + asyncio-concurrent execution for the minimal typed
execution graph. See docs/superpowers/specs/2026-09-10-verification-harness-and-graph-design.md
§3.3.2. Explicitly not LangGraph or any comparable framework (§3.3) — pure
DAGs, no cycles, no dynamic re-planning.
"""
from __future__ import annotations

import asyncio

from app.graph.errors import GraphCycleError, GraphValidationError, NodeSoftFailure
from app.graph.node import GraphContext, Node, PartialState
from app.obs import get_logger

_log = get_logger("graph.runner")


class _nullctx:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *exc):
        return False


def _topological_layers(nodes: list[Node], initial_keys: frozenset[str]) -> list[list[Node]]:
    """Static, build-time check: every node's `reads` must be satisfiable by
    the union of `writes` from nodes in strictly earlier layers (the graph's
    own inputs count as layer 0's available keys). Raises GraphValidationError
    for a key nothing in the WHOLE graph ever produces (genuinely
    unsatisfiable, not just a layering problem), and GraphCycleError for a
    mutual dependency among the remaining nodes despite every read being
    theoretically satisfiable by something in the graph."""
    all_produced = set(initial_keys) | {k for n in nodes for k in n.writes}
    for n in nodes:
        missing = n.reads - all_produced
        if missing:
            raise GraphValidationError(
                f"node {n.name!r} reads {sorted(missing)}, which no node (and no initial "
                "input) in this graph ever produces"
            )

    available = set(initial_keys)
    remaining = list(nodes)
    layers: list[list[Node]] = []
    while remaining:
        layer = [n for n in remaining if n.reads <= available]
        if not layer:
            raise GraphCycleError(
                f"cycle (or unsatisfiable ordering) among nodes: {[n.name for n in remaining]}"
            )
        layers.append(layer)
        remaining = [n for n in remaining if n not in layer]
        for n in layer:
            available |= n.writes
    return layers


async def _run_one(node: Node, ctx: GraphContext) -> PartialState:
    try:
        return await node.run(ctx)
    except NodeSoftFailure as soft:
        _log.warning("[graph] %s soft-failed, using fallback state", node.name)
        return soft.fallback
    # anything else propagates — run_graph's TaskGroup cancels the sibling
    # tasks in this layer and the whole run_graph() call raises.


async def run_graph(
    nodes: list[Node], initial: GraphContext, *, timeout_s: float | None = None,
) -> GraphContext:
    layers = _topological_layers(nodes, frozenset(initial))
    state: GraphContext = dict(initial)
    cm = asyncio.timeout(timeout_s) if timeout_s else _nullctx()
    async with cm:
        for layer in layers:
            tasks: dict[str, asyncio.Task] = {}
            try:
                async with asyncio.TaskGroup() as tg:
                    for n in layer:
                        tasks[n.name] = tg.create_task(_run_one(n, state))
            except* Exception as eg:
                # A hard failure inside this layer cancels its siblings (that's
                # what TaskGroup gives us) and the whole run_graph() call
                # raises — unwrap a single failure back to its original type
                # rather than leaking an ExceptionGroup wrapper to callers.
                excs = eg.exceptions
                if len(excs) == 1:
                    raise excs[0] from None
                raise
            for t in tasks.values():
                state.update(t.result())
    return state
