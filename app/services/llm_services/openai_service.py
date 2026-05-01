"""Async OpenAI client (chat completions + embeddings) over httpx.

We avoid the official `openai` SDK so the dependency surface stays small
and we keep full control over streaming.
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx
from fastapi import HTTPException

from app.core.config import get_settings


OPENAI_BASE = "https://api.openai.com/v1"


class OpenAIError(HTTPException):
    def __init__(self, code: int, detail: Any):
        super().__init__(status_code=code, detail=detail)


class OpenAIClient:
    def __init__(self, api_key: str, timeout: float = 60.0) -> None:
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._client = httpx.AsyncClient(
            base_url=OPENAI_BASE, headers=self._headers, timeout=timeout
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _raise(resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise OpenAIError(code=resp.status_code, detail=detail)

    # ------------------------------------------------------------------
    # Chat completions
    # ------------------------------------------------------------------
    async def chat_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        resp = await self._client.post("/chat/completions", json=payload)
        self._raise(resp)
        return resp.json()

    async def chat_completion_stream(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yields parsed delta chunks from the OpenAI streaming endpoint.

        Each yielded item is the JSON object from a `data: ...` SSE line
        (or the literal sentinel as ``{"done": True}``).
        """
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        async with self._client.stream("POST", "/chat/completions", json=payload) as resp:
            if resp.status_code >= 400:
                body = await resp.aread()
                try:
                    detail = json.loads(body)
                except Exception:  # noqa: BLE001
                    detail = body.decode("utf-8", errors="replace")
                raise OpenAIError(code=resp.status_code, detail=detail)

            async for line in resp.aiter_lines():
                if not line:
                    continue
                if not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    yield {"done": True}
                    return
                try:
                    yield json.loads(data)
                except json.JSONDecodeError:
                    continue

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------
    async def embeddings(
        self, *, model: str, input: str | list[str]
    ) -> dict[str, Any]:
        resp = await self._client.post(
            "/embeddings", json={"model": model, "input": input}
        )
        self._raise(resp)
        return resp.json()


# ----------------------------------------------------------------------
# FastAPI dependency / lifecycle helpers
# ----------------------------------------------------------------------
_singleton: OpenAIClient | None = None


def get_openai() -> OpenAIClient:
    global _singleton
    if _singleton is None:
        s = get_settings()
        _singleton = OpenAIClient(api_key=s.openai_api_key, timeout=s.http_timeout_seconds)
    return _singleton


async def close_openai() -> None:
    global _singleton
    if _singleton is not None:
        await _singleton.aclose()
        _singleton = None
