# Phase 6: Speech Voice Router

## Goal
Create `api/routers/voice_router.py` with speech synthesis endpoints.

## Working Directory: `D:/NELSON/2. Areas/Engine_test/`

## File: api/routers/voice_router.py
- `from fastapi import APIRouter, HTTPException`
- `from fastapi.responses import Response`
- `router = APIRouter(prefix="/api/voice", tags=["Voice"])`

2 endpoints:
1. `GET /emails/{email_id}` — MP3 audio of email body
   - Get email from `email_engine.core.email_bulk_verifier.get_email_by_id(email_id)`
   - Use `minimax.speech(text, model="speech-2.8-hd", voice="male-qn")`
   - Return `Response(content=mp3_bytes, media_type="audio/mpeg")`

2. `GET /digest` — MP3 audio of daily digest
   - Get from `email_engine.core.brief_synthesizer.get_today_digest()`
   - Same speech call + Response format

## Register in api/app.py after existing routers

## Acceptance
- No syntax errors
- `python -c "from api.routers.voice_router import router; print('OK')"` succeeds
