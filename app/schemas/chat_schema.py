"""Pydantic models for /chat."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    session_id: str | None = Field(
        default=None,
        description="Existing chat session UUID. If omitted, a new session is created.",
    )
    message: str = Field(..., min_length=1, description="The new user message.")
    system_prompt: str | None = Field(default=None, description="Optional system prompt for new sessions.")
    model: str | None = Field(default=None, description="Override the configured chat model.")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    stream: bool = Field(default=False, description="If true, response is streamed as SSE.")


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    role: Literal["assistant"] = "assistant"
    content: str
    model: str
    usage: dict[str, Any] | None = None
