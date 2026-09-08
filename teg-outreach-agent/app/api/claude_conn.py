"""Connect this service to Claude — browser sign-in or an API key.

Two ways in:

* **Browser sign-in** (`POST /claude/login`) hands off to `claude auth login`,
  which opens the user's own browser and stores the session itself. This app
  never sees or stores a token for that path.
* **API key** (`POST /claude/connect`) holds the key **in memory only** for the
  life of the process, seeded from ANTHROPIC_API_KEY at boot. It is never
  written to disk, never logged, and never returned by `GET /claude/status`.

Anthropic requires API-key auth for third-party products, so a deployment
serving real users should use the key path; browser sign-in is for local work.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, field_validator

from app.claude.cli import ClaudeCli
from app.obs import get_logger
from config.settings import get_settings

router = APIRouter()
_log = get_logger("api.claude")

# In-memory only, process lifetime. Seeded from the environment at import.
_api_key: str | None = get_settings().anthropic_api_key or None
_cli: ClaudeCli | None = None
_cli_pinned = False  # set by set_cli(); keeps a test double from being rebuilt


def get_api_key() -> str | None:
    return _api_key


def set_api_key(key: str | None) -> None:
    global _api_key, _cli
    _api_key = key or None
    if not _cli_pinned:
        _cli = None  # rebuild so the new key takes effect


def set_cli(cli: ClaudeCli | None) -> None:
    """Test seam. A pinned CLI survives set_api_key()."""
    global _cli, _cli_pinned
    _cli = cli
    _cli_pinned = cli is not None


def get_cli() -> ClaudeCli:
    global _cli
    if _cli is None:
        _cli = ClaudeCli(api_key=_api_key or "")
    return _cli


def _cwd() -> str:
    return str(Path(get_settings().skills_path).resolve().parent)


class ConnectBody(BaseModel):
    api_key: str

    @field_validator("api_key")
    @classmethod
    def _non_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("api_key must not be blank")
        return v.strip()


_CONNECT_PAGE = Path(__file__).resolve().parents[1] / "static" / "connect.html"


@router.get("/connect", response_class=HTMLResponse)
async def connect_page() -> HTMLResponse:
    if not _CONNECT_PAGE.is_file():  # pragma: no cover - packaging guard
        raise HTTPException(status_code=404, detail="connect page not found")
    return HTMLResponse(_CONNECT_PAGE.read_text("utf-8"))


@router.get("/claude/status")
async def status() -> dict:
    """Is Claude reachable, and how?  Never echoes the key."""
    cli = get_cli()
    settings = get_settings()

    # With no explicit key, read the CLI's own stored session instead of
    # spending a real round trip. This only ever *shortcuts* to a positive
    # answer — on any failure to read it we fall through to the real probe.
    if not _api_key:
        auth = await cli.auth_status(cwd=_cwd())
        if auth is not None:
            if auth["logged_in"]:
                return {
                    "connected": True,
                    "source": "local_login",
                    "email": auth.get("email"),
                    "subscription_type": auth.get("subscription_type"),
                }
            return {
                "connected": False,
                "reason": 'Not signed in — click "Sign in with browser" to '
                          "connect your Claude account, or paste an API key.",
            }

    ok, reason = await cli.probe(model=settings.claude_cli_model, cwd=_cwd())
    if ok:
        return {"connected": True, "source": "api_key" if _api_key else "local_login"}
    return {"connected": False, "reason": reason}


@router.post("/claude/login")
async def login() -> dict:
    """Open a real browser sign-in. Fire-and-forget; the client re-polls /status."""
    get_cli().start_login(cwd=_cwd())
    _log.info("claude browser sign-in started")
    return {"ok": True, "started": True}


@router.post("/claude/connect")
async def connect(body: ConnectBody) -> dict:
    set_api_key(body.api_key)
    _log.info("claude api key set (in memory, %d chars)", len(body.api_key))
    return {"ok": True}


@router.post("/claude/disconnect")
async def disconnect() -> dict:
    """Clear the in-memory key so /status falls back to any local login."""
    set_api_key(None)
    _log.info("claude api key cleared")
    return {"ok": True}
