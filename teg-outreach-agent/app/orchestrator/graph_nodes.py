"""FnNode factories for the inquiry pipeline's research graph.

See docs/superpowers/specs/2026-09-10-verification-harness-and-graph-design.md
§3.3.3. analyze_intake and persuasion_init each run as their own tiny
(un-timed) run_graph() call in Orchestrator.run_pipeline, exactly matching
the old sequential behavior for those two steps. The research layer —
research_company / research_person / verify_relevant_teg_claims, joined by
merge_dossier — runs as ONE run_graph() call wrapped in
asyncio.wait_for(..., pipeline_hard_timeout_s), with the same ask_prospect
fallback dossier on timeout. This is deliberately three separate
run_graph() calls, not one graph spanning the whole pipeline — a single
flat timeout across analyze_intake/persuasion_init too would change
behavior neither of them has today, and a research timeout must still let
the pipeline continue to persuasion_init with a substitute dossier, which a
single graph's all-or-nothing timeout can't express without inventing new
soft-fail semantics merge_dossier doesn't need.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.graph.node import FnNode
from app.obs import get_logger
from app.orchestrator.verification import read_verification_flags

if TYPE_CHECKING:
    from app.orchestrator.core import Orchestrator

_log = get_logger("orchestrator")


def analyze_intake_node(orch: "Orchestrator") -> FnNode:
    async def fn(ctx: dict) -> dict:
        intake = await orch.analysis.run(ctx["payload"])
        return {"intake": intake}

    return FnNode(name="analyze_intake", fn=fn,
                  reads=frozenset({"payload"}), writes=frozenset({"intake"}))


def research_company_node(orch: "Orchestrator") -> FnNode:
    async def fn(ctx: dict) -> dict:
        out = await orch.research.run_company_track(ctx["intake"], budget=ctx["_research_budget"])
        return {"company_partial": out}

    return FnNode(name="research_company", fn=fn,
                  reads=frozenset({"intake", "_research_budget"}),
                  writes=frozenset({"company_partial"}))


def research_person_node(orch: "Orchestrator") -> FnNode:
    async def fn(ctx: dict) -> dict:
        out = await orch.research.run_person_track(ctx["intake"], budget=ctx["_research_budget"])
        return {"person_partial": out}

    return FnNode(name="research_person", fn=fn,
                  reads=frozenset({"intake", "_research_budget"}),
                  writes=frozenset({"person_partial"}))


def verify_relevant_teg_claims_node() -> FnNode:
    async def fn(ctx: dict) -> dict:
        try:
            flags = read_verification_flags(ctx["intake"])
        except Exception as exc:  # noqa: BLE001 — must never block or slow the pipeline
            _log.warning("verify_relevant_teg_claims failed (%s); no confidence flags", exc)
            flags = []
        return {"kb_confidence_flags": flags}

    return FnNode(name="verify_relevant_teg_claims", fn=fn,
                  reads=frozenset({"intake"}), writes=frozenset({"kb_confidence_flags"}))


def merge_dossier_node(orch: "Orchestrator") -> FnNode:
    async def fn(ctx: dict) -> dict:
        dossier = await orch.research.merge_tracks(
            ctx["intake"], ctx["company_partial"], ctx["person_partial"],
            kb_confidence_flags=ctx["kb_confidence_flags"], budget=ctx["_research_budget"],
        )
        return {"dossier": dossier}

    return FnNode(
        name="merge_dossier", fn=fn,
        reads=frozenset({"intake", "company_partial", "person_partial", "kb_confidence_flags"}),
        writes=frozenset({"dossier"}),
    )


def persuasion_init_node(orch: "Orchestrator") -> FnNode:
    async def fn(ctx: dict) -> dict:
        init = await orch.persuasion.init(ctx["intake"], ctx["dossier"])
        return {"init": init}

    return FnNode(name="persuasion_init", fn=fn,
                  reads=frozenset({"intake", "dossier"}), writes=frozenset({"init"}))
