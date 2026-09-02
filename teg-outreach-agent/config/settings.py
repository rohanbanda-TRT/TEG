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

    # --- observability ---
    log_level: str = "INFO"          # DEBUG shows per-step detail
    log_verbose: bool = False        # True -> DEBUG + include prompt/response bodies
    log_body_chars: int = 800        # truncation for logged prompt/response bodies

    # --- KB explorer ---
    kb_explore_model: str = "gemini-3.7-flash"  # the graph map in _SYSTEM keeps flash on track
    kb_explore_timeout_s: int = 45   # wall-clock per explore() call
    kb_explore_max_steps: int = 8    # model turns before a forced answer
    kb_read_file_max_bytes: int = 6144  # read_file page size
    kb_grep_max_matches: int = 30    # grep result cap

    # --- proposal / PDF ---
    proposal_model: str = ""  # empty -> use llm_model_main
    proposal_soft_timeout_s: int = 12
    proposal_hard_timeout_s: int = 60
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
