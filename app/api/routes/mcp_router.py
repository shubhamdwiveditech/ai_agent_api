"""MCP HTTP+SSE transport — JSON-RPC 2.0 (MCP spec 2024-11-05)."""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


from app.services.supabase_service import SupabaseService, get_supabase_service
from app.services.supabase_service import SupabaseService
from app.services.mcp_service import get_mcp_service
from app.services.tool_executor_service import get_tool_executor


router = APIRouter(prefix="/mcp", tags=["mcp"])

_MCP_VERSION = "2024-11-05"
_SERVER_INFO = {"name": "ai-agent-api", "version": "1.0.0"}
_SERVER_CAPS = {"tools": {"listChanged": False}}

# session_id → asyncio.Queue of outbound JSON-RPC messages
_sessions: dict[str, asyncio.Queue] = {}


# ── JSON-RPC schemas ──────────────────────────────────────────


class _RpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int | None = None
    method: str
    params: dict[str, Any] | None = None


class _RpcError(BaseModel):
    code: int
    message: str
    data: Any | None = None


class _RpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int | None = None
    result: Any | None = None
    error: _RpcError | None = None


# ── SSE helpers ───────────────────────────────────────────────


def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


async def _session_stream(
    session_id: str, queue: asyncio.Queue, request: Request
) -> AsyncGenerator[str, None]:
    """Yield SSE events for this session until the client disconnects."""
    yield _sse("endpoint", "/mcp") 
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=25.0)
                if msg is None:  # sentinel: server-side close
                    break
                yield _sse("message", json.dumps(msg))
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"  # SSE comment keeps the TCP connection alive
    finally:
        _sessions.pop(session_id, None)


# ── Method handlers ───────────────────────────────────────────


def _on_initialize(_params: dict | None) -> dict:
    return {
        "protocolVersion": _MCP_VERSION,
        "capabilities": _SERVER_CAPS,
        "serverInfo": _SERVER_INFO,
    }


async def _on_tools_call(access_token: str, params: dict | None, request: Request) -> dict:
    if not params or not params.get("name"):
        raise ValueError("params.name is required")

    name: str = params["name"]
    arguments: dict = params.get("arguments") or {}

    tool = next((t for t in await get_mcp_service().get_mcp_tools(access_token=access_token) if t.name == name), None)

    if tool is None:
        raise KeyError(f"Unknown tool: {name}")

    # User context is optional — local handlers don't need it;
    # HTTP tools will raise naturally if auth is missing.
    user = getattr(request.state, "user", None)
    raw = await get_tool_executor().execute(tool=tool, arguments=arguments, user=user)

    text = raw if isinstance(raw, str) else json.dumps(raw)
    return {"content": [{"type": "text", "text": text}], "isError": False}


# ── Routes ────────────────────────────────────────────────────


@router.get("/")
async def sse_connect(request: Request) -> StreamingResponse:
    sid = str(uuid.uuid4())
    _sessions[sid] = asyncio.Queue()

    return StreamingResponse(
        _session_stream(sid, _sessions[sid], request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Mcp-Session-Id": sid 
        },
    )

@router.post("/")
async def handle_message(
    body: _RpcRequest,
    request: Request,
    mcp_session_id: str = Header(...),
    x_api_key: str = Header(...),
    supabase: SupabaseService = Depends(get_supabase_service),
) -> dict:
    queue = _sessions.get(mcp_session_id)
    if queue is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {mcp_session_id}")

    is_notification = body.id is None
    response_payload: dict | None = None

    def _build(result=None, error=None):
        return _RpcResponse(id=body.id, result=result, error=error).model_dump(
            exclude_none=True
        )

    try:
        if body.method == "initialize":
            response_payload = _build(_on_initialize(body.params))

        elif body.method == "ping":
            response_payload = _build({})

        elif body.method == "tools/list":
            tools = await get_mcp_service().get_mcp_tools(access_token=x_api_key)
            mcp_tools = [t.to_mcp_tool() for t in tools] if tools else []
            response_payload = _build({"tools": mcp_tools})

        elif body.method == "tools/call":
            result = await _on_tools_call(x_api_key, body.params, request)
            response_payload = _build(result)

        elif is_notification:
            return {}  # notifications get empty 200, no response

        else:
            response_payload = _build(
                error=_RpcError(code=-32601, message=f"Method not found: {body.method}")
            )

    except (KeyError, ValueError) as exc:
        response_payload = _build(error=_RpcError(code=-32602, message=str(exc)))
    except Exception as exc:
        response_payload = _build(error=_RpcError(code=-32603, message=str(exc)))

    # ── Also push to SSE queue for clients that read via stream ──
    if response_payload and not is_notification:
        await queue.put(response_payload)

    # ── Return directly in HTTP response (primary path) ──────────
    return response_payload or {}