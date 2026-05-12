"""Anthropic Messages API client + LLMService implementation over httpx."""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx
from fastapi import HTTPException

from app.schemas.llm_context_schema import LLMModelConfig
from app.schemas.tool_schema import ToolDefinition
from app.services.llm_services.llm_base import LLMService


ANTHROPIC_BASE = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 4096


class AnthropicError(HTTPException):
    def __init__(self, code: int, detail: Any):
        super().__init__(status_code=code, detail=detail)


class AnthropicService:
    """Raw httpx client for the Anthropic Messages API.

    Normalises all responses to the OpenAI-compatible shape the chat router
    expects so no changes are needed upstream.
    """

    def __init__(self, api_key: str, *, base_url: str = ANTHROPIC_BASE, timeout: float = 60.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "Content-Type": "application/json",
            },
            timeout=timeout,
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
            raise AnthropicError(code=resp.status_code, detail=detail)

    # ── Message format conversion ─────────────────────────────────────────────

    @staticmethod
    def _to_anthropic_messages(messages: list[dict]) -> tuple[str | None, list[dict]]:
        """Convert OpenAI-format messages → (system_prompt, Anthropic messages).

        Handles:
          - system role  → extracted as top-level system param
          - role:tool    → user turn with tool_result content block
          - role:assistant with tool_calls → assistant turn with tool_use blocks
          - plain user/assistant text → passed through unchanged
        """
        system: str | None = None
        out: list[dict] = []

        for msg in messages:
            role = msg["role"]
            content = msg.get("content") or ""

            if role == "system":
                system = content
                continue

            if role == "tool":
                # OpenAI tool result → Anthropic tool_result in a user turn
                out.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg["tool_call_id"],
                        "content": content,  # already JSON-serialised by _append_tool_messages
                    }],
                })
                continue

            if role == "assistant":
                # Rebuild content blocks: text + any tool_use
                blocks: list[dict] = []
                if content:
                    blocks.append({"type": "text", "text": content})
                for tc in msg.get("tool_calls") or []:
                    blocks.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "input": json.loads(tc["function"]["arguments"]),
                    })
                out.append({"role": "assistant", "content": blocks or content})
                continue

            # user message
            out.append({"role": "user", "content": content})

        return system, out

    # ── Response normalisation ────────────────────────────────────────────────

    @staticmethod
    def _normalize(resp: dict) -> dict:
        """Convert Anthropic response → OpenAI-compatible dict.

        The chat router's parse_llm_response() and streaming generators
        both expect this shape.
        """
        blocks: list[dict] = resp.get("content", [])
        stop_reason: str = resp.get("stop_reason", "end_turn")

        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        tool_use = [b for b in blocks if b.get("type") == "tool_use"]

        if stop_reason == "tool_use" and tool_use:
            return {
                "choices": [{
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": text or None,
                        "tool_calls": [
                            {
                                "id": b["id"],
                                "type": "function",
                                "function": {
                                    "name": b["name"],
                                    "arguments": json.dumps(b.get("input", {})),
                                },
                            }
                            for b in tool_use
                        ],
                    },
                }]
            }

        return {
            "choices": [{
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": text},
            }]
        }

    # ── Payload builder ───────────────────────────────────────────────────────

    def _build_payload(
        self,
        *,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int | None,
        tools: list[dict] | None,
        tool_choice: Any,
        stream: bool,
    ) -> dict:
        system, anthropic_messages = self._to_anthropic_messages(messages)
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens or DEFAULT_MAX_TOKENS,
            "messages": anthropic_messages,
            "temperature": temperature,
            "stream": stream,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = tools
            if tool_choice == "auto" or tool_choice is None:
                payload["tool_choice"] = {"type": "auto"}
            elif isinstance(tool_choice, dict):
                payload["tool_choice"] = tool_choice
        return payload

    # ── API calls ─────────────────────────────────────────────────────────────

    async def chat_completion(
        self,
        *,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        tool_choice: Any = None,
    ) -> dict:
        payload = self._build_payload(
            model=model, messages=messages, temperature=temperature,
            max_tokens=max_tokens, tools=tools, tool_choice=tool_choice, stream=False,
        )
        resp = await self._client.post("/v1/messages", json=payload)
        self._raise(resp)
        return self._normalize(resp.json())

    async def chat_completion_stream(
        self,
        *,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        tool_choice: Any = None,
    ) -> AsyncIterator[dict]:
        """Yield OpenAI-compatible chunks from the Anthropic SSE stream.

        Only called when the chat router is sure there are no tool calls
        (stream_direct path), so we only need to handle text_delta events.
        """
        payload = self._build_payload(
            model=model, messages=messages, temperature=temperature,
            max_tokens=max_tokens, tools=tools, tool_choice=tool_choice, stream=True,
        )
        async with self._client.stream("POST", "/v1/messages", json=payload) as resp:
            if resp.status_code >= 400:
                body = await resp.aread()
                try:
                    detail = json.loads(body)
                except Exception:
                    detail = body.decode("utf-8", errors="replace")
                raise AnthropicError(code=resp.status_code, detail=detail)

            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                raw = line[len("data:"):].strip()
                if not raw:
                    continue
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                etype = event.get("type")
                if etype == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            # Yield OpenAI-compatible chunk shape
                            yield {"choices": [{"delta": {"content": text}}]}
                elif etype == "message_stop":
                    yield {"done": True}
                    return


class AnthropicLLMService(LLMService):
    """LLMService adapter for Anthropic Claude models."""

    def __init__(self, *, config: LLMModelConfig) -> None:
        if not config.api_key:
            raise ValueError("Anthropic config missing api_key")
        if not config.model:
            raise ValueError("Anthropic config missing model")
        self._model = config.model
        self._client = AnthropicService(
            api_key=config.api_key,
            base_url=config.endpoint or ANTHROPIC_BASE,
        )

    @property
    def model(self) -> str:
        return self._model

    def format_tools(self, tool_definitions: list[ToolDefinition]) -> list[dict[str, Any]] | None:
        return [t.to_anthropic_tool() for t in tool_definitions] or None

    async def chat_completion(
        self,
        *,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        tool_choice: Any = None,
    ) -> dict:
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
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        tool_choice: Any = None,
    ) -> AsyncIterator[dict]:
        async for chunk in self._client.chat_completion_stream(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
        ):
            yield chunk

    async def embeddings(self, *, input: str | list[str]) -> dict:
        raise NotImplementedError("Anthropic does not provide an embeddings endpoint; use a dedicated embed model.")

    async def aclose(self) -> None:
        await self._client.aclose()
