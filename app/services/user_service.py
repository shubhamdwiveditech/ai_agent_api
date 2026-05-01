"""User-facing service layer built on Supabase RPCs."""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.supabase_headers import build_supabase_headers
from app.schemas.auth_schema import UserLogin
from app.schemas.llm_context_schema import LLMContext
from app.schemas.user_context_schema import TenantContext, UserContext
from app.services.supabase_service import get_supabase_service
from app.core.http import http_client


class UserService:
    async def token(self, form_data: UserLogin) -> str | None:
        """Authenticate user against Supabase and return the access token."""
        try:
            auth_url = f"{settings.supabase_url}/auth/v1/token?grant_type=password"
            headers = build_supabase_headers()
            body = {"email": form_data.email, "password": form_data.password}
            resp = await http_client.post(
                url=auth_url,
                json=body,
                headers=headers,
                params={"grant_type": "password"},
                raise_for_status=False,
            )
            if resp.status_code >= 400:
                return None
            payload = resp.json()
            return payload.get("access_token") if isinstance(payload, dict) else None
        except Exception:  # noqa: BLE001
            return None

    async def get_user_context(self, access_token: str) -> UserContext | None:
        """Call fn_get_profile and parse the first profile item into UserContext."""
        envelope = await get_supabase_service().rpc(access_token, "fn_get_profile", {})
        if not envelope.get("is_success"):
            return None

        data = envelope.get("data") or []
        profile: dict[str, Any] | None = None
        if isinstance(data, list) and data and isinstance(data[0], dict):
            profile = data[0]
        elif isinstance(data, dict):
            profile = data

        if not profile:
            return None

        tenant_payload = profile.get("tenant")
        tenant = TenantContext(**tenant_payload) if isinstance(tenant_payload, dict) else None
        return UserContext(
            id=profile.get("id"),
            user_id=str(profile.get("user_id") or profile.get("id") or ""),
            tenant_id=profile.get("tenant_id"),
            email=profile.get("email"),
            user_name=profile.get("user_name"),
            data=profile.get("data") or {},
            tenant=tenant,
            access_token=access_token,
        )

    async def get_llm_context(self, access_token: str) -> LLMContext | None:
        """Call fn_get_default_llm and parse into LLMContext."""
        envelope = await get_supabase_service().rpc(access_token, "fn_get_default_llm", {})
        if not envelope.get("is_success"):
            return None

        data = envelope.get("data") or []
        payload: dict[str, Any] | None = None
        if isinstance(data, list) and data and isinstance(data[0], dict):
            payload = data[0]
        elif isinstance(data, dict):
            payload = data

        if not payload:
            return None
        return LLMContext.model_validate(payload)


_user_service = UserService()


def get_user_service() -> UserService:
    return _user_service
