"""Pydantic models for Agent config payloads (fn_get_agent_full)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


HTTPMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
ToolAPIType = Literal["action", "analytics"]


class AgentToolField(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    path: str | None = None
    type: str | None = None
    required: bool | None = None
    description: str | None = None


class AgentTool(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int | None = None
    name: str
    url: str | None = None
    method: HTTPMethod | None = None
    headers: dict[str, Any] | None = None
    body: Any | None = None
    fields: list[AgentToolField] = Field(default_factory=list)
    api_type: ToolAPIType | str | None = None
    api_auth_id: int | None = None
    data_field_path: str | None = None


class AgentFull(BaseModel):
    """Single agent payload returned in envelope.data[0]."""

    model_config = ConfigDict(extra="allow")

    id: int
    tenant_id: int | None = None
    name: str | None = None
    description: str | None = None
    avatar: str | None = None
    is_active: bool | None = None

    system_prompt: str | None = None
    llm_provider: str | None = None
    llm_config_id: int | None = None

    data: dict[str, Any] | None = None
    tool_ids: list[int] | None = None
    sub_agents: list[Any] | None = None
    knowledge_bases: list[Any] | None = None

    tools: list[AgentTool] = Field(default_factory=list)
    analytics_tools: list[AgentTool] = Field(default_factory=list)

    @field_validator("tools", "analytics_tools", mode="before")
    @classmethod
    def coerce_none_to_list(cls, v: Any) -> Any:
        return v if v is not None else []

