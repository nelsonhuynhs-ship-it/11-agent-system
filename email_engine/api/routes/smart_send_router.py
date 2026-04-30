"""
Smart Send Router — Phase 2 Graph Migration v8.

Endpoints:
  POST /api/smart-send/preview   → build VIP email, return HTML preview + token
  POST /api/smart-send/confirm   → send VIP via Graph then bulk-send remaining

No Outlook COM required. Uses graph_sender for actual dispatch.
"""
from __future__ import annotations

import json
import logging
import secrets
import threading
import time
from datetime import date
from typing import Any

from fastapi import APIRouter, Body, HTTPException
import pandas as pd

from email_engine.senders.graph_sender import send_html_via_graph

log = logging.getLogger("smart-send-router")

router = APIRouter(prefix="/api/smart-send", tags=["smart-send"])

# In-memory token store — 10 min TTL, one-shot use
_PREVIEW_TOKENS: dict[str, float] = {}
_PREVIEW_TTL = 600  # seconds


# ── helpers ──────────────────────────────────────────────────────────────────

def _issue_preview_token() -> str:
    token = secrets.token_urlsafe(16)
    _PREVIEW_TOKENS[token] = time.time() + _PREVIEW_TTL
    now = time.time()
    for k in [k for k, exp in _PREVIEW_TOKENS.items() if exp < now]:
        _PREVIEW_TOKENS.pop(k, None)
    return token


def _consume_preview_token(token: str) -> bool:
    exp = _PREVIEW_TOKENS.pop(token, None)
    if exp is None:
        return False
    return exp >= time.time()


