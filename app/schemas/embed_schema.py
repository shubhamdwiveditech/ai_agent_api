"""Pydantic models for /embed."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EmbedRequest(BaseModel):
    id: int

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
