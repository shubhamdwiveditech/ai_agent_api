"""LLM context returned by fn_get_default_llm and used across the app."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class LLMModelConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str | None = None
    api_key: str | None = None
    endpoint: str | None = None
    provider: str | None = None


class LLMContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    chat_model: LLMModelConfig | None = None
    embed_model: LLMModelConfig | None = None

