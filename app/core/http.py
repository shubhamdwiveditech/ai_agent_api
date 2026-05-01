"""Shared async HTTP client helpers (httpx)."""

from __future__ import annotations

import httpx

from app.core.config import get_settings


class HTTPClient:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            settings = get_settings()
            self._client = httpx.AsyncClient(timeout=settings.http_timeout_seconds)
        return self._client

    async def post(self, *, url: str, json: object, headers: dict[str, str], raise_for_status: bool = True) -> httpx.Response:
        client = self._get_client()
        resp = await client.post(url, json=json, headers=headers)
        if raise_for_status:
            resp.raise_for_status()
        return resp

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


http_client = HTTPClient()

