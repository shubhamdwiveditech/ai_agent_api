"""Small cross-cutting helpers used across services."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone


def new_uuid() -> str:
    """Return a fresh UUIDv4 as a string."""
    return str(uuid.uuid4())


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()
