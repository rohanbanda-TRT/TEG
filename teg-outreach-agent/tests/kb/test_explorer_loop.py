from types import SimpleNamespace

from app.kb.explorer import ExploreResult, KBExplorer
from app.llm.replay import ReplayLLMClient

_TRANSCRIPT = {
    "goal": "Profile the company Third Rock Techkno. Return facts: sector, website.",
    "model_turns": [
        {"tool_calls": [{"id": "c0", "name": "read_file", "args": {"path": "INDEX.md"}}]},
        {"tool_calls": [{"id": "c1", "name": "read_file",
                         "args": {"path": "exhibitors/companies/third_rock_techkno.md"}}]},
        {"final": "{\"found\": true, \"summary\": \"custom AI & software dev\", "
                  "\"facts\": {\"sector\": \"AI & Machine Learning\", "
                  "\"website\": \"https://www.thirdrocktechkno.com/\"}, "
                  "\"sources\": [\"exhibitors/companies/third_rock_techkno.md\"], "
                  "\"confidence\": 0.9}"},
    ],
}


async def test_explorer_replays_against_live_kb():
    llm = ReplayLLMClient(_TRANSCRIPT)
    result = await KBExplorer(llm).explore(_TRANSCRIPT["goal"])
    assert isinstance(result, ExploreResult)
    assert result.found is True
    assert result.facts["sector"] == "AI & Machine Learning"
    assert "third_rock_techkno.md" in result.sources[0]


async def test_explorer_step_cap_forces_answer(monkeypatch):
    # a transcript that keeps asking for tools -> loop must hit the cap and
    # still return a parsed (empty) result rather than looping forever.
    turns = [{"tool_calls": [{"id": "c", "name": "list_dir", "args": {"path": "."}}]}] * 20
    llm = ReplayLLMClient({
        "goal": "g", "model_turns": turns,
        "final": "{\"found\": false, \"summary\": \"\", \"facts\": {}, "
                 "\"sources\": [], \"confidence\": 0.0}",
    })
    monkeypatch.setattr(
        "app.kb.explorer.get_settings",
        lambda: SimpleNamespace(kb_explore_max_steps=3, kb_explore_model="test-model"),
    )
    result = await KBExplorer(llm).explore("g")
    assert result.found is False


async def test_explorer_returns_empty_on_parse_failure(monkeypatch):
    llm = ReplayLLMClient({"goal": "g", "model_turns": [{"final": "not json at all"}]})
    result = await KBExplorer(llm).explore("g")
    assert result == ExploreResult()
