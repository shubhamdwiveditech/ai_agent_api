"""Tool execution service.

Separates:
- Tool definitions/handlers registry (ToolRegistry)
- Tool execution routing + credential/config resolution (ToolExecutorService)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import threading
from typing import Any

from app.core.config import get_settings
from app.core.http import http_client
from app.schemas.llm_context_schema import LLMContext
from app.schemas.user_context_schema import UserContext
from app.schemas.tool_schema import ToolDefinition
from app.services.tool_registry_service import ToolRegistry, get_tool_registry


@dataclass(frozen=True)
class HTTPToolConfig:
    url: str
    headers: dict[str, str]


class ToolExecutorService:
    """Executes tools based on ToolDefinition.runtime.

    - local: uses an in-process python handler registered in ToolRegistry
    - http: calls an HTTP gateway endpoint derived from settings + cached config
    """

    def __init__(self, *, registry: ToolRegistry | None = None) -> None:
        self._registry = registry or get_tool_registry()
        self._lock = threading.RLock()
        # Cache can vary by tenant; key it by "{tenant_id}:{tool_name}"
        self._http_cfg_cache: dict[str, HTTPToolConfig] = {}
        self._local_handlers: dict[str, Any] = {}

    def register_local_handler(self, tool_name: str, handler: Any, *, overwrite: bool = True) -> None:
        name = (tool_name or "").strip()
        if not name:
            raise ValueError("tool_name is required")
        with self._lock:
            if not overwrite and name in self._local_handlers:
                raise ValueError(f"Local handler already registered: {name}")
            self._local_handlers[name] = handler

    def unregister_local_handler(self, tool_name: str) -> None:
        with self._lock:
            self._local_handlers.pop(tool_name, None)

    def _cache_key(self, tool_name: str, user: UserContext) -> str:
        tenant = str(user.tenant_id or "")
        return f"{tenant}:{tool_name}"

    def prime_http_config(
        self,
        tool_name: str,
        *,
        user: UserContext,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Manually seed/override cached HTTP config for a tool."""
        cfg = HTTPToolConfig(url=url, headers=headers or {})
        with self._lock:
            self._http_cfg_cache[self._cache_key(tool_name, user)] = cfg

    def clear_cache(self) -> None:
        with self._lock:
            self._http_cfg_cache.clear()

    async def execute(
        self,
        *,
        tool: ToolDefinition,
        arguments: dict[str, Any],
        user: UserContext,
        llm_context: LLMContext | None = None,
    ) -> Any:
        """Execute the given tool definition.

        Args:
            tool: Tool metadata (contains runtime hint).
            arguments: Tool arguments validated by the model/provider.
            user: UserContext for auth/tenant scoping.
            llm_context: Optional LLMContext (useful for provider-specific routing).
        """
        runtime = (tool.runtime or "").strip().lower()
        if not runtime:
            runtime = "local" if self._has_local_handler(tool.name) else "http"

        if runtime == "local":
            handler = self._get_local_handler(tool.name)
            if handler is None:
                raise KeyError(f"No local handler registered for tool: {tool.name}")
            result = handler(arguments, user=user, llm_context=llm_context)
            if asyncio.iscoroutine(result):
                return await result
            return result

        if runtime == "http":
            
            headers = {
                "Content-Type": "application/json"
            }
            
            if user.access_token:
                is_jwt = user.access_token.count(".") == 2
                if is_jwt:
                    headers["Authorization"] = f"Bearer {user.access_token}"
                else:
                    headers["x-api-key"] = user.access_token
            
            tool.headers and headers.update(tool.headers)
            
            resp = await http_client.post(
                url=tool.url,
                json=arguments,
                headers=headers,
                raise_for_status=False,
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"Tool HTTP call failed ({resp.status_code}): {resp.text[:200]}")
            try:
                return resp.json()
            except Exception:
                return resp.text

        raise ValueError(f"Unsupported tool runtime: {runtime}")

    def _has_local_handler(self, tool_name: str) -> bool:
        with self._lock:
            return tool_name in self._local_handlers

    def _get_local_handler(self, tool_name: str) -> Any | None:
        with self._lock:
            return self._local_handlers.get(tool_name)



_executor = ToolExecutorService()


def get_tool_executor() -> ToolExecutorService:
    return _executor
