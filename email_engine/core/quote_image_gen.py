# -*- coding: utf-8 -*-
"""Quote sheet image generation via MiniMax Image-01."""

from __future__ import annotations

import httpx

from email_engine.core.minimax import minimax
from email_engine.core.minimax.models import ImageModel


def generate_quote_sheet(quote_data: dict) -> bytes:
    """Generate a professional freight quote sheet image.

    Args:
        quote_data: Dict with keys cnee_name, route, container_type,
                    rate_usd, incoterm, valid_until.

    Returns:
        Raw PNG bytes of the generated quote sheet.
    """
    cnee = quote_data.get("cnee_name", "N/A")
    route = quote_data.get("route", "N/A")
    container = quote_data.get("container_type", "40HQ")
    rate = quote_data.get("rate_usd", "N/A")
    incoterm = quote_data.get("incoterm", "N/A")
    valid = quote_data.get("valid_until", "N/A")

    prompt = (
        f"Professional freight quote sheet for {cnee}. "
        f"Route: {route}. Container: {container}. "
        f"Rate: USD {rate}. Incoterm: {incoterm}. "
        f"Valid until: {valid}. "
        f"Clean corporate layout, freight forwarding branding, "
        f"clear typography, export documentation style."
    )

    url = minimax.image(prompt=prompt, model=ImageModel.IMAGE_01, size="1024x1024")

    if url.startswith("[ERROR]") or url.startswith("[MOCK"):
        raise RuntimeError(f"Image generation failed: {url}")

    resp = httpx.get(url, timeout=120)
    resp.raise_for_status()
    return resp.content