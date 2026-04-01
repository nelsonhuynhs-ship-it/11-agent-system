# -*- coding: utf-8 -*-
"""
etl_sync.py — AI Brain Layer: ETL Synchronization
===================================================
Orchestrates the daily data pipeline:
  ERP Excel → DataLake (DuckDB/Pandas)
  Parquet   → DataLake

Runs as:
  - Daily cron at 05:30 (scheduled in bot_v5.py)
  - On-demand via /sync command
  - On bot startup

Usage:
    from etl_sync import ETLSync, run_sync
    result = run_sync(parquet_df, erp_file)
    # → {"rates": 19700, "quotes": 45, "jobs": 18, "customers": 8, "ok": True}
"""
import logging
import os
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)


def run_sync(parquet_df: pd.DataFrame, erp_file: str) -> dict:
    """
    Main ETL entry point — syncs all data sources into the DataLake.

    Args:
        parquet_df:  Pre-loaded Parquet DataFrame (from query_engine)
        erp_file:    Path to ERP_Master.xlsm

    Returns:
        dict with counts and status
    """
    result = {
        'ok': False,
        'rates':     0,
        'quotes':    0,
        'jobs':      0,
        'customers': 0,
        'error':     None,
        'synced_at': datetime.now().strftime('%H:%M %d/%m'),
    }

    try:
        # ── Step 1: Extract ────────────────────────────────────────────────────
        from erp_reader import get_quote_history, get_active_jobs, get_crm_profile
        from customer_profiles import list_profile_customers, get_profile

        logger.info("[ETL] Starting sync...")

        # Rates from Parquet
        rates_df = parquet_df if parquet_df is not None else pd.DataFrame()
        result['rates'] = len(rates_df)

        # Quotes from ERP
        quotes = get_quote_history(limit=500)
        result['quotes'] = len(quotes)

        # Jobs from ERP
        jobs = get_active_jobs(limit=200)
        result['jobs'] = len(jobs)

        # Customers: merge CRM + static profiles
        customers = _build_customer_list()
        result['customers'] = len(customers)

        # ── Step 2: Load into DataLake ─────────────────────────────────────────
        from data_lake import init_lake
        lake = init_lake(rates_df, quotes, jobs, customers)

        if lake.is_ready:
            logger.info(f"[ETL] Sync complete: {lake.status()}")
            result['ok'] = True
        else:
            result['error'] = "DataLake init failed"

    except Exception as e:
        logger.error(f"[ETL] Sync error: {e}")
        result['error'] = str(e)[:200]

    return result


def _build_customer_list() -> list:
    """
    Merge static customer profiles with ERP CRM data.
    Returns list of customer dicts.
    """
    customers = []
    try:
        from customer_profiles import list_profile_customers, get_profile
        from erp_reader import get_crm_profile

        static_codes = list_profile_customers()
        for code in (static_codes or []):
            try:
                static = get_profile(code) or {}
                crm = get_crm_profile(code) or {}
                customers.append({
                    'code':            code,
                    'name':            crm.get('name', static.get('name', code)),
                    'contact':         crm.get('contact', ''),
                    'email':           crm.get('email', ''),
                    'payment_terms':   crm.get('payment_terms', ''),
                    'preferred_lanes': str(static.get('preferred_lanes', [])),
                    'commodity':       str(static.get('commodity', [])),
                    'behavior_tag':    static.get('behavior_tag', ''),
                })
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"[ETL] customer build error: {e}")
    return customers


def format_sync_result(result: dict) -> str:
    """Format sync result for Telegram message."""
    if result['ok']:
        return (
            f"✅ DATA LAKE SYNCED\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🗂️  Rates:     {result['rates']:,} records\n"
            f"📋 Quotes:    {result['quotes']} records\n"
            f"🚢 Jobs:      {result['jobs']} records\n"
            f"👥 Customers: {result['customers']} profiles\n"
            f"⏱️  At: {result['synced_at']}\n\n"
            f"🧠 AI Brain ready. Try /predict /risk /reachout"
        )
    else:
        return (
            f"⚠️ SYNC PARTIAL/FAILED\n"
            f"Error: {result.get('error', 'unknown')}\n"
            f"Rates: {result['rates']:,} | Quotes: {result['quotes']} | Jobs: {result['jobs']}\n"
            f"Bot vẫn hoạt động bình thường với Parquet trực tiếp."
        )
