"""
graph_webhook_renew.py — Daily Subscription Renewal Cron
==========================================================
Phase 1 — Graph Webhook Migration v8

Run daily via Task Scheduler or cron:
  python -m email_engine.scripts.graph_webhook_renew

Action:
  1. Renew all active (non-expired) subscriptions in graph_subscriptions.db
  2. Delete + recreate any expired subscriptions
  3. Log results to logs/graph_renew.log
"""
from __future__ import annotations

import logging
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Setup logging
_BASE_DIR = Path(__file__).parent.parent.parent  # Engine_test/
_LOG_DIR  = _BASE_DIR / "email_engine" / "logs"
_LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(_LOG_DIR / "graph_renew.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("graph_renew")

DB_PATH = _BASE_DIR / "email_engine" / "data" / "graph_subscriptions.db"
EXPIRATION_DAYS = 3


def _get_graph_token():
    from email_engine.senders.graph_sender import get_token as _gt
    return _gt()


def _is_expired(expiration_str: str) -> bool:
    try:
        exp = datetime.fromisoformat(expiration_str.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) >= exp - timedelta(hours=1)
    except Exception:
        return True


def _renew(sub_id: str) -> bool:
    from email_engine.core.graph_subscription_manager import _renew_subscription
    return _renew_subscription(sub_id)


def _create_and_save() -> dict | None:
    from email_engine.core.graph_subscription_manager import _create_subscription, _save_subscription
    sub = _create_subscription()
    if sub:
        _save_subscription(sub)
    return sub


def run() -> int:
    """Renew all subscriptions. Returns count renewed."""
    if not DB_PATH.exists():
        log.warning("graph_subscriptions.db not found — nothing to renew")
        return 0

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT id, expiration_dt FROM subscriptions").fetchall()

    if not rows:
        log.info("No subscriptions in DB to renew")
        return 0

    renewed = 0
    for sub_id, exp_str in rows:
        if _is_expired(exp_str):
            log.info("Subscription %s expired — recreating", sub_id)
            new_sub = _create_and_save()
            if new_sub:
                log.info("  recreated as id=%s", new_sub["id"])
        else:
            if _renew(sub_id):
                new_exp = datetime.now(timezone.utc) + timedelta(days=EXPIRATION_DAYS)
                with sqlite3.connect(DB_PATH) as conn2:
                    conn2.execute(
                        "UPDATE subscriptions SET expiration_dt=? WHERE id=?",
                        [new_exp.isoformat(), sub_id]
                    )
                    conn2.commit()
                renewed += 1
                log.info("  renewed id=%s", sub_id)
            else:
                log.warning("  renew failed for id=%s — will retry next run", sub_id)

    log.info("graph_webhook_renew complete: %d renewed", renewed)
    return renewed


if __name__ == "__main__":
    count = run()
    sys.exit(0 if count >= 0 else 1)