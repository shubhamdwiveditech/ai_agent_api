"""Abstract LLM service interface (chat + embeddings)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator


class LLMService(ABC):
    """Provider-agnostic interface for LLM operations used by the app."""

    @abstractmethod
    async def chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def chat_completion_stream(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def embeddings(self, *, input: str | list[str]) -> dict[str, Any]:
        raise NotImplementedError

