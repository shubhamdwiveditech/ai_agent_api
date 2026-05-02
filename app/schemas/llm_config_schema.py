"""Pydantic models for fn_get_llm_config_for_cache."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class LLMConfigForCache(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    name: str | None = None
    provider: str | None = None
    model: str | None = None
    endpoint: str | None = None
    api_key: str | None = None
    is_default: bool | None = None
    metadata: dict[str, Any] | None = None
    data: dict[str, Any] | None = None

    @property
    def is_embed_model(self) -> bool:
        if not self.data:
            return False
        return bool(self.data.get("is_embed_model"))

