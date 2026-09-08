import pytest
from pydantic import BaseModel

from app.llm.fake import FakeLLMClient


class Out(BaseModel):
    x: int


async def test_fake_generate_returns_queued():
    c = FakeLLMClient(responses=["hello"])
    r = await c.generate(system="s", messages=[{"role": "user", "content": "hi"}])
    assert r == "hello"
    assert c.calls[0]["system"] == "s"


async def test_fake_generate_structured_returns_queued():
    c = FakeLLMClient(structured=[Out(x=5)])
    r = await c.generate_structured(
        system="s", messages=[{"role": "user", "content": "hi"}], schema=Out
    )
    assert r.x == 5


async def test_fake_structured_without_queue_raises():
    c = FakeLLMClient()
    with pytest.raises(AssertionError):
        await c.generate_structured(
            system="s", messages=[{"role": "user", "content": "hi"}], schema=Out
        )
