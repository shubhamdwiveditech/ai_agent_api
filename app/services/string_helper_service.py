"""String / text utilities used by the API layer."""
from __future__ import annotations

import re


_WHITESPACE_RE = re.compile(r"\s+")


def collapse_whitespace(text: str) -> str:
    """Replace any run of whitespace with a single space and strip ends."""
    return _WHITESPACE_RE.sub(" ", text).strip()


def truncate(text: str, max_len: int, suffix: str = "…") -> str:
    """Truncate text to `max_len` chars (including the suffix)."""
    if max_len <= 0 or len(text) <= max_len:
        return text
    cut = max_len - len(suffix)
    if cut <= 0:
        return suffix[:max_len]
    return text[:cut] + suffix


def safe_str(value: object | None, default: str = "") -> str:
    """Return str(value) or `default` for None."""
    return default if value is None else str(value)
