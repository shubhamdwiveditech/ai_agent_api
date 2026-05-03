"""Agent service layer built on Supabase RPCs."""

from __future__ import annotations
from typing import Any

from fastapi import HTTPException

from app.schemas.tool_schema import ToolDefinition, ToolInputSchema
from app.services.supabase_service import get_supabase_service


def _map_tool(raw: dict) -> ToolDefinition:
    """Map fn_get_mcp_tools row → ToolDefinition."""

    # description lives inside `data` object # EDIT: change key if different
    data: dict = raw.get("data") or {}
    description: str = data.get("description") or ""

    # Build inputSchema from `fields` array
    fields: list[dict] = raw.get("fields") or []
    properties: dict[str, Any] = {}
    required: list[str] = []

    for f in fields:
        field_name = f.get("name", "")
        field_type = f.get("type", "string")  # EDIT: map types if needed
        field_desc = f.get("description", "")

        properties[field_name] = {
            "type": field_type,
            **({"description": field_desc} if field_desc else {}),
        }
        if f.get("required"):
            required.append(field_name)

    input_schema = ToolInputSchema(
        type="object",
        properties=properties,
        required=required or None,
    )

    return ToolDefinition(
        name=raw["name"],
        title=None,                          # EDIT: map if added to DB later
        url=raw.get("url"),
        headers=raw.get("headers"),
        description=description,
        inputSchema=input_schema,
        runtime="http" if raw.get("url") else "local",
        icons=None,                          # EDIT: map if added to DB later
        execution=None,                      # EDIT: map if added to DB later
    )


class MCPService:
    async def get_mcp_tools(self, access_token: str) -> list[ToolDefinition] | None:
        """Fetch MCP tools via public.fn_get_mcp_tools()."""
        envelope = await get_supabase_service().rpc(
            access_token,
            "fn_get_mcp_tools",
            {},
        )

        if not envelope.get("is_success"):
            raise HTTPException(
                status_code=502,
                detail=envelope.get("message") or "Failed to fetch MCP tools",
            )

        data = envelope.get("data") or []
        if not isinstance(data, list) or not data:
            return None

        return [_map_tool(tool) for tool in data]


_mcp_service = MCPService()


def get_mcp_service() -> MCPService:
    return _mcp_service