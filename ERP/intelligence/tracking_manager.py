# -*- coding: utf-8 -*-
"""
tracking_manager.py — Container Tracking Manager
==================================================
Manages container tracking data in tracking.sqlite.
Supports manual entry, HPL T&T API polling, and webhook events.

Usage:
    from ERP.intelligence.tracking_manager import (
        add_containers_to_job, track_container,
        get_job_tracking_summary, format_job_tracking_bot,
        format_container_tracking_bot,
    )

    # Add containers to a job
    add_containers_to_job("NF-2026-0142", [
        {"container_no": "HLXU1234567", "cont_type": "40HQ"},
    ])

    # Track a specific container (manual or via API)
    track_container("HLXU1234567")

    # Get summary for Bot display
    summary = get_job_tracking_summary("NF-2026-0142")
"""
import logging
import os
import sqlite3
from datetime import datetime
from typing import Optional

import pandas as pd

logger = logging.getLogger("nelson.tracking")

# ── Paths ─────────────────────────────────────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(os.path.dirname(_THIS_DIR), "data")
TRACKING_DB = os.path.join(_DATA_DIR, "tracking.sqlite")
JOBS_MASTER = os.path.join(_DATA_DIR, "Jobs_Master.xlsx")

# ── DCSA Milestone Status Map ─────────────────────────────────
STATUS_MAP = {
    "PENDING": ("PENDING", "Cho thong tin"),
    "GTIN":    ("GTIN",    "Gate In cang di"),
    "STUF":    ("STUF",    "Da dong hang"),
    "LOAD":    ("LOAD",    "Da len tau"),
    "VD":      ("VD",      "Tau da khoi hanh"),
    "TS":      ("TS",      "Chuyen tai"),
    "VA":      ("VA",      "Tau den cang dich"),
    "DISC":    ("DISC",    "Da do hang"),
    "GTOT":    ("GTOT",    "Gate Out cang den"),
    "AVPU":    ("AVPU",    "San sang lay hang"),
    "DLVD":    ("DLVD",    "Da giao hang"),
}

# Status ordering for progress calculation
STATUS_ORDER = list(STATUS_MAP.keys())


def _get_conn() -> sqlite3.Connection:
    """Get SQLite connection with WAL mode via shared module."""
    from shared.db_connect import get_db
    return get_db(TRACKING_DB)


# ── Container CRUD ────────────────────────────────────────────

def add_containers_to_job(job_id: str, containers: list[dict],
                          pol: str = "", pod: str = "") -> str:
    """
    Add containers to a job in tracking.sqlite.

    Args:
        job_id: Job ID (e.g., "NF-2026-0142")
        containers: List of dicts with container_no and cont_type
        pol: Port of Loading
        pod: Port of Discharge

    Returns:
        Status message
    """
    conn = _get_conn()
    added = 0

    for c in containers:
        container_no = c.get("container_no", "").strip().upper()
        cont_type = c.get("cont_type", "40HQ").strip().upper()

        if not container_no:
            continue

        try:
            conn.execute("""
                INSERT OR IGNORE INTO containers
                (job_id, container_no, cont_type, pol, pod, source)
                VALUES (?, ?, ?, ?, ?, 'MANUAL')
            """, (job_id, container_no, cont_type, pol, pod))
            added += 1
        except sqlite3.IntegrityError:
            logger.info("[Track] Container %s already exists", container_no)

    conn.commit()

    # Update Jobs_Master summary columns
    _update_jobs_master_summary(conn, job_id)

    conn.close()

    msg = f"Added {added} containers to {job_id}"
    logger.info("[Track] %s", msg)
    return msg


def _update_jobs_master_summary(conn: sqlite3.Connection, job_id: str):
    """Update Cont_Count and Cont_Summary in Jobs_Master.xlsx."""
    rows = conn.execute("""
        SELECT cont_type, COUNT(*) as cnt
        FROM containers
        WHERE job_id = ?
        GROUP BY cont_type
    """, (job_id,)).fetchall()

    if not rows:
        return

    total = sum(r["cnt"] for r in rows)
    summary = ", ".join(f"{r['cnt']}x{r['cont_type']}" for r in rows)

    try:
        if not os.path.exists(JOBS_MASTER):
            return

        df = pd.read_excel(JOBS_MASTER, engine="openpyxl")

        mask = df["Job_ID"].astype(str) == job_id
        if mask.any():
            df.loc[mask, "Cont_Count"] = total
            df.loc[mask, "Cont_Summary"] = summary
            df.to_excel(JOBS_MASTER, index=False)
            logger.info("[Track] Jobs_Master updated: %s = %s", job_id, summary)

    except Exception as e:
        logger.warning("[Track] Could not update Jobs_Master: %s", e)


