"""app/graph/runner.py — deterministic, no LLM involved. See
docs/superpowers/specs/2026-09-10-verification-harness-and-graph-design.md §4."""
import asyncio
import time
from dataclasses import dataclass, field

import pytest

from app.graph.errors import GraphCycleError, GraphValidationError, NodeSoftFailure
from app.graph.runner import run_graph

pytestmark = pytest.mark.asyncio


@dataclass
class _Node:
    name: str
    reads: frozenset[str] = field(default_factory=frozenset)
    writes: frozenset[str] = field(default_factory=frozenset)
    fn: object = None  # async callable(ctx) -> dict

    async def run(self, ctx):
        return await self.fn(ctx)


async def test_a_parallel_layer_actually_runs_concurrently():
    timestamps: dict[str, float] = {}

    async def _slow(key):
        async def fn(ctx):
            await asyncio.sleep(0.2)
            timestamps[key] = time.monotonic()
            return {key: True}
        return fn

    a = _Node(name="a", writes=frozenset({"a"}), fn=await _slow("a"))
    b = _Node(name="b", writes=frozenset({"b"}), fn=await _slow("b"))

    t0 = time.monotonic()
    result = await run_graph([a, b], {}, timeout_s=5)
    elapsed = time.monotonic() - t0

    assert result == {"a": True, "b": True}
    assert elapsed < 0.35  # ~0.2s if concurrent, ~0.4s if accidentally serialized
    assert abs(timestamps["a"] - timestamps["b"]) < 0.05


async def test_node_soft_failure_uses_fallback_state():
    async def boom(ctx):
        raise NodeSoftFailure({"x": "fallback"})

    node = _Node(name="n", writes=frozenset({"x"}), fn=boom)
    result = await run_graph([node], {}, timeout_s=5)
    assert result == {"x": "fallback"}


async def test_bare_exception_propagates_and_cancels_siblings():
    sibling_cancelled = False

    async def failing(ctx):
        raise ValueError("boom")

    async def slow_sibling(ctx):
        nonlocal sibling_cancelled
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            sibling_cancelled = True
            raise
        return {"never": True}

    a = _Node(name="a", writes=frozenset({"a"}), fn=failing)
    b = _Node(name="b", writes=frozenset({"b"}), fn=slow_sibling)

    with pytest.raises(ValueError, match="boom"):
        await run_graph([a, b], {}, timeout_s=5)
    assert sibling_cancelled is True


async def test_unsatisfiable_read_raises_at_build_time_before_any_node_runs():
    ran = False

    async def fn(ctx):
        nonlocal ran
        ran = True
        return {}

    node = _Node(name="n", reads=frozenset({"nothing_produces_this"}), fn=fn)
    with pytest.raises(GraphValidationError):
        await run_graph([node], {}, timeout_s=5)
    assert ran is False


async def test_cyclic_graph_raises_a_named_error_not_a_hang():
    async def fn(ctx):
        return {}

    a = _Node(name="a", reads=frozenset({"b"}), writes=frozenset({"a"}), fn=fn)
    b = _Node(name="b", reads=frozenset({"a"}), writes=frozenset({"b"}), fn=fn)
    with pytest.raises(GraphCycleError):
        await run_graph([a, b], {}, timeout_s=5)


async def test_layers_run_in_dependency_order():
    order: list[str] = []

    async def mk(name, keys):
        async def fn(ctx):
            order.append(name)
            return {k: True for k in keys}
        return fn

    a = _Node(name="a", writes=frozenset({"a"}), fn=await mk("a", {"a"}))
    b = _Node(name="b", reads=frozenset({"a"}), writes=frozenset({"b"}), fn=await mk("b", {"b"}))
    c = _Node(name="c", reads=frozenset({"b"}), writes=frozenset({"c"}), fn=await mk("c", {"c"}))

    result = await run_graph([c, a, b], {}, timeout_s=5)  # deliberately out of order
    assert order == ["a", "b", "c"]
    assert result == {"a": True, "b": True, "c": True}


async def test_initial_context_counts_as_satisfied_reads():
    async def fn(ctx):
        assert ctx["seed"] == 1
        return {"out": ctx["seed"] + 1}

    node = _Node(name="n", reads=frozenset({"seed"}), writes=frozenset({"out"}), fn=fn)
    result = await run_graph([node], {"seed": 1}, timeout_s=5)
    assert result["out"] == 2
