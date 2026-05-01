from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ── CORS configuration (edit here to change behaviour) ────────────────────────
_DEFAULT_ASSETINFINITY_REGEX = r"^https://([a-z0-9-]+\.)*assetinfinity\.(io|ai)$"
_LOCALHOST_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

_DEFAULT_ALLOW_METHODS = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
_DEFAULT_ALLOW_HEADERS = "*"


def _split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _env_str(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return default if value is None else value


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _cors_is_dev_mode() -> bool:
    environment = (_env_str("ENVIRONMENT", "dev") or "dev").strip().lower()
    return environment in {"dev", "local"}


def _or_regex(existing: str | None, extra: str) -> str:
    if not existing:
        return extra
    return f"(?:{existing})|(?:{extra})"


def setup_cors(app: FastAPI) -> None:
    """
    Attach CORSMiddleware to *app*.

    Rules
    -----
    - No origins / regex configured → allow-all ("*"), credentials forced off
      (wildcard + credentials is an invalid CORS combination).
    - Origins configured but no regex, and DEBUG or ENVIRONMENT=="dev"
      → localhost auto-whitelisted via regex.
    - ALLOW_HEADERS="*" is kept as-is; anything else is split on commas.
    """
    parsed_origins: list[str] = _split_csv(_env_str("CORS_ALLOW_ORIGINS", ""))
    parsed_regex: str | None = _env_str("CORS_ALLOW_ORIGIN_REGEX", "").strip() or None
    allow_credentials = _env_bool("CORS_ALLOW_CREDENTIALS", True)

    cors_is_configured = bool(parsed_origins) or bool(parsed_regex)

    if not cors_is_configured:
        parsed_origins = []
        parsed_regex = _DEFAULT_ASSETINFINITY_REGEX

    if _cors_is_dev_mode():
        parsed_regex = _or_regex(parsed_regex, _LOCALHOST_REGEX)

    parsed_methods = _split_csv(_env_str("CORS_ALLOW_METHODS", _DEFAULT_ALLOW_METHODS)) or ["*"]
    allow_headers_raw = _env_str("CORS_ALLOW_HEADERS", _DEFAULT_ALLOW_HEADERS).strip()
    parsed_headers = ["*"] if allow_headers_raw == "*" else _split_csv(allow_headers_raw)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=parsed_origins,
        allow_origin_regex=parsed_regex,
        allow_credentials=allow_credentials,
        allow_methods=parsed_methods,
        allow_headers=parsed_headers,
    )
