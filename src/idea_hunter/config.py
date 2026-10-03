from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://ideahunter:ideahunter@localhost:5432/ideahunter"

    # Local Ollama (pre-filter / cheap tasks)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model_small: str = "granite3.1-dense:2b"
    ollama_model_medium: str = "granite3.1-dense:2b"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_timeout_seconds: float = 30.0

    # Hosted LLM (reasoning-heavy extraction)
    llm_provider: str = "openrouter"          # "ollama" | "openai" | "anthropic" | "openrouter"
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_max_tokens: int = 1024
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-haiku-20241022"

    # Cost guardrails
    max_cost_per_run_usd: float = 2.0
    max_agent_iterations: int = 3
    extraction_clusters_per_run: int = 2
    research_problems_per_run: int = 1

    # Evidence-spend gate. Hosted extraction is allowed only when a cluster
    # meets one of the configured corroboration paths.
    spend_gate_min_independent_authors: int = 3
    spend_gate_min_sources: int = 2
    spend_gate_min_active_days: int = 14
    spend_gate_max_evidence_age_days: int = 30
    path_b_confidence_cap: float = 0.25
    worker_poll_seconds: float = 2.0
    api_cors_origins: str = "http://localhost:5173"

    # GitHub
    github_token: str = ""

    # Reddit
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "IdeaHunter/0.1"

    # Public-source adapters
    product_hunt_token: str = ""
    collector_user_agent: str = "IdeaHunter/0.1 (+local research collector)"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
