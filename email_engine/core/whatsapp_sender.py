# whatsapp_sender.py — Meta WhatsApp Cloud API sender
import csv, logging, os, time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

log = logging.getLogger("wa-sender")

# ── Config from env ──────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass  # dotenv optional

WA_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID", "")
WA_ACCESS_TOKEN    = os.getenv("WA_ACCESS_TOKEN", "")
WA_API_VERSION     = os.getenv("WA_API_VERSION", "v21.0")

BASE_URL = f"https://graph.facebook.com/{WA_API_VERSION}"
LOG_FILE = Path(__file__).parent.parent / "logs" / "whatsapp_log.csv"
LOG_FILE.parent.mkdir(exist_ok=True)

TEMPLATE_NAMES = ("rate_update", "follow_up", "market_alert")


def is_configured() -> bool:
    return bool(WA_PHONE_NUMBER_ID and WA_ACCESS_TOKEN)


# ── Phone validation ─────────────────────────────────────────────
def verify_phone(phone: str) -> Optional[str]:
    """Normalize and validate phone. Returns E.164 string or None."""
    if not phone:
        return None
    p = str(phone).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not p.startswith("+"):
        p = "+" + p
    digits = p[1:]
    if not digits.isdigit():
        return None
    if not (7 <= len(digits) <= 15):
        return None
    return p


# ── CSV logger ───────────────────────────────────────────────────
def _log_wa(phone: str, template: str, status: str, message_id: str = "", error: str = ""):
    exists = LOG_FILE.exists()
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["timestamp", "phone", "template", "status", "message_id", "error"])
        w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), phone, template, status, message_id, error])


# ── Core sender ──────────────────────────────────────────────────
def _post_with_backoff(payload: dict, retries: int = 3) -> dict:
    """POST to Meta Graph API with exponential backoff on 429."""
    url = f"{BASE_URL}/{WA_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WA_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    delay = 1.0
    for attempt in range(retries):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            if resp.status_code == 429:
                log.warning(f"Rate limited — waiting {delay}s (attempt {attempt+1})")
                time.sleep(delay)
                delay *= 2
                continue
            return {"status_code": resp.status_code, "body": resp.json()}
        except Exception as e:
            return {"status_code": 0, "body": {}, "error": str(e)}
    return {"status_code": 429, "body": {}, "error": "Rate limit exceeded after retries"}


def send_template(to_phone: str, template_name: str, params: list = None) -> dict:
    """Send a WhatsApp template message. Returns {success, message_id, error}."""
    if not is_configured():
        return {"success": False, "message_id": "", "error": "WhatsApp not configured"}

    phone = verify_phone(to_phone)
    if not phone:
        _log_wa(to_phone, template_name, "INVALID_PHONE", error="Invalid phone number")
        return {"success": False, "message_id": "", "error": "Invalid phone number"}

    components = []
    if params:
        components = [{"type": "body", "parameters": params}]

    payload = {
        "messaging_product": "whatsapp",
        "to": phone.lstrip("+"),
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "en"},
            "components": components,
        },
    }

    result = _post_with_backoff(payload)
    body = result.get("body", {})

    if result.get("status_code") == 200 and "messages" in body:
        mid = body["messages"][0].get("id", "")
        _log_wa(phone, template_name, "SENT", message_id=mid)
        log.info(f"WA SENT -> {phone} [{template_name}] id={mid}")
        return {"success": True, "message_id": mid, "error": ""}
    else:
        err_msg = body.get("error", {}).get("message", result.get("error", "Unknown error"))
        _log_wa(phone, template_name, "FAILED", error=err_msg)
        log.error(f"WA FAIL -> {phone}: {err_msg}")
        return {"success": False, "message_id": "", "error": err_msg}


def send_text(to_phone: str, body: str) -> dict:
    """Send a free-form text message (24h session window only)."""
    if not is_configured():
        return {"success": False, "message_id": "", "error": "WhatsApp not configured"}

    phone = verify_phone(to_phone)
    if not phone:
        return {"success": False, "message_id": "", "error": "Invalid phone number"}

    payload = {
        "messaging_product": "whatsapp",
        "to": phone.lstrip("+"),
        "type": "text",
        "text": {"body": body},
    }

    result = _post_with_backoff(payload)
    body_resp = result.get("body", {})

    if result.get("status_code") == 200 and "messages" in body_resp:
        mid = body_resp["messages"][0].get("id", "")
        _log_wa(phone, "text", "SENT", message_id=mid)
        return {"success": True, "message_id": mid, "error": ""}
    else:
        err_msg = body_resp.get("error", {}).get("message", "Unknown error")
        _log_wa(phone, "text", "FAILED", error=err_msg)
        return {"success": False, "message_id": "", "error": err_msg}


def bulk_send_templates(contacts_df, template_name: str, params_fn=None) -> dict:
    """
    Bulk send template to contacts where WHATSAPP_OK=True and PHONE is set.
    params_fn(row) -> list of {type, text} params, or None.
    Respects 80msg/sec limit (0.05s delay per send).
    """
    sent = failed = 0
    errors = []

    mask = (
        contacts_df.get("WHATSAPP_OK", False).astype(str).str.upper().isin(["TRUE", "1", "YES"]) &
        contacts_df.get("PHONE", "").astype(str).str.strip().ne("") &
        contacts_df.get("PHONE", "").astype(str).str.strip().ne("nan")
    )
    eligible = contacts_df[mask]
    log.info(f"Bulk WA send: {len(eligible)} eligible contacts for [{template_name}]")

    for _, row in eligible.iterrows():
        phone = str(row.get("PHONE", "")).strip()
        params = params_fn(row) if params_fn else None
        result = send_template(phone, template_name, params)
        if result["success"]:
            sent += 1
        else:
            failed += 1
            errors.append({"phone": phone, "error": result["error"]})
        time.sleep(0.05)  # 80 msg/sec rate limit

    log.info(f"Bulk WA done: sent={sent}, failed={failed}")
    return {"sent": sent, "failed": failed, "errors": errors}
