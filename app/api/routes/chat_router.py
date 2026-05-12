"""/chat endpoint — multi-turn chat persisted to Supabase."""
from __future__ import annotations
import json
from typing import Any
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


# ── Block detection ───────────────────────────────────────────────────────────
# Results whose "type" is in this set are emitted as tool_block events so the
# UI renders them natively (no server-side rendering, fastest path).
_BLOCK_TYPES = frozenset({"form", "table", "chart", "card", "list", "kanban"})


def _is_block(result: Any) -> bool:
    return isinstance(result, dict) and result.get("type") in _BLOCK_TYPES


def _row_count(result: Any) -> int:
    if isinstance(result, list):
        return len(result)
    if isinstance(result, dict):
        for key in ("data", "chunks", "rows", "items", "results"):
            if isinstance(result.get(key), list):
                return len(result[key])
    return 1 if result else 0


# ── SSE helpers (StreamEvent wire contract) ───────────────────────────────────
# Client union type:
#   { type: "text_delta";  text: string }
#   { type: "tool_block";  block: ToolBlock }      — UI renders form/table/chart natively
#   { type: "mcp_call";    tool: string; params: Record<string, unknown> }
#   { type: "mcp_result";  tool: string; rowCount: number }
#   { type: "sources";     sources: RagSource[] }  — RAG citations (extra, not in TS union)
#   { type: "done" }

def _sse_text_delta(text: str) -> str:
    return f"data: {json.dumps({'type': 'text_delta', 'text': text})}\n\n"

def _sse_tool_block(block: dict) -> str:
    return f"data: {json.dumps({'type': 'tool_block', 'block': block})}\n\n"

def _sse_mcp_call(tool: str, params: dict) -> str:
    return f"data: {json.dumps({'type': 'mcp_call', 'tool': tool, 'params': params})}\n\n"

def _sse_mcp_result(tool: str, row_count: int) -> str:
    return f"data: {json.dumps({'type': 'mcp_result', 'tool': tool, 'rowCount': row_count})}\n\n"

def _sse_sources(sources: list[RagSource]) -> str:
    return f"data: {json.dumps({'type': 'sources', 'sources': [s.model_dump(exclude_none=True) for s in sources]})}\n\n"

SSE_DONE = 'data: {"type":"done"}\n\n'


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
    """stream=True, no tool call: pipe tokens straight to the client."""
    content = ""
    async for chunk in llm_service.chat_completion_stream(messages=messages):
        if chunk.get("done"):
            break
        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
        if delta:
            content += delta
            yield _sse_text_delta(delta)
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
    """stream=True + tool call: mcp_call → execute → tool_block/mcp_result → stream reply."""
    # 1. Announce tool invocations
    for tc in tool_calls:
        yield _sse_mcp_call(tc["name"], tc.get("args", {}))

    # 2. Execute all tools
    tool_results, sources = await get_agent_service().run_tools_with_sources(
        ctx.tool_definitions, tool_calls, user, ctx.llm_context,
    )

    # 3. Emit block events (form/table/chart rendered by UI) + completion signal
    for tr in tool_results:
        result = tr["result"]
        if _is_block(result):
            yield _sse_tool_block(result)
        yield _sse_mcp_result(tr["name"], _row_count(result))

    # 4. RAG citations (kept for backward compat — UI can optionally handle)
    if sources:
        yield _sse_sources(sources)

    # 5. Stream LLM follow-up text with tool context
    tool_messages = _append_tool_messages(ctx.llm_dict_messages, assistant_msg, tool_results)

    content = ""
    async for chunk in ctx.llm_service.chat_completion_stream(messages=tool_messages):
        if chunk.get("done"):
            break
        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
        if delta:
            content += delta
            yield _sse_text_delta(delta)

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

    provider_tools = ctx.llm_service.format_tools(ctx.tool_definitions)

    # ── Case 2: stream=True, no tools — stream first call directly ────────────
    if body.stream and not provider_tools:
        return StreamingResponse(
            _stream_direct(ctx.llm_service, ctx.llm_dict_messages, *persist_args),
            media_type="text/event-stream",
        )

    # ── First LLM call (non-streaming) — required for tool-call detection ─────
    response = await ctx.llm_service.chat_completion(
        messages=ctx.llm_dict_messages, tools=provider_tools,
    )

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

        # Pull out UI-rendered blocks before feeding results back to the LLM
        blocks = [tr["result"] for tr in tool_results if _is_block(tr["result"])] or None

        tool_messages = _append_tool_messages(
            ctx.llm_dict_messages, response["choices"][0]["message"], tool_results,
        )
        final = await ctx.llm_service.chat_completion(messages=tool_messages)
        content = final["choices"][0]["message"].get("content", "")
        await get_agent_service().persist_chat_response(*persist_args, content)

    # ── Case 4: stream=False + no tool call ───────────────────────────────────
    else:
        sources = []
        blocks = None
        content = payload

    return ChatResponse(role="assistant", content=content, sources=sources or None, blocks=blocks)
