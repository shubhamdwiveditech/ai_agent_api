"""Embedding service: generates vectors and (optionally) persists them to Supabase."""
from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.schemas.embed_schema import EmbedItem, EmbedRequest, EmbedResponse
from app.services.common_service import new_uuid
from app.services.llm_services.openai_service import OpenAIClient
from app.services.supabase_service import SupabaseClient


EMBEDDINGS_TABLE = "embeddings"


async def generate_and_store_embeddings(
    body: EmbedRequest,
    *,
    openai: OpenAIClient,
    supabase: SupabaseClient,
) -> EmbedResponse:
    settings = get_settings()
    model = body.model or settings.openai_embed_model

    inputs = [body.input] if isinstance(body.input, str) else list(body.input)
    if not inputs:
        return EmbedResponse(model=model, count=0, items=[])

    result: dict[str, Any] = await openai.embeddings(model=model, input=inputs)
    embeddings = [d["embedding"] for d in sorted(result["data"], key=lambda d: d["index"])]

    items: list[EmbedItem] = []
    rows_to_insert: list[dict[str, Any]] = []
    for content, vector in zip(inputs, embeddings):
        row_id = new_uuid()
        items.append(
            EmbedItem(
                id=row_id if body.persist else None,
                content=content,
                embedding=vector,
                metadata=body.metadata,
            )
        )
        if body.persist:
            rows_to_insert.append(
                {
                    "id": row_id,
                    "namespace": body.namespace,
                    "content": content,
                    "embedding": vector,
                    "metadata": body.metadata,
                    "model": model,
                }
            )

    if rows_to_insert:
        await supabase.insert(EMBEDDINGS_TABLE, rows_to_insert, return_representation=False)

    return EmbedResponse(
        model=model,
        count=len(items),
        items=items,
        usage=result.get("usage"),
    )
