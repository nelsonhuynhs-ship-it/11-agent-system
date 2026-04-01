"""
Reply Analyzer — Cross-reference sales replies with Panjiva data
================================================================
Generates enriched context for Nelson's dashboard.
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def enrich_reply(reply_record: dict, cnee_master_path: Path) -> dict:
    """
    Given a sales_reply record, lookup customer in cnee_master.xlsx.
    Returns enriched dict with Panjiva context + recommendation text.

    Parameters
    ----------
    reply_record     : dict from sales_replies table
    cnee_master_path : Path to cnee_master.xlsx (Panjiva data)

    Returns
    -------
    dict — original record + panjiva_* fields + recommendation
    """
    try:
        import pandas as pd
    except ImportError:
        log.error("pandas not installed. Run: pip install pandas openpyxl")
        return {**reply_record, 'recommendation': 'Install pandas to enrich.'}

    customer = (reply_record.get('customer_name') or '').upper().strip()
    intent   = reply_record.get('intent', 'UNKNOWN')

    # Lookup in cnee_master
    panjiva_context: dict = {}
    if cnee_master_path.exists() and customer:
        try:
            df = pd.read_excel(cnee_master_path)
            df['COMPANY_UPPER'] = df['COMPANY'].astype(str).str.upper().str.strip()
            match = df[df['COMPANY_UPPER'] == customer]

            if not match.empty:
                row = match.iloc[0]
                panjiva_context = {
                    'vol_month':    row.get('TOTAL_SHIPMENT', 0),
                    'carrier':      row.get('CARRIER', ''),
                    'destination':  row.get('DESTINATION', ''),
                    'already_sent': row.get('ALREADY_SENT', 'N'),
                }
        except Exception as e:
            log.warning("Could not read cnee_master: %s", e)

    # Recommendation logic
    carrier_note = (
        f"Đang dùng {panjiva_context.get('carrier', '')} — cơ hội chuyển sang HPL."
        if panjiva_context.get('carrier') else ''
    )
    dest_note = panjiva_context.get('destination', 'họ đang dùng')
    vol_note  = panjiva_context.get('vol_month', '?')

    rec_map = {
        'HOT': (
            f"CALL NOW — {customer} đang quan tâm. {carrier_note}"
        ),
        'WARM': (
            f"Email hôm nay — gửi HPL schedule tuyến {dest_note}."
        ),
        'PRICE_FIGHT': (
            f"Kiểm tra SC — {customer} đang so sánh giá. "
            f"Volume: {vol_note} cont/tháng — đáng chase."
        ),
        'TIMING':       "Schedule follow-up sau 30 ngày.",
        'WRONG_PERSON': "Update contact trong contact_master.xlsx — tìm đúng người.",
        'REFERRAL':     "Email ngay người được giới thiệu — warm lead.",
        'NEGATIVE':     "Mark UNSUBSCRIBE trong cnee_master.",
        'AUTO_REPLY':   "Chờ họ về, kiểm tra replacement contact.",
    }

    enriched = {
        **reply_record,
        **{f'panjiva_{k}': v for k, v in panjiva_context.items()},
        'recommendation': rec_map.get(intent, 'Review manually'),
    }

    return enriched
