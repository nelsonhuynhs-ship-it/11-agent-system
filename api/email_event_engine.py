# -*- coding: utf-8 -*-
"""
email_event_engine.py — Email → Shipment Sync Engine
======================================================
Reads outlook_dataset.json, matches email events to shipments in
shipment_state.json, updates stages/risks/summaries, and provides
alert detection.

Called from server.py API endpoints.

Architecture:
    outlook_dataset.json  →  [MATCH]  →  shipment_state.json
         (emails)          by HBL/BKG       (shipments)
"""

from __future__ import annotations

import json
import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent                    # api/
EMAIL_DATA_DIR = BASE_DIR / "email_data"
EMAIL_DATA_DIR.mkdir(exist_ok=True)

# Dataset sources (check webapp-local first, then original email_engine)
WEBAPP_DATASET = EMAIL_DATA_DIR / "outlook_dataset.json"
ORIGINAL_DATASET = Path(r"D:\NELSON\email_engine\outlook_dataset.json")

# Shipment state
SHIPMENT_STATE = Path(r"D:\NELSON\email_engine\shipment_state.json")

# Sync state (track what we've already processed)
SYNC_STATE_FILE = EMAIL_DATA_DIR / "sync_state.json"

# ─── Stage Precedence ─────────────────────────────────────────────────────────
STAGE_PRECEDENCE = {
    "BOOKING_CONFIRMED":   10,
    "SI_SUBMITTED":        20,
    "SI_RECEIVED":         20,
    "GATE_IN_CONFIRMED":   25,
    "DRAFT_BL_ISSUED":     30,
    "DRAFT_BL_CONFIRMED":  35,
    "HBL_ISSUED":          35,
    "LOADED":              50,
    "ATD":                 60,
    "ETA_UPDATE":          65,
    "DN_SENT":             70,
    "INVOICE_ISSUED":      80,
    "PAYMENT_CONFIRMED":   100,
    # Risk/info stages (don't advance lifecycle)
    "DELAY_NOTICE":        -1,
    "CHANGE_VESSEL":       -2,
}

# ─── Trouble Keywords ─────────────────────────────────────────────────────────
TROUBLE_KEYWORDS = [
    "delay", "roll", "custom hold", "document missing",
    "customs hold", "amendment", "rollover", "postpone",
    "short ship", "cargo damage", "container damage",
    "overweight", "seal broken", "hold",
]

# ─── Stage → Display Label ────────────────────────────────────────────────────
STAGE_LABELS = {
    "BOOKING_CONFIRMED": "Booking confirmed",
    "SI_SUBMITTED": "SI submitted",
    "SI_RECEIVED": "SI received",
    "GATE_IN_CONFIRMED": "Container gate in",
    "DRAFT_BL_ISSUED": "Draft B/L issued",
    "DRAFT_BL_CONFIRMED": "Draft B/L confirmed",
    "HBL_ISSUED": "HBL issued",
    "LOADED": "Loaded on board",
    "ATD": "Vessel departed (ATD)",
    "ETA_UPDATE": "ETA updated",
    "DN_SENT": "Debit note sent",
    "INVOICE_ISSUED": "Invoice issued",
    "PAYMENT_CONFIRMED": "Payment confirmed",
    "DELAY_NOTICE": "⚠️ Delay notice",
    "CHANGE_VESSEL": "🚨 Vessel changed",
}


# ==============================================================================
# 1. DATASET LOADING
# ==============================================================================

def load_email_dataset() -> dict:
    """Load outlook_dataset.json — check webapp-local first, then original."""
    for path in [WEBAPP_DATASET, ORIGINAL_DATASET]:
        if path.exists():
            try:
                with path.open(encoding="utf-8") as f:
                    data = json.load(f)
                log.info("Loaded email dataset from %s (%d emails)",
                         path.name, data.get("total_emails", 0))
                return data
            except Exception as e:
                log.warning("Failed to load %s: %s", path, e)
    return {"shipments": [], "customers": [], "total_emails": 0}


def load_shipment_state() -> dict:
    """Load shipment_state.json."""
    if not SHIPMENT_STATE.exists():
        return {"shipments": {}, "last_updated": ""}
    try:
        with SHIPMENT_STATE.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.error("Failed to load shipment_state.json: %s", e)
        return {"shipments": {}, "last_updated": ""}


def save_shipment_state(state: dict) -> None:
    """Write state back to shipment_state.json atomically."""
    state["last_updated"] = datetime.now().isoformat()
    tmp = SHIPMENT_STATE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    tmp.replace(SHIPMENT_STATE)


