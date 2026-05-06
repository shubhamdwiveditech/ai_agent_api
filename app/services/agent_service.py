"""Agent service layer built on Supabase RPCs."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException

from app.schemas.agent_schema import AgentFull, AgentTool
from app.schemas.chat_schema import ChatMessage, RagSource
from app.schemas.llm_config_schema import LLMConfigForCache
from app.schemas.llm_context_schema import LLMContext
from app.schemas.tool_schema import ToolDefinition, ToolInputSchema
from app.schemas.user_context_schema import UserContext
from app.services.llm_services.llm_base import LLMService
from app.services.llm_services.llm_factory import get_llm_service
from app.services.supabase_service import get_supabase_service
from app.services.tool_executor_service import get_tool_executor


# ── RAG source extraction ─────────────────────────────────────────────────────

def _extract_rag_sources(tool_results: list[dict]) -> list[RagSource]:
    """Pull chunk metadata out of tool results that look like KB search responses."""
    sources: list[RagSource] = []
    n = 1
    for tr in tool_results:
        raw = tr.get("result") or {}
        chunks: list = []
        if isinstance(raw, dict):
            chunks = raw.get("chunks") or raw.get("data") or []
        elif isinstance(raw, list):
            chunks = raw
        for c in chunks:
            if not isinstance(c, dict):
                continue
            if not any(k in c for k in ("chunk_id", "item_id", "kb_id")):
                continue
            sim = c.get("similarity")
            sources.append(RagSource(
                n=n,
                chunk_id=c.get("chunk_id"),
                item_id=c.get("item_id"),
                kb_id=c.get("kb_id"),
                item_name=c.get("item_name"),
                kb_name=c.get("kb_name"),
                item_url=c.get("item_url"),
                similarity=round(float(sim), 3) if sim is not None else None,
            ))
            n += 1
    return sources


# ── Chat context dataclass ────────────────────────────────────────────────────

@dataclass
class ChatContext:
    agent: AgentFull
    llm_service: LLMService
    llm_context: LLMContext
    tool_definitions: list[ToolDefinition]
    llm_dict_messages: list[dict]


# ── Service ───────────────────────────────────────────────────────────────────

class AgentService:

    # ── Agent / LLM config ────────────────────────────────────────────────────

    async def get_agent_full(self, access_token: str, *, agent_id: int) -> AgentFull | None:
        envelope = await get_supabase_service().rpc(
            access_token, "fn_get_agent_full", {"p_agent_id": int(agent_id)},
        )
        if not envelope.get("is_success"):
            raise HTTPException(status_code=502, detail=envelope.get("message") or "Failed to fetch agent")
        data = envelope.get("data") or []
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            return None
        return AgentFull.model_validate(data[0])

    async def get_llm_configs_for_cache(self, access_token: str, *, config_id: int | None = None) -> list[LLMConfigForCache]:
        payload = {"p_id": int(config_id)} if config_id is not None else {"p_id": None}
        envelope = await get_supabase_service().rpc(access_token, "fn_get_llm_config_for_cache", payload)
        if not envelope.get("is_success"):
            raise HTTPException(status_code=502, detail=envelope.get("message") or "Failed to fetch LLM configs")
        data = envelope.get("data") or []
        return [LLMConfigForCache.model_validate(r) for r in data if isinstance(r, dict)]

    async def get_llm_context_by_agent_config(self, llm_config: LLMConfigForCache) -> LLMContext | None:
        if llm_config is None:
            return None
        is_embed = llm_config.data.get("is_embed_model", False)
        embed_model = None
        chat_model = None
        if is_embed:
            embed_model = {
                "model": llm_config.embed_model, "api_key": llm_config.embed_model_api_key,
                "endpoint": llm_config.embed_model_endpoint, "provider": llm_config.embed_model_provider,
            }
        else:
            chat_model = {
                "model": llm_config.model, "api_key": llm_config.api_key,
                "endpoint": llm_config.endpoint, "provider": llm_config.provider,
            }
        return LLMContext.model_validate({"embed_model": embed_model, "chat_model": chat_model})

    # ── Chat persistence ──────────────────────────────────────────────────────

    async def save_chat(self, access_token: str, *, session_id: int, role: str, content: str) -> dict:
        envelope = await get_supabase_service().rpc(
            access_token, "fn_save_chat",
            {"p_session_id": session_id, "p_role": role, "p_content": content},
        )
        if not envelope.get("is_success"):
            raise HTTPException(status_code=502, detail=envelope.get("message") or "Failed to save chat")
        data = envelope.get("data") or []
        if not isinstance(data, list) or len(data) == 0:
            raise HTTPException(status_code=502, detail="No data returned from fn_save_chat")
        return data[0]

    async def get_chats(self, access_token: str, *, session_id: int) -> list[ChatMessage]:
        envelope = await get_supabase_service().rpc(
            access_token, "fn_get_chats", {"p_session_id": session_id},
        )
        if not envelope.get("is_success"):
            raise HTTPException(status_code=502, detail=envelope.get("message") or "Failed to fetch chats")
        data = envelope.get("data") or []
        return [ChatMessage.model_validate(r) for r in data if isinstance(r, dict)]

    async def save_agent_execution_log(
        self, access_token: str, *, name: str, run_id: str,
        node_name: str, event_type: str, data: dict = {},
    ) -> dict:
        envelope = await get_supabase_service().rpc(
            access_token, "fn_save_agent_execution_log",
            {"p_name": name, "p_run_id": run_id, "p_node_name": node_name, "p_event_type": event_type, "p_data": data},
        )
        if not envelope.get("is_success"):
            raise HTTPException(status_code=502, detail=envelope.get("message") or "Failed to save agent execution log")
        result = envelope.get("data") or []
        if not isinstance(result, list) or len(result) == 0:
            raise HTTPException(status_code=502, detail="No data returned from fn_save_agent_execution_log")
        return result[0]

    async def persist_chat_response(
        self, access_token: str, agent_name: str, session_id, content: str,
    ) -> None:
        """Save execution log + assistant chat message in one call."""
        await self.save_agent_execution_log(
            access_token=access_token, name=agent_name, run_id=session_id,
            node_name="chat_node", event_type="response", data={"response": content},
        )
        await self.save_chat(access_token, session_id=session_id, role="assistant", content=content)

    # ── Chat context setup ────────────────────────────────────────────────────

    async def prepare_chat_context(
        self, access_token: str, *, agent_id: int, session_id, user_message: str,
    ) -> ChatContext:
        """Fetch agent, LLM config, history, and build the full context for one chat turn."""
        agent = await self.get_agent_full(access_token, agent_id=agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found")

        await self.save_agent_execution_log(
            access_token=access_token, name=agent.name, run_id=session_id,
            node_name="chat_node", event_type="agent_fullfilled", data={"agent_full": agent.model_dump()},
        )

        all_llms = await self.get_llm_configs_for_cache(access_token, config_id=agent.llm_config_id)
        if not all_llms:
            raise HTTPException(status_code=404, detail="LLM configuration is not found for selected agent")

        llm_context = await self.get_llm_context_by_agent_config(all_llms[0])
        llm_service = get_llm_service(llm_context, mode="chat")

        history = await self.get_chats(access_token, session_id=session_id)
        messages: list[ChatMessage] = [
            ChatMessage(session_id=session_id, role="system", content=agent.system_prompt),
            *history,
            ChatMessage(session_id=session_id, role="user", content=user_message),
        ]

        tool_definitions = self.agent_tools_to_tool_definitions(agent.tools, agent.analytics_tools)
        llm_dict_messages = [m.to_llm_dict() for m in messages]

        return ChatContext(
            agent=agent,
            llm_service=llm_service,
            llm_context=llm_context,
            tool_definitions=tool_definitions,
            llm_dict_messages=llm_dict_messages,
        )

    # ── Tool execution ────────────────────────────────────────────────────────

    async def run_tools_with_sources(
        self,
        tool_definitions: list[ToolDefinition],
        tool_calls: list[dict],
        user: UserContext,
        llm_context: LLMContext,
    ) -> tuple[list[dict], list[RagSource]]:
        """Execute all tool calls and extract any RAG source metadata from their results."""
        tool_results: list[dict] = []
        for tc in tool_calls:
            matched = next((t for t in tool_definitions if t.name == tc["name"]), None)
            result = await get_tool_executor().execute(
                tool=matched, arguments=tc["args"], user=user, llm_context=llm_context,
            )
            print(f"Tool [{tc['name']}] response:", result)
            tool_results.append({"tool_call_id": tc["id"], "name": tc["name"], "result": result})
        return tool_results, _extract_rag_sources(tool_results)

    # ── Tool definitions ──────────────────────────────────────────────────────

    def agent_tools_to_tool_definitions(self, *tool_lists: list[AgentTool]) -> list[ToolDefinition]:
        definitions: list[ToolDefinition] = []
        seen: set[str] = set()
        for tool_list in tool_lists:
            for tool in tool_list:
                if tool.name in seen:
                    continue
                seen.add(tool.name)
                properties: dict[str, Any] = {}
                required: list[str] = []
                for field in tool.fields:
                    prop: dict[str, Any] = {"type": field.type or "string"}
                    if field.description:
                        prop["description"] = field.description
                    if field.path:
                        prop["path"] = field.path
                    properties[field.name] = prop
                    if field.required:
                        required.append(field.name)
                definitions.append(ToolDefinition(
                    name=tool.name,
                    description=tool.name.replace("_", " ").title(),
                    url=tool.url,
                    headers=tool.headers,
                    runtime="http" if tool.url else "local",
                    inputSchema=ToolInputSchema(
                        type="object", properties=properties, required=required or None,
                    ),
                ))
        return definitions


_agent_service = AgentService()


def get_agent_service() -> AgentService:
    return _agent_service
