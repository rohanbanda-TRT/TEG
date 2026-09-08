from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel


class Out(BaseModel):
    name: str


@pytest.fixture
def gemini_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    from config.settings import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_generate_returns_text(gemini_env):
    from app.llm.gemini_client import GeminiClient

    fake_resp = SimpleNamespace(text="hi there", parsed=None)
    with patch("app.llm.gemini_client.genai.Client") as m:
        m.return_value.aio.models.generate_content = AsyncMock(return_value=fake_resp)
        c = GeminiClient()
        out = await c.generate(system="s", messages=[{"role": "user", "content": "x"}])
    assert out == "hi there"


async def test_generate_structured_parses_json(gemini_env):
    from app.llm.gemini_client import GeminiClient

    fake_resp = SimpleNamespace(text='{"name": "Rohan"}', parsed=None)
    with patch("app.llm.gemini_client.genai.Client") as m:
        m.return_value.aio.models.generate_content = AsyncMock(return_value=fake_resp)
        c = GeminiClient()
        out = await c.generate_structured(
            system="s", messages=[{"role": "user", "content": "x"}], schema=Out
        )
    assert out.name == "Rohan"


def test_get_llm_selects_gemini(gemini_env):
    from app.llm.base import get_llm
    from app.llm.gemini_client import GeminiClient
    from app.llm.logging_client import LoggingLLMClient
    client = get_llm()
    assert isinstance(client, LoggingLLMClient)
    assert isinstance(client._inner, GeminiClient)
