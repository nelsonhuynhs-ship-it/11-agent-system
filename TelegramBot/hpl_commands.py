# -*- coding: utf-8 -*-
"""
hpl_commands.py — Bot Command Handlers for HPL Integration
============================================================
Telegram Bot handlers for /track and /spot commands.
Follows GEMINI.md rules: new module, NOT modifying bot_v5.py core.

Usage in bot_v5.py:
    from hpl_commands import register_hpl_commands
    register_hpl_commands(app)  # app = telegram.ext.Application
"""
import logging
import os
import re
import sys
from typing import Optional

logger = logging.getLogger("nelson.hpl_commands")

# ── Paths ─────────────────────────────────────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ENGINE_DIR = os.path.join(os.path.dirname(_THIS_DIR), "ERP")
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, os.path.dirname(_ENGINE_DIR))


# ── Container number detection ────────────────────────────────
# HPL containers: HLXU/HLCU + 7 digits
# Generic: 4 letters + 7 digits (ISO 6346)
CONTAINER_RE = re.compile(r'^[A-Z]{4}\d{7}$')
JOB_ID_RE = re.compile(r'^(J\d{10,}|NF-\d{4}-\d{4,})$', re.IGNORECASE)


def _is_container_no(text: str) -> bool:
    """Check if text looks like a container number."""
    return bool(CONTAINER_RE.match(text.strip().upper()))


def _is_job_id(text: str) -> bool:
    """Check if text looks like a Job ID."""
    return bool(JOB_ID_RE.match(text.strip()))


# ── /track command ────────────────────────────────────────────

async def handle_track(update, context) -> None:
    """
    Handle /track command — track a container or job.

    Usage:
        /track HLXU1234567       → track single container
        /track J202505100000     → track all containers in a job
        /track NF-2026-0142      → same, with NF-format job ID
        /track add J2025... HLXU1234567 HLXU1234568  → add containers to job
    """
    try:
        args = context.args if context.args else []

        if not args:
            await update.message.reply_text(
                "Cach dung:\n"
                "  /track HLXU1234567 — theo doi 1 container\n"
                "  /track J202505100000 — theo doi ca lo hang\n"
                "  /track add <JobID> <Cont1> <Cont2> — them container vao lo"
            )
            return

        # Sub-command: /track add <job_id> <cont1> <cont2> ...
        if args[0].lower() == "add":
            await _handle_track_add(update, args[1:])
            return

        query = args[0].strip().upper()

        # Detect: container number or job ID?
        if _is_container_no(query):
            await _handle_track_container(update, query)
        elif _is_job_id(query):
            await _handle_track_job(update, query)
        else:
            await update.message.reply_text(
                f"'{query}' khong phai container number (VD: HLXU1234567) "
                f"hay Job ID (VD: J202505100000).\n"
                f"Thu lai: /track HLXU1234567"
            )

    except Exception as e:
        logger.error("[/track] Error: %s", e)
        await update.message.reply_text(f"Loi khi tra cuu tracking: {e}")


async def _handle_track_container(update, container_no: str) -> None:
    """Track a single container."""
    from ERP.intelligence.tracking_manager import (
        format_container_tracking_bot,
        track_container_hpl,
    )

    # Try to pull latest from HPL API first
    track_container_hpl(container_no)

    output = format_container_tracking_bot(container_no)
    await update.message.reply_text(output)


async def _handle_track_job(update, job_id: str) -> None:
    """Track all containers in a job."""
    from ERP.intelligence.tracking_manager import format_job_tracking_bot

    # Try to get job info from ERP reader
    job_info = _get_job_info(job_id)

    output = format_job_tracking_bot(job_id, job_info)
    await update.message.reply_text(output)


async def _handle_track_add(update, args: list) -> None:
    """Add containers to a job: /track add <job_id> <cont1> <cont2> ..."""
    if len(args) < 2:
        await update.message.reply_text(
            "Cach dung: /track add <JobID> <Container1> <Container2> ...\n"
            "Vi du: /track add J202505100000 HLXU1234567 HLXU1234568"
        )
        return

    job_id = args[0].strip()
    containers = []
    for arg in args[1:]:
        cn = arg.strip().upper()
        if _is_container_no(cn):
            containers.append({"container_no": cn, "cont_type": "40HQ"})
        else:
            await update.message.reply_text(f"'{cn}' khong phai container number hop le")
            return

    from ERP.intelligence.tracking_manager import add_containers_to_job
    result = add_containers_to_job(job_id, containers)
    await update.message.reply_text(f"OK: {result}")


def _get_job_info(job_id: str) -> dict:
    """Get basic job info from ERP reader for display context."""
    try:
        from TelegramBot.erp_reader import get_active_jobs
        jobs = get_active_jobs(limit=200)
        for j in jobs:
            if j.get("job_id", "").upper() == job_id.upper():
                return {
                    "customer": j.get("customer", ""),
                    "pol": j.get("routing", "").split("-")[0].strip() if "-" in j.get("routing", "") else "",
                    "pod": j.get("routing", "").split("-")[-1].strip() if "-" in j.get("routing", "") else "",
                    "place": j.get("routing", "").split("-")[-1].strip() if "-" in j.get("routing", "") else "",
                }
    except Exception as e:
        logger.debug("[/track] Could not load job info: %s", e)
    return {}


