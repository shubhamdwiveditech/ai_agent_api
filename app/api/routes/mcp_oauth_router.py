"""MCP OAuth 2.1 + PKCE router for Claude.ai custom MCP connectors.

Flow
----
1.  Claude hits /mcp  →  receives 401 + WWW-Authenticate header.
2.  Claude fetches /.well-known/oauth-protected-resource
3.  Claude fetches /.well-known/oauth-authorization-server
4.  Claude POST /oauth/register  →  receives client_id
5.  Claude opens browser → GET /oauth/authorize → user sees API-key form
6.  User submits key → POST /oauth/authorize-submit → redirect to Claude with code
7.  Claude POST /oauth/token → exchanges code for Bearer token (= api key)
8.  Subsequent MCP requests carry: Authorization: Bearer <api-key>

NOTE: For step 1 to trigger OAuth discovery, the MCP SSE endpoint must return
      401 with `WWW-Authenticate: Bearer realm="<base_url>"` when no bearer token
      is present.  Wire that response in mcp_router.py or a middleware as needed.
In-memory stores are process-scoped.  For multi-instance deployments replace
_registered_clients and _pending_codes with a shared cache (e.g. Redis).
"""
from __future__ import annotations

import asyncio
import html
import uuid
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

router = APIRouter(tags=["mcp-oauth"])

_registered_clients: dict[str, str] = {}


@dataclass
class _PendingCode:
    redirect_uri: str
    state: Optional[str]
    api_key: str


_pending_codes: dict[str, _PendingCode] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


async def _expire_code(code: str, delay: float = 300.0) -> None:
    await asyncio.sleep(delay)
    _pending_codes.pop(code, None)


# ── Discovery ─────────────────────────────────────────────────────────────────


@router.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource(request: Request) -> JSONResponse:
    """RFC 9728 — Protected Resource Metadata.

    Claude.ai calls this immediately after receiving a 401 from /mcp.
    """
    base = _base_url(request)
    return JSONResponse({
        "resource": f"{base}/mcp",
        "authorization_servers": [base],
    })


@router.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server(request: Request) -> JSONResponse:
    """RFC 8414 — Authorization Server Metadata."""
    base = _base_url(request)
    return JSONResponse({
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "registration_endpoint": f"{base}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
    })


# ── Dynamic Client Registration (RFC 7591) ────────────────────────────────────


@router.post("/oauth/register")
async def oauth_register() -> JSONResponse:
    """Claude.ai registers itself as an OAuth client dynamically.

    Returns a client_id — no client_secret needed (public client + PKCE).
    """
    client_id = uuid.uuid4().hex
    _registered_clients[client_id] = client_id
    return JSONResponse({
        "client_id": client_id,
        "client_secret_expires_at": 0,
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
    })


# ── Authorization Endpoint ────────────────────────────────────────────────────


@router.get("/oauth/authorize", response_class=HTMLResponse)
async def oauth_authorize(
    redirect_uri: str,
    state: str,
    client_id: str,
    code_challenge: str,
    code_challenge_method: str = "S256",
) -> HTMLResponse:
    """Renders an API-key entry form for the user."""

    def _e(value: str) -> str:
        return html.escape(value or "")

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Connect AI Agent to Claude</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
         background:#f5f5f5;display:flex;align-items:center;
         justify-content:center;min-height:100vh}}
    .card{{background:#fff;border-radius:12px;
           box-shadow:0 4px 24px rgba(0,0,0,.1);
           padding:40px;width:100%;max-width:420px}}
    h1{{font-size:22px;margin-bottom:8px;color:#111}}
    p{{font-size:14px;color:#666;margin-bottom:28px;line-height:1.5}}
    label{{display:block;font-size:13px;font-weight:500;
           color:#333;margin-bottom:6px}}
    input[type=password]{{width:100%;padding:10px 14px;border:1px solid #ddd;
                          border-radius:8px;font-size:14px;
                          margin-bottom:20px;outline:none}}
    input[type=password]:focus{{border-color:#6366f1;
                                box-shadow:0 0 0 3px rgba(99,102,241,.15)}}
    button{{width:100%;padding:12px;background:#6366f1;color:#fff;
            border:none;border-radius:8px;font-size:15px;
            font-weight:600;cursor:pointer}}
    button:hover{{background:#4f46e5}}
    .logo{{font-size:28px;margin-bottom:16px}}
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">&#x1F916;</div>
    <h1>Connect AI Agent to Claude</h1>
    <p>Enter your API key to allow Claude to access your data and tools.</p>
    <form method="post" action="/oauth/authorize-submit">
      <input type="hidden" name="redirect_uri"   value="{_e(redirect_uri)}"/>
      <input type="hidden" name="state"          value="{_e(state)}"/>
      <input type="hidden" name="client_id"      value="{_e(client_id)}"/>
      <input type="hidden" name="code_challenge" value="{_e(code_challenge)}"/>
      <label for="api_key">API Key</label>
      <input type="password" id="api_key" name="api_key"
             placeholder="Enter your API key" required autofocus/>
      <button type="submit">Connect to Claude</button>
    </form>
  </div>
</body>
</html>"""
    return HTMLResponse(page)


@router.post("/oauth/authorize-submit")
async def oauth_authorize_submit(
    redirect_uri: str = Form(...),
    state: str = Form(""),
    client_id: str = Form(...),
    code_challenge: str = Form(...),
    api_key: str = Form(...),
) -> RedirectResponse:
    """Stores the API key against a short-lived code and redirects back to Claude."""
    code = uuid.uuid4().hex
    _pending_codes[code] = _PendingCode(
        redirect_uri=redirect_uri,
        state=state or None,
        api_key=api_key,
    )
    asyncio.create_task(_expire_code(code))

    redirect_url = f"{redirect_uri}?code={code}&state={quote(state or '', safe='')}"
    return RedirectResponse(url=redirect_url, status_code=302)


# ── Token Endpoint ────────────────────────────────────────────────────────────


@router.post("/oauth/token")
async def oauth_token(
    grant_type: str = Form(...),
    code: str = Form(...),
    redirect_uri: str = Form(""),
    client_id: str = Form(""),
    code_verifier: Optional[str] = Form(None),
) -> JSONResponse:
    """Exchanges the authorization code for a Bearer access token (= the API key).

    The returned access_token IS the user's API key, so the existing x_api_key
    check in mcp_router.py can validate it directly once that endpoint is updated
    to also accept Authorization: Bearer <token>.
    """
    if not code:
        return JSONResponse(
            {"error": "invalid_request", "error_description": "code is required"},
            status_code=400,
        )

    pending = _pending_codes.pop(code, None)
    if pending is None:
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "Code not found or expired"},
            status_code=400,
        )

    return JSONResponse({
        "access_token": pending.api_key,
        "token_type": "Bearer",
        "expires_in": 3600,
    })
