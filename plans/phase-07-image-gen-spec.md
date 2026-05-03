# Phase 7: Quote Image Generation

## Goal
Create `email_engine/core/quote_image_gen.py` using MiniMax Image-01.

## Working Directory: `D:/NELSON/2. Areas/Engine_test/`

## File: email_engine/core/quote_image_gen.py

Function: `generate_quote_sheet(quote_data: dict) -> bytes`

quote_data keys: cnee_name, route, container_type, rate_usd, incoterm, valid_until

Logic:
1. Build detailed prompt for professional freight quote sheet image
2. Call `minimax.image(prompt, model=ImageModel.IMAGE_01, size="1024x1024")`
3. Download PNG bytes from returned URL using httpx
4. Return raw PNG bytes

Imports:
- `from email_engine.core.minimax import minimax`
- `from email_engine.core.minimax.models import ImageModel`
- `import httpx`

## Acceptance
- No syntax errors
- `python -c "from email_engine.core.quote_image_gen import generate_quote_sheet; print('OK')"` succeeds
