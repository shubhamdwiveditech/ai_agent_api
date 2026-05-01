"""Supabase auth header helpers (kept separate to avoid import cycles)."""

from __future__ import annotations

from app.core.config import get_settings


def build_auth_headers(access_token: str) -> dict[str, str]:
    settings = get_settings()
    return {
        "apikey": settings.supabase_key,
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

