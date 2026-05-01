"""User context returned by fn_get_profile and attached to request.state."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TenantContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int | str | None = None
    code: str | None = None
    name: str | None = None
    domain: str | None = None
    data: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class UserContext(BaseModel):
    """Subset of profile fields used by handlers. Extra fields are preserved."""

    model_config = ConfigDict(extra="allow")

    id: int | str | None = None
    user_id: str = Field(..., description="auth.users.id (JWT sub)")
    tenant_id: int | str | None = None
    email: str | None = None
    user_name: str | None = None
    data: dict[str, Any] | None = None
    tenant: TenantContext | None = None

    # Raw access token (forwarded to PostgREST so RLS sees the caller).
    access_token: str = Field(..., description="Bearer token from the request, forwarded to PostgREST")

    @property
    def is_admin(self) -> bool:
        if not self.data:
            return False
        return bool(self.data.get("is_admin"))
