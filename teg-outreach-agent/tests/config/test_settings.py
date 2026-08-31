from config.settings import Settings, get_settings


def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    s = Settings()
    assert s.llm_provider == "anthropic"
    assert s.web_search_provider == "tavily"
    assert s.research_max_searches_per_track == 2
    assert s.linkedin_provider == "none"
    assert s.kb_path.endswith("teg-kb-agent/knowledge_base")


def test_get_settings_is_cached(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    assert get_settings() is get_settings()
