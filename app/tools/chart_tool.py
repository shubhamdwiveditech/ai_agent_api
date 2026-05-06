"""Chart generation tool — runtime: local."""
from __future__ import annotations

from typing import Any

from app.schemas.tool_schema import ToolDefinition, ToolInputSchema
from app.services.chart_service.chart_service import generate_chart
from app.services.tool_executor_service import get_tool_executor
from app.services.tool_registry_service import get_tool_registry

TOOL_NAME = "generate_chart"

_DEFINITION = ToolDefinition(
    name=TOOL_NAME,
    description=(
        "Generate a chart image from data and return it as a base64 PNG data URL. "
        "Supported types: bar, horizontal_bar, line, area, pie, doughnut, radar."
    ),
    runtime="local",
    inputSchema=ToolInputSchema(
        type="object",
        properties={
            "chart_type": {
                "type": "string",
                "description": "Chart type: bar, horizontal_bar, line, area, pie, doughnut, radar",
            },
            "labels": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Category or slice labels",
            },
            "datasets": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "data": {"type": "array", "items": {"type": "number"}},
                    },
                    "required": ["data"],
                },
                "description": "Data series: [{label: string, data: number[]}]",
            },
            "title": {
                "type": "string",
                "description": "Optional chart title",
            },
            "width": {
                "type": "integer",
                "description": "Figure width in inches (default: 10)",
            },
            "height": {
                "type": "integer",
                "description": "Figure height in inches (default: 6)",
            },
        },
        required=["chart_type", "labels", "datasets"],
    ),
)


def _handler(arguments: dict[str, Any], *, user=None, llm_context=None) -> dict[str, Any]:
    return generate_chart(
        chart_type=arguments.get("chart_type", "bar"),
        labels=arguments.get("labels", []),
        datasets=arguments.get("datasets", []),
        title=arguments.get("title"),
        width=int(arguments.get("width", 10)),
        height=int(arguments.get("height", 6)),
    )


def ensure_registered() -> ToolDefinition:
    get_tool_executor().register_local_handler(TOOL_NAME, _handler)
    return _DEFINITION