# ── /spot command ─────────────────────────────────────────────

async def handle_spot(update, context) -> None:
    """
    Handle /spot command — query HPL spot rates.

    Usage:
        /spot HPH LAX           → spot rate HPH to LAX (default 40HQ)
        /spot HPH LAX 20GP      → spot rate with container type
        /spot refresh           → force refresh spot cache
    """
    try:
        args = context.args if context.args else []

        if not args:
            await update.message.reply_text(
                "Cach dung:\n"
                "  /spot HPH LAX — xem Spot rate HPH -> LAX\n"
                "  /spot HPH LAX 20GP — xem theo container type\n"
                "  /spot refresh — cap nhat spot cache"
            )
            return

        # Sub-command: /spot refresh
        if args[0].lower() == "refresh":
            await _handle_spot_refresh(update)
            return

        # Parse POL/POD
        pol_raw = args[0].strip().upper()
        pod_raw = args[1].strip().upper() if len(args) > 1 else ""
        cont_type = args[2].strip().upper() if len(args) > 2 else "40HQ"

        if not pod_raw:
            await update.message.reply_text("Can nhap POD. VD: /spot HPH LAX")
            return

        # Normalize to UN/LOCODE format
        pol = _normalize_port(pol_raw)
        pod = _normalize_port(pod_raw)

        await _handle_spot_query(update, pol, pod, cont_type)

    except Exception as e:
        logger.error("[/spot] Error: %s", e)
        await update.message.reply_text(f"Loi khi tra cuu spot: {e}")


async def _handle_spot_query(update, pol: str, pod: str, cont_type: str) -> None:
    """Query and format spot rate response."""
    from ERP.intelligence.spot_cache import get_all_spots, get_spot_comparison

    spots = get_all_spots(pol, pod)

    if not spots:
        await update.message.reply_text(
            f"Chua co Spot rate cho {pol} -> {pod}\n"
            f"Thu /spot refresh de cap nhat cache"
        )
        return

    # Format output
    lines = [f"HPL Spot Rate: {pol} -> {pod}"]
    lines.append("-" * 35)

    for s in spots:
        marker = " <--" if s["cont_type"] == cont_type else ""
        lines.append(
            f"  {s['cont_type']}:  ${s['amount']:,.0f}  "
            f"(valid {s['valid_to']}){marker}"
        )

    # Compare with FAK if available
    comparison = get_spot_comparison(pol, pod, cont_type)
    if comparison.get("insight"):
        lines.append(f"\n{comparison['insight']}")

    lines.append(f"\nNguon: HPL Offers API | Cap nhat: {spots[0].get('fetched_at', '')[:16]}")
    lines.append("Luu y: Day la gia SPOT, khong phai contract rate!")

    await update.message.reply_text("\n".join(lines))


async def _handle_spot_refresh(update) -> None:
    """Force refresh spot cache."""
    from ERP.intelligence.spot_cache import refresh_spot_cache

    await update.message.reply_text("Dang cap nhat spot cache...")

    result = refresh_spot_cache()

    await update.message.reply_text(
        f"Da cap nhat: {result['total_inserted']} rates\n"
        f"Mode: {result['mode']}\n"
        f"Routes: {result['routes_checked']}\n"
        f"Errors: {len(result['errors'])}"
    )


# ── Port normalization ────────────────────────────────────────
# Nelson system uses short codes, HPL API uses UN/LOCODE

PORT_MAP = {
    # Vietnam
    "HPH": "VNHPH", "HCM": "VNSGN", "SGN": "VNSGN", "DAD": "VNDAD",
    # US West Coast
    "LAX": "USLAX", "LGB": "USLGB", "SEA": "USSEA", "OAK": "USOAK",
    # US East Coast
    "NYC": "USNYC", "ORF": "USORF", "SAV": "USSAV", "CHS": "USCHS",
    # US Gulf
    "HOU": "USHOU", "MSY": "USMSY",
    # US Inland
    "DEN": "USDEN", "ELP": "USELP", "KCK": "USKCK", "ATL": "USATL",
    "DAL": "USDAL", "CHI": "USCHI",
    # Canada
    "YVR": "CAYVR", "YTO": "CAYTO",
}


def _normalize_port(code: str) -> str:
    """Normalize short port code to UN/LOCODE format."""
    code = code.strip().upper()
    # Already in UN/LOCODE format (5 chars)?
    if len(code) == 5 and code[:2].isalpha():
        return code
    return PORT_MAP.get(code, f"US{code}" if len(code) == 3 else code)


# ── Registration ──────────────────────────────────────────────

def register_hpl_commands(app) -> None:
    """
    Register HPL commands with the Telegram bot application.

    Call this in bot_v5.py:
        from hpl_commands import register_hpl_commands
        register_hpl_commands(app)
    """
    from telegram.ext import CommandHandler

    app.add_handler(CommandHandler("track", handle_track))
    app.add_handler(CommandHandler("spot", handle_spot))

    logger.info("[HPL] Registered /track and /spot commands")