def _load_master_df_safe():
    try:
        from email_engine.core.rotation_helpers import load_master_df
        return load_master_df()
    except Exception as exc:
        log.error("_load_master_df_safe: %s", exc)
        return None


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/preview")
def smart_send_preview(
    body: dict = Body(default={}),
) -> dict[str, Any]:
    """Build VIP email preview + issue preview_token.

    POST /api/smart-send/preview
    Body (optional): { "markup": 20, "force": false }

    Returns:
        {
          "preview_token": str,
          "ttl_seconds": 600,
          "previewed_to": str,
          "subject": str,
          "html_body": str,      ← local HTML render (Option B — KISS)
          "first_commodity": str,
          "plan_total": int,
        }
    """
    markup = (body.get("markup") if body else None)
    if markup is None:
        markup = 20
    force = bool(body.get("force")) if body else False

    try:
        from email_engine.core.rotation_engine import build_daily_plan
        from email_engine.intelligence import builder as _builder
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f"Engine unavailable: {exc}")

    # Load today's plan (reuse rotation_router's _load_plan)
    from email_engine.api.routes.rotation_router import _load_plan
    plan = _load_plan(date.today())
    if plan is None or plan.get("skipped_reason") or force:
        try:
            plan = build_daily_plan(force_build=force)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Plan build failed: {exc}")

    by_commodity = plan.get("by_commodity", {})
    if not by_commodity:
        skip_reason = plan.get("skipped_reason") or "no eligible commodities"
        raise HTTPException(
            status_code=404,
            detail=f"Rotation skipped: {skip_reason}. Use ?force=true to override.",
        )

    # Pick first commodity's first email (rotation_engine sorts by priority)
    first_commodity = None
    sample_email = None
    for comm, info in by_commodity.items():
        emails = info.get("emails", [])
        if emails:
            first_commodity = comm
            sample_email = emails[0].strip()
            break

    if not sample_email:
        raise HTTPException(status_code=404, detail="No emails in today's plan")

    # Load master + resolve CNEE config
    df = _load_master_df_safe()
    if df is None:
        raise HTTPException(status_code=503, detail="Master contact file unavailable")

    try:
        from email_engine.core.rule_engine import resolve_config
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f"Rule engine unavailable: {exc}")

    email_col = "EMAIL" if "EMAIL" in df.columns else "CNEE_EMAIL"
    df_indexed = df.set_index(df[email_col].str.lower().str.strip())
    key = sample_email.lower()

    if key not in df_indexed.index:
        raise HTTPException(status_code=404, detail=f"CNEE {sample_email} not in master")

    row = df_indexed.loc[key]
    if isinstance(row, pd.DataFrame):
        row = row.iloc[0]

    # Build email
    config = resolve_config(row.to_dict(), int(markup))
    pol = config.get("pol", "HPH")
    destination = config.get("destination", "USLAX,USLGB")
    # destination is comma-separated string, build_email expects list
    destinations = [d.strip() for d in destination.split(",")]

    try:
        email_dict = _builder.build_email(
            cnee_email=sample_email,
            pol=pol,
            destinations=destinations,
            markup=float(markup),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Email build failed: {exc}")

    token = _issue_preview_token()
    plan_total = int(plan.get("actual_total", 0))

    # Store VIP email data keyed by token (for confirm phase — avoids re-lookup)
    _PREVIEW_TOKENS[f"_vip_{token}"] = {
        "cnee_email": sample_email,
        "pol": pol,
        "destinations": destinations,
        "markup": float(markup),
        "first_commodity": first_commodity,
        "campaign_id": f"SMART_{int(time.time())}",
    }

    return {
        "status": "previewed",
        "preview_token": token,
        "ttl_seconds": _PREVIEW_TTL,
        "previewed_to": email_dict["to"],
        "subject": email_dict["subject"],
        "html_body": email_dict.get("html_body", ""),
        "first_commodity": first_commodity,
        "plan_total": plan_total,
        "message": f"Preview ready. Confirm to send {plan_total} emails.",
    }


@router.post("/confirm")
def smart_send_confirm(
    body: dict = Body(default={}),
) -> dict[str, Any]:
    """Confirm + execute smart send batch.

    POST /api/smart-send/confirm
    Body: { "preview_token": "<token>", "markup": 20, "force": false }

    Flow:
      1. Validate preview_token (one-shot, 10 min TTL)
      2. Retrieve stored VIP email data
      3. Send VIP via Graph (no COM)
      4. Build remaining email list from today's plan, enqueue for batch send
    """
    token = (body.get("preview_token") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="preview_token required")

    if not _consume_preview_token(token):
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired preview_token. Run Smart Send preview first.",
        )

    vip_data = _PREVIEW_TOKENS.pop(f"_vip_{token}", None)
    if not vip_data:
        # Token was valid (consumed) but VIP data expired — rebuild from plan
        raise HTTPException(
            status_code=400,
            detail="VIP data expired. Run Smart Send preview again.",
        )

    cnee_email = vip_data["cnee_email"]
    pol = vip_data["pol"]
    destinations = vip_data["destinations"]
    markup = vip_data["markup"]
    first_commodity = vip_data["first_commodity"]
    campaign_id = vip_data["campaign_id"]

    try:
        from email_engine.core.rotation_engine import build_daily_plan
        from email_engine.intelligence import builder as _builder
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f"Engine unavailable: {exc}")

    force = bool(body.get("force", False))

    # Rebuild plan to get remaining emails
    from email_engine.api.routes.rotation_router import _load_plan
    plan = _load_plan(date.today())
    if plan is None or plan.get("skipped_reason") or force:
        try:
            plan = build_daily_plan(force_build=force)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Plan build failed: {exc}")

    by_commodity = plan.get("by_commodity", {})

    # Build VIP email
    try:
        email_dict = _builder.build_email(
            cnee_email=cnee_email,
            pol=pol,
            destinations=destinations,
            markup=markup,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"VIP email build failed: {exc}")

    # Send VIP via Graph (no COM)
    try:
        ok, msg_id = send_html_via_graph(
            to=email_dict["to"],
            subject=email_dict["subject"],
            html_body=email_dict["html_body"],
            save_to_sent=True,
        )
        if not ok:
            raise RuntimeError(f"Graph send returned ok=False: {msg_id}")
    except Exception as exc:
        log.error("[smart-send] VIP send failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"VIP send failed: {exc}")

    # Build remaining email list (skip VIP = first email of first commodity)
    remaining_emails = []
    found_vip = False
    for comm, info in by_commodity.items():
        emails = info.get("emails", [])
        for em in emails:
            if not found_vip and em.strip().lower() == cnee_email.lower():
                found_vip = True
                continue  # skip VIP — already sent
            remaining_emails.append(em.strip())

    # Enqueue remaining batch via background thread
    if remaining_emails:
        from email_engine.core.rule_engine import resolve_config
        from email_engine.api.routes.rotation_router import _load_master_df_safe

        def _send_remaining():
            from email_engine.web_server import _do_send_built_emails

            df = _load_master_df_safe()
            email_col = "EMAIL" if "EMAIL" in df.columns else "CNEE_EMAIL"
            df_indexed = df.set_index(df[email_col].str.lower().str.strip())

            emails_out = []
            for em in remaining_emails:
                key = em.lower().strip()
                if key not in df_indexed.index:
                    log.warning("[smart-send] skip %s — not in master", em)
                    continue
                row = df_indexed.loc[key]
                if hasattr(row, "to_dict"):
                    row_dict = row.to_dict() if hasattr(row, "iloc") else dict(row)
                else:
                    row_dict = dict(row)

                config = resolve_config(
                    row.to_dict() if hasattr(row, "to_dict") else dict(row),
                    user_markup=int(markup),
                    campaign_override=first_commodity,
                )
                try:
                    result = _builder.build_email(
                        cnee_email=em,
                        pol=config.get("pol", "HPH"),
                        destinations=[d.strip() for d in config.get("destination", "USLAX,USLGB").split(",")],
                        markup=float(markup),
                    )
                    html_body = result.get("html_body", "")
                    if not html_body or "No rates available" in html_body:
                        log.info("[smart-send] skip %s — no rates", em)
                        continue
                except Exception as exc:
                    log.warning("[smart-send] build error for %s: %s", em, exc)
                    continue

                emails_out.append({
                    "cnee_email": em,
                    "subject": result.get("subject", ""),
                    "html_body": html_body,
                    "campaign_id": campaign_id,
                    "meta_json": json.dumps({"source": "smart-send", "commodity": first_commodity}),
                })
            if emails_out:
                _do_send_built_emails(campaign_id, emails_out)
                log.info("[smart-send] batch sent %s emails", len(emails_out))
            else:
                log.warning("[smart-send] no valid emails to send in batch")

        threading.Thread(
            target=_send_remaining,
            daemon=True,
            name=f"smart-send-batch-{campaign_id}",
        ).start()
        log.info("[smart-send] enqueued %s remaining emails (campaign=%s)", len(remaining_emails), campaign_id)

    total = 1 + len(remaining_emails)
    return {
        "status": "sent",
        "vip_sent_to": email_dict["to"],
        "vip_graph_msg_id": msg_id,
        "campaign_id": campaign_id,
        "total": total,
        "sent": 1,
        "enqueued": len(remaining_emails),
        "message": f"VIP sent + {len(remaining_emails)} enqueued for batch send.",
    }