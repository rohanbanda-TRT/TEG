"""Claude-backed web research, as a drop-in ResearchTool."""
import pathlib

import pytest

from app.claude.cli import ClaudeCli, ClaudeResult
from app.claude.web_research import ClaudeWebSearch
from app.research.tools import ResearchQuery

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
        return ClaudeResult(data=self._data, cost_usd=0.02, session_id="s")


def _query(track="company", subject="DataZen Analytics"):
    return ResearchQuery(
        track=track, subject=subject, context="Ahmedabad tech company",
        want=["sector", "company_size", "hq"],
    )


async def test_returns_the_fields_claude_found():
    claude = _FakeClaude({
        "sector": "AI & Machine Learning", "hq": "Ahmedabad", "company_size": "30",
        "confidence": 0.8, "source_url": "https://datazen.example/about",
    })

    res = await ClaudeWebSearch(claude).lookup(_query())

    assert res.available is True
    assert res.fields["sector"] == "AI & Machine Learning"
    assert res.fields["hq"] == "Ahmedabad"
    assert res.source_url == "https://datazen.example/about"
    assert res.tool_name == "web"


async def test_the_research_session_gets_skill_plus_web_tools():
    claude = _FakeClaude({"sector": "X"})

    await ClaudeWebSearch(claude).lookup(_query())

    call = claude.calls[0]
    # Skill lets Claude discover and invoke teg-research itself; the web tools
    # must ALSO be pre-approved, or dontAsk denies them at call time.
    assert set(call["tools"]) == {"Skill", "WebSearch", "WebFetch"}
    assert set(call["allowed_tools"]) == {"Skill", "WebSearch", "WebFetch"}
    # never filesystem or shell access, even here
    assert not {"Read", "Write", "Bash", "Edit"} & set(call["tools"])


async def test_the_session_runs_at_the_repo_root_so_the_skill_is_discoverable():
    claude = _FakeClaude({"sector": "X"})

    await ClaudeWebSearch(claude).lookup(_query())

    cwd = claude.calls[0]["cwd"]
    assert (pathlib.Path(cwd) / ".claude" / "skills" / "teg-research" / "SKILL.md").is_file()


async def test_the_system_prompt_points_at_the_skill_by_name():
    claude = _FakeClaude({"sector": "X"})

    await ClaudeWebSearch(claude).lookup(_query())

    # We no longer inject the skill body — just tell Claude to use it.
    assert "teg-research skill" in claude.calls[0]["system_prompt"]


async def test_a_missing_skill_file_fails_cleanly():
    claude = _FakeClaude({"sector": "X"})
    import app.claude.web_research as wr

    real = wr._SKILL_FILE
    wr._SKILL_FILE = real.with_name("nope.md")
    try:
        res = await ClaudeWebSearch(claude).lookup(_query())
    finally:
        wr._SKILL_FILE = real

    assert res.available is False
    assert "skill missing" in res.notes
    assert claude.calls == []


async def test_null_fields_are_dropped_not_stringified():
    claude = _FakeClaude({"sector": "Textile", "hq": None, "founder": None})

    res = await ClaudeWebSearch(claude).lookup(_query())

    assert res.fields == {"sector": "Textile"}
    assert "hq" not in res.fields
    assert "None" not in str(res.fields.values())


async def test_confidence_is_applied_per_field():
    claude = _FakeClaude({"sector": "Fintech", "confidence": 0.4})

    res = await ClaudeWebSearch(claude).lookup(_query())

    assert res.confidence["sector"] == 0.4


async def test_a_failure_returns_unavailable_rather_than_raising():
    claude = _FakeClaude(boom=RuntimeError("claude exited with code 1"))

    res = await ClaudeWebSearch(claude).lookup(_query())

    assert res.available is False
    assert "claude exited" in res.notes


async def test_person_track_asks_about_the_person():
    claude = _FakeClaude({"designation": "CTO", "seniority": "c_level"})

    res = await ClaudeWebSearch(claude).lookup(
        ResearchQuery(track="person", subject="Rohan B",
                      context="at DataZen Analytics", want=["designation"])
    )

    assert res.fields["designation"] == "CTO"
    assert "Rohan B" in claude.calls[0]["user_prompt"]


async def test_booleans_survive_as_strings_for_the_dossier():
    claude = _FakeClaude({"is_technical": True, "person_company_match": False})

    res = await ClaudeWebSearch(claude).lookup(_query(track="person"))

    assert res.fields["is_technical"] == "true"
    assert res.fields["person_company_match"] == "false"
