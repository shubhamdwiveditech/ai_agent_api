"""Async OpenAI REST client + LLMService implementation over httpx."""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx
from fastapi import HTTPException

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
            except Exception:
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
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice or "auto"

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
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice or "auto"

        async with self._client.stream("POST", "/chat/completions", json=payload) as resp:
            if resp.status_code >= 400:
                body = await resp.aread()
                try:
                    detail = json.loads(body)
                except Exception:
                    detail = body.decode("utf-8", errors="replace")
                raise OpenAIError(code=resp.status_code, detail=detail)

            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
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
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._client.chat_completion(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
        )

    async def chat_completion_stream(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        async for chunk in self._client.chat_completion_stream(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
        ):
            yield chunk

    async def embeddings(self, *, input: str | list[str]) -> dict[str, Any]:
        return await self._client.embeddings(model=self._model, input=input)

    async def aclose(self) -> None:
        await self._client.aclose()