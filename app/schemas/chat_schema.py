"""Pydantic models for /chat."""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="The new user message.")
    agent_id: int | None = Field(default=None, description="Optional other wise will use the default agent.")
    session_id: str | None = Field(default=None, description="Override other wise a new session_id will be generated for each request.")
    stream: bool = Field(default=False, description="If true, response is streamed as SSE.")


class ChatResponse(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str
    usage: dict[str, Any] | None = None
