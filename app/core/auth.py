"""Bearer-token authentication for Supabase JWTs.

Flow per request
----------------
1. Read `Authorization: Bearer <access_token>` header.
2. (Optional) Verify JWT locally with HS256 + SUPABASE_JWT_SECRET. If the
   secret isn't configured, we skip local verification and rely entirely on
   PostgREST (it will reject an invalid token when we call fn_get_profile).
3. Call PostgREST RPC `fn_get_profile` with the same token forwarded as
   Authorization (apikey = SUPABASE_KEY). The function reads the JWT claim
   server-side via fn_get_request_context and returns the profile envelope.
4. Parse the envelope and attach a `UserContext` to `request.state.user`.
"""
from __future__ import annotations

import logging
from typing import Any

import jwt as pyjwt
from fastapi import Header, HTTPException, Request, status

from app.core.config import get_settings
from app.schemas.user_context_schema import TenantContext, UserContext
from app.services.user_service import get_user_service


_log = logging.getLogger(__name__)
_BEARER = "bearer"



def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    parts = authorization.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != _BEARER:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must be of form 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = parts[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


def _verify_jwt_locally(token: str) -> dict[str, Any] | None:
    """Verify HS256 signature when SUPABASE_JWT_SECRET is configured.

    Returns claims on success, None when local verification is disabled.
    Raises 401 on a structural / signature / expiry failure.
    """
    s = get_settings()
    if not s.supabase_jwt_secret:
        return None
    try:
        return pyjwt.decode(
            token,
            key=s.supabase_jwt_secret,
            algorithms=["HS256"],
            audience=s.supabase_jwt_audience,
            options={"require": ["exp", "sub"]},
        )
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Access token expired") from None
    except pyjwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid access token: {exc}") from None


def _parse_envelope(envelope: Any, *, access_token: str) -> UserContext:
    """fn_get_profile returns:
        { is_success: bool, message: str, data: [ { ...profile... } ] }
    """
    if not isinstance(envelope, dict) or not envelope.get("is_success"):
        msg = (envelope or {}).get("message") if isinstance(envelope, dict) else None
        raise HTTPException(status_code=401, detail=msg or "Profile lookup failed")

    data = envelope.get("data") or []
    if isinstance(data, list):
        if not data:
            raise HTTPException(status_code=401, detail="Profile not found")
        profile = data[0]
    elif isinstance(data, dict):
        profile = data
    else:
        raise HTTPException(status_code=401, detail="Unexpected profile payload")

    tenant = profile.get("tenant")
    return UserContext(
        id=profile.get("id"),
        user_id=str(profile.get("user_id") or profile.get("id")),
        tenant_id=profile.get("tenant_id"),
        email=profile.get("email"),
        user_name=profile.get("user_name"),
        data=profile.get("data") or {},
        tenant=TenantContext(**tenant) if isinstance(tenant, dict) else None,
        access_token=access_token,
    )


async def require_user(
    request: Request,
    authorization: str | None = Header(default=None),
) -> UserContext:
    """FastAPI dependency: validate Bearer + load profile via fn_get_profile."""
    token = _extract_bearer(authorization)

    # 1. Local signature check (best-effort; skipped if no secret configured).
    _verify_jwt_locally(token)

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
