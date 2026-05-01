"""Async OpenAI REST client + LLMService implementation over httpx.

We avoid the official `openai` SDK so the dependency surface stays small
and we keep full control over streaming.
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx
from fastapi import HTTPException

from app.core.config import get_settings
from app.schemas.llm_context_schema import LLMModelConfig
from app.services.llm_services.llm_base import LLMService


OPENAI_BASE = "https://api.openai.com/v1"


class OpenAIError(HTTPException):
    def __init__(self, code: int, detail: Any):
        super().__init__(status_code=code, detail=detail)


class OpenAIService:
    """Raw REST client for OpenAI / OpenAI-compatible endpoints."""

    def __init__(self, api_key: str, *, base_url: str = OPENAI_BASE, timeout: float = 60.0) -> None:
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), headers=self._headers, timeout=timeout
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


class OpenAILLMService(LLMService):
    """LLMService implementation for OpenAI / OpenAI-compatible endpoints."""

    def __init__(self, *, config: LLMModelConfig) -> None:
        if not config.api_key:
            raise ValueError("OpenAI config missing api_key")
        if not config.endpoint:
            raise ValueError("OpenAI config missing endpoint")
        if not config.model:
            raise ValueError("OpenAI config missing model")

        self._model = config.model
        self._client = OpenAIService(api_key=config.api_key, base_url=config.endpoint)

    @property
    def model(self) -> str:
        return self._model

    async def chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        return await self._client.chat_completion(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def chat_completion_stream(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        async for chunk in self._client.chat_completion_stream(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield chunk

    async def embeddings(self, *, input: str | list[str]) -> dict[str, Any]:
        return await self._client.embeddings(model=self._model, input=input)

    async def aclose(self) -> None:
        await self._client.aclose()


# ----------------------------------------------------------------------
# FastAPI dependency / lifecycle helpers
# ----------------------------------------------------------------------
_singleton: OpenAIService | None = None


def get_openai() -> OpenAIService:
    global _singleton
    if _singleton is None:
        s = get_settings()
        _singleton = OpenAIService(api_key=s.openai_api_key, base_url=OPENAI_BASE, timeout=s.http_timeout_seconds)
    return _singleton


async def close_openai() -> None:
    global _singleton
    if _singleton is not None:
        await _singleton.aclose()
        _singleton = None
