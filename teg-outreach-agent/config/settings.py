from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    llm_provider: str = "anthropic"
    llm_model_fast: str = "claude-haiku-4-5-20251001"
    llm_model_main: str = "claude-sonnet-5"
    anthropic_api_key: str = ""
    web_search_provider: str = "tavily"
    tavily_api_key: str = ""
    brave_api_key: str = ""
    research_max_searches_per_track: int = 2
    research_max_scrapes: int = 3
    pipeline_soft_timeout_s: int = 8
    pipeline_hard_timeout_s: int = 20
    kb_path: str = "../teg-kb-agent/knowledge_base"
    data_retention_days: int = 180
    linkedin_provider: str = "none"


@lru_cache
def get_settings() -> Settings:
    return Settings()
