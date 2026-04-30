"""
graph_subscription_manager.py — Microsoft Graph Mail Webhook Subscriptions
==========================================================================
Phase 1 — Graph Webhook Migration v8

Create / renew / delete Graph push subscriptions for inbox notifications.
Stores active subscription state in graph_subscriptions.db (SQLite).

Subscription lifecycle:
  - Create on startup (ensure_active)
  - Renew daily (graph_webhook_renew.py cron)
  - Delete on shutdown (graceful)
"""
from __future__ import annotations

import logging
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import requests

log = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).parent.parent  # email_engine/
_DATA_DIR = _BASE_DIR / "data"
_DATA_DIR.mkdir(exist_ok=True)
DB_PATH   = _DATA_DIR / "graph_subscriptions.db"

# Graph API
GRAPH_SUBSCRIPTIONS = "https://graph.microsoft.com/v1.0/subscriptions"

# Subscription config
SUBSCRIPTION_RESOURCE = "me/mailFolders('inbox')/messages"
NOTIFICATION_URL     = "https://laptop-no6f8ibp.tail82dc4e.ts.net/api/graph/webhook"
EXPIRATION_DAYS      = 3   # Graph max = 423 days, we use 3-day rolling window

# Default clientState — production reads from env
DEFAULT_CLIENT_STATE = "nelson-freight-graph-v8"


def _get_client_state() -> str:
    """Return webhook secret from env or fallback to default."""
    import os
    return os.environ.get("GRAPH_WEBHOOK_CLIENT_STATE", DEFAULT_CLIENT_STATE)


def _init_db() -> None:
    """Create subscriptions table if not exists."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id              TEXT PRIMARY KEY,
                client_state    TEXT NOT NULL,
                resource        TEXT NOT NULL,
                expiration_dt   TEXT NOT NULL,
                created_at      TEXT NOT NULL,
                renewed_at      TEXT
            )
        """)
        conn.commit()
    log.info("[GraphSub] DB initialized at %s", DB_PATH)


def _get_graph_token() -> str:
    """Acquire Graph access token via MSAL."""
    from email_engine.senders.graph_sender import get_token as _gt
    return _gt()


def _create_subscription() -> Optional[dict]:
    """POST a new inbox message subscription to Graph API."""
    expiration = datetime.now(timezone.utc) + timedelta(days=EXPIRATION_DAYS)
    payload = {
        "changeType":         "created",
        "notificationUrl":    NOTIFICATION_URL,
        "resource":           SUBSCRIPTION_RESOURCE,
        "expirationDateTime": expiration.isoformat().replace("+00:00", "Z"),
        "clientState":        _get_client_state(),
    }
    headers = {
        "Authorization": f"Bearer {_get_graph_token()}",
        "Content-Type":  "application/json",
    }
    resp = requests.post(GRAPH_SUBSCRIPTIONS, json=payload, headers=headers, timeout=30)
    if resp.status_code not in (200, 201):
        log.error("[GraphSub] create failed %s: %s", resp.status_code, resp.text)
        return None

    data = resp.json()
    sub_id = data.get("id")
    if not sub_id:
        log.error("[GraphSub] no subscriptionId in response: %s", data)
        return None

    exp_str = data.get("expirationDateTime", expiration.isoformat())
    log.info("[GraphSub] created subscription id=%s exp=%s", sub_id, exp_str)
    return {
        "id":           sub_id,
        "client_state": _get_client_state(),
        "resource":     SUBSCRIPTION_RESOURCE,
        "expiration":   exp_str,
    }


