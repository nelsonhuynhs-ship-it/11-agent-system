# Phase 5: Attachment Vision

## Goal
Create `email_engine/core/attachment_vision.py` using MiniMax VL-02 for OCR.

## Working Directory: `D:/NELSON/2. Areas/Engine_test/`

## File: email_engine/core/attachment_vision.py

3 functions:
1. `extract_invoice(image_path) -> dict` — invoice_number, date, amount, currency, company_name, items
2. `extract_bill_of_lading(image_path) -> dict` — bl_number, shipper, consignee, container_numbers, pol, pod, etd, eta  
3. `extract_packing_list(image_path) -> dict` — cbm, gross_weight_kg, carton_count, items

All use:
- `from email_engine.core.minimax import minimax`
- `from email_engine.core.minimax.models import VLModel`
- `from email_engine.core.minimax.policy_loader import build_system_prompt`
- `minimax.vision(image_path, prompt, model=VLModel.VL_02)`

## Acceptance
- No syntax errors
- `python -c "from email_engine.core.attachment_vision import extract_invoice, extract_bill_of_lading, extract_packing_list; print('OK')"` succeeds
