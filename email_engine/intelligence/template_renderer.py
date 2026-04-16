# -*- coding: utf-8 -*-
"""
template_renderer.py — Simple {{token}} substitution with HTML escape + nested lookup.

Public API
----------
render_text(template_str, tokens) -> str
    Replace {{key}} or {{dot.path}} with tokens[...], escape HTML by default.
    Keys ending in '_html' or '_raw' are NOT escaped (allow pre-rendered HTML).

render_email(template, tokens) -> dict
    Build a full email dict: {subject, html_body, intro_html, cta_html}.
    `template` is the dict returned by template_selector.match().
"""
from __future__ import annotations

import html as _html
import logging
import re
from typing import Any

log = logging.getLogger("template_renderer")

# {{ key }} or {{profile.first_name}} — non-greedy, allow spaces
_TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\}\}")

# Default fallbacks per token name (when key missing or blank)
_DEFAULTS = {
    "first_name": "Team",
    "company": "your team",
    "typical_pol": "HPH",
    "typical_dest": "USLAX",
    "default_intro": "Asia-US ocean freight weekly update.",
    "suffix": "NELSON",
}


def _dig(tokens: dict, path: str) -> Any:
    """Dotted-path lookup in a dict. Returns None if missing."""
    if not tokens or not path:
        return None
    parts = path.split(".")
    cur: Any = tokens
    for p in parts:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return None
    return cur


def _to_str(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, float):
        # Avoid "1234.0" noise — render integers as integers
        if val.is_integer():
            return str(int(val))
        return f"{val:.2f}"
    return str(val)


def render_text(template_str: str, tokens: dict | None) -> str:
    """
    Replace {{token}} placeholders in `template_str` with values from `tokens`.

    Rules:
    - Missing key → fallback from `_DEFAULTS` or empty string (logs debug).
    - Keys ending in '_html' or '_raw' → NOT escaped.
    - All other values → HTML-escape before insertion.
    - Nested keys supported via dot: {{profile.first_name}}.
    """
    if not template_str:
        return ""
    tokens = tokens or {}

    def _replace(m: re.Match) -> str:
        key = m.group(1)
        last = key.split(".")[-1]
        val = _dig(tokens, key)

        if val is None or (isinstance(val, str) and val.strip() == ""):
            # fallback
            if last in _DEFAULTS:
                val = _DEFAULTS[last]
            else:
                log.debug("[render] missing token: %s", key)
                val = ""

        s = _to_str(val)
        # '*_html' / '*_raw' → bypass escape (pre-rendered HTML allowed)
        if last.endswith("_html") or last.endswith("_raw"):
            return s
        return _html.escape(s, quote=True)

    return _TOKEN_RE.sub(_replace, template_str)


def _newlines_to_html(text: str) -> str:
    """Convert '\\n\\n' → paragraph breaks, single '\\n' → <br>. Input is already HTML-escaped."""
    if not text:
        return ""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return "".join(
        f"<p style='margin:6px 0;line-height:1.5;'>{p.replace(chr(10), '<br>')}</p>"
        for p in paragraphs
    )


def render_email(template: dict, tokens: dict | None) -> dict:
    """
    Render a full email from a template dict.

    Args:
        template: {id, subject, intro, cta, ...} (from template_selector.match)
        tokens:   dict of substitution values

    Returns:
        {
            subject:    rendered subject line,
            intro_html: rendered intro as HTML,
            cta_html:   rendered CTA as HTML,
            html_body:  intro + rate_table + cta + signature,
            template_id: source template id,
        }
    """
    tokens = dict(tokens or {})
    subject = render_text(template.get("subject", ""), tokens)
    intro_rendered = render_text(template.get("intro", ""), tokens)
    cta_rendered = render_text(template.get("cta", ""), tokens)

    intro_html = _newlines_to_html(intro_rendered)
    cta_html = _newlines_to_html(cta_rendered)

    rate_table_html = str(tokens.get("rate_table_html", "") or "")
    signature_html = str(tokens.get("signature_html", "") or "")
    if not signature_html:
        # Plain-text signature fallback (HTML-escape safe)
        sig = tokens.get("signature", "")
        if sig:
            signature_html = _newlines_to_html(_html.escape(str(sig), quote=True))

    body_parts = [
        "<div style='font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#1f2937;'>",
        intro_html,
        rate_table_html,
        cta_html,
    ]
    if signature_html:
        body_parts.append(
            "<hr style='border:none;border-top:1px solid #e5e7eb;margin:16px 0;'>"
        )
        body_parts.append(signature_html)
    body_parts.append("</div>")
    html_body = "\n".join(p for p in body_parts if p)

    return {
        "subject": subject,
        "intro_html": intro_html,
        "cta_html": cta_html,
        "html_body": html_body,
        "template_id": template.get("id", "unknown"),
    }
