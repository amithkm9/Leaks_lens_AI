from functools import lru_cache
from pathlib import Path
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")
    environment: str = "development"
    database_url: str = "sqlite:///../.data/leaklens.db"
    redis_url: str = "redis://localhost:6379/0"
    job_mode: str = "local"
    data_dir: Path = Path("../.data")
    fingerprint_key: str = ""
    cookie_secure: bool = False
    allowed_origin: str = "http://localhost:5173"
    session_hours: int = 12
    max_file_bytes: int = 10 * 1024 * 1024
    max_documents: int = 100
    max_pdf_pages: int = 50
    max_csv_rows: int = 10000
    max_text_chars: int = 200000
    max_history_commits: int = 20
    http_rate_seconds: float = 0.2
    local_repo_root: Path = Path("../.data/repos")
    raw_retention_hours: int = 24
    llm_mode: str = "offline"
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-20250514"
    agent_max_tools: int = 6
    agent_timeout_seconds: int = 90
    agent_max_input_tokens: int = 18000
    agent_max_output_tokens: int = 3000
    input_price_per_million: float | None = None
    output_price_per_million: float | None = None
    agent_max_cost_usd: float = 0.25
    public_read_only: bool = False
    fixture_origin: str = ""  # Development only, exact origin; never broad private-network access.

    @model_validator(mode="after")
    def validate_production(self):
        if self.environment == "production":
            if (
                not self.cookie_secure
                or self.job_mode != "rq"
                or not self.database_url.startswith("postgresql")
            ):
                raise ValueError("Production requires PostgreSQL, RQ, and secure cookies")
            if len(self.fingerprint_key) < 32 or self.fixture_origin:
                raise ValueError("Production requires a fingerprint key and forbids fixture exceptions")
        return self


@lru_cache
def settings():
    return Settings()
