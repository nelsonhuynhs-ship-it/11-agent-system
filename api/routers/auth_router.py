# -*- coding: utf-8 -*-
"""
auth_router.py — Authentication Endpoints (Phase 1: API Key)
==============================================================
Phase 1: Simple API key auth for bot/erp (no user login)
Phase 2: Supabase Auth + JWT (when ready for multi-user)
"""
from __future__ import annotations

import os
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

router = APIRouter(prefix="/api/auth", tags=["Auth"])

# Phase 1: Simple API key (for bot/erp clients)
API_KEY = os.environ.get("NELSON_API_KEY", "")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)):
    """
    Verify API key if configured.
    Phase 1: Optional — if NELSON_API_KEY is set, enforce it.
    Phase 2: Replace with JWT verification.
    """
    if not API_KEY:
        return {"user": "anonymous", "role": "admin"}  # no auth configured
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return {"user": "api_client", "role": "admin"}


@router.get("/me")
async def auth_me(user=Depends(verify_api_key)):
    """Current user info (returns API key identity)."""
    return {
        "user": user,
        "auth_mode": "api_key" if API_KEY else "none",
        "note": "Phase 1 — simple API key auth. Phase 2 will add Supabase JWT.",
    }


@router.get("/status")
async def auth_status():
    """Auth system status."""
    return {
        "mode": "api_key" if API_KEY else "open",
        "api_key_configured": bool(API_KEY),
        "supabase_configured": False,  # Phase 2
        "jwt_enabled": False,          # Phase 2
    }
