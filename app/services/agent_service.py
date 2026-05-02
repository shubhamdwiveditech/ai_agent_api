"""Agent service layer built on Supabase RPCs."""

from __future__ import annotations

from fastapi import HTTPException

from app.schemas.agent_schema import AgentFull
from app.schemas.chat_schema import ChatMessage
from app.schemas.llm_config_schema import LLMConfigForCache
from app.schemas.llm_context_schema import LLMContext
from app.services.supabase_service import get_supabase_service


class AgentService:
    async def get_agent_full(self, access_token: str, *, agent_id: int) -> AgentFull | None:
        """Fetch agent config via public.fn_get_agent_full(p_agent_id)."""
        envelope = await get_supabase_service().rpc(
            access_token,
            "fn_get_agent_full",
            {"p_agent_id": int(agent_id)},
        )
        if not envelope.get("is_success"):
            raise HTTPException(status_code=502, detail=envelope.get("message") or "Failed to fetch agent")

        data = envelope.get("data") or []
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            return None
        return AgentFull.model_validate(data[0])

    async def get_llm_configs_for_cache(self, access_token: str, *, config_id: int | None = None) -> list[LLMConfigForCache]:
        """Fetch LLM configs via public.fn_get_llm_config_for_cache(p_id)."""
        payload = {"p_id": int(config_id)} if config_id is not None else {"p_id": None}
        envelope = await get_supabase_service().rpc(
            access_token,
            "fn_get_llm_config_for_cache",
            payload,
        )
        if not envelope.get("is_success"):
            raise HTTPException(status_code=502, detail=envelope.get("message") or "Failed to fetch LLM configs")

        data = envelope.get("data") or []
        if not isinstance(data, list):
            return []
        items: list[LLMConfigForCache] = []
        for row in data:
            if isinstance(row, dict):
                items.append(LLMConfigForCache.model_validate(row))
        return items


    async def get_llm_context_by_agent_config(self, llm_config: LLMConfigForCache) -> LLMContext | None:
        """Call get_llm_context_by_agent_config and parse into LLMContext."""

        if llm_config is None:
            return None

        is_embed = llm_config.data.get("is_embed_model", False) 

        embed_model = None
        chat_model = None

        if is_embed:
            embed_model = {   
                "model":    llm_config.embed_model,
                "api_key":  llm_config.embed_model_api_key,
                "endpoint": llm_config.embed_model_endpoint,
                "provider": llm_config.embed_model_provider,
            }
        else:
            chat_model = {  
                "model":    llm_config.model,
                "api_key":  llm_config.api_key,
                "endpoint": llm_config.endpoint,
                "provider": llm_config.provider,
            }

        payload = {
            "embed_model": embed_model,
            "chat_model":  chat_model, 
        }

        return LLMContext.model_validate(payload)
    
    async def save_chat( self, access_token: str, *, session_id: int, role: str,content: str,) -> dict:
        """Save a chat message via public.fn_save_chat."""
        payload = {
            "p_session_id": session_id,
            "p_role": role,
            "p_content": content,
        }
        envelope = await get_supabase_service().rpc(
            access_token,
            "fn_save_chat",
            payload,
        )
        if not envelope.get("is_success"):
            raise HTTPException(
                status_code=502,
                detail=envelope.get("message") or "Failed to save chat",
            )

        data = envelope.get("data") or []
        if not isinstance(data, list) or len(data) == 0:
            raise HTTPException(status_code=502, detail="No data returned from fn_save_chat")

        return data[0]
    
    async def get_chats( self, access_token: str, * , session_id: int, ) -> list[ChatMessage]:
        """Fetch chats for a session via public.fn_get_chats."""
        payload = {
            "p_session_id": session_id,
        }
        envelope = await get_supabase_service().rpc(
            access_token,
            "fn_get_chats",
            payload,
        )
        if not envelope.get("is_success"):
            raise HTTPException(
                status_code=502,
                detail=envelope.get("message") or "Failed to fetch chats",
            )

        data = envelope.get("data") or []
        if not isinstance(data, list):
            return []

        items: list[ChatMessage] = []
        for row in data:
            if isinstance(row, dict):
                items.append(ChatMessage.model_validate(row))
        return items

    async def save_agent_execution_log(
        self,
        access_token: str,
        *,
        name: str,
        run_id: str,
        node_name: str,
        event_type: str,
        data: dict = {},
    ) -> dict:
        """Save agent execution log via public.fn_save_agent_execution_log."""
        payload = {
            "p_name":       name,
            "p_run_id":     run_id,
            "p_node_name":  node_name,
            "p_event_type": event_type,
            "p_data":       data,
        }
        envelope = await get_supabase_service().rpc(
            access_token,
            "fn_save_agent_execution_log",
            payload,
        )
        if not envelope.get("is_success"):
            raise HTTPException(
                status_code=502,
                detail=envelope.get("message") or "Failed to save agent execution log",
            )

        result = envelope.get("data") or []
        if not isinstance(result, list) or len(result) == 0:
            raise HTTPException(status_code=502, detail="No data returned from fn_save_agent_execution_log")

        return result[0]

_agent_service = AgentService()


def get_agent_service() -> AgentService:
    return _agent_service
