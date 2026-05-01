import logging
import os

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.api.routes import chat_router, embed_router
from app.services.cors_service import setup_cors
from app.services.supabase_service import close_supabase
from app.services.llm_services.openai_service import close_openai

# ── Logging ───────────────────────────────────────────────────────────────────
_level_name = (os.getenv("LOG_LEVEL") or "INFO").upper().strip()
_level = getattr(logging, _level_name, logging.INFO)
logging.basicConfig(level=_level)
# Quiet very chatty third-party loggers unless explicitly enabled.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

app = FastAPI(title="AI Agent API", version="1.0.0")

# ── CORS ──────────────────────────────────────────────────────────────────────
setup_cors(app)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(chat_router.router)
app.include_router(embed_router.router)


# ── Lifecycle ─────────────────────────────────────────────────────────────────
@app.on_event("shutdown")
async def shutdown_event():
    """Close async HTTP clients on shutdown."""
    await close_supabase()
    await close_openai()


# ── Root ──────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def root():
    return """
    <html>
        <title>AI Agent API</title>
        <body style="font-family: Arial; text-align:center; margin-top:50px;">
            <h1>AI Agent API - Service</h1>
            <a href="/docs" style="display:inline-block; margin-top:20px; padding:10px 20px;
               background-color:#007BFF; color:white; text-decoration:none; border-radius:5px;">
               Swagger Docs</a>
            <a href="/redoc" style="display:inline-block; margin-top:20px; padding:10px 20px;
               background-color:#007BFF; color:white; text-decoration:none; border-radius:5px;">
               ReDoc</a>
        </body>
    </html>
    """
