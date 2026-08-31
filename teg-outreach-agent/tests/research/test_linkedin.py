import pytest

from app.research.tools import ResearchQuery
from app.research.linkedin import LinkedInStub


async def test_linkedin_stub_always_unavailable(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("LINKEDIN_PROVIDER", "none")
    r = await LinkedInStub().lookup(ResearchQuery(
        track="person", subject="Someone", context="Acme", want=["linkedin_url"],
    ))
    assert r.available is False
    assert r.tool_name == "linkedin"


def test_linkedin_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("LINKEDIN_PROVIDER", "apify")
    from config.settings import get_settings
    get_settings.cache_clear()
    with pytest.raises(NotImplementedError):
        LinkedInStub()
    get_settings.cache_clear()
