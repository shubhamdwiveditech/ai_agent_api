// deno-lint-ignore-file no-explicit-any
import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version",
};

interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

interface ChunkRow {
  chunk_id: number;
  item_id: number;
  kb_id: number;
  chunk_index: number;
  content: string;
  item_name: string;
  item_type: string;
  item_url: string | null;
  kb_name: string;
  similarity: number;
}

const EMBED_MODEL = "text-embedding-3-small";
const CHAT_MODEL = "gpt-4o-mini";
const MATCH_THRESHOLD = 0.3;
const MATCH_COUNT = 6;

function jsonResp(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

async function embedQuery(text: string, apiKey: string): Promise<number[]> {
  const r = await fetch("https://api.openai.com/v1/embeddings", {
    method: "POST",
    headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
    body: JSON.stringify({ model: EMBED_MODEL, input: text }),
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(`Embedding failed: ${r.status} ${t.slice(0, 200)}`);
  }
  const j = await r.json();
  return j.data[0].embedding as number[];
}

/** Build the strict-RAG system prompt. The model is told to refuse anything not in CONTEXT. */
function buildStrictSystemPrompt(chunks: ChunkRow[]): string {
  const ctx = chunks
    .map(
      (c, i) =>
        `[#${i + 1}] (source: "${c.item_name}" — KB: ${c.kb_name})\n${c.content}`
    )
    .join("\n\n---\n\n");

  return `You are BLS AI, a retrieval-augmented assistant for BLS International Services Ltd.

RULES:
1. Answer the user's question using ONLY the information present in the CONTEXT below. The CONTEXT contains excerpts retrieved from the company's knowledge base and is your single source of truth.
2. If the CONTEXT contains information that is relevant to the question — even partially — use it to answer as helpfully as you can. Summarize, quote, or rephrase what is in the CONTEXT. Do NOT refuse just because the answer is incomplete; provide what the CONTEXT supports and clearly note any gaps.
3. Only if the CONTEXT contains NOTHING related to the user's question at all, reply EXACTLY:
   "I don't know based on the available knowledge base."
4. NEVER invent facts, names, numbers, dates, URLs, or quotations that are not in the CONTEXT. Do not use outside or general knowledge.
5. Cite EVERY factual claim with the matching chunk marker like [#1], [#2]. Multiple citations allowed: [#1][#3].
6. Format with markdown when helpful (lists, tables, code). Be concise and direct.

CONTEXT:
${ctx}`;
}

/** Stream a plain text message back as OpenAI-style SSE so the client parser keeps working. */
function streamPlainText(text: string, sources: unknown[]): Response {
  const enc = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      // Stream the text in small chunks for a typewriter feel
      const words = text.split(/(\s+)/);
      let i = 0;
      const push = () => {
        if (i >= words.length) {
          // emit sources sentinel + DONE
          controller.enqueue(
            enc.encode(`data: ${JSON.stringify({ sources })}\n\n`)
          );
          controller.enqueue(enc.encode(`data: [DONE]\n\n`));
          controller.close();
          return;
        }
        const chunk = words[i++];
        const payload = { choices: [{ delta: { content: chunk } }] };
        controller.enqueue(enc.encode(`data: ${JSON.stringify(payload)}\n\n`));
        setTimeout(push, 12);
      };
      push();
    },
  });
  return new Response(stream, {
    headers: { ...corsHeaders, "Content-Type": "text/event-stream" },
  });
}

