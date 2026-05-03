"""Tool metadata schemas (MCP/OpenAI/Claude compatible shape)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, schema


JSONSchemaType = Literal[
    "object",
    "array",
    "string",
    "number",
    "integer",
    "boolean",
    "null",
]


class ToolIcon(BaseModel):
    src: str = Field(..., description="Icon URL or data URL.")
    mimeType: str | None = Field(default=None, description="MIME type, e.g. image/png.")
    sizes: list[str] | None = Field(default=None, description='Sizes like ["48x48"].')


class ToolExecution(BaseModel):
    taskSupport: Literal["optional", "required", "none"] | None = Field(
        default=None, description="Whether task-style execution is supported."
    )



class ToolInputSchema(BaseModel):
    """A minimal JSON Schema (draft-agnostic) for tool inputs."""

    model_config = ConfigDict(extra="allow")

    type: JSONSchemaType = Field(default="object")
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] | None = None


class ToolDefinition(BaseModel):
    """Provider-agnostic tool definition.

    Designed to be easy to render into:
    - MCP tool lists
    - OpenAI "function" tools
    - Anthropic/Claude tools
    """

    model_config = ConfigDict(extra="allow")

    name: str = Field(..., min_length=1)
    title: str | None = None
    url: str | None = None
    headers: dict[str, str] | None = None
    description: str = Field(..., min_length=1)
    inputSchema: ToolInputSchema = Field(default_factory=ToolInputSchema)
    icons: list[ToolIcon] | None = None
    execution: ToolExecution | None = None
    runtime: str | None = None  # "local" or "http", default to "http" if http is set
    
    
    def to_openai_tool(self) -> dict[str, Any]:
        schema = self.inputSchema.model_dump(exclude_none=True)
        schema.setdefault("properties", {})  
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }

    def to_anthropic_tool(self) -> dict[str, Any]:
        """Render into Anthropic/Claude tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.inputSchema.model_dump(exclude_none=True),
        }

    def to_mcp_tool(self) -> dict[str, Any]:
        """Render into MCP tool list format (same shape as this schema)."""
        return self.model_dump(exclude_none=True, exclude={"runtime"})
