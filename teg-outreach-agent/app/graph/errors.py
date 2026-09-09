"""Errors for the minimal typed execution graph. See
docs/superpowers/specs/2026-09-10-verification-harness-and-graph-design.md §3.3.
"""
from __future__ import annotations

PartialState = dict[str, object]


class NodeSoftFailure(Exception):
    """Raise this, not a bare exception, when a node can't complete but has
    a known-safe partial/fallback state to contribute instead of crashing
    the whole graph. `runner.py` catches only this — anything else
    propagates, same "explicit fallback states, not silent excepts"
    discipline the rest of this codebase already follows (e.g.
    `ResearchDossier(ask_prospect=[...])` on a research timeout today)."""

    def __init__(self, fallback: PartialState) -> None:
        super().__init__(f"soft failure, fallback keys={sorted(fallback)}")
        self.fallback = fallback


class GraphCycleError(Exception):
    """The declared node graph is not a DAG. Explicitly not supported (§5
    non-goal) — neither pipeline this graph runs needs a cycle, and a
    cyclic declaration is almost certainly a bug in the node list, not an
    intentional loop."""


class GraphValidationError(Exception):
    """A node declares a `reads` key that nothing in an earlier layer (nor
    the graph's initial inputs) ever `writes` — caught at build time, before
    any node runs, per §3.3.1."""
