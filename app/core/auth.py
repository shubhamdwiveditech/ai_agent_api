"""Bearer-token authentication for Supabase JWTs.

Flow per request
----------------
1. Read `Authorization: Bearer <access_token>` header.
2. Call Supabase RPC `fn_get_profile` with the same token forwarded.
3. Attach the parsed `UserContext` to `request.state.user`.
"""
from __future__ import annotations

import logging
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.schemas.user_context_schema import UserContext
from app.services.user_service import get_user_service


_log = logging.getLogger(__name__)
_bearer_scheme = HTTPBearer(auto_error=False)


async def require_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> UserContext:
    """FastAPI dependency: validate Bearer + load profile via fn_get_profile."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")

    token = credentials.credentials.strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty bearer token")

    service = get_user_service()
    try:
        user = await service.get_user_context(token)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _log.exception("fn_get_profile call failed: %s", exc)
        raise HTTPException(status_code=502, detail="Auth backend unavailable") from exc

    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
    request.state.user = user
    return user


async def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """FastAPI dependency: verify static X-API-Key header."""
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key header")
    expected = get_settings().api_key
    if x_api_key != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")
