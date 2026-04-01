# -*- coding: utf-8 -*-
"""
job_service.py — Active Job Business Logic (nelson-flow)
==========================================================
Core business logic for Quote → Active Job conversion.

nelson-flow Flow 3: Quote → Active Job
  - Activate job from winning quote
  - Assign FAST_JOB_NO (column AL)
  - Assign HBL_NO (column AN)
  - Build booking email (column AK)
  - Notify via Telegram

Used by: POST /api/jobs/activate
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional


def activate_job(
    quote_data: dict,
    shipper: str = "",
    consignee: str = "",
    etd: str = "",
    volume: str = "",
    fast_job_no: str = "",
    hbl_no: str = "",
) -> dict:
    """
    Convert a quote into an active job.

    Args:
        quote_data: Quote from /api/quotes/{id} or /api/quotes/build
        shipper: Shipper name
        consignee: Consignee name
        etd: Expected departure date
        volume: Container volume (e.g. "1x40HQ")
        fast_job_no: Job number from FAST system (column AL)
        hbl_no: House B/L number (column AN)

    Returns:
        Active job record with booking email draft
    """
    now = datetime.now()
    job_id = f"JOB-{now.strftime('%y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

    # Extract pricing from quote
    carrier = quote_data.get("carrier", "")
    pol = quote_data.get("pol", "")
    pod = quote_data.get("pod", "")
    place = quote_data.get("place", pod)
    container = quote_data.get("container", "40HQ")
    selling_rate = float(quote_data.get("selling_rate", quote_data.get("sell_rate", 0)))
    buying_rate = float(quote_data.get("buying_rate", quote_data.get("buying", 0)))
    profit = selling_rate - buying_rate if selling_rate and buying_rate else 0

    # Build booking email draft (column AK in ERP)
    booking_email = build_booking_email(
        carrier=carrier,
        pol=pol,
        pod=pod,
        place=place,
        container=container,
        volume=volume,
        etd=etd,
        shipper=shipper,
        consignee=consignee,
        fast_job_no=fast_job_no,
    )

    job = {
        "job_id": job_id,
        "quote_id": quote_data.get("quote_id", ""),
        "status": "ACTIVE",
        # Parties
        "customer": quote_data.get("customer", ""),
        "shipper": shipper,
        "consignee": consignee,
        # Routing
        "carrier": carrier,
        "pol": pol,
        "pod": pod,
        "place": place,
        "container": container,
        "volume": volume,
        "etd": etd,
        # Pricing (locked at activation)
        "selling_rate": round(selling_rate, 2),
        "buying_rate": round(buying_rate, 2),
        "profit": round(profit, 2),
        "cost_breakdown": quote_data.get("cost_breakdown", []),
        # ERP columns
        "fast_job_no": fast_job_no,    # Column AL
        "hbl_no": hbl_no,              # Column AN
        "booking_email": booking_email,  # Column AK
        # Metadata
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "is_soc": quote_data.get("is_soc", False),
    }

    return job


def build_booking_email(
    carrier: str,
    pol: str,
    pod: str,
    place: str,
    container: str,
    volume: str,
    etd: str,
    shipper: str,
    consignee: str,
    fast_job_no: str = "",
) -> dict:
    """
    Build booking email draft for carrier (column AK in ERP).

    Returns dict with subject + body ready for Outlook.
    """
    routing = f"{place} ({pod})" if place and pod and place != pod else place or pod

    subject = f"Booking Request - {pol} → {routing} | {container} | ETD {etd}"

    body = f"""Dear {carrier} Team,

Please kindly arrange booking as below:

SHIPPER: {shipper}
CONSIGNEE: {consignee}
POL: {pol}
POD/PLACE: {routing}
CONTAINER: {volume or container}
ETD: {etd}
{f'JOB REF: {fast_job_no}' if fast_job_no else ''}

Please confirm space and sailing schedule.

Thank you & Best regards,
Nelson Freight Team
"""

    return {
        "subject": subject,
        "body": body.strip(),
        "to": f"booking@{carrier.lower()}.com",  # Template — user replaces
    }


def update_fast_no(job: dict, fast_job_no: str) -> dict:
    """Update FAST_JOB_NO (column AL) for an existing job."""
    job["fast_job_no"] = fast_job_no
    job["updated_at"] = datetime.now().isoformat()
    return job


def format_job_telegram(job: dict) -> str:
    """Format job notification for Telegram."""
    soc_tag = " [SOC]" if job.get("is_soc") else ""
    lines = [
        f"🚢 NEW JOB ACTIVATED",
        "━" * 25,
        f"🆔 {job['job_id']}",
        f"👤 {job['customer']}",
        f"📦 {job['carrier']}{soc_tag} | {job.get('volume', job['container'])}",
        f"🛣️ {job['pol']} → {job.get('place') or job['pod']}",
        f"📅 ETD: {job.get('etd', 'TBA')}",
        f"💰 Selling: ${job['selling_rate']:,.0f} | Profit: ${job['profit']:,.0f}",
    ]

    if job.get("fast_job_no"):
        lines.append(f"📋 FAST: {job['fast_job_no']}")
    if job.get("hbl_no"):
        lines.append(f"📄 HBL: {job['hbl_no']}")

    return "\n".join(lines)
