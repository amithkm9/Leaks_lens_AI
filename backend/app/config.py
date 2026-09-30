from functools import lru_cache
import os
from pathlib import Path
from typing import Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore", allow_inf_nan=False)
    environment: Literal["development", "production"] = "development"
    database_url: str = "sqlite:///../.data/leaklens.db"
    redis_url: str = "redis://localhost:6379/0"
    job_mode: Literal["local", "rq"] = "local"
    data_dir: Path = Path("../.data")
    fingerprint_key: str = ""
    cookie_secure: bool = False
    allowed_origin: str = "http://localhost:5173"
    session_hours: int = Field(default=12, gt=0)
    max_file_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    max_documents: int = Field(default=100, gt=0)
    max_pdf_pages: int = Field(default=50, gt=0)
    max_csv_rows: int = Field(default=10000, gt=0)
    max_text_chars: int = Field(default=200000, gt=0)
    max_history_commits: int = Field(default=20, gt=0)
    http_rate_seconds: float = Field(default=0.2, ge=0)
    local_repo_root: Path = Path("../.data/repos")
    raw_retention_hours: int = Field(default=24, gt=0)
    llm_mode: Literal["offline", "live"] = "offline"
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-20250514"
    agent_max_tools: int = Field(default=6, ge=1, le=6)
    agent_timeout_seconds: int = Field(default=90, gt=0)
    agent_max_input_tokens: int = Field(default=18000, gt=0)
    agent_max_output_tokens: int = Field(default=3000, gt=0)
    input_price_per_million: float | None = Field(default=None, ge=0)
    output_price_per_million: float | None = Field(default=None, ge=0)
    agent_max_cost_usd: float = Field(default=0.25, gt=0)
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
    if os.environ.get("LEAKLENS_MCP_CASE"):
        # MCP receives its database/case scope from the worker, never the owner's .env.
        return Settings(_env_file=None, anthropic_api_key="", llm_mode="offline")
    return Settings()
