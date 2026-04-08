# -*- coding: utf-8 -*-
"""
query-rate.py — GoClaw Tool: Query freight rates from local Parquet via DuckDB.

Usage:
    python query-rate.py --pol HPH --pod LAX --container 40HQ
    python query-rate.py --pol HPH --pod LAX --container 40HQ --days 30 --top 5
"""
import argparse
import json
import sys
from pathlib import Path

# ── Setup paths ───────────────────────────────────────────────────────────────
_repo_root = str(Path(__file__).parent.parent.parent)  # tools/goclaw → tools → Engine_test
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from db.duckdb_engine import FreightDB
from shared.paths import PARQUET_FILE


def query_rates(pol: str, pod: str, container: str, days: int = 30, top: int = 10) -> dict:
    """Query rates from Parquet via DuckDB."""
    try:
        db = FreightDB(PARQUET_FILE)
        pod_normalized = pod.upper().removeprefix("US")  # USLAX → LAX, LAX → LAX (safe)

        df = db.query_rates(
            pol=pol.upper(),
            pod=pod_normalized,
            container_type=container.upper(),
            days=days,
        )

        if df is None or len(df) == 0:
            # Fallback to wider window
            for fallback_days in [60, 90]:
                df = db.query_rates(
                    pol=pol.upper(),
                    pod=pod_normalized,
                    container_type=container.upper(),
                    days=fallback_days,
                )
                if df is not None and len(df) > 0:
                    break

        if df is None or len(df) == 0:
            records = []
        else:
            records = df.head(top).to_dict(orient="records")

        return {
            "status": "ok",
            "pol": pol.upper(),
            "pod": pod.upper(),
            "container": container.upper(),
            "days_searched": days,
            "count": len(records),
            "rates": records,
        }
    except Exception as e:
        return {"error": str(e), "pol": pol, "pod": pod, "container": container}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Query freight rates")
    p.add_argument("--pol", required=True, help="Port of Loading (HPH/HCM)")
    p.add_argument("--pod", required=True, help="Port of Discharge (LAX/LGB/NYC...)")
    p.add_argument("--container", required=True, help="Container type (40HQ/20GP...)")
    p.add_argument("--days", type=int, default=30, help="Look back days (default 30)")
    p.add_argument("--top", type=int, default=10, help="Max results (default 10)")
    args = p.parse_args()

    result = query_rates(args.pol, args.pod, args.container, args.days, args.top)
    print(json.dumps(result, ensure_ascii=False, default=str))
    sys.exit(0 if "error" not in result else 1)
