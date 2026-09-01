from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    llm_provider: str = "gemini"
    llm_model_fast: str = "gemini-flash-latest"
    llm_model_main: str = "gemini-flash-latest"
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
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

    # --- proposal / PDF ---
    proposal_model: str = ""  # empty -> use llm_model_main
    proposal_soft_timeout_s: int = 8
    proposal_hard_timeout_s: int = 20
    proposal_dir: str = "./proposals"
    email_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
