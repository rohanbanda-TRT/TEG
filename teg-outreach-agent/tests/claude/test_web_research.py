"""Claude-backed web research, as a drop-in ResearchTool."""
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


async def test_the_research_session_gets_web_tools_only():
    claude = _FakeClaude({"sector": "X"})

    await ClaudeWebSearch(claude).lookup(_query())

    call = claude.calls[0]
    assert set(call["tools"]) == {"WebSearch", "WebFetch"}
    # Availability is not permission: under --permission-mode dontAsk the web
    # tools must ALSO be pre-approved, or every call is silently denied and
    # Claude answers from the prompt alone.
    assert set(call["allowed_tools"]) == {"WebSearch", "WebFetch"}
    # never filesystem or shell access, even here
    assert not {"Read", "Write", "Bash", "Edit"} & set(call["tools"])


async def test_the_research_skill_is_loaded():
    claude = _FakeClaude({"sector": "X"})

    await ClaudeWebSearch(claude).lookup(_query())

    assert "TEG Prospect Research" in claude.calls[0]["system_prompt"]


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
