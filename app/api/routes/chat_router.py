"""/chat endpoint — multi-turn chat persisted to Supabase."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from fastapi import HTTPException
import json
from app.core.auth import require_user
from app.schemas.chat_schema import ChatMessage, ChatRequest, ChatResponse
from app.schemas.user_context_schema import UserContext
from app.services.agent_service import get_agent_service
from app.services.common_service import LLMResponseType, parse_llm_response
from app.services.supabase_service import SupabaseService, get_supabase_service
from app.services.llm_services.llm_factory import get_llm_service
from app.services.tool_executor_service import get_tool_executor

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(require_user)])

# ---------------------------------------------------------------------- routes
@router.post("", response_model=ChatResponse, response_model_exclude_none=True)
async def chat(
    body: ChatRequest,
    user: UserContext = Depends(require_user),
    supabase: SupabaseService = Depends(get_supabase_service),
):
    _ = supabase
    content: str = ""  # ✅ initialize early to avoid UnboundLocalError

    if body.agent_id is not None:

        _ = await get_agent_service().save_chat(user.access_token, session_id=body.session_id, role="user", content=body.message)

        agent = await get_agent_service().get_agent_full(user.access_token, agent_id=body.agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found")

        _ = await get_agent_service().save_agent_execution_log(
            access_token=user.access_token, name=agent.name, run_id=body.session_id,
            node_name="chat_node", event_type="agent_fullfilled", data={"agent_full": agent.model_dump()}
        )

        all_llms = await get_agent_service().get_llm_configs_for_cache(user.access_token, config_id=agent.llm_config_id)
        if not all_llms:
            raise HTTPException(status_code=404, detail="LLM configuration is not found for selected agent")

        llm_context = await get_agent_service().get_llm_context_by_agent_config(all_llms[0])

        messages: list[ChatMessage] = []
        messages.append(ChatMessage(session_id=body.session_id, role="system", content=agent.system_prompt))

        messages_history = await get_agent_service().get_chats(user.access_token, session_id=body.session_id)
        messages.extend(messages_history)
        messages.append(ChatMessage(session_id=body.session_id, role="user", content=body.message))

        llm_service = get_llm_service(llm_context, mode="chat")

        tool_definitions = get_agent_service().agent_tools_to_tool_definitions(
            agent.tools,
            agent.analytics_tools,
        )

        response = await llm_service.chat_completion(
            messages=[m.to_llm_dict() for m in messages],
            tools=[t.to_openai_tool() for t in tool_definitions] or None,  # ✅ pass None if no tools
        )

        print("LLM response:", response)

        response_type, payload = parse_llm_response(response)

        if response_type == LLMResponseType.TOOL_CALL:
            tool_results = []
            for tool_call in payload:
                matched_tool = next((t for t in tool_definitions if t.name == tool_call["name"]), None)

                tool_response = await get_tool_executor().execute(  # ✅ await if async
                    tool=matched_tool,
                    arguments=tool_call["args"],
                    user=user,
                    llm_context=llm_context,
                )
                print(f"Tool [{tool_call['name']}] response:", tool_response)
                tool_results.append({
                    "tool_call_id": tool_call["id"],
                    "name":         tool_call["name"],
                    "result":       tool_response,
                })

            # ✅ Send tool results back to LLM for final response
            llm_messages = [m.to_llm_dict() for m in messages]
            llm_messages.append(response["choices"][0]["message"])          # assistant turn with tool_calls
            for tr in tool_results:
                llm_messages.append({
                    "role":         "tool",
                    "tool_call_id": tr["tool_call_id"],
                    "content":      json.dumps(tr["result"]),
                })

            final_response = await llm_service.chat_completion(messages=llm_messages)
            content = final_response["choices"][0]["message"].get("content", "")

        elif response_type == LLMResponseType.MESSAGE:
            # ✅ use payload directly — it's already the content string
            content = payload

        _ = await get_agent_service().save_agent_execution_log(
            access_token=user.access_token, name=agent.name, run_id=body.session_id,
            node_name="chat_node", event_type="response", data={"response": content}
        )

        _ = await get_agent_service().save_chat(user.access_token, session_id=body.session_id, role="assistant", content=content)

    return ChatResponse(role="assistant", content=content)
    
def get_reply(response: dict) -> str:
    return response["choices"][0]["message"]["content"]

