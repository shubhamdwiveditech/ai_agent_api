"""/chat endpoint — multi-turn chat persisted to Supabase."""
from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.auth import require_api_key
from app.core.config import get_settings
from app.schemas.chat_schema import ChatRequest, ChatResponse
from app.services.common_service import new_uuid
from app.services.llm_services.openai_service import OpenAIClient, get_openai
from app.services.supabase_service import SupabaseClient, get_supabase

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(require_api_key)])

CHAT_SESSIONS = "chat_sessions"
CHAT_MESSAGES = "chat_messages"


# ---------------------------------------------------------------------- helpers
async def _get_or_create_session(
    supabase: SupabaseClient,
    *,
    session_id: str | None,
    user_id: str | None,
    system_prompt: str | None,
) -> dict:
    if session_id:
        existing = await supabase.select(
            CHAT_SESSIONS,
            filters={"id": f"eq.{session_id}"},
            single=True,
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"session_id {session_id} not found",
            )
        return existing  # type: ignore[return-value]

    new_id = new_uuid()
    rows = await supabase.insert(
        CHAT_SESSIONS,
        {"id": new_id, "user_id": user_id, "system_prompt": system_prompt},
    )
    return rows[0]


async def _load_history(supabase: SupabaseClient, session_id: str) -> list[dict]:
    msgs = await supabase.select(
        CHAT_MESSAGES,
        filters={"session_id": f"eq.{session_id}"},
        order="created_at.asc",
    )
    return msgs or []  # type: ignore[return-value]


def _build_openai_messages(
    *, system_prompt: str | None, history: list[dict], new_user_message: str
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if system_prompt:
        out.append({"role": "system", "content": system_prompt})
    for m in history:
        out.append({"role": m["role"], "content": m["content"]})
    out.append({"role": "user", "content": new_user_message})
    return out


# ---------------------------------------------------------------------- routes
@router.post("", response_model=ChatResponse, response_model_exclude_none=True)
async def chat(
    body: ChatRequest,
    supabase: SupabaseClient = Depends(get_supabase),
    openai: OpenAIClient = Depends(get_openai),
):
    settings = get_settings()
    model = body.model or settings.openai_chat_model

    session = await _get_or_create_session(
        supabase,
        session_id=body.session_id,
        user_id=body.user_id,
        system_prompt=body.system_prompt,
    )
    history = await _load_history(supabase, session["id"])
    messages = _build_openai_messages(
        system_prompt=session.get("system_prompt"),
        history=history,
        new_user_message=body.message,
    )

    # Persist user's message first so it shows up even if the LLM call fails.
    user_msg_id = new_uuid()
    await supabase.insert(
        CHAT_MESSAGES,
        {
            "id": user_msg_id,
            "session_id": session["id"],
            "role": "user",
            "content": body.message,
        },
    )

    # ------------------------------------------------------------------
    # Streaming branch (SSE)
    # ------------------------------------------------------------------
    if body.stream:
        assistant_msg_id = new_uuid()

        async def event_source() -> AsyncIterator[bytes]:
            collected: list[str] = []

            meta = {
                "type": "meta",
                "session_id": session["id"],
                "message_id": assistant_msg_id,
                "model": model,
            }
            yield f"data: {json.dumps(meta)}\n\n".encode("utf-8")

            try:
                async for chunk in openai.chat_completion_stream(
                    model=model,
                    messages=messages,
                    temperature=body.temperature,
                ):
                    if chunk.get("done"):
                        break
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    piece = delta.get("content")
                    if piece:
                        collected.append(piece)
                        out = {"type": "delta", "content": piece}
                        yield f"data: {json.dumps(out)}\n\n".encode("utf-8")
            except Exception as exc:  # noqa: BLE001
                err = {"type": "error", "detail": str(exc)}
                yield f"data: {json.dumps(err)}\n\n".encode("utf-8")
                return

            full_text = "".join(collected)
            try:
                await supabase.insert(
                    CHAT_MESSAGES,
                    {
                        "id": assistant_msg_id,
                        "session_id": session["id"],
                        "role": "assistant",
                        "content": full_text,
                        "model": model,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                err = {"type": "error", "detail": f"persist failed: {exc}"}
                yield f"data: {json.dumps(err)}\n\n".encode("utf-8")
                return

            done = {"type": "done", "message_id": assistant_msg_id}
            yield f"data: {json.dumps(done)}\n\n".encode("utf-8")
            yield b"data: [DONE]\n\n"

        return StreamingResponse(
            event_source(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    # ------------------------------------------------------------------
    # Non-streaming branch
    # ------------------------------------------------------------------
    completion = await openai.chat_completion(
        model=model, messages=messages, temperature=body.temperature
    )
    choice = (completion.get("choices") or [{}])[0]
    content = (choice.get("message") or {}).get("content", "") or ""

    assistant_msg_id = new_uuid()
    await supabase.insert(
        CHAT_MESSAGES,
        {
            "id": assistant_msg_id,
            "session_id": session["id"],
            "role": "assistant",
            "content": content,
            "model": model,
        },
    )

    return ChatResponse(
        session_id=session["id"],
        message_id=assistant_msg_id,
        content=content,
        model=model,
        usage=completion.get("usage"),
    )


@router.get("/sessions/{session_id}/messages")
async def list_messages(
    session_id: str,
    supabase: SupabaseClient = Depends(get_supabase),
):
    """Return the full message history for a session."""
    rows = await supabase.select(
        CHAT_MESSAGES,
        filters={"session_id": f"eq.{session_id}"},
        order="created_at.asc",
    )
    return {"session_id": session_id, "messages": rows or []}
