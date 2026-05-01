"""/embed endpoint — embed a knowledge-base item (file or website)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import require_user
from app.schemas.embed_schema import (
    EmbedKnowledgeItemResponse,
    EmbedRequest,
)
from app.schemas.user_context_schema import UserContext
from app.services.kb_item_embed_service import embed_knowledge_item
from app.services.supabase_service import SupabaseService, get_supabase_service

router = APIRouter(prefix="/embed", tags=["embed"], dependencies=[Depends(require_user)])


@router.post("", response_model=EmbedKnowledgeItemResponse)
async def embed(
    body: EmbedRequest,
    user: UserContext = Depends(require_user),
    supabase: SupabaseService = Depends(get_supabase_service),
):
    chunks = await embed_knowledge_item(
        item_id=body.id,
        access_token=user.access_token,
        supabase=supabase,
    )
    return EmbedKnowledgeItemResponse(item_id=body.id, chunks=chunks)