def _renew_subscription(sub_id: str) -> bool:
    """PATCH /subscriptions/{id} to extend expiration by EXPIRATION_DAYS."""
    new_expiry = datetime.now(timezone.utc) + timedelta(days=EXPIRATION_DAYS)
    payload = {"expirationDateTime": new_expiry.isoformat().replace("+00:00", "Z")}
    headers = {
        "Authorization": f"Bearer {_get_graph_token()}",
        "Content-Type":  "application/json",
    }
    url = f"{GRAPH_SUBSCRIPTIONS}/{sub_id}"
    resp = requests.patch(url, json=payload, headers=headers, timeout=30)
    if resp.status_code not in (200, 201):
        log.warning("[GraphSub] renew failed %s: %s", resp.status_code, resp.text)
        return False

    exp_str = resp.json().get("expirationDateTime", new_expiry.isoformat())
    log.info("[GraphSub] renewed subscription id=%s new_exp=%s", sub_id, exp_str)
    return True


def _delete_subscription(sub_id: str) -> bool:
    """DELETE /subscriptions/{id}."""
    headers = {"Authorization": f"Bearer {_get_graph_token()}"}
    url = f"{GRAPH_SUBSCRIPTIONS}/{sub_id}"
    resp = requests.delete(url, headers=headers, timeout=30)
    if resp.status_code not in (200, 204):
        log.warning("[GraphSub] delete failed %s: %s", resp.status_code, resp.text)
        return False
    log.info("[GraphSub] deleted subscription id=%s", sub_id)
    return True


def _save_subscription(sub: dict) -> None:
    """Upsert subscription into SQLite."""
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO subscriptions
              (id, client_state, resource, expiration_dt, created_at, renewed_at)
            VALUES (?, ?, ?, ?, ?,
                    (SELECT renewed_at FROM subscriptions WHERE id = ?))
        """, [sub["id"], sub["client_state"], sub["resource"],
              sub["expiration"], now, sub["id"]])
        conn.commit()


def _load_active_subscription() -> Optional[dict]:
    """Read active subscription from DB (first row, ordered by created_at desc)."""
    if not DB_PATH.exists():
        return None
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, expiration_dt FROM subscriptions ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    return {"id": row[0], "expiration": row[1]}


def _is_expired(expiration_str: str) -> bool:
    """Check if subscription expiration is in the past."""
    try:
        exp = datetime.fromisoformat(expiration_str.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) >= exp - timedelta(hours=1)  # 1h buffer
    except Exception:
        return True  # treat parse failures as expired


def ensure_active() -> Optional[dict]:
    """Ensure an active subscription exists. Create if missing or expired.

    Returns:
        Subscription dict or None on failure.
    """
    _init_db()
    sub = _load_active_subscription()
    if sub and not _is_expired(sub["expiration"]):
        log.info("[GraphSub] active subscription found: id=%s exp=%s", sub["id"], sub["expiration"])
        return sub

    log.info("[GraphSub] no active subscription — creating new")
    new_sub = _create_subscription()
    if new_sub:
        _save_subscription(new_sub)
    return new_sub


def renew_all() -> int:
    """Renew all non-expired subscriptions in DB. Returns count renewed."""
    _init_db()
    if not DB_PATH.exists():
        return 0
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, expiration_dt FROM subscriptions"
        ).fetchall()

    count = 0
    for sub_id, exp_str in rows:
        if _is_expired(exp_str):
            continue
        if _renew_subscription(sub_id):
            # Update DB with new expiration
            new_exp = datetime.now(timezone.utc) + timedelta(days=EXPIRATION_DAYS)
            conn2 = sqlite3.connect(DB_PATH)
            conn2.execute(
                "UPDATE subscriptions SET expiration_dt=? WHERE id=?",
                [new_exp.isoformat(), sub_id]
            )
            conn2.commit()
            conn2.close()
            count += 1
    log.info("[GraphSub] renew_all complete: %d renewed", count)
    return count


def cleanup() -> None:
    """Delete all subscriptions in DB and on Graph side."""
    _init_db()
    if not DB_PATH.exists():
        return
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT id FROM subscriptions").fetchall()
    for (sub_id,) in rows:
        _delete_subscription(sub_id)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM subscriptions")
        conn.commit()
    log.info("[GraphSub] cleanup done")