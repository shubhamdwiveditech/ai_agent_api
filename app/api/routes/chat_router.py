"""/chat endpoint — multi-turn chat persisted to Supabase."""
from __future__ import annotations
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.auth import require_user
from app.schemas.chat_schema import ChatRequest, ChatResponse, RagSource
from app.schemas.user_context_schema import UserContext
from app.services.agent_service import ChatContext, get_agent_service
from app.services.common_service import LLMResponseType, parse_llm_response
from app.services.llm_services.llm_base import LLMService
from app.services.supabase_service import SupabaseService, get_supabase_service

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(require_user)])


# ── SSE formatting ────────────────────────────────────────────────────────────
# UI contract:
#   {"type": "status",  "message": "..."}          process notification
#   {"type": "content", "content": "token..."}     text delta
#   {"type": "sources", "sources": [{...}, ...]}   RAG citations (before DONE)
#   data: [DONE]                                   stream end

def _sse_content(delta: str) -> str:
    return f"data: {json.dumps({'type': 'content', 'content': delta})}\n\n"

def _sse_status(message: str) -> str:
    return f"data: {json.dumps({'type': 'status', 'message': message})}\n\n"

def _sse_sources(sources: list[RagSource]) -> str:
    return f"data: {json.dumps({'type': 'sources', 'sources': [s.model_dump(exclude_none=True) for s in sources]})}\n\n"

SSE_DONE = "data: [DONE]\n\n"


# ── Shared message builder ────────────────────────────────────────────────────

def _append_tool_messages(base: list[dict], assistant_msg: dict, tool_results: list[dict]) -> list[dict]:
    msgs = list(base)
    msgs.append(assistant_msg)
    for tr in tool_results:
        msgs.append({"role": "tool", "tool_call_id": tr["tool_call_id"], "content": json.dumps(tr["result"])})
    return msgs


# ── Streaming generators ──────────────────────────────────────────────────────

async def _stream_direct(
    llm_service: LLMService,
    messages: list[dict],
    access_token: str,
    agent_name: str,
    session_id,
):
    """Case 2 — stream=True, no tool call: pipe tokens straight to the client."""
    content = ""
    async for chunk in llm_service.chat_completion_stream(messages=messages):
        if chunk.get("done"):
            break
        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
        if delta:
            content += delta
            yield _sse_content(delta)
    yield SSE_DONE
    await get_agent_service().persist_chat_response(access_token, agent_name, session_id, content)


async def _stream_after_tools(
    ctx: ChatContext,
    tool_calls: list[dict],
    assistant_msg: dict,
    user: UserContext,
    access_token: str,
    agent_name: str,
    session_id,
):
    """Case 1 — stream=True, tool call: notify progress → emit sources → stream final reply."""
    for tc in tool_calls:
        yield _sse_status(f"Calling tool: {tc['name']}...")

    tool_results, sources = await get_agent_service().run_tools_with_sources(
        ctx.tool_definitions, tool_calls, user, ctx.llm_context,
    )

    for tr in tool_results:
        yield _sse_status(f"Tool '{tr['name']}' completed")

    if sources:
        yield _sse_sources(sources)

    tool_messages = _append_tool_messages(ctx.llm_dict_messages, assistant_msg, tool_results)
    yield _sse_status("Generating response...")

    content = ""
    async for chunk in ctx.llm_service.chat_completion_stream(messages=tool_messages):
        if chunk.get("done"):
            break
        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
        if delta:
            content += delta
            yield _sse_content(delta)

    yield SSE_DONE
    await get_agent_service().persist_chat_response(access_token, agent_name, session_id, content)


# ── Route ─────────────────────────────────────────────────────────────────────

@router.post("", response_model=ChatResponse, response_model_exclude_none=True)
async def chat(
    body: ChatRequest,
    user: UserContext = Depends(require_user),
    supabase: SupabaseService = Depends(get_supabase_service),
):
    _ = supabase

    if body.agent_id is None:
        return ChatResponse(role="assistant", content="")

    await get_agent_service().save_chat(
        user.access_token, session_id=body.session_id, role="user", content=body.message,
    )

    ctx = await get_agent_service().prepare_chat_context(
        user.access_token,
        agent_id=body.agent_id,
        session_id=body.session_id,
        user_message=body.message,
    )

    persist_args = (user.access_token, ctx.agent.name, body.session_id)

    # ── Case 2: stream=True, no tools — stream first call directly ────────────
    if body.stream and not ctx.openai_tools:
        return StreamingResponse(
            _stream_direct(ctx.llm_service, ctx.llm_dict_messages, *persist_args),
            media_type="text/event-stream",
        )

    # ── First LLM call (non-streaming) — required for tool-call detection ─────
    response = await ctx.llm_service.chat_completion(
        messages=ctx.llm_dict_messages, tools=ctx.openai_tools,
    )
    print("LLM response:", response)
    response_type, payload = parse_llm_response(response)

    # ── Case 1: stream=True + tool call ───────────────────────────────────────
    if body.stream and response_type == LLMResponseType.TOOL_CALL:
        return StreamingResponse(
            _stream_after_tools(ctx, payload, response["choices"][0]["message"], user, *persist_args),
            media_type="text/event-stream",
        )

    # ── Case 2b: stream=True, tools defined but LLM skipped them ─────────────
    if body.stream and response_type == LLMResponseType.MESSAGE:
        return StreamingResponse(
            _stream_direct(ctx.llm_service, ctx.llm_dict_messages, *persist_args),
            media_type="text/event-stream",
        )

    # ── Case 3: stream=False + tool call ──────────────────────────────────────
    if response_type == LLMResponseType.TOOL_CALL:
        tool_results, sources = await get_agent_service().run_tools_with_sources(
            ctx.tool_definitions, payload, user, ctx.llm_context,
        )
        tool_messages = _append_tool_messages(
            ctx.llm_dict_messages, response["choices"][0]["message"], tool_results,
        )
        final = await ctx.llm_service.chat_completion(messages=tool_messages)
        content = final["choices"][0]["message"].get("content", "")

    # ── Case 4: stream=False + no tool call ───────────────────────────────────
    else:
        sources = []
        content = payload

    await get_agent_service().persist_chat_response(*persist_args, content)
    return ChatResponse(role="assistant", content=content, sources=sources or None)
