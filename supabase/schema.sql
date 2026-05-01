-- Supabase schema for ai_agent_api
-- Run in the Supabase SQL editor (or psql) once per project.

-- pgvector for embeddings (1536 dims for text-embedding-3-small)
create extension if not exists vector;
create extension if not exists "pgcrypto"; -- for gen_random_uuid()

-- ----------------------------------------------------------------- chat
create table if not exists public.chat_sessions (
    id              uuid primary key default gen_random_uuid(),
    user_id         text,
    system_prompt   text,
    created_at      timestamptz not null default now()
);

create index if not exists chat_sessions_user_id_idx
    on public.chat_sessions (user_id);

create table if not exists public.chat_messages (
    id           uuid primary key default gen_random_uuid(),
    session_id   uuid not null references public.chat_sessions(id) on delete cascade,
    role         text not null check (role in ('system','user','assistant')),
    content      text not null,
    model        text,
    created_at   timestamptz not null default now()
);

create index if not exists chat_messages_session_id_idx
    on public.chat_messages (session_id, created_at);

-- ------------------------------------------------------------ embeddings
create table if not exists public.embeddings (
    id          uuid primary key default gen_random_uuid(),
    namespace   text,
    content     text not null,
    embedding   vector(1536),
    metadata    jsonb,
    model       text,
    created_at  timestamptz not null default now()
);

create index if not exists embeddings_namespace_idx
    on public.embeddings (namespace);

-- Approximate-NN index (build after some data is loaded)
-- create index on public.embeddings using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- Optional: similarity-search RPC for RAG (callable via /rest/v1/rpc/match_embeddings)
create or replace function public.match_embeddings(
    query_embedding vector(1536),
    match_count int default 5,
    filter_namespace text default null
) returns table (
    id uuid,
    content text,
    metadata jsonb,
    similarity float
)
language sql stable as $$
    select
        e.id,
        e.content,
        e.metadata,
        1 - (e.embedding <=> query_embedding) as similarity
    from public.embeddings e
    where filter_namespace is null or e.namespace = filter_namespace
    order by e.embedding <=> query_embedding
    limit match_count;
$$;

-- Note: tables are created in `public` schema with no RLS so the
-- service_role key (used by the API) can read/write directly.
-- Add RLS + policies before exposing through anon key.