def load_sync_state() -> dict:
    """Load sync state (what emails we've already processed)."""
    if not SYNC_STATE_FILE.exists():
        return {"processed_hashes": [], "last_sync": "", "sync_count": 0}
    try:
        with SYNC_STATE_FILE.open(encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"processed_hashes": [], "last_sync": "", "sync_count": 0}


def save_sync_state(sync_state: dict) -> None:
    """Save sync state."""
    with SYNC_STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(sync_state, f, ensure_ascii=False, indent=2)


# ==============================================================================
# 2. EMAIL → SHIPMENT MATCHING
# ==============================================================================

def _email_hash(email_entry: dict) -> str:
    """Generate unique hash for an email entry to detect duplicates."""
    key = f"{email_entry.get('shipment_id','')}|{email_entry.get('timestamp','')}|{email_entry.get('sender','')}"
    return hashlib.md5(key.encode()).hexdigest()[:16]


def match_email_to_shipment(email_entry: dict, shipments: dict) -> Optional[str]:
    """
    Match an email entry from outlook_dataset.json to a shipment in
    shipment_state.json. Returns shipment_id or None.

    Matching strategy (in order of priority):
    1. Exact shipment_id match
    2. HBL match
    3. BKG match
    4. Customer + Route fuzzy match (when no ID match)
    """
    sid = email_entry.get("shipment_id", "")

    # 1. Direct ID match
    if sid and sid in shipments:
        return sid

    # 2. HBL match
    for hbl in email_entry.get("hbl", []):
        if hbl in shipments:
            return hbl
        # Check if any shipment has this HBL in its ID
        for ship_id, ship in shipments.items():
            if hbl == ship_id or hbl in str(ship.get("last_subject", "")):
                return ship_id

    # 3. BKG match
    for bkg in email_entry.get("bkg", []):
        if bkg in shipments:
            return bkg
        for ship_id, ship in shipments.items():
            if bkg in str(ship.get("last_subject", "")):
                return ship_id

    # 4. No match — could create new shipment from email
    return None


def normalize_route(route: str) -> str:
    """Normalize route string for comparison."""
    return re.sub(r'[,\s]+', ' ', route.strip().upper()).replace("  ", " ")


# ==============================================================================
# 3. STAGE MERGING (with dedup + precedence)
# ==============================================================================

def merge_stage_event(shipment: dict, stage: str, timestamp: str,
                      subject: str, sender: str) -> dict:
    """
    Merge a stage event into a shipment record.
    Uses precedence to advance stage (never goes backward).
    Returns dict of changes made.
    """
    changes = {}
    now_str = timestamp or datetime.now().isoformat()

    # Check for duplicate in stage_history
    history = shipment.setdefault("stage_history", [])
    for h in history:
        if h.get("stage") == stage and h.get("subject", "")[:40] == subject[:40]:
            return {}  # Already processed

    # Add to history
    history.append({
        "stage": stage,
        "at": now_str,
        "subject": subject[:60],
        "sender": sender,
        "source": "email",
    })

    # Check if we should advance the stage
    current_stage = shipment.get("stage", "")
    old_prec = STAGE_PRECEDENCE.get(current_stage, 0)
    new_prec = STAGE_PRECEDENCE.get(stage, 0)

    if new_prec > 0 and new_prec > old_prec:
        changes["stage_advanced"] = True
        changes["from_stage"] = current_stage
        changes["to_stage"] = stage
        shipment["stage"] = stage
        shipment["updated_at"] = now_str
        shipment["last_subject"] = subject[:80]
        shipment["last_sender"] = sender

    return changes


# ==============================================================================
# 4. TROUBLE / ALERT DETECTION
# ==============================================================================

def detect_email_alerts(email_entry: dict) -> list[dict]:
    """Detect trouble alerts from an email entry."""
    alerts = []
    text = f"{email_entry.get('email_subject', '')} {email_entry.get('sender', '')}".lower()

    for kw in TROUBLE_KEYWORDS:
        if kw in text:
            alerts.append({
                "type": "TROUBLE",
                "keyword": kw,
                "shipment_id": email_entry.get("shipment_id", ""),
                "customer": email_entry.get("customer", ""),
                "subject": email_entry.get("email_subject", "")[:60],
                "timestamp": email_entry.get("timestamp", ""),
            })

    # Check risks from dataset
    for risk in email_entry.get("risks", []):
        if isinstance(risk, str) and ":" in risk:
            level, detail = risk.split(":", 1)
            alerts.append({
                "type": f"RISK_{level}",
                "keyword": detail.strip(),
                "shipment_id": email_entry.get("shipment_id", ""),
                "customer": email_entry.get("customer", ""),
                "subject": email_entry.get("email_subject", "")[:60],
                "timestamp": email_entry.get("timestamp", ""),
            })

    return alerts


