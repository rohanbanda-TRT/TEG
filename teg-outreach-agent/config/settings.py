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
    # How long a stored company_briefs row is trusted before a new inquiry
    # for the same company re-runs research instead of reusing it.
    company_brief_staleness_days: int = 30
    pipeline_soft_timeout_s: int = 15
    pipeline_hard_timeout_s: int = 90
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

    # --- claude CLI backend ---
    # When true, ProposalAgent generates through the `claude` CLI (skills as
    # prompt assets, --json-schema structured output) instead of the LLM client.
    # Guardrails run identically on the result either way.
    claude_cli_enabled: bool = True
    claude_cli_model: str = "claude-sonnet-5"
    # 240s, not the previous 180s: genuine multi-hop research (several
    # WebSearch calls, following a link, cross-checking a second source)
    # needs real time inside one CLI invocation — 240s gives room for
    # roughly 5-10 tool calls at a realistic 15-25s each, and matches the
    # budget proposal_hard_timeout_s already uses for a comparable
    # single-CLI-call workload.
    claude_cli_timeout_s: float = 240.0
    skills_path: str = "./skills"

    # --- TEG-claim verification harness (app/verify/) ---
    # Wall-clock bound for one verify_claim() call — one or two WebSearch/
    # WebFetch round-trips per the teg-verify skill's search budget.
    verify_claim_timeout_s: float = 120.0

    # --- discovery v2 ---
    # When true, the conversation runs the evidence-aware DiscoveryState +
    # completeness + policy layer, and the proposal trigger is gated on
    # discovery being sufficient (+ a validation playback). Off -> the legacy
    # _Analysis.discovery dict + shallow merge, unchanged.
    discovery_v2_enabled: bool = False

    # --- proposal / PDF ---
    proposal_model: str = ""  # empty -> use llm_model_main
    proposal_soft_timeout_s: int = 240
    proposal_hard_timeout_s: int = 240
    proposal_dir: str = "./proposals"
    # Bounded retry budget for the cross-field self-consistency check
    # (ProposalAgent.build(), post per-field guardrail loop). Start
    # conservative, same discipline as every other step cap in this repo.
    proposal_consistency_max_loops: int = 1
    # Proposals are delivered as a link to `/p/{id}`, not a PDF. The widget
    # resolves that path against its own origin fine, but an emailed link
    # needs an absolute URL — set this to the deployed app's origin (no
    # trailing slash), e.g. "https://outreach.techexpogujarat.com".
    public_base_url: str = ""
    email_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
