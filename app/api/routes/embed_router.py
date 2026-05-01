"""/embed endpoint — generate embeddings and (optionally) persist them."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import require_api_key
from app.schemas.embed_schema import EmbedRequest, EmbedResponse
from app.services.embed_service.embed_service import generate_and_store_embeddings
from app.services.llm_services.openai_service import OpenAIClient, get_openai
from app.services.supabase_service import SupabaseClient, get_supabase

router = APIRouter(prefix="/embed", tags=["embed"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=EmbedResponse, response_model_exclude_none=True)
async def embed(
    body: EmbedRequest,
    supabase: SupabaseClient = Depends(get_supabase),
    openai: OpenAIClient = Depends(get_openai),
):
    return await generate_and_store_embeddings(body, openai=openai, supabase=supabase)
