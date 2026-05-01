"""/auth endpoints — obtain Supabase access tokens."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.auth_schema import TokenResponse, UserLogin
from app.services.user_service import get_user_service


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=TokenResponse)
async def token(body: UserLogin) -> TokenResponse:
    access_token = await get_user_service().token(body)
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(access_token=access_token)
