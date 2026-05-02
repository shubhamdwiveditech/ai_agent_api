"""/chat endpoint — multi-turn chat persisted to Supabase."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from fastapi import HTTPException
from app.core.auth import require_user
from app.schemas.chat_schema import ChatMessage, ChatRequest, ChatResponse
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
        
        _ = await get_agent_service().save_chat(user.access_token, session_id=body.session_id, role="user", content=body.message)
        
        """Fetch agent config for the given agent_id."""
        agent = await get_agent_service().get_agent_full(user.access_token, agent_id=body.agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found")

        _ = await get_agent_service().save_agent_execution_log(access_token=user.access_token, name=agent.name, run_id=body.session_id, node_name="chat_node", event_type="agent_fullfilled", data={"agent_full": agent.model_dump()})
            
        """Fetch LLM context for the agent's LLM config."""
        all_llms = await get_agent_service().get_llm_configs_for_cache(user.access_token, config_id=agent.llm_config_id)
        if all_llms is None:
            raise HTTPException(status_code=404, detail="LLM configuration is not found for selected agent")
        
        """Here we are assuming that the first config is the one we want. In future, we can have more logic to select the appropriate config if there are multiple."""
        llm_context = await get_agent_service().get_llm_context_by_agent_config(all_llms[0])
        
        messages: list[ChatMessage] = []
        
        messages.append(ChatMessage(session_id=body.session_id, role="system", content=agent.system_prompt))
         
        """Here we fetch the chat history for the session and then call the LLM service to get a response."""
        messages_history = await get_agent_service().get_chats(user.access_token, session_id=body.session_id)
        
        """Initialize the LLM service with the context and then get a response for the current message."""
        llm_service = get_llm_service(llm_context, mode="chat")
        
                
        messages.extend(messages_history)
        
        messages.append(ChatMessage(session_id=body.session_id, role="user", content=body.message))
      
        response = await llm_service.chat_completion(
                    messages=[m.to_llm_dict() for m in messages]
                )
                        
        print("LLM response:", response)
        content = get_reply(response)
        
        _ = await get_agent_service().save_agent_execution_log(access_token=user.access_token, name=agent.name, run_id=body.session_id, node_name="chat_node", event_type="response", data={"response": content})
        
        _ = await get_agent_service().save_chat(user.access_token, session_id=body.session_id, role="assistant", content=content )

    return ChatResponse(
        role="assistant",
        content=content
    )
    
def get_reply(response: dict) -> str:
    return response["choices"][0]["message"]["content"]

