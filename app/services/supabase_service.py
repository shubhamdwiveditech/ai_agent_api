"""
Designed to be used for invoking Supabase RPC functions with a normalized response envelope.
"""
from typing import Dict, List  # noqa: E402
from __future__ import annotations
from typing import Any

from app.core.supabase_headers import build_auth_headers  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.http import http_client  # noqa: E402
from app.schemas.current_user_schema import Msi  # noqa: E402


class SupabaseService:
    """Utility wrapper around Supabase RPC invocations."""

    def _normalize_success(self, payload: Any, status_code: int = 200) -> Dict[str, Any]:
        data: List[Dict[str, Any]] = []
        paging = {"page_size": 0, "page_index": 1, "total_records": 0}
        message = "Success"
        is_success = True

        if isinstance(payload, dict):
            raw_data = payload.get("data")
            if isinstance(raw_data, list):
                data = [item for item in raw_data if isinstance(item, dict)]
            elif isinstance(raw_data, dict):
                data = [raw_data]
            elif raw_data is None:
                if "data" not in payload and payload:
                    data = [payload]
            else:
                data = [{"value": raw_data}]

            if isinstance(payload.get("paging"), dict):
                paging = {
                    "page_size": int(payload["paging"].get("page_size", len(data))),
                    "page_index": int(payload["paging"].get("page_index", 1)),
                    "total_records": int(payload["paging"].get("total_records", len(data))),
                }
            else:
                paging = {"page_size": len(data), "page_index": 1, "total_records": len(data)}

            message = str(payload.get("message", "Success"))
            is_success = bool(payload.get("is_success", True))
            status_code = int(payload.get("status_code", status_code))
        elif isinstance(payload, list):
            data = [item for item in payload if isinstance(item, dict)]
            paging = {"page_size": len(data), "page_index": 1, "total_records": len(data)}
        elif payload is not None:
            data = [{"value": payload}]
            paging = {"page_size": 1, "page_index": 1, "total_records": 1}

        return {
            "data": data,
            "paging": paging,
            "message": message,
            "is_success": is_success,
            "status_code": status_code,
        }

    def _normalize_error(self, message: str, status_code: int) -> Dict[str, Any]:
        return {
            "data": [],
            "paging": {"page_size": 0, "page_index": 1, "total_records": 0},
            "message": message,
            "is_success": False,
            "status_code": status_code,
        }

    async def rpc(self, access_token: str, fn_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = build_auth_headers(access_token)
        url = f"{settings.supabase_url}/rest/v1/rpc/{fn_name}"
        response = await http_client.post(url=url, json=payload, headers=headers, raise_for_status=False)
        if response.status_code >= 400:
            try:
                error_payload = response.json()
                error_message = (
                    error_payload.get("message")
                    if isinstance(error_payload, dict)
                    else str(error_payload)
                )
            except Exception:
                error_message = response.text or "Supabase RPC error"
            return self._normalize_error(message=str(error_message), status_code=response.status_code)
        try:
            return self._normalize_success(payload=response.json(), status_code=response.status_code)
        except Exception:
            return self._normalize_error(message="Invalid Supabase RPC response", status_code=response.status_code)


_supabase_service = SupabaseService()


def get_supabase_service() -> SupabaseService:
    return _supabase_service
