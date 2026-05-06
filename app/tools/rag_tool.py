"""Knowledge-base semantic search tool — runtime: local."""
from __future__ import annotations

from typing import Any

from app.schemas.llm_context_schema import LLMContext
from app.schemas.tool_schema import ToolDefinition, ToolInputSchema
from app.schemas.user_context_schema import UserContext
from app.services.llm_services.llm_factory import get_llm_service
from app.services.supabase_service import get_supabase_service
from app.services.tool_executor_service import get_tool_executor
from app.services.tool_registry_service import get_tool_registry
from app.services.user_service import get_user_service

TOOL_NAME = "search_knowledge_base"

_MATCH_THRESHOLD = 0.7
_MATCH_COUNT = 5

_DEFINITION = ToolDefinition(
    name=TOOL_NAME,
    description=(
        "Search the knowledge base using semantic similarity to find relevant document chunks. "
        "Returns matching chunks with source metadata (item name, KB name, similarity score, URL)."
    ),
    runtime="local",
    inputSchema=ToolInputSchema(
        type="object",
        properties={
            "query": {
                "type": "string",
                "description": "The question or search query to find relevant knowledge base content for",
            },
            "kb_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Optional list of knowledge base IDs to restrict the search scope",
            },
        },
        required=["query"],
    ),
)


async def _handler(
    arguments: dict[str, Any],
    *,
    user: UserContext,
    llm_context: LLMContext | None = None,
) -> dict[str, Any]:
    query: str = (arguments.get("query") or "").strip()
    kb_ids: list[int] | None = arguments.get("kb_ids") or None

    embed_context = await get_user_service().get_llm_context(user.access_token)
    if embed_context is None:
        return {"chunks": [], "error": "No LLM configuration found for embedding"}

    llm = get_llm_service(embed_context, mode="embed")
    try:
        embed_result = await llm.embeddings(input=query)
        data = embed_result.get("data") or []
        if not data:
            return {"chunks": [], "error": "Embedding returned no data"}
        embedding: list[float] = data[0].get("embedding", [])

        envelope = await get_supabase_service().rpc(
            user.access_token,
            "fn_search_kb_chunks",
            {
                "p_query_embedding": embedding,
                "p_kb_ids": kb_ids,
                "p_match_threshold": _MATCH_THRESHOLD,
                "p_match_count": _MATCH_COUNT,
            },
        )
        if not envelope.get("is_success"):
            return {"chunks": []}

        return {"chunks": envelope.get("data") or []}
    finally:
        await llm.aclose()


def ensure_registered() -> ToolDefinition:
    get_tool_executor().register_local_handler(TOOL_NAME, _handler)
    return _DEFINITION
