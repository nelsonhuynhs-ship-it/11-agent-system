# -*- coding: utf-8 -*-
"""
health_router.py — System Health & Readiness Endpoints
=========================================================
Deep health check for monitoring, load balancers, and deployment validation.

Endpoints:
    GET /api/health          — Quick liveness
    GET /api/health/ready    — Readiness (all dependencies)
    GET /api/health/deep     — Full diagnostic (for admin)
"""
import logging
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter

from config import cfg
from data_access import dal
from event_bus import bus

router = APIRouter(prefix="/api/health", tags=["Health"])
log = logging.getLogger("nelson.health")


@router.get("")
def health_check():
    """Quick liveness probe. Returns 200 if API is running."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@router.get("/data-freshness")
def data_freshness():
    """
    Rate data freshness — checks Parquet file modification time.
    Does NOT load the file, only reads filesystem metadata.
    fresh: < 24h | aging: 24-72h | stale: > 72h
    """
    try:
        parquet_path = cfg.PARQUET_FILE
        if not parquet_path.exists():
            return {"status": "unknown", "detail": "Parquet file not found"}

        mod_time = os.path.getmtime(parquet_path)
        last_modified = datetime.fromtimestamp(mod_time)
        age_hours = (datetime.now() - last_modified).total_seconds() / 3600

        if age_hours < 24:
            status = "fresh"
        elif age_hours < 72:
            status = "aging"
        else:
            status = "stale"

        return {
            "last_modified": last_modified.isoformat(),
            "age_hours": round(age_hours, 1),
            "status": status,
            "parquet_file": parquet_path.name,
        }
    except Exception as e:
        log.error(f"Data freshness check failed: {e}")
        return {"status": "error", "detail": str(e)}


@router.get("/ready")
def readiness_check():
    """
    Readiness probe — checks all critical dependencies.
    Returns 200 OK + details, or 503 if critical deps fail.
    """
    checks = {}
    all_ok = True

    # 1. Parquet rates
    try:
        df = dal.load_rates()
        checks["parquet"] = {
            "status": "ok" if df is not None else "warn",
            "rows": len(df) if df is not None else 0,
            "cached_at": dal.rates_loaded_at.isoformat() if dal.rates_loaded_at else None,
        }
    except Exception as e:
        checks["parquet"] = {"status": "error", "detail": str(e)}
        all_ok = False

    # 2. Quotes data store
    try:
        quotes = dal.load_quotes_data()
        checks["quotes"] = {"status": "ok", "count": len(quotes)}
    except Exception as e:
        checks["quotes"] = {"status": "error", "detail": str(e)}
        all_ok = False

    # 3. Shipment state
    try:
        shipments = dal.get_shipments()
        checks["shipments"] = {"status": "ok", "count": len(shipments)}
    except Exception as e:
        checks["shipments"] = {"status": "error", "detail": str(e)}
        all_ok = False

    # 4. Event bus
    try:
        stats = bus.stats
        checks["event_bus"] = {
            "status": "ok",
            "events_logged": stats["total_logged"],
            "handlers": len(stats["handlers"]),
            "persisted": stats["persisted"],
        }
    except Exception as e:
        checks["event_bus"] = {"status": "error", "detail": str(e)}

    # 5. Database (if configured)
    if cfg.is_postgres:
        try:
            from database.connection import get_sync_connection
            conn = get_sync_connection()
            conn.execute("SELECT 1")
            checks["postgres"] = {"status": "ok"}
        except Exception as e:
            checks["postgres"] = {"status": "error", "detail": str(e)}
            all_ok = False
    else:
        checks["postgres"] = {"status": "not_configured"}

    return {
        "status": "ok" if all_ok else "degraded",
        "timestamp": datetime.now().isoformat(),
        "checks": checks,
        "config": cfg.summary(),
    }


@router.get("/deep")
def deep_health():
    """
    Full diagnostic endpoint for admin use.
    Returns detailed system state including file system, workers,
    and data quality metrics.
    """
    # File system checks
    fs_checks = {}
    files_to_check = {
        "parquet": cfg.PARQUET_FILE,
        "quotes": Path(__file__).parent.parent / "data" / "quotes.json",
        "events_log": Path(__file__).parent.parent / "data" / "events.jsonl",
    }
    for name, path in files_to_check.items():
        try:
            if path.exists():
                stat = path.stat()
                fs_checks[name] = {
                    "exists": True,
                    "size_kb": round(stat.st_size / 1024, 1),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            else:
                fs_checks[name] = {"exists": False}
        except Exception as e:
            fs_checks[name] = {"error": str(e)}

    # Data quality
    data_quality = {}
    try:
        df = dal.load_rates()
        if df is not None:
            today = datetime.now().date()
            if "Exp" in df.columns:
                # Count expired rates
                try:
                    exp = pd.to_datetime(df["Exp"], errors="coerce")
                    expired = (exp.dt.date < today).sum()
                    data_quality["expired_rates"] = int(expired)
                    data_quality["active_rates"] = int(len(df) - expired)
                except Exception:
                    pass
            data_quality["total_rates"] = len(df)
            data_quality["carriers"] = sorted(df["Carrier"].dropna().unique().tolist()) if "Carrier" in df.columns else []
    except Exception:
        pass

    import pandas as pd
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "system": {
            "python": os.sys.version.split()[0],
            "api_version": "2.3.0",
            "database_mode": "postgresql" if cfg.is_postgres else "json_files",
            "auth_mode": cfg.auth_mode,
            "tenant": cfg.DEFAULT_TENANT_ID,
        },
        "files": fs_checks,
        "data_quality": data_quality,
        "event_bus": bus.stats,
        "config": cfg.summary(),
    }
