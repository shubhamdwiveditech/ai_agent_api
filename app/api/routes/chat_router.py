"""/chat endpoint — multi-turn chat persisted to Supabase."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from fastapi import HTTPException
from app.core.auth import require_user
from app.schemas.chat_schema import ChatRequest, ChatResponse
from app.schemas.user_context_schema import UserContext
from app.services.agent_service import get_agent_service
from app.services.supabase_service import SupabaseService, get_supabase_service
from app.services.llm_services.llm_factory import get_llm_service

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(require_user)])

# ---------------------------------------------------------------------- routes
@router.post("", response_model=ChatResponse, response_model_exclude_none=True)
async def chat(
    body: ChatRequest,
    user: UserContext = Depends(require_user),
    supabase: SupabaseService = Depends(get_supabase_service),
):
    _ = supabase
    if body.agent_id is not None:
        agent = await get_agent_service().get_agent_full(user.access_token, agent_id=body.agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found")

        all_llms = await get_agent_service().get_llm_configs_for_cache(user.access_token, config_id=agent.llm_config_id)
        if all_llms is None:
            raise HTTPException(status_code=404, detail="LLM configuration is not found for selected agent")
        
        llm_context = await get_agent_service().get_llm_context_by_agent_config(all_llms[0])
        
        llm_service = get_llm_service(llm_context, mode="chat")
        
        messages = [
            {"role": "system", "content": agent.system_prompt},
            {"role": "user", "content": body.message},
        ]
        response = await llm_service.chat_completion( messages=messages)
        
        print("LLM response:", response)
        content = get_reply(response)
                    
    return ChatResponse(
        content=content
    )
    
def get_reply(response: dict) -> str:
    return response["choices"][0]["message"]["content"]