# ── Status Update ─────────────────────────────────────────────

def update_container_status(container_no: str, status: str,
                            vessel: str = None, voyage_no: str = None,
                            etd: str = None, eta: str = None,
                            last_event: str = None,
                            source: str = "HPL_API") -> bool:
    """
    Update the tracking status of a container.

    Args:
        container_no: Container number (e.g., "HLXU1234567")
        status: DCSA milestone code (GTIN, LOAD, VD, VA, etc.)
        vessel: Vessel name
        voyage_no: Voyage number
        etd: Estimated departure date
        eta: Estimated arrival date
        last_event: Human-readable event description
        source: Data source (HPL_API, MANUAL, WEBHOOK)
    """
    status_info = STATUS_MAP.get(status, (status, status))
    status_label = status_info[1]

    conn = _get_conn()

    # Update container record
    updates = ["status = ?", "status_label = ?",
               "last_tracked = datetime('now')", "updated_at = datetime('now')",
               "source = ?"]
    params = [status, status_label, source]

    if vessel:
        updates.append("vessel = ?")
        params.append(vessel)
    if voyage_no:
        updates.append("voyage_no = ?")
        params.append(voyage_no)
    if etd:
        updates.append("etd = ?")
        params.append(etd)
    if eta:
        updates.append("eta = ?")
        params.append(eta)
    if last_event:
        updates.append("last_event = ?")
        params.append(last_event)

    params.append(container_no.upper())

    result = conn.execute(
        f"UPDATE containers SET {', '.join(updates)} WHERE container_no = ?",
        params
    )

    # Log tracking event
    conn.execute("""
        INSERT INTO tracking_events
        (container_no, event_type, event_label, event_time, location)
        VALUES (?, ?, ?, datetime('now'), ?)
    """, (container_no.upper(), status, status_label,
          last_event or ""))

    conn.commit()

    updated = result.rowcount > 0
    if updated:
        logger.info("[Track] %s -> %s (%s)", container_no, status, status_label)
    else:
        logger.warning("[Track] Container %s not found in DB", container_no)

    conn.close()
    return updated


# ── HPL T&T API ───────────────────────────────────────────────

