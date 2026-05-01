// deno-lint-ignore-file no-explicit-any
import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY")!;
const OPENAI_API_KEY = Deno.env.get("OPENAI_API_KEY");

// Tunables
const CHUNK_SIZE = 1200; // characters
const CHUNK_OVERLAP = 150;
const EMBED_BATCH = 16;
const EMBED_MODEL = "text-embedding-3-small";
const EMBED_DIMS = 1536;

interface KbItem {
  id: number;
  kb_id: number;
  name: string;
  item_type: "file" | "website";
  file_type: string | null;
  storage_path: string | null;
  url: string | null;
}

function sanitizeForPg(s: string): string {
  // Postgres text/jsonb cannot store \u0000. Also strip other C0 control chars
  // (except tab/newline) and lone surrogates which break UTF-8 / JSON encoding.
  return s
    .replace(/\u0000/g, "")
    .replace(/[\x01-\x08\x0B\x0C\x0E-\x1F\x7F]/g, "")
    .replace(/[\uD800-\uDFFF]/g, "");
}

function chunkText(text: string): string[] {
  const clean = sanitizeForPg(text).replace(/\s+/g, " ").trim();
  if (!clean) return [];
  const chunks: string[] = [];
  let start = 0;
  while (start < clean.length) {
    const end = Math.min(start + CHUNK_SIZE, clean.length);
    chunks.push(clean.slice(start, end));
    if (end === clean.length) break;
    start = end - CHUNK_OVERLAP;
  }
  return chunks;
}

function stripHtml(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/\s+/g, " ")
    .trim();
}

async function decodeBufferToText(buf: ArrayBuffer, fileType: string | null, name: string): Promise<string> {
  const lower = (fileType || name.split(".").pop() || "").toLowerCase();

  // Plain text-like
  if (["txt", "md", "csv", "json", "html", "htm", "log", "xml", "yaml", "yml"].includes(lower)) {
    const text = new TextDecoder().decode(buf);
    return lower === "html" || lower === "htm" ? stripHtml(text) : text;
  }

  // Best-effort: try utf-8 and keep printable. PDF/DOCX/etc. are not natively
  // parseable in Workers without native libs — surface a helpful error.
  // PDFs, images, and Office docs need native parsing not available in Workers.
  // Accept upload but skip text extraction gracefully (will be handled later).
  if (["pdf", "docx", "doc", "pptx", "xlsx", "png", "jpg", "jpeg", "webp", "gif", "bmp", "tiff"].includes(lower)) {
    throw new Error(
      `${lower.toUpperCase()} content extraction is not supported yet. The file is uploaded but cannot be embedded.`
    );
  }

  // Fallback: utf-8 decode
  return new TextDecoder().decode(buf);
}

async function embedBatch(texts: string[]): Promise<number[][]> {
  const resp = await fetch("https://api.openai.com/v1/embeddings", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${OPENAI_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: EMBED_MODEL,
      input: texts,
    }),
  });

  if (!resp.ok) {
    const txt = await resp.text();
    throw new Error(`OpenAI embeddings ${resp.status}: ${txt.slice(0, 300)}`);
  }
  const json = await resp.json();
  const list: number[][] = (json.data || []).map((d: any) => d.embedding);
  if (list.length !== texts.length) {
    throw new Error(`Embedding count mismatch: got ${list.length}, expected ${texts.length}`);
  }
  for (const v of list) {
    if (!Array.isArray(v) || v.length !== EMBED_DIMS) {
      throw new Error(`Embedding dimension ${v?.length} != ${EMBED_DIMS}`);
    }
  }
  return list;
}

function vectorLiteral(v: number[]): string {
  // pgvector text format: "[0.1,0.2,...]"
  return "[" + v.map((x) => (Number.isFinite(x) ? x.toFixed(6) : "0")).join(",") + "]";
}

serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  // Authenticated supabase client (uses caller's JWT, RLS applies)
  const authHeader = req.headers.get("Authorization") ?? "";
  const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    global: { headers: { Authorization: authHeader } },
    auth: { persistSession: false, autoRefreshToken: false },
  });

  let itemId: number | null = null;

  try {
    if (!OPENAI_API_KEY) throw new Error("OPENAI_API_KEY is not configured");

    const body = await req.json().catch(() => ({}));
    itemId = Number(body?.item_id);
    if (!itemId || Number.isNaN(itemId)) throw new Error("item_id is required");

    // Load item (RLS allows tenant-wide SELECT)
    const { data: itemRows, error: itemErr } = await supabase
      .from("knowledge_base_items")
      .select("id, kb_id, name, item_type, file_type, storage_path, url")
      .eq("id", itemId)
      .limit(1);

    if (itemErr) throw itemErr;
    const item = (itemRows?.[0] ?? null) as KbItem | null;
    if (!item) throw new Error("Item not found");

    // Mark processing
    await supabase.rpc("fn_set_kb_item_status" as never, {
      p_id: itemId, p_status: "processing", p_error: null,
    } as never);

    // ── Extract text ────────────────────────────────────────
    let text = "";
    if (item.item_type === "file") {
      if (!item.storage_path) throw new Error("Missing storage_path");
      const { data: blob, error: dlErr } = await supabase
        .storage.from("knowledge-base")
        .download(item.storage_path);
      if (dlErr || !blob) throw new Error(dlErr?.message || "Failed to download file");
      const buf = await blob.arrayBuffer();
      text = await decodeBufferToText(buf, item.file_type, item.name);
    } else if (item.item_type === "website") {
      if (!item.url) throw new Error("Missing URL");
      const resp = await fetch(item.url, {
        headers: { "User-Agent": "Mozilla/5.0 BLS-AI-KB-Bot" },
      });
      if (!resp.ok) throw new Error(`Failed to fetch URL: ${resp.status}`);
      const html = await resp.text();
      text = stripHtml(html);
    } else {
      throw new Error(`Unsupported item type: ${item.item_type}`);
    }

    if (!text || text.length < 20) {
      throw new Error("Document is empty or too short to embed");
    }

    // ── Chunk ────────────────────────────────────────
    const chunks = chunkText(text);
    if (chunks.length === 0) throw new Error("No chunks produced");

    // ── Embed in batches ────────────────────────────────────
    const allEmbeddings: number[][] = [];
    for (let i = 0; i < chunks.length; i += EMBED_BATCH) {
      const batch = chunks.slice(i, i + EMBED_BATCH);
      const vecs = await embedBatch(batch);
      allEmbeddings.push(...vecs);
    }

    // ── Save via RPC ────────────────────────────────────────
    const payload = chunks.map((content, idx) => ({
      chunk_index: idx,
      content,
      token_count: Math.ceil(content.length / 4), // rough estimate
      embedding: vectorLiteral(allEmbeddings[idx]),
    }));

    const { data: saveData, error: saveErr } = await supabase.rpc(
      "fn_save_kb_chunks" as never,
      { p_item_id: itemId, p_chunks: payload } as never
    );
    if (saveErr) throw saveErr;
    const env = saveData as any;
    if (env && env.is_success === false) throw new Error(env.message || "Failed to save chunks");

    // Mark ready
    await supabase.rpc("fn_set_kb_item_status" as never, {
      p_id: itemId, p_status: "ready", p_error: null,
    } as never);

    return new Response(
      JSON.stringify({ ok: true, item_id: itemId, chunks: chunks.length }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  } catch (e: any) {
    const message = String(e?.message ?? e ?? "Unknown error").slice(0, 500);
    console.error("embed-knowledge-item error:", message);
    if (itemId) {
      try {
        await supabase.rpc("fn_set_kb_item_status" as never, {
          p_id: itemId, p_status: "failed", p_error: message,
        } as never);
      } catch (_) { /* swallow */ }
    }
    return new Response(JSON.stringify({ error: message }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
