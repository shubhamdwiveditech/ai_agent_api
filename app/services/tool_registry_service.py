"""In-memory tool registry.

This registry is meant to unify tool metadata for MCP listings and
LLM providers (OpenAI/Anthropic/etc.) while allowing dynamic registration
at runtime (e.g. per-tenant, per-agent, or local tools like send_mail).
"""

from __future__ import annotations

import threading
from typing import Any

from app.schemas.tool_schema import ToolDefinition

class ToolRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        tool: ToolDefinition | dict[str, Any],
        *,
        overwrite: bool = True,
    ) -> ToolDefinition:
        """Register a tool definition (metadata only).

        Args:
            tool: ToolDefinition or a dict payload compatible with ToolDefinition.
            overwrite: If false, raises ValueError when tool already exists.
        """
        parsed = tool if isinstance(tool, ToolDefinition) else ToolDefinition.model_validate(tool)
        name = parsed.name.strip()
        if not name:
            raise ValueError("Tool name is required")

        with self._lock:
            if not overwrite and name in self._tools:
                raise ValueError(f"Tool already registered: {name}")
            self._tools[name] = parsed
        return parsed

    def unregister(self, name: str) -> None:
        with self._lock:
            self._tools.pop(name, None)

    def get(self, name: str) -> ToolDefinition | None:
        with self._lock:
            return self._tools.get(name)

    def list(self) -> list[ToolDefinition]:
        with self._lock:
            return list(self._tools.values())

    def list_openai_tools(self) -> list[dict[str, Any]]:
        return [t.to_openai_tool() for t in self.list()]

    def list_anthropic_tools(self) -> list[dict[str, Any]]:
        return [t.to_anthropic_tool() for t in self.list()]

    def list_mcp_tools(self) -> list[dict[str, Any]]:
        return [t.to_mcp_tool() for t in self.list()]


_registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    return _registry
