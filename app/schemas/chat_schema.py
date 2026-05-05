"""Pydantic models for /chat."""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    session_id: int
    role: Literal["system", "user", "assistant"]
    content: str

    def to_llm_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class RagSource(BaseModel):
    """One retrieved chunk surfaced to the client as a citation."""
    n: int
    chunk_id: str | None = None
    item_id: str | None = None
    kb_id: str | None = None
    item_name: str | None = None
    kb_name: str | None = None
    item_url: str | None = None
    similarity: float | None = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="The new user message.")
    agent_id: int | None = Field(default=None, description="Optional other wise will use the default agent.")
    session_id: str | None = Field(default=None, description="Override other wise a new session_id will be generated for each request.")
    stream: bool = Field(default=False, description="If true, response is streamed as SSE.")


class ChatResponse(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str
    sources: list[RagSource] | None = None
    usage: dict[str, Any] | None = None
