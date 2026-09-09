"""app/research/deep.py — no network, same _FakeClaude(ClaudeCli) pattern as
tests/claude/test_web_research.py / tests/verify/test_claude_verifier.py."""
import pytest

from app.claude.cli import ClaudeCli, ClaudeResult
from app.research.deep import DeepFindings, deep_research

pytestmark = pytest.mark.asyncio


class _FakeClaude(ClaudeCli):
    def __init__(self, *, data: dict | None = None, boom: Exception | None = None):
        self._data = data or {}
        self._boom = boom
        self.calls: list[dict] = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        if self._boom is not None:
            raise self._boom
        return ClaudeResult(data=self._data, cost_usd=0.1, session_id="s", tool_calls=4)


async def test_returns_findings_on_success():
    claude = _FakeClaude(data={
        "funding_status": "bootstrapped", "growth_trend": "headcount up, revenue flat",
        "competitive_position": "ranked ~2,600th of 130,000+ tracked competitors (Tracxn)",
        "named_clients": ["Databricks", "Teladoc"], "certifications": ["ISO 27001", "AWS Partner"],
        "review_sentiment_themes": [{"theme": "overtime", "mention_count": 38}],
        "notable_visibility": "CEO featured in CEO India magazine",
        "sources": ["https://example.com"], "notes": "financial figures are third-party estimates",
    })
    result = await deep_research("Tudip Technologies", "Jane Doe", cli=claude)
    assert isinstance(result, DeepFindings)
    assert result.funding_status == "bootstrapped"
    assert result.named_clients == ["Databricks", "Teladoc"]
    assert result.review_sentiment_themes[0].theme == "overtime"
    assert result.review_sentiment_themes[0].mention_count == 38


async def test_grants_only_websearch_and_webfetch():
    claude = _FakeClaude(data={})
    await deep_research("Acme Co", "X", cli=claude)
    call = claude.calls[0]
    assert set(call["tools"]) == {"WebSearch", "WebFetch"}
    assert set(call["allowed_tools"]) == {"WebSearch", "WebFetch"}
    assert not {"Read", "Write", "Bash", "Edit", "Skill"} & set(call["tools"])


async def test_uses_the_deep_research_timeout_setting():
    from config.settings import get_settings

    claude = _FakeClaude(data={})
    await deep_research("Acme Co", "X", cli=claude)
    assert claude.calls[0]["timeout_s"] == get_settings().deep_research_timeout_s


async def test_a_cli_failure_returns_none_not_raise():
    claude = _FakeClaude(boom=RuntimeError("claude exited with code 1"))
    result = await deep_research("Acme Co", "X", cli=claude)
    assert result is None


async def test_missing_skill_file_returns_none_not_raise():
    import app.research.deep as deep_mod

    real = deep_mod._SKILLS_DIR
    deep_mod._SKILLS_DIR = real / "does-not-exist"
    try:
        result = await deep_research("Acme Co", "X", cli=_FakeClaude(data={}))
    finally:
        deep_mod._SKILLS_DIR = real
    assert result is None
