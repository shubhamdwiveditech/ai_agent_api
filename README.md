# ai_agent_api

A small **FastAPI** service exposing two endpoints — `/chat` and `/embed` —
backed by **Supabase via REST** (PostgREST `/rest/v1`, no `supabase` SDK).
Chat sessions and messages are persisted; embeddings can be stored in a
`pgvector` column for retrieval-augmented workflows.

## Stack

- FastAPI + Uvicorn
- httpx (async) for both **OpenAI** and **Supabase REST**
- Pydantic v2 settings from `.env`
- Static API-key auth via `X-API-Key` header
- SSE streaming on `/chat` when `stream: true`

### 3. Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload


python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

```
