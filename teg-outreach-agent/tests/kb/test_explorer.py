"""Replay recorded KBExplorer sessions against the LIVE knowledge base.

The transcripts in tests/kb/transcripts/ hold only the model's turns. Replay
runs the real loop with the real fs_tools, so if a KB file a transcript reads
has moved or been renamed, read_file returns an error, the assertions fail, and
the fix is to re-record that transcript:

    GEMINI_API_KEY=... python scripts/record_kb_transcript.py <name> "<goal>"
"""
import json
from pathlib import Path

import pytest

from app.kb import fs_tools
from app.kb.explorer import KBExplorer
from app.llm.replay import ReplayLLMClient

_DIR = Path(__file__).parent / "transcripts"
_CASES = sorted(p.stem for p in _DIR.glob("*.json"))


@pytest.mark.parametrize("name", _CASES)
async def test_transcript_reads_still_resolve(name):
    """Every read_file the recorded run performed SUCCESSFULLY must still work.
    A moved or renamed KB file breaks this loudly. (Reads the model attempted
    that missed during recording — deliberate slug probes on a found=false run
    — are listed in `reads_missed` and not checked.)"""
    data = json.loads((_DIR / f"{name}.json").read_text())
    for path in data.get("reads_ok", []):
        out = fs_tools.read_file(path)
        assert not out.startswith("error:"), (
            f"{name}: recorded read {path!r} now errors: {out[:120]}\n"
            f'  -> re-record: python scripts/record_kb_transcript.py {name} "<goal>"'
        )


@pytest.mark.parametrize("name", _CASES)
async def test_transcript_replays_to_expected_result(name):
    data = json.loads((_DIR / f"{name}.json").read_text())
    result = await KBExplorer(ReplayLLMClient(data)).explore(data["goal"])
    exp = data["expected"]

    assert result.found == exp["found"], f"{name}: found mismatch"
    for key in exp["facts"]:
        assert key in result.facts, f"{name}: expected fact {key!r} missing (re-record?)"
    if exp["sources"]:
        assert result.sources, f"{name}: expected sources, got none (re-record?)"


def test_known_it_service_specifics():
    data = json.loads((_DIR / "known_it_service.json").read_text())
    result = json.loads(_DIR.joinpath("known_it_service.json").read_text())["expected"]
    assert data["expected"]["found"] is True
    assert result["facts"]["sector"] == "AI & Machine Learning"
    assert "ViitorCloud" in result["facts"]["sector_peers"]


def test_unknown_person_is_a_miss():
    exp = json.loads((_DIR / "known_company_unknown_person.json").read_text())["expected"]
    assert exp["found"] is False
    assert exp["facts"] == {}
