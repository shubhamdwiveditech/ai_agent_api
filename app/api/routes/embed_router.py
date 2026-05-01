"""/embed endpoint — generate embeddings and (optionally) persist them."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import require_user
from app.schemas.embed_schema import EmbedRequest, EmbedResponse
from app.schemas.user_context_schema import UserContext
from app.services.embed_service.embed_service import generate_and_store_embeddings
from app.services.supabase_service import SupabaseService, get_supabase_service

router = APIRouter(prefix="/embed", tags=["embed"], dependencies=[Depends(require_user)])


@router.post("", response_model=EmbedResponse, response_model_exclude_none=True)
async def embed(
    body: EmbedRequest,
    user: UserContext = Depends(require_user),
    supabase: SupabaseService = Depends(get_supabase_service),
):
    
    _ = user
    return await generate_and_store_embeddings(body, supabase=supabase)
