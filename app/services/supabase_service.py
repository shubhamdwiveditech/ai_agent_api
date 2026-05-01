"""Async Supabase REST client built on httpx (no `supabase` SDK).

Talks to PostgREST (`/rest/v1`) and Storage (`/storage/v1`). Two construction
modes:

* `SupabaseClient.for_user(token)` — uses the publishable/anon key as `apikey`
  and the user's JWT as `Authorization: Bearer …`. Server-side RLS is honoured.
  This is the default mode — every authenticated request should use this.

* `SupabaseClient.unauthenticated()` — apikey only, no bearer. Used by the
  auth middleware to call `fn_get_profile` while forwarding the caller's
  token (the token is supplied via headers per-call).
"""
from __future__ import annotations

from typing import Any, AsyncIterator, Iterable
from urllib.parse import quote

import httpx
from fastapi import HTTPException

from app.core.config import get_settings


class SupabaseError(HTTPException):
    """HTTP error raised when Supabase / PostgREST returns a non-2xx response."""

    def __init__(self, code: int, detail: Any):
        super().__init__(status_code=code, detail=detail)


class SupabaseClient:
    """Lightweight async wrapper around Supabase PostgREST + Storage."""

    def __init__(
        self,
        *,
        project_url: str,
        apikey: str,
        bearer: str | None,
        timeout: float = 60.0,
    ) -> None:
        self._project_url = project_url.rstrip("/")
        self._apikey = apikey
        self._bearer = bearer
        self._client = httpx.AsyncClient(timeout=timeout)

    # ------------------------------------------------------------------ ctors
    @classmethod
    def for_user(cls, access_token: str) -> "SupabaseClient":
        s = get_settings()
        return cls(
            project_url=s.supabase_url,
            apikey=s.supabase_key,
            bearer=access_token,
            timeout=s.http_timeout_seconds,
        )

    @classmethod
    def unauthenticated(cls) -> "SupabaseClient":
        s = get_settings()
        return cls(
            project_url=s.supabase_url,
            apikey=s.supabase_key,
            bearer=None,
            timeout=s.http_timeout_seconds,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------ infra
    def _headers(self, *, override_bearer: str | None = None, extra: dict[str, str] | None = None) -> dict[str, str]:
        bearer = override_bearer or self._bearer
        out: dict[str, str] = {
            "apikey": self._apikey,
            "Content-Type": "application/json",
        }
        if bearer:
            out["Authorization"] = f"Bearer {bearer}"
        if extra:
            out.update(extra)
        return out

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise SupabaseError(code=resp.status_code, detail=detail)

    # ------------------------------------------------------------------ REST
    async def select(
        self,
        table: str,
        *,
        columns: str = "*",
        filters: dict[str, str] | None = None,
        order: str | None = None,
        limit: int | None = None,
        single: bool = False,
    ) -> list[dict[str, Any]] | dict[str, Any] | None:
        params: dict[str, str] = {"select": columns}
        if filters:
            params.update(filters)
        if order:
            params["order"] = order
        if limit is not None:
            params["limit"] = str(limit)

        headers = self._headers(extra={"Accept": "application/vnd.pgrst.object+json"} if single else None)

        url = f"{self._project_url}/rest/v1/{table}"
        resp = await self._client.get(url, params=params, headers=headers)
        if single and resp.status_code == 406:
            return None  # PostgREST: empty result under object accept
        self._raise_for_status(resp)
        return resp.json()

    async def insert(
        self,
        table: str,
        rows: dict[str, Any] | list[dict[str, Any]],
        *,
        return_representation: bool = True,
    ) -> list[dict[str, Any]]:
        headers = self._headers(extra={
            "Prefer": "return=representation" if return_representation else "return=minimal",
        })
        url = f"{self._project_url}/rest/v1/{table}"
        resp = await self._client.post(url, json=rows, headers=headers)
        self._raise_for_status(resp)
        if not return_representation:
            return []
        data = resp.json()
        return data if isinstance(data, list) else [data]

    async def update(
        self,
        table: str,
        values: dict[str, Any],
        *,
        filters: dict[str, str],
    ) -> list[dict[str, Any]]:
        if not filters:
            raise ValueError("update() requires at least one filter to avoid full-table updates.")
        url = f"{self._project_url}/rest/v1/{table}"
        resp = await self._client.patch(url, params=filters, json=values, headers=self._headers())
        self._raise_for_status(resp)
        return resp.json()

    async def delete(self, table: str, *, filters: dict[str, str]) -> list[dict[str, Any]]:
        if not filters:
            raise ValueError("delete() requires at least one filter to avoid full-table deletes.")
        url = f"{self._project_url}/rest/v1/{table}"
        resp = await self._client.delete(url, params=filters, headers=self._headers())
        self._raise_for_status(resp)
        try:
            return resp.json()
        except ValueError:
            return []

    # ------------------------------------------------------------------ RPC
    async def rpc(
        self,
        fn: str,
        payload: dict[str, Any] | None = None,
        *,
        bearer: str | None = None,
    ) -> Any:
        url = f"{self._project_url}/rest/v1/rpc/{fn}"
        headers = self._headers(override_bearer=bearer)
        resp = await self._client.post(url, json=payload or {}, headers=headers)
        self._raise_for_status(resp)
        try:
            return resp.json()
        except ValueError:
            return None

    # ------------------------------------------------------------------ Storage
    async def storage_download(self, bucket: str, path: str) -> bytes:
        """Download a file from Supabase Storage and return its bytes."""
        # Match Supabase JS: GET /storage/v1/object/{bucket}/{path}
        encoded = quote(path, safe="/")
        url = f"{self._project_url}/storage/v1/object/{quote(bucket, safe='')}/{encoded}"
        headers = self._headers()
        # Storage doesn't accept JSON content-type on GET — but it's harmless.
        resp = await self._client.get(url, headers=headers)
        self._raise_for_status(resp)
        return resp.content


def build_eq_filters(pairs: Iterable[tuple[str, str]]) -> dict[str, str]:
    """Helper to turn (col, val) pairs into PostgREST eq filters."""
    return {col: f"eq.{val}" for col, val in pairs}


# ----------------------------------------------------------------------
# Lifecycle helpers
# ----------------------------------------------------------------------
# We do NOT cache user-scoped clients (each request gets its own short-lived
# client). This function exists so app shutdown has something to await.
async def close_supabase() -> None:
    return None


async def get_supabase() -> AsyncIterator[SupabaseClient]:
    """FastAPI dependency: short-lived unauthenticated Supabase client."""
    client = SupabaseClient.unauthenticated()
    try:
        yield client
    finally:
        await client.aclose()