def track_container_hpl(container_no: str) -> Optional[dict]:
    """
    Pull latest tracking status from HPL Track & Trace API v2.

    Returns parsed tracking data dict, or None if API unavailable.
    """
    try:
        from ERP.intelligence.hpl_auth import get_auth
        import requests as req

        auth = get_auth()
        if not auth.is_configured:
            logger.info("[Track] No API key — cannot poll HPL T&T for %s",
                        container_no)
            return None

        headers = auth.headers()
        params = {
            "equipmentReference": container_no.upper(),
            "eventType": "EQUIPMENT,TRANSPORT,SHIPMENT",
        }

        resp = req.get(
            auth.get_endpoint("track"),
            headers=headers,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        events = data.get("events", [])
        if not events:
            return {"container_no": container_no, "events": [], "status": "NO_EVENTS"}

        # Find latest event
        latest = events[-1]
        event_type = latest.get("eventClassifierCode", "")
        location = latest.get("transportCall", {}).get("location", {}).get("locationName", "")

        # Update our DB
        update_container_status(
            container_no=container_no,
            status=event_type,
            vessel=latest.get("transportCall", {}).get("vessel", {}).get("vesselName"),
            voyage_no=latest.get("transportCall", {}).get("carrierVoyageNumber"),
            eta=latest.get("estimatedDeliveryDate"),
            last_event=f"{event_type} at {location}",
            source="HPL_API",
        )

        return {
            "container_no": container_no,
            "events": events,
            "latest_status": event_type,
            "latest_location": location,
        }

    except Exception as e:
        logger.error("[Track] HPL T&T API error for %s: %s", container_no, e)
        return None


# ── Webhook Handler ───────────────────────────────────────────

def handle_webhook_event(event_data: dict) -> bool:
    """
    Process a DCSA T&T webhook push event.

    Expected format (DCSA T&T v2.2):
        {
            "eventType": "EQUIPMENT",
            "eventClassifierCode": "LOAD",
            "equipmentReference": "HLXU1234567",
            "transportCall": {
                "vessel": {"vesselName": "EVER GLORY"},
                "carrierVoyageNumber": "123E"
            }
        }
    """
    try:
        container_no = event_data.get("equipmentReference", "")
        event_type = event_data.get("eventClassifierCode", "")
        vessel_name = (event_data.get("transportCall", {})
                       .get("vessel", {}).get("vesselName"))
        voyage = (event_data.get("transportCall", {})
                  .get("carrierVoyageNumber"))
        location = (event_data.get("transportCall", {})
                    .get("location", {}).get("locationName", ""))

        if not container_no or not event_type:
            logger.warning("[Webhook] Missing container_no or event_type")
            return False

        # Store raw event
        conn = _get_conn()
        conn.execute("""
            INSERT INTO tracking_events
            (container_no, event_type, event_label, event_time, location, raw_data)
            VALUES (?, ?, ?, datetime('now'), ?, ?)
        """, (container_no, event_type,
              STATUS_MAP.get(event_type, (event_type, event_type))[1],
              location, str(event_data)))
        conn.commit()
        conn.close()

        # Update container status
        update_container_status(
            container_no=container_no,
            status=event_type,
            vessel=vessel_name,
            voyage_no=voyage,
            last_event=f"{event_type} at {location}",
            source="WEBHOOK",
        )

        logger.info("[Webhook] Processed: %s -> %s", container_no, event_type)
        return True

    except Exception as e:
        logger.error("[Webhook] Error processing event: %s", e)
        return False


# ── Query Functions ───────────────────────────────────────────

def get_job_tracking_summary(job_id: str) -> list[dict]:
    """Get all containers and their status for a job."""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT container_no, cont_type, status, status_label,
               vessel, etd, eta, last_event, last_tracked, source
        FROM containers
        WHERE job_id = ?
        ORDER BY container_no
    """, (job_id,)).fetchall()
    conn.close()

    return [dict(r) for r in rows]


def get_container_detail(container_no: str) -> Optional[dict]:
    """Get full detail for a single container including event history."""
    conn = _get_conn()

    # Container info
    container = conn.execute("""
        SELECT * FROM containers WHERE container_no = ?
    """, (container_no.upper(),)).fetchone()

    if not container:
        conn.close()
        return None

    # Event history
    events = conn.execute("""
        SELECT event_type, event_label, event_time, location
        FROM tracking_events
        WHERE container_no = ?
        ORDER BY created_at ASC
    """, (container_no.upper(),)).fetchall()

    conn.close()

    return {
        "container": dict(container),
        "events": [dict(e) for e in events],
    }


def get_containers_needing_update(hours: int = 6) -> list[str]:
    """Find containers that haven't been tracked recently."""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT container_no FROM containers
        WHERE status NOT IN ('DLVD', 'AVPU')
          AND (last_tracked IS NULL
               OR last_tracked < datetime('now', ? || ' hours'))
    """, (f"-{hours}",)).fetchall()
    conn.close()
    return [r["container_no"] for r in rows]


# ── Bot Formatters ────────────────────────────────────────────

def format_job_tracking_bot(job_id: str, job_info: dict = None) -> str:
    """
    Format tracking output for Telegram Bot /track <job_id> command.

    Output:
        [box] Lo hang NF-2026-0142 -- HML | HPH -> Denver
        [ship] Tau: EVER GLORY | ETD: 22/03 | ETA: 18/04

        Containers (3/3):
          HLXU1234567  40HQ  [check] Da len tau 22/03
          HLXU1234568  40HQ  [check] Da len tau 22/03
          HLXU1234569  40HQ  [wait] Cho len tau
    """
    containers = get_job_tracking_summary(job_id)

    if not containers:
        return f"Khong tim thay container nao cho lo {job_id}"

    # Header
    customer = (job_info or {}).get("customer", "")
    pol = (job_info or {}).get("pol", "")
    pod = (job_info or {}).get("pod", "")
    place = (job_info or {}).get("place", pod)

    lines = []
    lines.append(f"Lo hang {job_id}")
    if customer or pol:
        lines.append(f"{customer} | {pol} -> {place}")

    # Vessel info (from first container with vessel data)
    vessel = next((c["vessel"] for c in containers if c.get("vessel")), None)
    etd = next((c["etd"] for c in containers if c.get("etd")), None)
    eta = next((c["eta"] for c in containers if c.get("eta")), None)

    if vessel:
        vessel_line = f"Tau: {vessel}"
        if etd:
            vessel_line += f" | ETD: {etd[:10]}"
        if eta:
            vessel_line += f" | ETA: {eta[:10]}"
        lines.append(vessel_line)

    # Container table
    total = len(containers)
    loaded = sum(1 for c in containers
                 if STATUS_ORDER.index(c.get("status", "PENDING")) >= STATUS_ORDER.index("LOAD"))

    lines.append(f"\nContainers ({loaded}/{total}):")

    alerts = []
    for c in containers:
        status = c.get("status", "PENDING")
        label = c.get("status_label", "Cho thong tin")
        icon = "[OK]" if STATUS_ORDER.index(status) >= STATUS_ORDER.index("LOAD") else "[..]"
        line = f"  {c['container_no']}  {c['cont_type']}  {icon} {label}"
        if c.get("etd"):
            line += f"  {c['etd'][:10]}"
        lines.append(line)

        if status in ("PENDING", "GTIN"):
            alerts.append(f"  {c['container_no']} chua len tau!")

    if alerts:
        lines.append(f"\n{len(alerts)} cont chua len tau:")
        lines.extend(alerts)

    if eta:
        try:
            eta_dt = datetime.strptime(eta[:10], "%Y-%m-%d")
            days_left = (eta_dt - datetime.now()).days
            if days_left > 0:
                lines.append(f"\nETA du kien: {eta[:10]} (con {days_left} ngay)")
        except ValueError:
            pass

    return "\n".join(lines)


def format_container_tracking_bot(container_no: str) -> str:
    """
    Format tracking output for Telegram Bot /track <container_no> command.

    Output:
        [box] HLXU1234567 | 40HQ
        Thuoc lo: NF-2026-0142 (HML)
        [check] Len tau: 22/03 tai HPH
        [ship] Dang tren bien -- EVER GLORY
        ETA: 18/04 tai Los Angeles
        Con ~30 ngay
    """
    detail = get_container_detail(container_no)

    if not detail:
        return f"Khong tim thay container {container_no}"

    c = detail["container"]
    events = detail["events"]

    lines = []
    lines.append(f"{c['container_no']} | {c.get('cont_type', '')}")
    lines.append(f"Thuoc lo: {c['job_id']}")

    # Current status
    status = c.get("status", "PENDING")
    label = c.get("status_label", "Cho thong tin")
    lines.append(f"Trang thai: {label}")

    if c.get("vessel"):
        lines.append(f"Tau: {c['vessel']}")

    if c.get("eta"):
        lines.append(f"ETA: {c['eta'][:10]}")
        try:
            eta_dt = datetime.strptime(c["eta"][:10], "%Y-%m-%d")
            days = (eta_dt - datetime.now()).days
            if days > 0:
                lines.append(f"Con ~{days} ngay")
        except ValueError:
            pass

    # Event timeline
    if events:
        lines.append(f"\nLich su ({len(events)} su kien):")
        for e in events[-5:]:  # Last 5 events
            time_str = e["event_time"][:16] if e.get("event_time") else ""
            loc = e.get("location", "")
            lines.append(f"  {e['event_label']} {time_str} {loc}")

    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)-5s | %(message)s")

    # Demo: add containers to a mock job
    print("=== Demo: Add containers ===")
    result = add_containers_to_job("J202505100000", [
        {"container_no": "HLXU1234567", "cont_type": "40HQ"},
        {"container_no": "HLXU1234568", "cont_type": "40HQ"},
        {"container_no": "HLXU1234569", "cont_type": "40HQ"},
    ], pol="HPH", pod="USLAX")
    print(result)

    # Demo: update status
    print("\n=== Demo: Update status ===")
    update_container_status("HLXU1234567", "LOAD",
                            vessel="EVER GLORY", voyage_no="123E",
                            etd="2026-03-22", eta="2026-04-18",
                            last_event="Loaded at HPH 22/03")
    update_container_status("HLXU1234568", "LOAD",
                            vessel="EVER GLORY", voyage_no="123E",
                            etd="2026-03-22", eta="2026-04-18",
                            last_event="Loaded at HPH 22/03")
    update_container_status("HLXU1234569", "GTIN",
                            last_event="Gate In HPH 20/03")

    # Demo: format for bot
    print("\n=== Bot Output: /track J202505100000 ===")
    job_info = {"customer": "WOODPECKER LUMBER", "pol": "HPH",
                "pod": "USLAX", "place": "Seattle"}
    output = format_job_tracking_bot("J202505100000", job_info)
    print(output)

    print("\n=== Bot Output: /track HLXU1234567 ===")
    output2 = format_container_tracking_bot("HLXU1234567")
    print(output2)
