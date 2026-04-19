# -*- coding: utf-8 -*-
"""
smart_compose.py — Agent A3 Smart Compose with Customer Memory  v1.0
====================================================================
Generate personalized ocean freight quote emails by combining:
  1. Per-CNEE memory (vault/cnee/{email}/memory.md) via A1's cnee_memory module
  2. Customer rules (customer_rules.json) matched by email domain
  3. Fallback email_rules.yaml template keyed on destination region

Modes:
  - MEMORY mode  : structured memory + history events exist → LLM personalizes
  - FALLBACK mode: no memory yet → use email_rules.yaml + master metadata

Usage:
    from email_engine.core.smart_compose import compose_for_cnee

    draft = compose_for_cnee("liuyumei@kukahome.com")
    # draft = {"subject": ..., "body": ..., "rationale": ...,
    #          "memory_used": True, "fallback": False,
    #          "context_summary": {...}}

Public API:
    compose_for_cnee(cnee_email, context=None) -> dict
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

import httpx

log = logging.getLogger(__name__)

# ─── Paths ────────────────────────────────────────────────────────────────────
_ONEDRIVE_EMAIL = Path("D:/OneDrive/NelsonData/email")
_ENGINE_TEST = Path(__file__).resolve().parent.parent.parent
_CUSTOMER_RULES = _ONEDRIVE_EMAIL / "customer_rules.json"
_EMAIL_RULES = _ENGINE_TEST / "email_engine" / "templates" / "email_rules.yaml"
_CNEE_MASTER_V2 = _ONEDRIVE_EMAIL / "cnee_master_v2_final.xlsx"

# ─── LLM config (reuse llm_client pattern) ────────────────────────────────────
_DEFAULT_ENDPOINT = "https://api.minimax.io/v1/text/chatcompletion_v2"
_MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M2")  # Nelson key supports M2
_MAX_TOKENS = 800
_TEMPERATURE = 0.4
_HTTP_TIMEOUT = 40  # seconds

# ─── A1 memory integration (soft import) ──────────────────────────────────────
try:
    from email_engine.core.cnee_memory import read_memory as _read_memory_real  # type: ignore
    _MEMORY_AVAILABLE = True
except Exception as _exc:  # pragma: no cover
    log.info("A1 cnee_memory module not yet available: %s", _exc)
    _MEMORY_AVAILABLE = False

    def _read_memory_real(email: str) -> dict:  # type: ignore
        return {"markdown": "", "structured": {}, "last_event_at": None}


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _safe_read_memory(email: str) -> dict:
    """Call A1's read_memory but never raise — always return shape.

    A1 actual shape (as of 2026-04-19):
        markdown_text, structured_fields, event_count, last_event_at, exists
    We normalize to the internal names we use downstream.
    """
    try:
        mem = _read_memory_real(email) or {}
    except Exception as exc:
        log.warning("cnee_memory.read_memory(%s) raised: %s", email, exc)
        mem = {}
    # Accept both A1's current keys and the legacy names (for stub compat)
    markdown = mem.get("markdown_text") or mem.get("markdown") or ""
    structured = mem.get("structured_fields") or mem.get("structured") or {}
    return {
        "markdown": markdown,
        "structured": structured,
        "last_event_at": mem.get("last_event_at"),
        "event_count": mem.get("event_count", 0),
        "exists": bool(mem.get("exists", bool(markdown))),
    }


def _load_customer_rule_for(email: str) -> Optional[dict]:
    """Return the single customer dict whose email_domains matches email domain."""
    if not _CUSTOMER_RULES.exists() or not email or "@" not in email:
        return None
    domain = email.split("@", 1)[1].lower().strip()
    try:
        data = json.loads(_CUSTOMER_RULES.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("customer_rules.json parse failed: %s", exc)
        return None

    customers = data.get("customers", {}) or {}
    for cname, crule in customers.items():
        doms = [d.lower().strip() for d in (crule.get("email_domains") or [])]
        if domain in doms:
            out = dict(crule)
            out["_customer_name"] = cname
            return out
    return None


def _lookup_master_row(email: str) -> dict:
    """Find CNEE metadata (COMPANY, PIC, CAMPAIGN_ID, DESTINATION, COMMODITY_CATEGORY)."""
    if not _CNEE_MASTER_V2.exists():
        return {}
    try:
        import pandas as pd
        df = pd.read_excel(_CNEE_MASTER_V2)
        df.columns = df.columns.str.strip().str.upper()
        if "EMAIL" not in df.columns:
            return {}
        mask = df["EMAIL"].astype(str).str.lower().str.strip() == email.lower().strip()
        hits = df[mask]
        if hits.empty:
            return {}
        r = hits.iloc[0].to_dict()
        # Normalize
        out = {}
        for k, v in r.items():
            if v is None:
                continue
            try:
                import math
                if isinstance(v, float) and math.isnan(v):
                    continue
            except Exception:
                pass
            out[k] = v
        return out
    except Exception as exc:
        log.warning("cnee_master_v2 lookup failed for %s: %s", email, exc)
        return {}


def _extract_first_name(pic_or_email: str) -> str:
    """Guess first name from PIC 'Ms Lisa Wang' or email local part."""
    if not pic_or_email:
        return "there"
    s = str(pic_or_email).strip()
    if "@" in s:
        local = s.split("@", 1)[0]
        # take letters before digits/dots
        token = re.split(r"[._\d]", local)[0]
        return token.capitalize() if token else "there"
    # drop titles
    s2 = re.sub(r"^(mr|mrs|ms|miss|mister)\.?\s+", "", s, flags=re.I)
    parts = s2.split()
    return parts[0] if parts else "there"


def _pick_template_for_destination(dest: str) -> dict:
    """Pick a fallback template from email_rules.yaml by destination code."""
    default = {
        "subject": "Asia-US Ocean Freight Update | Week {{week}} | NELSON",
        "intro": (
            "Dear {{first_name}},\n\n"
            "Please find our latest ocean freight rates — valid through end of the month."
        ),
        "cta": "Please confirm booking 7 days before ETD. Reply anytime.",
    }
    if not _EMAIL_RULES.exists():
        return default
    try:
        import yaml  # PyYAML is already used elsewhere
        data = yaml.safe_load(_EMAIL_RULES.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        log.warning("email_rules.yaml parse failed: %s", exc)
        return default

    templates = data.get("templates", []) or []
    dest_up = (dest or "").upper().strip()
    for t in templates:
        match = t.get("match", {}) or {}
        dests = [d.upper() for d in (match.get("destinations") or [])]
        if dest_up and dest_up in dests:
            return {
                "subject": t.get("subject") or default["subject"],
                "intro": t.get("intro") or default["intro"],
                "cta": t.get("cta") or default["cta"],
            }
    # First "any" template as last resort
    for t in templates:
        if "any" in (t.get("match", {}) or {}).get("destinations", []):
            return {
                "subject": t.get("subject") or default["subject"],
                "intro": t.get("intro") or default["intro"],
                "cta": t.get("cta") or default["cta"],
            }
    return default


def _render_fallback(email: str, master: dict, context: dict) -> dict:
    """Build a non-LLM template-based email when no memory exists."""
    from datetime import date
    first = _extract_first_name(master.get("PIC") or email)
    company = str(master.get("COMPANY") or master.get("CNEE_NAME") or "").strip() or "your team"
    dest = str(master.get("DESTINATION") or "").strip().upper()
    pol = str(master.get("POL") or "HPH").strip().upper()
    commodity = str(master.get("COMMODITY_CATEGORY") or master.get("CAMPAIGN_ID") or "").strip()

    tmpl = _pick_template_for_destination(dest)
    week = date.today().isocalendar()[1]
    subject = tmpl["subject"].replace("{{week}}", str(week)).replace("{{suffix}}", "NELSON")
    intro = tmpl["intro"].replace("{{first_name}}", first).replace("{{company}}", company)
    cta = tmpl["cta"]

    commodity_hint = f"\nWe have consistent sailing for {commodity.lower()} shipments." if commodity else ""
    body_parts = [
        intro.rstrip(),
        f"If {company} is planning {pol}{('→' + dest) if dest else ''} moves this month, I can share current ocean freight with recommended carriers.{commodity_hint}",
        cta.rstrip(),
        "",
        "Best regards,",
        "Nelson Huynh — Nelson Freight (NVOCC)",
    ]
    body = "\n\n".join(p for p in body_parts if p.strip()) + "\n"

    return {
        "subject": subject[:120],
        "body": body,
        "rationale": (
            "Cold prospect — chưa có memory. Dùng template "
            f"{dest or 'default'} + commodity hint '{commodity or 'n/a'}'."
        ),
        "memory_used": False,
        "fallback": True,
        "context_summary": {
            "preferred_pods": [dest] if dest else [],
            "last_intent": None,
            "events_count": 0,
            "customer_name": None,
        },
    }


# ─── LLM prompt construction ──────────────────────────────────────────────────
_SYSTEM_PROMPT = (
    "You are Nelson Huynh, owner of Nelson Freight (NVOCC). "
    "You write concise, warm, professional ocean freight quote follow-up emails "
    "to EXISTING prospects you have corresponded with before. Tone is personal — "
    "never salesy, never marketing-speak. You reference specific past interactions "
    "to show you remember. Output STRICT JSON only with keys subject, body, rationale. "
    "Subject ≤ 60 chars. Body plain text, 80-150 words, no markdown, no bullet lists. "
    "Sign off 'Best regards,\\nNelson'."
)


def _build_user_prompt(
    email: str,
    master: dict,
    memory: dict,
    customer_rule: Optional[dict],
    context: dict,
) -> str:
    structured = memory.get("structured") or {}
    history_md = (memory.get("markdown") or "").strip()
    # Keep last ~2500 chars of memory.md (roughly last few events)
    if len(history_md) > 2500:
        history_md = "…\n" + history_md[-2500:]

    preferred_pods = (
        context.get("override_pod")
        or structured.get("preferred_pods")
        or ([master.get("DESTINATION")] if master.get("DESTINATION") else [])
    )
    markup = context.get("override_markup") or structured.get("markup") or 20
    preferred_carriers = structured.get("preferred_carriers") or []
    last_intent = structured.get("last_intent")
    last_sentiment = structured.get("last_sentiment")
    volume_est = structured.get("volume_est")

    customer_block = ""
    if customer_rule:
        customer_block = (
            "EXISTING CUSTOMER MATCH (by email domain):\n"
            f"- name: {customer_rule.get('_customer_name')}\n"
            f"- type: {customer_rule.get('type')}\n"
            f"- priority: {customer_rule.get('priority')}\n"
            f"- carrier_affinity: {customer_rule.get('carrier_affinity') or []}\n"
            f"- routes: {customer_rule.get('routes') or []}\n"
            f"- notes: {customer_rule.get('notes') or ''}\n\n"
        )

    structured_block = (
        "CUSTOMER CONTEXT (from memory):\n"
        f"- email: {email}\n"
        f"- company: {master.get('COMPANY') or '—'}\n"
        f"- contact_name: {master.get('PIC') or '—'}\n"
        f"- preferred_pods: {preferred_pods}\n"
        f"- preferred_carriers: {preferred_carriers}\n"
        f"- typical_markup_usd: {markup}\n"
        f"- last_intent: {last_intent}\n"
        f"- last_sentiment: {last_sentiment}\n"
        f"- volume_est: {volume_est}\n"
        f"- last_event_at: {memory.get('last_event_at')}\n\n"
    )

    history_block = (
        "HISTORY EXCERPT (memory.md tail):\n"
        f"{history_md if history_md else '(no events logged yet)'}\n\n"
    )

    task_block = (
        "TASK:\n"
        "Write a short follow-up email (80-150 words) to this prospect.\n"
        "Rules:\n"
        " 1. Greet by first name from contact_name.\n"
        " 2. Reference ONE specific past interaction from the history (intent, carrier, POD, or sentiment).\n"
        " 3. Mention the preferred POD explicitly.\n"
        " 4. Offer to share updated ocean freight rates. Do NOT quote numbers.\n"
        " 5. Ask one light question to invite a reply.\n"
        " 6. Sign off 'Best regards,\\nNelson'.\n"
        " 7. Rationale (<=200 chars) explains WHY you wrote it that way (cho Nelson review).\n\n"
        "Return JSON: {\"subject\": \"...\", \"body\": \"...\", \"rationale\": \"...\"}"
    )

    return customer_block + structured_block + history_block + task_block


def _call_llm(user_prompt: str) -> Optional[dict]:
    """Call MiniMax chat completion. Returns parsed JSON dict or None."""
    api_key = os.environ.get("MINIMAX_API_KEY")
    endpoint = os.environ.get("MINIMAX_API_URL", _DEFAULT_ENDPOINT)
    if not api_key:
        log.info("smart_compose: MINIMAX_API_KEY not set — skipping LLM call")
        return None

    payload = {
        "model": _MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": _TEMPERATURE,
        "max_tokens": _MAX_TOKENS,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            resp = client.post(endpoint, json=payload, headers=headers)
            resp.raise_for_status()
        data = resp.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(l for l in lines if not l.startswith("```")).strip()
        return json.loads(content)
    except httpx.HTTPStatusError as exc:
        log.warning("smart_compose LLM HTTP %s: %s",
                    exc.response.status_code, exc.response.text[:200])
    except json.JSONDecodeError as exc:
        log.warning("smart_compose LLM returned non-JSON: %s", exc)
    except Exception as exc:
        log.warning("smart_compose LLM error: %s", exc)
    return None


# ─── Public API ───────────────────────────────────────────────────────────────
def compose_for_cnee(cnee_email: str, context: Optional[dict] = None) -> dict:
    """
    Generate a personalized email draft for a CNEE.

    Args:
        cnee_email: prospect email address
        context: optional dict with keys:
            - override_pod: list[str]   (overrides memory's preferred_pods)
            - override_markup: int      (overrides memory markup)

    Returns:
        dict with keys:
            subject, body, rationale, memory_used (bool), fallback (bool),
            context_summary (dict), optionally error_note (str)
    """
    context = context or {}
    cnee_email = (cnee_email or "").strip()
    if not cnee_email or "@" not in cnee_email:
        return {
            "subject": "",
            "body": "",
            "rationale": "Invalid email address.",
            "memory_used": False,
            "fallback": True,
            "context_summary": {},
            "error_note": "invalid_email",
        }

    master = _lookup_master_row(cnee_email)
    memory = _safe_read_memory(cnee_email)
    customer_rule = _load_customer_rule_for(cnee_email)

    has_memory = bool(
        memory.get("exists")
        or (memory.get("markdown") or "").strip()
        or (memory.get("structured") or {})
    )

    # ─── Fallback path: no memory → template ──────────────────────────────────
    if not has_memory:
        draft = _render_fallback(cnee_email, master, context)
        if customer_rule:
            draft["context_summary"]["customer_name"] = customer_rule.get("_customer_name")
        return draft

    # ─── Memory path: build LLM prompt ────────────────────────────────────────
    user_prompt = _build_user_prompt(cnee_email, master, memory, customer_rule, context)
    llm_out = _call_llm(user_prompt)

    if llm_out and isinstance(llm_out, dict) and llm_out.get("subject") and llm_out.get("body"):
        structured = memory.get("structured") or {}
        events_count = memory.get("event_count") or 0
        if not events_count:
            md = memory.get("markdown") or ""
            if md:
                events_count = md.count("\n## ") or md.count("\n- ")
        return {
            "subject": str(llm_out["subject"])[:120],
            "body": str(llm_out["body"]).strip() + "\n",
            "rationale": str(llm_out.get("rationale") or "LLM personalized from memory."),
            "memory_used": True,
            "fallback": False,
            "context_summary": {
                "preferred_pods": structured.get("preferred_pods") or [],
                "preferred_carriers": structured.get("preferred_carriers") or [],
                "last_intent": structured.get("last_intent"),
                "last_sentiment": structured.get("last_sentiment"),
                "events_count": events_count,
                "customer_name": (customer_rule or {}).get("_customer_name"),
                "last_event_at": str(memory.get("last_event_at") or ""),
            },
        }

    # LLM call failed → fallback with note
    draft = _render_fallback(cnee_email, master, context)
    draft["error_note"] = "llm_unavailable_used_template"
    draft["rationale"] = (draft.get("rationale") or "") + " (LLM không khả dụng, dùng template.)"
    return draft


# ─── Helpers exposed for web_server ───────────────────────────────────────────
def body_text_to_html(body: str) -> str:
    """Minimal plain-text → HTML: wrap paragraphs in <p>."""
    if not body:
        return ""
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    return "\n".join(f"<p style='margin:0 0 12px 0'>{_html_escape(p).replace(chr(10), '<br>')}</p>" for p in paras)


def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


__all__ = ["compose_for_cnee", "body_text_to_html"]