/** Wrap the upstream OpenAI SSE stream and append a final `data: {sources:[...]}` event before [DONE]. */
function pipeWithSources(upstream: ReadableStream<Uint8Array>, sources: unknown[]): Response {
  const enc = new TextEncoder();
  const dec = new TextDecoder();
  const reader = upstream.getReader();

  const stream = new ReadableStream({
    async start(controller) {
      let buf = "";
      try {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += dec.decode(value, { stream: true });

          // Pass everything through except the final [DONE] line — we re-emit it.
          let nl: number;
          while ((nl = buf.indexOf("\n")) !== -1) {
            const line = buf.slice(0, nl + 1);
            buf = buf.slice(nl + 1);
            const trimmed = line.trim();
            if (trimmed === "data: [DONE]") {
              controller.enqueue(
                enc.encode(`data: ${JSON.stringify({ sources })}\n\n`)
              );
              controller.enqueue(enc.encode(`data: [DONE]\n\n`));
              continue;
            }
            controller.enqueue(enc.encode(line));
          }
        }
        if (buf) controller.enqueue(enc.encode(buf));
      } catch (e) {
        console.error("stream error", e);
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: { ...corsHeaders, "Content-Type": "text/event-stream" },
  });
}

serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { messages, kbIds } = (await req.json()) as {
      messages: ChatMessage[];
      kbIds?: number[] | null;
    };

    if (!Array.isArray(messages) || messages.length === 0) {
      return jsonResp({ error: "messages must be a non-empty array" }, 400);
    }

    const OPENAI_API_KEY = Deno.env.get("OPENAI_API_KEY");
    const SUPABASE_URL = Deno.env.get("SUPABASE_URL");
    const SUPABASE_ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY");
    if (!OPENAI_API_KEY) return jsonResp({ error: "OPENAI_API_KEY not configured" }, 500);
    if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
      return jsonResp({ error: "Supabase env not configured" }, 500);
    }

    const authHeader = req.headers.get("Authorization") ?? "";
    const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      global: { headers: { Authorization: authHeader } },
    });

    // ── 1. Get the user's latest question ───────────────────────────────
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUser?.content?.trim()) {
      return jsonResp({ error: "No user message found" }, 400);
    }

    // ── 2. Embed the question ───────────────────────────────────────────
    let queryEmbedding: number[];
    try {
      queryEmbedding = await embedQuery(lastUser.content, OPENAI_API_KEY);
    } catch (e: any) {
      console.error("embed error", e);
      return jsonResp({ error: "Failed to embed query" }, 500);
    }

    // ── 3. Vector search via RPC (tenant-scoped, future-filterable) ─────
    const { data: rpcData, error: rpcErr } = await supabase.rpc("fn_search_kb_chunks", {
      p_query_embedding: queryEmbedding as unknown as string,
      p_kb_ids: kbIds && kbIds.length > 0 ? kbIds : null,
      p_match_threshold: MATCH_THRESHOLD,
      p_match_count: MATCH_COUNT,
    });

    if (rpcErr) {
      console.error("fn_search_kb_chunks error", rpcErr);
      return jsonResp({ error: "Knowledge base search failed" }, 500);
    }

    const env = rpcData as { is_success?: boolean; data?: ChunkRow[]; message?: string } | null;
    if (!env?.is_success) {
      console.error("RPC unsuccessful", env?.message);
      return jsonResp({ error: env?.message ?? "Search failed" }, 500);
    }

    const chunks: ChunkRow[] = env.data ?? [];

    // ── 4a. EMPTY CONTEXT — refuse + suggest rephrasings (no LLM hallucination path) ─────
    if (chunks.length === 0) {
      const refusal = `I couldn't find anything relevant in the knowledge base for your question.\n\n`;

      // Ask the LLM ONLY for rephrasing suggestions — never to answer the question itself.
      let suggestions = "";
      try {
        const sugResp = await fetch("https://api.openai.com/v1/chat/completions", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${OPENAI_API_KEY}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            model: CHAT_MODEL,
            temperature: 0.3,
            max_tokens: 200,
            messages: [
              {
                role: "system",
                content:
                  "The user asked a question, but a knowledge-base search returned no results. " +
                  "Suggest 2-3 SHORT alternative ways they could rephrase their question to get better search hits. " +
                  "Do NOT answer the question. Do NOT add any other text. " +
                  "Respond as a markdown bulleted list only.",
              },
              { role: "user", content: lastUser.content },
            ],
          }),
        });
        if (sugResp.ok) {
          const j = await sugResp.json();
          suggestions = j.choices?.[0]?.message?.content?.trim() ?? "";
        }
      } catch (e) {
        console.error("suggestion call failed", e);
      }

      const body =
        refusal +
        (suggestions
          ? `**Try rephrasing — for example:**\n\n${suggestions}`
          : `Try rephrasing your question, or ask an admin to add a relevant document to the knowledge base.`);

      return streamPlainText(body, []);
    }

    // ── 4b. CONTEXT FOUND — strict RAG with citations ───────────────────
    const systemPrompt = buildStrictSystemPrompt(chunks);

    const upstream = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${OPENAI_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: CHAT_MODEL,
        stream: true,
        temperature: 0,
        messages: [{ role: "system", content: systemPrompt }, ...messages],
      }),
    });

    if (!upstream.ok || !upstream.body) {
      const text = upstream.body ? await upstream.text() : "";
      console.error("OpenAI error", upstream.status, text);
      if (upstream.status === 429) return jsonResp({ error: "Rate limit exceeded." }, 429);
      if (upstream.status === 401) return jsonResp({ error: "Invalid OpenAI API key." }, 401);
      return jsonResp({ error: `OpenAI error: ${text.slice(0, 200)}` }, 500);
    }

    // Build the sources payload to send after the stream completes
    const sources = chunks.map((c, i) => ({
      n: i + 1,
      chunk_id: c.chunk_id,
      item_id: c.item_id,
      kb_id: c.kb_id,
      item_name: c.item_name,
      kb_name: c.kb_name,
      item_url: c.item_url,
      similarity: Number(c.similarity.toFixed(3)),
    }));

    return pipeWithSources(upstream.body, sources);
  } catch (e: any) {
    console.error("chat error", e);
    return jsonResp({ error: e?.message ?? "Unknown error" }, 500);
  }
});
