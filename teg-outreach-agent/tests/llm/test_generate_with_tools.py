import pytest

from app.llm.base import ToolCall, ToolTurn
from app.llm.fake import FakeLLMClient


async def test_fake_returns_queued_tool_turn():
    turn = ToolTurn(tool_calls=[ToolCall(id="a", name="list_dir", args={"path": "."})])
    fake = FakeLLMClient(tool_turns=[turn])
    got = await fake.generate_with_tools(system="s", messages=[], tools=[])
    assert got.tool_calls[0].name == "list_dir"


async def test_fake_returns_text_turn_then_raises_when_empty():
    fake = FakeLLMClient(tool_turns=[ToolTurn(text="done")])
    assert (await fake.generate_with_tools(system="s", messages=[], tools=[])).text == "done"
    with pytest.raises(AssertionError):
        await fake.generate_with_tools(system="s", messages=[], tools=[])
