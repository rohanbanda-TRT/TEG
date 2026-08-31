from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel


class Out(BaseModel):
    name: str


@pytest.fixture
def anthropic_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")


async def test_generate_extracts_text(anthropic_env):
    from app.llm.anthropic_client import AnthropicClient

    fake_resp = SimpleNamespace(content=[SimpleNamespace(type="text", text="hi there")])
    with patch("app.llm.anthropic_client.AsyncAnthropic") as m:
        m.return_value.messages.create = AsyncMock(return_value=fake_resp)
        c = AnthropicClient()
        out = await c.generate(system="s", messages=[{"role": "user", "content": "x"}])
    assert out == "hi there"


async def test_generate_structured_parses_tool_input(anthropic_env):
    from app.llm.anthropic_client import AnthropicClient

    fake_resp = SimpleNamespace(content=[
        SimpleNamespace(type="tool_use", name="emit", input={"name": "Rohan"})
    ])
    with patch("app.llm.anthropic_client.AsyncAnthropic") as m:
        m.return_value.messages.create = AsyncMock(return_value=fake_resp)
        c = AnthropicClient()
        out = await c.generate_structured(
            system="s", messages=[{"role": "user", "content": "x"}], schema=Out
        )
    assert out.name == "Rohan"
