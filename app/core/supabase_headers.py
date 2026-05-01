"""Supabase auth header helpers (kept separate to avoid import cycles)."""

from __future__ import annotations

from app.core.config import get_settings


def build_supabase_headers(access_token: str | None = None) -> dict[str, str]:
    settings = get_settings()
    headers = {
        "apikey": settings.supabase_key,
        "Content-Type": "application/json",
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def build_auth_headers(access_token: str) -> dict[str, str]:
    return build_supabase_headers(access_token)
