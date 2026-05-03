# -*- coding: utf-8 -*-
"""attachment_vision.py — OCR via MiniMax VL-02 for invoice/BL/packing list images."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from email_engine.core.minimax import minimax
from email_engine.core.minimax.models import VLModel
from email_engine.core.minimax.policy_loader import build_system_prompt

log = logging.getLogger(__name__)


def _vision(image_path: str, prompt: str) -> str:
    return minimax.vision(image_path, prompt, model=VLModel.VL_02)


def _parse(response: str, keys: list[str]) -> dict:
    """Extract JSON from VL response, falling back to partial dict on parse error."""
    try:
        data = json.loads(response)
        return {k: data.get(k) for k in keys}
    except (json.JSONDecodeError, TypeError):
        result = {}
        for key in keys:
            parts = response.split(key)
            if len(parts) > 1:
                val = parts[1].strip().split("\n")[0].strip(":. ")
                result[key] = val
            else:
                result[key] = None
        return result


def extract_invoice(image_path: str) -> dict:
    prompt = (
        "Extract invoice data from this image. Return a JSON object with exactly these keys: "
        "invoice_number, date, amount, currency, company_name, items (array of objects with description/quantity/unit_price/total). "
        "If a field is not found, use null. Output only valid JSON."
    )
    system = build_system_prompt("invoice_ocr")
    raw = minimax.vision(image_path, prompt, model=VLModel.VL_02)
    return _parse(raw, ["invoice_number", "date", "amount", "currency", "company_name", "items"])


def extract_bill_of_lading(image_path: str) -> dict:
    prompt = (
        "Extract bill of lading data from this image. Return a JSON object with exactly these keys: "
        "bl_number, shipper, consignee, container_numbers (array), pol, pod, etd, eta. "
        "If a field is not found, use null. Output only valid JSON."
    )
    system = build_system_prompt("bill_of_lading_ocr")
    raw = minimax.vision(image_path, prompt, model=VLModel.VL_02)
    return _parse(raw, ["bl_number", "shipper", "consignee", "container_numbers", "pol", "pod", "etd", "eta"])


def extract_packing_list(image_path: str) -> dict:
    prompt = (
        "Extract packing list data from this image. Return a JSON object with exactly these keys: "
        "cbm, gross_weight_kg, carton_count, items (array of objects with description/quantity/weight/dimensions). "
        "If a field is not found, use null. Output only valid JSON."
    )
    system = build_system_prompt("packing_list_ocr")
    raw = minimax.vision(image_path, prompt, model=VLModel.VL_02)
    return _parse(raw, ["cbm", "gross_weight_kg", "carton_count", "items"])