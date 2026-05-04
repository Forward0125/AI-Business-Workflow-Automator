"""Application settings -- env-driven, validated via pydantic-settings.

The .env file at the repo root is the source of truth in development.
In production we read straight from process env (Render, Vercel, etc.).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# api/app/settings.py -> api/app -> api -> repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """All env-driven configuration for the workflow-automator API."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ─── Database ───────────────────────────────────────────────
    database_url: str = Field(..., description="Postgres connection URL")

    # ─── LLM ────────────────────────────────────────────────────
    openai_api_key:   str = Field(default="",            description="OpenAI API key")
    generator_model:  str = "gpt-4o-mini"
    evaluator_model:  str = "gpt-4o-mini"

    # ─── Web search ─────────────────────────────────────────────
    # Brave Search free tier (2k/mo). Empty string = skip the
    # web-search step entirely; research uses URL scrape only.
    brave_api_key: str = ""

    # ─── API server ─────────────────────────────────────────────
    api_host:        str = "0.0.0.0"
    api_port:        int = 8000
    api_cors_origins: str = "http://localhost:3000"

    # ─── Cost guards ────────────────────────────────────────────
    daily_spend_cap_usd:      float = 5.0
    workflow_runs_per_hour:   int   = 5
    max_fetch_bytes:          int   = 5_242_880
    fetch_timeout_seconds:    int   = 30

    # ─── Observability ──────────────────────────────────────────
    log_level: str = "INFO"

    # ─── HTTP user agent ────────────────────────────────────────
    http_user_agent: str = (
        "AIBusinessWorkflowAutomator/0.1 "
        "(+https://github.com/Forward0125/AI-Business-Workflow-Automator)"
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]


# Module-level singleton -- instantiated once on import.
settings = Settings()
