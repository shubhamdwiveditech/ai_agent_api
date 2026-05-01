"""Application configuration loaded from environment variables.

Picks the right env file via the ENVIRONMENT variable:
  ENVIRONMENT=dev      -> .env.dev   (default)
  ENVIRONMENT=staging  -> .env.staging
  ENVIRONMENT=prod     -> .env.prod
A plain `.env` is also honoured if present.
"""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _env_file_for(environment: str | None) -> tuple[str, ...]:
    env = (environment or os.getenv("ENVIRONMENT") or "dev").strip().lower()
    return (".env", f".env.{env}")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_file_for(None),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    environment: str = "dev"
    app_name: str = "ai_agent_api"

    # Auth
    api_key: str = Field(..., description="Static API key for X-API-Key auth")

    # Supabase REST (publishable / anon key + project URL)
    supabase_url: str = Field(..., description="Supabase project URL, e.g. https://<ref>.supabase.co")
    supabase_key: str = Field(..., description="Supabase publishable / anon key (apikey header)")

    # JWT verification
    # If set, JWT is verified locally with HS256 (legacy Supabase secret).
    # If empty, JWT verification is skipped locally and we rely on
    # fn_get_profile (PostgREST validates the JWT server-side via the apikey).
    supabase_jwt_secret: str | None = None
    supabase_jwt_audience: str = "authenticated"

    # OpenAI
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_chat_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"
    openai_embed_dims: int = 1536

    # RAG tuning (mirrors edge function defaults)
    rag_match_threshold: float = 0.3
    rag_match_count: int = 6

    # Embedding job tuning
    embed_chunk_size: int = 1200
    embed_chunk_overlap: int = 150
    embed_batch_size: int = 16
    embed_storage_bucket: str = "knowledge-base"

    # HTTP
    http_timeout_seconds: float = 60.0

    @property
    def supabase_rest_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/rest/v1"

    @property
    def supabase_storage_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/storage/v1"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
