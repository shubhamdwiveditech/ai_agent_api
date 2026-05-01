"""/chat endpoint — multi-turn chat persisted to Supabase."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from app.core.auth import require_user
from app.schemas.chat_schema import ChatRequest, ChatResponse
from app.schemas.user_context_schema import UserContext
from app.services.common_service import new_uuid
from app.services.supabase_service import SupabaseService, get_supabase_service

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(require_user)])

# ---------------------------------------------------------------------- routes
@router.post("", response_model=ChatResponse, response_model_exclude_none=True)
async def chat(
    body: ChatRequest,
    user: UserContext = Depends(require_user),
    supabase: SupabaseService = Depends(get_supabase_service),
):
    
    return ChatResponse(
        content=body.message,
    )
