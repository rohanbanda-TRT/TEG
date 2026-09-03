"""The Claude connection API: status, browser login, API-key connect/disconnect."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.api import claude_conn
from app.claude.cli import ClaudeCli
from app.main import app

pytestmark = pytest.mark.asyncio


class _FakeCli(ClaudeCli):
    def __init__(self, *, auth=None, probe_ok=True, probe_reason="nope"):
        self._auth = auth
        self._probe_ok = probe_ok
        self._probe_reason = probe_reason
        self.login_started = 0
        self.probe_calls: list[dict] = []

    async def auth_status(self, *, cwd):
        return self._auth

    async def probe(self, *, model, cwd, timeout_s=15.0):
        self.probe_calls.append({"model": model})
        return (True, "") if self._probe_ok else (False, self._probe_reason)

    def start_login(self, *, cwd):
        self.login_started += 1


@pytest.fixture(autouse=True)
def _reset():
    claude_conn.set_cli(None)
    claude_conn.set_api_key(None)
    yield
    claude_conn.set_cli(None)
    claude_conn.set_api_key(None)


async def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def test_status_reports_a_local_login_without_a_model_call():
    fake = _FakeCli(auth={"logged_in": True, "email": "a@b.com", "subscription_type": "pro"})
    claude_conn.set_cli(fake)

    async with await _client() as c:
        r = await c.get("/claude/status")

    assert r.status_code == 200
    body = r.json()
    assert body["connected"] is True
    assert body["source"] == "local_login"
    assert body["email"] == "a@b.com"
    assert body["subscription_type"] == "pro"
    # the fast path must not spend a real round trip
    assert fake.probe_calls == []


async def test_status_reports_not_signed_in():
    claude_conn.set_cli(_FakeCli(auth={"logged_in": False}))

    async with await _client() as c:
        body = (await c.get("/claude/status")).json()

    assert body["connected"] is False
    assert "sign in" in body["reason"].lower()


async def test_status_falls_back_to_probe_when_auth_status_is_unreadable():
    fake = _FakeCli(auth=None, probe_ok=True)
    claude_conn.set_cli(fake)

    async with await _client() as c:
        body = (await c.get("/claude/status")).json()

    assert body["connected"] is True
    assert fake.probe_calls, "an unreadable auth status must fall back to a probe"


async def test_status_uses_the_probe_when_an_api_key_is_set():
    fake = _FakeCli(auth={"logged_in": True}, probe_ok=True)
    claude_conn.set_cli(fake)
    claude_conn.set_api_key("sk-ant-test")

    async with await _client() as c:
        body = (await c.get("/claude/status")).json()

    assert body["connected"] is True
    assert body["source"] == "api_key"
    assert fake.probe_calls, "an explicit key must be verified, not assumed"


async def test_status_surfaces_a_probe_failure_reason():
    claude_conn.set_cli(_FakeCli(auth=None, probe_ok=False, probe_reason="credit balance too low"))

    async with await _client() as c:
        body = (await c.get("/claude/status")).json()

    assert body["connected"] is False
    assert "credit balance" in body["reason"]


async def test_login_starts_the_browser_flow():
    fake = _FakeCli()
    claude_conn.set_cli(fake)

    async with await _client() as c:
        r = await c.post("/claude/login")

    assert r.status_code == 200
    assert r.json() == {"ok": True, "started": True}
    assert fake.login_started == 1


async def test_connect_stores_the_key_and_disconnect_clears_it():
    claude_conn.set_cli(_FakeCli(auth={"logged_in": True}))

    async with await _client() as c:
        r = await c.post("/claude/connect", json={"api_key": "sk-ant-abc123"})
        assert r.status_code == 200
        assert claude_conn.get_api_key() == "sk-ant-abc123"

        r = await c.post("/claude/disconnect")
        assert r.status_code == 200
        assert claude_conn.get_api_key() is None


async def test_connect_rejects_a_missing_key():
    async with await _client() as c:
        r = await c.post("/claude/connect", json={})

    assert r.status_code == 422


async def test_connect_rejects_a_blank_key():
    async with await _client() as c:
        r = await c.post("/claude/connect", json={"api_key": "   "})

    assert r.status_code == 422


async def test_connect_page_is_served():
    async with await _client() as c:
        r = await c.get("/connect")

    assert r.status_code == 200
    assert "Connect Claude" in r.text
    assert "Sign in with browser" in r.text


async def test_status_never_echoes_the_key_back():
    claude_conn.set_cli(_FakeCli(auth=None, probe_ok=True))
    claude_conn.set_api_key("sk-ant-super-secret")

    async with await _client() as c:
        raw = (await c.get("/claude/status")).text

    assert "sk-ant-super-secret" not in raw