# ==============================================================================
# 5. EMAIL SUMMARY GENERATOR
# ==============================================================================

def generate_summary(shipment: dict) -> str:
    """
    Generate a concise natural-language summary of the latest email event.
    Example: "ATD confirmed – vessel departed on 16 Mar"
    """
    history = shipment.get("stage_history", [])
    if not history:
        return ""

    # Get most recent event
    latest = history[-1]
    stage = latest.get("stage", "")
    at = latest.get("at", "")
    subject = latest.get("subject", "")

    label = STAGE_LABELS.get(stage, stage)

    # Try to extract date
    date_str = ""
    if at:
        try:
            dt = datetime.fromisoformat(at.replace("Z", "+00:00").split("+")[0])
            date_str = dt.strftime("%d %b")
        except:
            date_str = at[:10]

    # Build summary
    if stage == "ATD":
        return f"ATD confirmed – vessel departed on {date_str}"
    elif stage == "DELAY_NOTICE":
        return f"⚠️ Delay notice received on {date_str}"
    elif stage == "CHANGE_VESSEL":
        return f"🚨 Vessel changed – {date_str}"
    elif stage == "PAYMENT_CONFIRMED":
        return f"✅ Payment confirmed on {date_str}"
    elif stage == "DRAFT_BL_ISSUED":
        return f"Draft B/L issued on {date_str}"
    elif stage == "DN_SENT":
        return f"Debit note sent on {date_str}"
    elif stage == "INVOICE_ISSUED":
        return f"Invoice issued on {date_str}"
    elif stage == "LOADED":
        return f"Cargo loaded on board – {date_str}"
    elif stage == "BOOKING_CONFIRMED":
        return f"Booking confirmed on {date_str}"
    else:
        return f"{label} – {date_str}" if date_str else label


# ==============================================================================
# 6. MAIN SYNC ENGINE
# ==============================================================================

