"""Pydantic models for /embed."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EmbedRequest(BaseModel):
    input: str | list[str] = Field(..., description="Single string or list of strings to embed.")
    metadata: dict[str, Any] | None = Field(
        default=None, description="Optional metadata stored alongside each embedding row."
    )
    namespace: str | None = Field(
        default=None, description="Logical bucket / collection name to group embeddings."
    )
    persist: bool = Field(default=True, description="If false, return embeddings without writing to DB.")
    model: str | None = Field(default=None, description="Override the configured embedding model.")


class EmbedItem(BaseModel):
    id: str | None = None
    content: str
    embedding: list[float]
    metadata: dict[str, Any] | None = None


class EmbedResponse(BaseModel):
    model: str
    count: int
    items: list[EmbedItem]
    usage: dict[str, Any] | None = None
