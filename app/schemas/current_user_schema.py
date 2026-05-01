"""Current user context schema (compat)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class CurrentUserContext(BaseModel):
    access_token: str | None = None
    user_id: str | None = None
    tenant_id: str | None = None
    data: dict[str, Any] = {}