def sync_email_dataset() -> dict:
    """
    Main sync function:
    1. Load outlook_dataset.json
    2. Load shipment_state.json
    3. Match emails to shipments
    4. Merge stage events (with dedup)
    5. Generate summaries & alerts
    6. Save updated state
    Returns stats dict.
    """
    log.info("=" * 50)
    log.info("Email Event Engine — Sync starting")
    log.info("=" * 50)

    # Load data
    dataset = load_email_dataset()
    state = load_shipment_state()
    sync_state = load_sync_state()
    shipments = state.get("shipments", {})

    email_entries = dataset.get("shipments", [])
    processed_hashes = set(sync_state.get("processed_hashes", []))

    stats = {
        "total_emails": len(email_entries),
        "matched": 0,
        "new_events": 0,
        "stages_advanced": 0,
        "alerts_detected": 0,
        "skipped_duplicate": 0,
        "unmatched": 0,
        "new_shipments_created": 0,
    }

    all_alerts = []

    for entry in email_entries:
        # Dedup check
        eh = _email_hash(entry)
        if eh in processed_hashes:
            stats["skipped_duplicate"] += 1
            continue

        # Match to shipment
        matched_id = match_email_to_shipment(entry, shipments)

        if matched_id:
            stats["matched"] += 1
            shipment = shipments[matched_id]

            # Merge each detected stage
            for stage in entry.get("stages", []):
                changes = merge_stage_event(
                    shipment, stage,
                    entry.get("timestamp", ""),
                    entry.get("email_subject", ""),
                    entry.get("sender", ""),
                )
                if changes:
                    stats["new_events"] += 1
                    if changes.get("stage_advanced"):
                        stats["stages_advanced"] += 1

            # Update shipment metadata from email if missing
            if not shipment.get("carrier") and entry.get("carrier"):
                shipment["carrier"] = entry["carrier"]
            if not shipment.get("routing") and entry.get("route"):
                shipment["routing"] = entry["route"]
            if not shipment.get("container") and entry.get("container_type"):
                shipment["container"] = entry["container_type"]

            # Generate summary
            shipment["email_summary"] = generate_summary(shipment)

            # Detect alerts
            alerts = detect_email_alerts(entry)
            if alerts:
                stats["alerts_detected"] += len(alerts)
                all_alerts.extend(alerts)
                shipment.setdefault("email_alerts", [])
                for a in alerts:
                    if a not in shipment["email_alerts"][-5:]:
                        shipment["email_alerts"].append(a)
                # Keep only last 10 alerts per shipment
                shipment["email_alerts"] = shipment["email_alerts"][-10:]

            # Track delay count
            delay_stages = [s for s in entry.get("stages", [])
                           if s in ("DELAY_NOTICE", "CHANGE_VESSEL")]
            if delay_stages:
                shipment["delay_count"] = shipment.get("delay_count", 0) + len(delay_stages)

        else:
            # No match — create new shipment from email if it has valid identifier
            sid = entry.get("shipment_id", "")
            if sid and sid != "UNKNOWN" and len(sid) >= 5:
                shipments[sid] = {
                    "customer": entry.get("customer", "UNKNOWN"),
                    "type": entry.get("customer_type", ""),
                    "stage": entry.get("stages", [""])[0] if entry.get("stages") else "",
                    "routing": entry.get("route", ""),
                    "carrier": entry.get("carrier", ""),
                    "container": entry.get("container_type", ""),
                    "quantity": 1,
                    "etd": "",
                    "eta": "",
                    "ata": "",
                    "selling_rate": 0,
                    "buying_rate": 0,
                    "profit": 0,
                    "profit_margin": "",
                    "delay_count": 0,
                    "stage_history": [{
                        "stage": entry.get("stages", [""])[0] if entry.get("stages") else "",
                        "at": entry.get("timestamp", datetime.now().isoformat()),
                        "subject": entry.get("email_subject", "")[:60],
                        "sender": entry.get("sender", ""),
                        "source": "email",
                    }],
                    "risks": [],
                    "email_alerts": [],
                    "created_at": entry.get("timestamp", datetime.now().isoformat()),
                    "updated_at": entry.get("timestamp", datetime.now().isoformat()),
                    "last_subject": entry.get("email_subject", "")[:80],
                    "last_sender": entry.get("sender", ""),
                    "source": "email_dataset",
                }
                shipments[sid]["email_summary"] = generate_summary(shipments[sid])
                stats["new_shipments_created"] += 1
                stats["matched"] += 1
            else:
                stats["unmatched"] += 1

        processed_hashes.add(eh)

    # Generate summaries for ALL shipments (including ones that already had data)
    for sid, ship in shipments.items():
        if "email_summary" not in ship:
            ship["email_summary"] = generate_summary(ship)

    # Save updated state
    state["shipments"] = shipments
    save_shipment_state(state)

    # Save sync state
    sync_state["processed_hashes"] = list(processed_hashes)
    sync_state["last_sync"] = datetime.now().isoformat()
    sync_state["sync_count"] = sync_state.get("sync_count", 0) + 1
    sync_state["last_stats"] = stats
    save_sync_state(sync_state)

    # Save alerts to separate file for quick access
    alerts_file = EMAIL_DATA_DIR / "active_alerts.json"
    with alerts_file.open("w", encoding="utf-8") as f:
        json.dump({
            "alerts": all_alerts[-50:],  # Keep last 50
            "generated_at": datetime.now().isoformat(),
            "total": len(all_alerts),
        }, f, ensure_ascii=False, indent=2)

    log.info("Sync complete: %s", json.dumps(stats, indent=2))
    return stats


# ==============================================================================
# 7. QUERY HELPERS (for API endpoints)
# ==============================================================================

def get_sync_status() -> dict:
    """Return sync status for the status endpoint."""
    sync_state = load_sync_state()
    return {
        "last_sync": sync_state.get("last_sync", "never"),
        "sync_count": sync_state.get("sync_count", 0),
        "last_stats": sync_state.get("last_stats", {}),
        "processed_emails": len(sync_state.get("processed_hashes", [])),
    }


def get_active_alerts() -> list[dict]:
    """Return active trouble alerts."""
    alerts_file = EMAIL_DATA_DIR / "active_alerts.json"
    if not alerts_file.exists():
        return []
    try:
        with alerts_file.open(encoding="utf-8") as f:
            data = json.load(f)
        return data.get("alerts", [])
    except:
        return []


def get_shipment_email_timeline(shipment_id: str) -> list[dict]:
    """Get email-sourced events for a specific shipment."""
    state = load_shipment_state()
    ship = state.get("shipments", {}).get(shipment_id, {})
    history = ship.get("stage_history", [])
    # Filter to email-sourced events
    return [h for h in history if h.get("source") == "email"]


# ==============================================================================
# CLI ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = sync_email_dataset()
    print(json.dumps(result, indent=2, ensure_ascii=False))
