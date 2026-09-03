"""Claude-backed KB explorer — same ExploreResult contract as the LLM one."""
import pytest

from app.claude.cli import ClaudeCli, ClaudeResult
from app.claude.kb_explorer import ClaudeKBExplorer
from app.kb.explorer import ExploreResult

pytestmark = pytest.mark.asyncio


class _FakeClaude(ClaudeCli):
    def __init__(self, data: dict | None = None, boom: Exception | None = None):
        self._data = data or {}
        self._boom = boom
        self.calls: list[dict] = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        if self._boom:
            raise self._boom
        return ClaudeResult(data=self._data, cost_usd=0.03, session_id="s")


async def test_returns_an_exploreresult():
    claude = _FakeClaude({
        "found": True,
        "summary": "Third Rock Techkno is an AI/ML exhibitor.",
        "facts": {"sector": "AI & Machine Learning", "sector_peers": "ViitorCloud, NeuraMonks"},
        "sources": ["exhibitors/companies/third_rock_techkno.md"],
        "confidence": 0.9,
    })

    r = await ClaudeKBExplorer(claude).explore("Profile Third Rock Techkno")

    assert isinstance(r, ExploreResult)
    assert r.found is True
    assert r.facts["sector"] == "AI & Machine Learning"
    assert r.confidence == 0.9


async def test_read_only_tools_and_the_kb_is_mounted():
    claude = _FakeClaude({"found": False})

    await ClaudeKBExplorer(claude, kb_path="/kb").explore("g")

    call = claude.calls[0]
    assert set(call["tools"]) == {"Read", "Grep", "Glob"}
    assert set(call["allowed_tools"]) == {"Read", "Grep", "Glob"}
    # NEVER Write/Edit/Bash — the KB is read-only
    assert not {"Write", "Edit", "Bash"} & set(call["tools"])
    assert "/kb" in call["add_dirs"]


async def test_the_kb_skill_is_loaded():
    claude = _FakeClaude({"found": False})

    await ClaudeKBExplorer(claude).explore("g")

    assert "TEG Knowledge Base" in claude.calls[0]["system_prompt"]


async def test_the_goal_is_the_user_prompt():
    claude = _FakeClaude({"found": True, "facts": {}})

    await ClaudeKBExplorer(claude).explore("Profile Itorix Infotech LLP and its sector")

    assert "Itorix Infotech LLP" in claude.calls[0]["user_prompt"]


async def test_a_failure_returns_an_empty_result_not_an_exception():
    claude = _FakeClaude(boom=RuntimeError("claude timed out"))

    r = await ClaudeKBExplorer(claude).explore("g")

    assert isinstance(r, ExploreResult)
    assert r.found is False
    assert r.facts == {}


async def test_non_string_fact_values_are_coerced():
    claude = _FakeClaude({
        "found": True,
        "facts": {"sector_peer_count": 12, "sector": "AI & Machine Learning"},
    })

    r = await ClaudeKBExplorer(claude).explore("g")

    assert r.facts["sector_peer_count"] == "12"
    assert r.facts["sector"] == "AI & Machine Learning"


async def test_missing_optional_keys_default_sanely():
    claude = _FakeClaude({"found": True})  # no summary/facts/sources/confidence

    r = await ClaudeKBExplorer(claude).explore("g")

    assert r.summary == ""
    assert r.facts == {}
    assert r.sources == []
    assert r.confidence == 0.0
