# Phase 8: Testing + Monitoring — Token Dashboard + Tests

## Goal
Create token admin router + 3 test files.

## Working Directory: `D:/NELSON/2. Areas/Engine_test/`

## Files to Create

### 1. api/routers/admin_router.py
```python
# -*- coding: utf-8 -*-
"""admin_router.py — Token usage monitoring endpoints."""
from __future__ import annotations
import os, sys
from fastapi import APIRouter
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

router = APIRouter(prefix="/api/admin", tags=["Admin"])

@router.get("/token-usage")
def token_usage_current():
    """Return current in-process token usage stats."""
    from email_engine.core.minimax.token_tracker import get_usage
    return {"date": str(date.today()), "usage": get_usage()}

@router.get("/token-usage/history")
def token_usage_history():
    """Return historical token usage from parquet store."""
    from pathlib import Path
    import pandas as pd
    token_file = Path("D:/OneDrive/NelsonData/email/token_usage.parquet")
    if not token_file.exists():
        return {"date": str(date.today()), "history": [], "total": 0}
    df = pd.read_parquet(token_file)
    df = df[df["date"] >= str(date.today().replace(day=1))]  # current month
    return {"date": str(date.today()), "history": df.to_dict("records"), "total": len(df)}
```

### 2. tests/test_minimax_client.py
Test file for minimax client. Use MOCK mode (no API key needed).
```python
# -*- coding: utf-8 -*-
import pytest
from email_engine.core.minimax import minimax, TextModel, VLModel, ImageModel

def test_text_returns_string():
    result = minimax.text("say hello")
    assert isinstance(result, str)
    assert len(result) > 0

def test_vision_returns_string():
    # Test mock path (no real image needed for MOCK mode)
    result = minimax.vision("/fake/path.jpg", "describe this")
    assert isinstance(result, str)

def test_image_returns_string():
    result = minimax.image("a blue square")
    assert isinstance(result, str)

def test_speech_returns_bytes():
    result = minimax.speech("hello world")
    assert isinstance(result, bytes)

def test_get_usage():
    usage = minimax.get_usage()
    assert isinstance(usage, dict)

def test_extract_backward_compat():
    from email_engine.core.minimax import extract
    result = extract("Booking confirmed for HPL2604001")
    assert isinstance(result, str)
```

### 3. tests/test_policy_loader.py
```python
# -*- coding: utf-8 -*-
import pytest
from email_engine.core.minimax.policy_loader import get_schema, build_system_prompt

def test_get_schema_returns_dict():
    schema = get_schema()
    assert isinstance(schema, dict)
    assert schema["company"]["name"] == "Nelson Freight"

def test_build_system_prompt_returns_string():
    prompt = build_system_prompt("summarize_email")
    assert isinstance(prompt, str)
    assert "Nelson Freight" in prompt
    assert len(prompt) > 100

def test_policy_schema_has_required_keys():
    schema = get_schema()
    assert "company" in schema
    assert "services" in schema
    assert "campaigns" in schema
    assert "carriers" in schema
    assert "email_policy" in schema
    assert "intent_mapping" in schema
```

### 4. tests/test_ai_email.py
```python
# -*- coding: utf-8 -*-
import pytest
from email_engine.core.ai_email import summarize_email, draft_reply, suggest_next_sentence

def test_summarize_email_returns_dict():
    result = summarize_email("Hello, I need a quote for shipping to USA", "test@example.com")
    assert isinstance(result, dict)

def test_draft_reply_returns_string():
    incoming = {"subject": "Quote?", "body": "Please quote 40HQ to LA", "sender": "test@example.com"}
    cnee = {"name": "ABC Corp", "campaign": "FURNITURE", "preferred_pods": ["USLAX"], "preferred_carriers": ["MSC"]}
    result = draft_reply(incoming, cnee)
    assert isinstance(result, str)
    assert len(result) > 0

def test_suggest_next_sentence_returns_string():
    result = suggest_next_sentence(["Hello", "I need shipping"], "Thank you for your inquiry")
    assert isinstance(result, str)
```

## Important
- admin_router.py needs to be registered in api/app.py (add import + include_router)
- Tests should pass even without real API key (MOCK mode)
- Keep existing tests unchanged

## Acceptance
- `python -m pytest tests/test_minimax_client.py tests/test_policy_loader.py tests/test_ai_email.py -v` passes (or at least no import errors)
