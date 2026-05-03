"""MCP endpoint for tool discovery and registration."""
from __future__ import annotations

from fastapi import APIRouter

from app.schemas.tool_schema import ToolDefinition
from app.services.tool_registry_service import get_tool_registry

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get("", response_model=list[ToolDefinition])
def list_mcp_tools():
    """Return registered tools in MCP-compatible format."""
    return get_tool_registry().list_mcp_tools()


@router.post("/tools", response_model=ToolDefinition)
def register_tool(tool: ToolDefinition):
    """Register a new tool definition for MCP and local tool execution."""
    return get_tool_registry().register(tool)
