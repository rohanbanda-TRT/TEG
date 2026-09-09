"""app/verify/claude_verifier.py — no network.

The design spec's §4 describes these as "record/replay... same pattern as
tests/kb/test_explorer.py" (recorded live transcripts replayed against
fixtures). This environment has no live `claude` CLI credentials to record
real transcripts with, so — same as tests/claude/test_web_research.py, the
existing convention for every OTHER ClaudeCli-backed caller in this repo —
these tests inject a `_FakeClaude(ClaudeCli)` subclass returning canned
`ClaudeResult`/exceptions in place of a real subprocess call. This covers the
same four cases the spec asks for (confirmed / conflicting / unverifiable /
RuntimeError) without requiring network access; a genuine recorded-transcript
suite is future work once real credentials are available in this environment.
"""
import pytest

from app.claude.cli import ClaudeCli, ClaudeResult
from app.verify.claims import CLAIMS
from app.verify.claude_verifier import verify_all, verify_claim

pytestmark = pytest.mark.asyncio


class _FakeClaude(ClaudeCli):
    def __init__(self, *, results: list[ClaudeResult] | None = None,
                 boom: Exception | None = None):
        self._results = list(results or [])
        self._boom = boom
        self.calls: list[dict] = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        if self._boom is not None:
            raise self._boom
        return self._results.pop(0)


def _claim(claim_id="dates_venue"):
    return CLAIMS[claim_id]


async def test_confirmed_transcript():
    claude = _FakeClaude(results=[
        ClaudeResult(data={"web_says": "still 27-29 Nov 2026 at GUCEC", "status": "confirmed",
                            "sources": ["https://www.techexpogujarat.com/"]},
                     cost_usd=0.01, session_id="s1"),
    ])
    result, session_id = await verify_claim(_claim(), cli=claude)

    assert result.status == "confirmed"
    assert result.claim == "dates_venue"
    assert session_id == "s1"
    call = claude.calls[0]
    assert set(call["tools"]) == {"WebSearch", "WebFetch"}
    assert set(call["allowed_tools"]) == {"WebSearch", "WebFetch"}
    assert "Skill" not in call["tools"]  # addressed by name, not granted as a discoverable tool


async def test_conflicting_transcript():
    """A deliberately-stale claim — proves the harness actually flags a real
    mismatch and doesn't just always say confirmed."""
    claude = _FakeClaude(results=[
        ClaudeResult(
            data={
                "web_says": "the official portal now lists visitor pricing at ₹499",
                "status": "conflicting",
                "sources": ["https://events.techexpogujarat.com/"],
            },
            cost_usd=0.02, session_id="s2",
        ),
    ])
    result, _ = await verify_claim(_claim("visitor_pricing_published"), cli=claude)

    assert result.status == "conflicting"
    assert "₹499" in result.web_says


async def test_unverifiable_transcript():
    claude = _FakeClaude(results=[
        ClaudeResult(data={"web_says": "", "status": "unverifiable", "sources": []},
                     cost_usd=0.0, session_id="s3"),
    ])
    result, _ = await verify_claim(_claim("scale_targets"), cli=claude)
    assert result.status == "unverifiable"


async def test_runtime_error_returns_unverifiable_not_raise():
    claude = _FakeClaude(boom=RuntimeError("claude exited with code 1"))
    result, session_id = await verify_claim(_claim(), cli=claude)
    assert result.status == "unverifiable"
    assert session_id is None


async def test_verify_all_resumes_across_claims():
    claude = _FakeClaude(results=[
        ClaudeResult(data={"web_says": "", "status": "confirmed", "sources": []}, session_id="sA"),
        ClaudeResult(data={"web_says": "", "status": "confirmed", "sources": []}, session_id="sA"),
        ClaudeResult(data={"web_says": "", "status": "confirmed", "sources": []}, session_id="sA"),
        ClaudeResult(data={"web_says": "", "status": "confirmed", "sources": []}, session_id="sA"),
    ])
    results = await verify_all(cli=claude)
    assert len(results) == len(CLAIMS)
    # first call cold (no resume), every subsequent call resumes the same session
    assert claude.calls[0]["resume"] is None
    assert all(c["resume"] == "sA" for c in claude.calls[1:])


async def test_verify_all_falls_back_to_fresh_call_on_resumed_failure():
    class _FlakyResume(ClaudeCli):
        def __init__(self):
            self.calls: list[dict] = []

        async def generate(self, **kwargs):
            self.calls.append(kwargs)
            if kwargs.get("resume"):
                raise RuntimeError("resumed session broke")
            return ClaudeResult(data={"web_says": "", "status": "confirmed", "sources": []},
                                session_id="sB")

    claude = _FlakyResume()
    results = await verify_all(cli=claude)
    # every claim still resolves — none silently dropped when its resumed
    # attempt failed and had to retry fresh.
    assert len(results) == len(CLAIMS)
    assert all(r.status == "confirmed" for r in results)
