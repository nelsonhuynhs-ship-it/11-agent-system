# -*- coding: utf-8 -*-
"""
voice_router.py — Speech Synthesis Endpoints
=============================================
MP3 audio generation from email body or daily digest via MiniMax T2A API.
"""
from __future__ import annotations

import sys
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

router = APIRouter(prefix="/api/voice", tags=["Voice"])


def _get_email_by_id(email_id: str) -> str:
    """Fetch email body text by ID. Raises HTTPException if not found."""
    try:
        from email_engine.core.email_bulk_verifier import get_email_by_id
        email = get_email_by_id(email_id)
        if not email:
            raise HTTPException(status_code=404, detail=f"Email {email_id} not found")
        return email
    except ImportError:
        raise HTTPException(status_code=501, detail="email_bulk_verifier module not available")
    except AttributeError:
        raise HTTPException(status_code=501, detail="get_email_by_id not implemented in email_bulk_verifier")


def _get_today_digest() -> str:
    """Fetch today's digest text. Raises HTTPException if not available."""
    try:
        from email_engine.core.brief_synthesizer import get_today_digest
        digest = get_today_digest()
        if not digest:
            raise HTTPException(status_code=404, detail="No digest available today")
        return digest
    except ImportError:
        raise HTTPException(status_code=501, detail="brief_synthesizer module not available")
    except AttributeError:
        raise HTTPException(status_code=501, detail="get_today_digest not implemented in brief_synthesizer")


@router.get("/emails/{email_id}")
def get_email_audio(email_id: str) -> Response:
    """
    GET /api/voice/emails/{email_id} — MP3 audio of email body.

    Synthesizes the email body to speech using MiniMax T2A API.
    Returns audio/mpeg response.
    """
    email_body = _get_email_by_id(email_id)

    try:
        from email_engine.core.minimax.client import minimax
        mp3_bytes = minimax.speech(email_body, model="speech-2.8-hd", voice="male-qn")
        if mp3_bytes.startswith(b"[ERROR") or mp3_bytes.startswith(b"[MOCK"):
            raise HTTPException(status_code=502, detail="Speech synthesis failed")
        return Response(content=mp3_bytes, media_type="audio/mpeg")
    except ImportError:
        raise HTTPException(status_code=501, detail="minimax client not available")


@router.get("/digest")
def get_digest_audio() -> Response:
    """
    GET /api/voice/digest — MP3 audio of daily digest.

    Synthesizes today's briefing digest to speech using MiniMax T2A API.
    Returns audio/mpeg response.
    """
    digest_text = _get_today_digest()

    try:
        from email_engine.core.minimax.client import minimax
        mp3_bytes = minimax.speech(digest_text, model="speech-2.8-hd", voice="male-qn")
        if mp3_bytes.startswith(b"[ERROR") or mp3_bytes.startswith(b"[MOCK"):
            raise HTTPException(status_code=502, detail="Speech synthesis failed")
        return Response(content=mp3_bytes, media_type="audio/mpeg")
    except ImportError:
        raise HTTPException(status_code=501, detail="minimax client not available")