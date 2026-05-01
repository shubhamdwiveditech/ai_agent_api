"""Knowledge-base item embedding pipeline (file + website) via Supabase RPC."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import HTTPException

from app.core.config import get_settings
from app.core.http import http_client
from app.services.embed_service.content_parser_service import parse_file_bytes
from app.services.llm_services.llm_factory import get_llm_service
from app.services.supabase_service import SupabaseService
from app.services.user_service import get_user_service


KbItemType = Literal["file", "website"]


@dataclass(frozen=True)
class KbItem:
    id: int
    kb_id: int
    name: str
    item_type: KbItemType
    file_type: str | None
    storage_path: str | None
    url: str | None


_C0_CTRL_RE = re.compile(r"[\x01-\x08\x0B\x0C\x0E-\x1F\x7F]")
_SURROGATE_RE = re.compile(r"[\uD800-\uDFFF]")
_WHITESPACE_RE = re.compile(r"\s+")
_SCRIPT_RE = re.compile(r"<script[\s\S]*?</script>", re.IGNORECASE)
_STYLE_RE = re.compile(r"<style[\s\S]*?</style>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


def sanitize_for_pg(text: str) -> str:
    # Postgres text/jsonb cannot store \u0000.
    text = text.replace("\u0000", "")
    text = _C0_CTRL_RE.sub("", text)
    text = _SURROGATE_RE.sub("", text)
    return text


def strip_html(html: str) -> str:
    text = _SCRIPT_RE.sub(" ", html)
    text = _STYLE_RE.sub(" ", text)
    text = _TAG_RE.sub(" ", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    return _WHITESPACE_RE.sub(" ", text).strip()


def chunk_text(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
    clean = _WHITESPACE_RE.sub(" ", sanitize_for_pg(text)).strip()
    if not clean:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = min(start + chunk_size, len(clean))
        chunks.append(clean[start:end])
        if end >= len(clean):
            break
        start = max(0, end - chunk_overlap)
    return chunks


def vector_literal(vec: list[float]) -> str:
    # pgvector text format: "[0.1,0.2,...]"
    parts = []
    for x in vec:
        xf = float(x)
        parts.append(f"{xf:.6f}" if math.isfinite(xf) else "0")
    return "[" + ",".join(parts) + "]"


async def embed_knowledge_item(
    *,
    item_id: int,
    access_token: str,
    supabase: SupabaseService,
) -> int:
    """End-to-end: load KB item, extract text, chunk, embed, save via RPCs.

    Returns:
        Number of chunks saved.
    """
    settings = get_settings()

    item = await _load_kb_item(access_token=access_token, supabase=supabase, item_id=item_id)

    await _set_item_status(
        access_token=access_token, supabase=supabase, item_id=item_id, status="processing", error=None
    )

    llm_context = await get_user_service().get_llm_context(access_token)
    if llm_context is None:
        await _set_item_status(
            access_token=access_token,
            supabase=supabase,
            item_id=item_id,
            status="failed",
            error="Default LLM config not found",
        )
        raise HTTPException(status_code=502, detail="Default LLM config not found")

    llm = get_llm_service(llm_context, mode="embed")
    expected_dims = settings.embed_expected_dims
    embed_model_name = getattr(getattr(llm_context, "embed_model", None), "model", None)
    try:
        text = await _extract_item_text(access_token=access_token, supabase=supabase, item=item)
        if not text or len(text) < 20:
            raise ValueError("Document is empty or too short to embed")

        chunks = chunk_text(
            text,
            chunk_size=settings.embed_chunk_size,
            chunk_overlap=settings.embed_chunk_overlap,
        )
        if not chunks:
            raise ValueError("No chunks produced")

        embeddings: list[list[float]] = []
        for i in range(0, len(chunks), settings.embed_batch_size):
            batch = chunks[i : i + settings.embed_batch_size]
            result: dict[str, Any] = await llm.embeddings(input=batch)
            data = result.get("data") if isinstance(result, dict) else None
            if not isinstance(data, list) or len(data) != len(batch):
                raise ValueError("Embedding count mismatch")
            ordered = [d for d in sorted(data, key=lambda d: d.get("index", 0))]
            for d in ordered:
                vec = d.get("embedding")
                if not isinstance(vec, list):
                    raise ValueError("Invalid embedding payload from provider")
                if expected_dims is not None and len(vec) != expected_dims:
                    model_hint = f" (model={embed_model_name})" if embed_model_name else ""
                    raise ValueError(
                        f"Embedding dimension mismatch{model_hint}: expected {expected_dims}, got {len(vec)}. "
                        "Fix by selecting a model with the expected dimensions in your default embed config "
                        "(fn_get_default_llm), or change `knowledge_base_chunks.embedding` vector dimension."
                    )
                embeddings.append(vec)

        payload = [
            {
                "chunk_index": idx,
                "content": chunk,
                "token_count": int(math.ceil(len(chunk) / 4)),
                "embedding": vector_literal(embeddings[idx]),
            }
            for idx, chunk in enumerate(chunks)
        ]

        save_env = await supabase.rpc(
            access_token,
            "fn_save_kb_chunks",
            {"p_item_id": item_id, "p_chunks": payload},
        )
        if not save_env.get("is_success"):
            raise ValueError(save_env.get("message") or "Failed to save chunks")

        await _set_item_status(
            access_token=access_token, supabase=supabase, item_id=item_id, status="ready", error=None
        )
        return len(chunks)
    except Exception as exc:  # noqa: BLE001
        message = str(getattr(exc, "detail", None) or str(exc) or "Unknown error")[:500]
        try:
            await _set_item_status(
                access_token=access_token, supabase=supabase, item_id=item_id, status="failed", error=message
            )
        except Exception:
            pass
        raise
    finally:
        try:
            await llm.aclose()
        except Exception:
            pass


async def _load_kb_item(*, access_token: str, supabase: SupabaseService, item_id: int) -> KbItem:
    env = await supabase.rpc(access_token, "fn_get_kb_item", {"p_id": item_id})
    if not env.get("is_success"):
        raise HTTPException(status_code=502, detail=env.get("message") or "Failed to load item")

    data = env.get("data") or []
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise HTTPException(status_code=404, detail="Item not found")
    row = data[0]
    try:
        return KbItem(
            id=int(row["id"]),
            kb_id=int(row["kb_id"]),
            name=str(row.get("name") or ""),
            item_type=str(row.get("item_type") or "file"),  # type: ignore[assignment]
            file_type=(str(row["file_type"]) if row.get("file_type") is not None else None),
            storage_path=(str(row["storage_path"]) if row.get("storage_path") is not None else None),
            url=(str(row["url"]) if row.get("url") is not None else None),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="Invalid item payload from RPC") from exc


async def _set_item_status(
    *,
    access_token: str,
    supabase: SupabaseService,
    item_id: int,
    status: str,
    error: str | None,
) -> None:
    env = await supabase.rpc(
        access_token,
        "fn_set_kb_item_status",
        {"p_id": item_id, "p_status": status, "p_error": error},
    )
    if not env.get("is_success"):
        raise HTTPException(status_code=502, detail=env.get("message") or "Failed to update status")


async def _extract_item_text(*, access_token: str, supabase: SupabaseService, item: KbItem) -> str:
    settings = get_settings()

    if item.item_type == "file":
        if not item.storage_path:
            raise ValueError("Missing storage_path")
        file_bytes = await supabase.storage_download_bytes(
            access_token,
            bucket=settings.embed_storage_bucket,
            path=item.storage_path,
        )
        # `file_type` is typically "pdf"/"docx"/...; pass as filename extension hint.
        filename = item.name or f"file.{(item.file_type or '').strip('.')}"
        content_type = None
        return parse_file_bytes(file_bytes, filename=filename, content_type=content_type).text

    if item.item_type == "website":
        if not item.url:
            raise ValueError("Missing URL")
        resp = await http_client.get(
            url=item.url,
            headers={"User-Agent": "Mozilla/5.0 BLS-AI-KB-Bot"},
            raise_for_status=False,
        )
        if resp.status_code >= 400:
            raise ValueError(f"Failed to fetch URL: {resp.status_code}")
        return strip_html(resp.text)

    raise ValueError(f"Unsupported item type: {item.item_type}")
