"""Checks TEG-authored KB claims against the live web.

See docs/superpowers/specs/2026-09-10-verification-harness-and-graph-design.md
§3.1. One `ClaudeCli.generate()` call per claim, `tools=["WebSearch",
"WebFetch"]` — the CLI subprocess runs its own internal agentic loop, so no
hand-rolled Python loop lives here (§3.1.2 explains why this differs from
KBExplorer's shape). The teg-verify skill is loaded BY NAME into the system
prompt (like teg-proposal/teg-conversation), not granted as a discoverable
`Skill` tool — this caller has exactly one job every run, so there's nothing
for the model to discover.

Inputs are TEG's own maintained claim text (app/verify/claims.py) — never
prospect-supplied text — so this is the one caller in the codebase where the
"don't grant tools to prospect-facing prompts" concern is structurally
absent, not just mitigated (§3.1.1).
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from app.claude.cli import ClaudeCli
from app.claude.prompt_builder import render_skill
from app.claude.skill_loader import load_skill
from app.obs import get_logger
from app.verify.claims import CLAIMS
from app.verify.schemas import Claim, VerificationResult
from config.settings import get_settings

_log = get_logger("verify.claude_verifier")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILLS_DIR = _REPO_ROOT / ".claude" / "skills"

_SYSTEM_PREFIX = (
    "You check ONE claim from Tech Expo Gujarat's own knowledge base against "
    "the live web. Follow the teg-verify skill below for how to search and "
    "how to judge what you find. Return only the JSON the schema asks for."
)


class _Findings(BaseModel):
    web_says: str = ""
    status: str = "unverifiable"  # "confirmed" | "conflicting" | "unverifiable"
    sources: list[str] = []


def _system_prompt() -> str:
    skill = load_skill(str(_SKILLS_DIR), "teg-verify")
    return _SYSTEM_PREFIX + "\n\n" + render_skill(skill)


async def verify_claim(
    claim: Claim, *, cli: ClaudeCli | None = None, resume: str | None = None,
) -> tuple[VerificationResult, str | None]:
    """Check one claim. Returns (result, session_id) — session_id is only
    ever populated when the call succeeds, for verify_all()'s resume chain."""
    s = get_settings()
    cli = cli or ClaudeCli()
    if not cli.api_key:
        from app.api.claude_conn import get_api_key

        cli.api_key = get_api_key() or ""

    user = (
        f"Claim: {claim.text}\n"
        f"KB source: {claim.kb_source_file}\n"
        + (f"Where to look first: {claim.check_hint}\n" if claim.check_hint else "")
        + "\nCheck this against the live web and return your verdict."
    )
    try:
        result = await cli.generate(
            model=s.claude_cli_model,
            system_prompt=_system_prompt(),
            user_prompt=user,
            json_schema=_Findings.model_json_schema(),
            cwd=str(_REPO_ROOT),
            tools=["WebSearch", "WebFetch"],
            allowed_tools=["WebSearch", "WebFetch"],
            timeout_s=s.verify_claim_timeout_s,
            resume=resume,
        )
    except RuntimeError as exc:
        _log.warning("[%s] verification failed: %s", claim.id, exc)
        return (
            VerificationResult(
                claim=claim.id, kb_says=claim.text, status="unverifiable",
                checked_at=datetime.now(UTC).date(),
            ),
            None,
        )

    found = _Findings.model_validate(result.data)
    status = found.status if found.status in ("confirmed", "conflicting", "unverifiable") else "unverifiable"
    return (
        VerificationResult(
            claim=claim.id, kb_says=claim.text, web_says=found.web_says or None,
            status=status, sources=found.sources, checked_at=datetime.now(UTC).date(),
        ),
        result.session_id,
    )


async def verify_all(*, cli: ClaudeCli | None = None) -> list[VerificationResult]:
    """Checks every claim in CLAIMS, one process invocation. Uses `resume`
    (§3.1.5) as a latency/cost optimization ONLY — never a correctness
    dependency: a resumed call's RuntimeError retries once fresh (no
    resume) before giving up on that claim, so a bad session never takes
    down claims after it."""
    cli = cli or ClaudeCli()
    results: list[VerificationResult] = []
    session_id: str | None = None
    for claim in CLAIMS.values():
        result, new_session = await verify_claim(claim, cli=cli, resume=session_id)
        if new_session is None and session_id is not None:
            # The resumed call failed — retry once fresh before moving on.
            _log.warning("[%s] resumed call failed; retrying fresh (no resume)", claim.id)
            result, new_session = await verify_claim(claim, cli=cli, resume=None)
        session_id = new_session or session_id
        results.append(result)
    return results
