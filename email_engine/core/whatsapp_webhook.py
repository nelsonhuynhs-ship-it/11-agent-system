# whatsapp_webhook.py — Meta WhatsApp webhook handler
import csv, logging, os
from datetime import datetime
from pathlib import Path

log = logging.getLogger("wa-webhook")

WA_VERIFY_TOKEN = os.getenv("WA_VERIFY_TOKEN", "my_webhook_verify_token")
LOG_FILE        = Path(__file__).parent.parent / "logs" / "whatsapp_log.csv"
CNEE_V2         = Path(__file__).parent.parent / "data" / "cnee_master_v2.xlsx"

STOP_KEYWORDS = {"stop", "opt out", "unsubscribe", "remove"}


# ── Webhook GET verification ─────────────────────────────────────
def verify_webhook(mode: str, token: str, challenge: str) -> str | None:
    """Meta webhook verification. Returns challenge string if valid, None if invalid."""
    if mode == "subscribe" and token == WA_VERIFY_TOKEN:
        log.info("Webhook verified by Meta")
        return challenge
    log.warning(f"Webhook verify failed: mode={mode}, token={token}")
    return None


# ── Helpers ──────────────────────────────────────────────────────
def _log_event(phone: str, event_type: str, status: str, message_id: str = "", note: str = ""):
    exists = LOG_FILE.exists()
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["timestamp", "phone", "template", "status", "message_id", "error"])
        w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), phone, event_type, status, message_id, note])


def _update_cnee(phone: str, field: str, value):
    """Update a field in cnee_master_v2.xlsx by PHONE match."""
    if not CNEE_V2.exists():
        return
    try:
        import pandas as pd
        df = pd.read_excel(CNEE_V2)
        df.columns = df.columns.str.strip().str.upper()
        if "PHONE" not in df.columns:
            return
        mask = df["PHONE"].astype(str).str.strip().str.lstrip("+") == str(phone).strip().lstrip("+")
        if not mask.any():
            return
        df.loc[mask, field] = value
        df.to_excel(CNEE_V2, index=False)
        log.info(f"cnee_master_v2: updated {field}={value} for phone={phone}")
    except Exception as e:
        log.error(f"cnee update failed: {e}")


# ── Main webhook processor ───────────────────────────────────────
def process_webhook(payload: dict) -> int:
    """
    Process incoming Meta webhook payload.
    Returns count of events processed.
    """
    processed = 0
    entries = payload.get("entry", [])

    for entry in entries:
        for change in entry.get("changes", []):
            value = change.get("value", {})

            # Status updates (delivered, read, failed)
            for status_obj in value.get("statuses", []):
                mid   = status_obj.get("id", "")
                phone = status_obj.get("recipient_id", "")
                status = status_obj.get("status", "unknown")
                _log_event(phone, "status_update", status.upper(), message_id=mid)
                processed += 1

            # Incoming messages (replies)
            for msg in value.get("messages", []):
                phone = msg.get("from", "")
                mid   = msg.get("id", "")
                msg_type = msg.get("type", "text")
                body = ""

                if msg_type == "text":
                    body = msg.get("text", {}).get("body", "")

                log.info(f"Incoming WA from {phone}: [{msg_type}] {body[:80]}")

                # Opt-out: STOP keyword
                if body.strip().lower() in STOP_KEYWORDS:
                    _update_cnee(phone, "WHATSAPP_OK", False)
                    _log_event(phone, "reply", "OPT_OUT", message_id=mid, note=body[:100])
                    log.info(f"OPT_OUT: {phone} removed from WA list")
                else:
                    # Regular reply — update LAST_REPLY and bump LEAD_SCORE
                    _update_cnee(phone, "LAST_REPLY", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    _log_event(phone, "reply", "RECEIVED", message_id=mid, note=body[:100])

                processed += 1

    return processed
