import httpx
import respx

from app.research.tools import ResearchQuery
from app.research.web_search import TavilySearch, BraveSearch, get_web_search


@respx.mock
async def test_tavily_returns_context_and_linkedin(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    from config.settings import get_settings
    get_settings.cache_clear()
    respx.post("https://api.tavily.com/search").mock(return_value=httpx.Response(200, json={
        "results": [
            {"title": "Acme", "url": "https://acme.example", "content": "Acme builds ERP in Ahmedabad."},
            {"title": "Rohan on LinkedIn", "url": "https://in.linkedin.com/in/rohanb", "content": "CTO at Acme"},
        ]
    }))
    r = await TavilySearch().lookup(ResearchQuery(
        track="company", subject="Acme", context="Rohan B", want=["web_context", "linkedin_url"],
    ))
    assert r.available is True
    assert "Ahmedabad" in r.fields["web_context"]
    assert r.fields["linkedin_url"] == "https://in.linkedin.com/in/rohanb"
    get_settings.cache_clear()


@respx.mock
async def test_tavily_http_error_unavailable(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    from config.settings import get_settings
    get_settings.cache_clear()
    respx.post("https://api.tavily.com/search").mock(return_value=httpx.Response(500))
    r = await TavilySearch().lookup(ResearchQuery(
        track="company", subject="Acme", context="", want=["web_context"],
    ))
    assert r.available is False
    get_settings.cache_clear()


async def test_tavily_missing_key_unavailable(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("TAVILY_API_KEY", "")
    from config.settings import get_settings
    get_settings.cache_clear()
    r = await TavilySearch().lookup(ResearchQuery(
        track="company", subject="Acme", context="", want=["web_context"],
    ))
    assert r.available is False
    get_settings.cache_clear()


async def test_get_web_search_selects_provider(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "none")
    from config.settings import get_settings
    get_settings.cache_clear()
    assert get_web_search() is None
    get_settings.cache_clear()
