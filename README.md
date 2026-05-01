# ai_agent_api

A small **FastAPI** service with:

- `POST /auth/token` — email/password login via **Supabase Auth REST** (returns `access_token`)
- `POST /chat` — authenticated chat endpoint (requires `Authorization: Bearer <token>`)
- `POST /embed` — embed a Supabase knowledge-base item (file or website) via RPC + Storage download

## Stack

- FastAPI + Uvicorn
- httpx (async) for both **Supabase REST** and **OpenAI REST**
- Pydantic v2 settings from `.env`
- Bearer auth using Supabase access tokens (`Authorization: Bearer ...`)

## Code Structure (high level)

- `app/api/routes/auth_router.py` — `/auth/token`
- `app/api/routes/chat_router.py` — `/chat`
- `app/api/routes/embed_router.py` — `/embed`
- `app/services/supabase_service.py` — `SupabaseService` (RPC DAL, normalized envelope)
- `app/services/user_service.py` — `UserService` (`token()`, `get_user_context()`, `get_llm_context()`)
- `app/services/llm_services/` — provider-agnostic LLM interface + factory + OpenAI REST implementation

## Environment

Required:

- `API_KEY` is **not used** (X-API-Key auth removed)
- `SUPABASE_URL`
- `SUPABASE_KEY` (anon/publishable key, sent as `apikey`)

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Quick test (curl)

1) Get token:

```bash
curl -sS -X POST http://127.0.0.1:8000/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"your-password"}'
```

2) Embed a knowledge-base item by id:

```bash
curl -sS -X POST http://127.0.0.1:8000/embed \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H 'Content-Type: application/json' \
  -d '{"id":123}'
```
