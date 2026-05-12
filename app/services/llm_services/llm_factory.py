"""Factory for provider-specific LLM services based on LLMContext."""

from __future__ import annotations

from typing import Literal

from app.schemas.llm_context_schema import LLMContext, LLMModelConfig
from app.services.llm_services.llm_base import LLMService
from app.services.llm_services.openai_service import OpenAILLMService
from app.services.llm_services.anthropic_service import AnthropicLLMService


LLMMode = Literal["chat", "embed"]


def _pick_config(context: LLMContext, *, mode: LLMMode) -> LLMModelConfig:
    config = context.chat_model if mode == "chat" else context.embed_model
    if config is None:
        raise ValueError(f"LLMContext missing {mode}_model config")
    return config


def get_llm_service(context: LLMContext, *, mode: LLMMode) -> LLMService:
    config = _pick_config(context, mode=mode)
    provider = (config.provider or "").strip().lower()

    if provider == "openai":
        return OpenAILLMService(config=config)

    if provider == "anthropic":
        return AnthropicLLMService(config=config)

    raise ValueError(f"Unsupported LLM provider: {config.provider!r}")
