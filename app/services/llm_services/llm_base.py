"""Abstract LLM service interface (chat + embeddings + tool calling)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, AsyncIterator

if TYPE_CHECKING:
    from app.schemas.tool_schema import ToolDefinition


class LLMService(ABC):
    """Provider-agnostic interface for LLM operations used by the app."""

    def format_tools(self, tool_definitions: list[ToolDefinition]) -> list[dict[str, Any]] | None:
        """Convert generic ToolDefinitions to the provider-specific tools format.

        Override in each LLMService implementation.
        """
        return None

    @abstractmethod
    async def chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def chat_completion_stream(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def embeddings(self, *, input: str | list[str]) -> dict[str, Any]:
        raise NotImplementedError

    async def aclose(self) -> None:
        """Optional cleanup hook for providers with their own HTTP clients."""
        return None