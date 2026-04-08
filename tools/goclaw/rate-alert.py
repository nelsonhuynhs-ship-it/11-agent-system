# -*- coding: utf-8 -*-
"""
rate-alert.py — Phát hiện thay đổi giá sau RateImport, gửi Telegram alert.

So sánh avg rate hôm nay (3 ngày gần nhất) vs 7-10 ngày trước.
Gửi Telegram nếu delta >= threshold.

Usage:
    python rate-alert.py
    python rate-alert.py --routes HPH-USLAX-40HQ,HPH-USNYC-40HQ
    python rate-alert.py --threshold-pct 10 --dry-run
"""
import argparse
import io
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

# Fix Windows cp1258 stdout — allow emoji/UTF-8 in print()
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Setup paths ───────────────────────────────────────────────────────────────
_repo_root = str(Path(__file__).parent.parent.parent)  # tools/goclaw → tools → Engine_test
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from shared.paths import PARQUET_FILE

try:
    import duckdb
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "duckdb", "-q"])
    import duckdb

# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_ROUTES = [
    ("HPH", "LAX",  "40HQ"),
    ("HPH", "LGB",  "40HQ"),
    ("HPH", "NYC",  "40HQ"),
    ("HPH", "EWR",  "40HQ"),
    ("HPH", "SAV",  "40HQ"),
    ("HCM", "LAX",  "40HQ"),
    ("HCM", "LGB",  "40HQ"),
]
ALERT_THRESHOLD_PCT = 8    # alert nếu |delta| >= 8%
ALERT_THRESHOLD_USD = 100  # hoặc nếu |delta| >= $100

# ── Load .env ─────────────────────────────────────────────────────────────────
_env_candidates = [
    Path(__file__).parent / ".env",
    Path(__file__).parent.parent.parent / "api" / ".env",
]
for _env_path in _env_candidates:
    if _env_path.exists():
        for _line in _env_path.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                if _k.strip() not in os.environ:
                    os.environ[_k.strip()] = _v.strip()


def _avg_rate(parquet: str, pol: str, pod: str, container: str,
              days_from: int, days_to: int) -> float:
    """
    Query avg Amount for route within a date window.
    days_from=3, days_to=0  → today window (last 3 days)
    days_from=10, days_to=7 → reference window (7-10 days ago)
    """
    sql = f"""
        SELECT AVG(Amount)
        FROM read_parquet('{parquet}')
        WHERE UPPER(TRIM(POL)) = UPPER(?)
          AND UPPER(CAST(POD AS VARCHAR)) LIKE '%' || UPPER(?) || '%'
          AND UPPER(Container_Type) = UPPER(?)
          AND Charge_Name = 'Total Ocean Freight'
          AND Amount > 0
          AND Eff >= CURRENT_DATE - INTERVAL '{days_from}' DAY
          AND Eff <= CURRENT_DATE - INTERVAL '{days_to}' DAY
    """
    con = duckdb.connect()
    try:
        result = con.execute(sql, [pol, pod, container]).fetchone()
        return float(result[0]) if result and result[0] is not None else 0.0
    finally:
        con.close()


def check_route(parquet: str, pol: str, pod: str, container: str,
                threshold_pct: float = ALERT_THRESHOLD_PCT,
                threshold_usd: float = ALERT_THRESHOLD_USD) -> dict | None:
    """
    Compare recent avg vs reference avg for a route.
    recent  = last 3 days  (days_from=3, days_to=0  → Eff in [-3, today])
    ref     = 7-10 days ago (days_from=10, days_to=6 → Eff in [-10, -7] inclusive)
    Returns alert dict if delta exceeds threshold, else None.
    """
    now_avg = _avg_rate(parquet, pol, pod, container, days_from=3, days_to=0)
    # days_to=6 (not 7) so Eff <= CURRENT_DATE-6 includes day -7 (fence-post fix)
    ref_avg = _avg_rate(parquet, pol, pod, container, days_from=10, days_to=6)

    if now_avg == 0 or ref_avg == 0:
        return None  # không đủ data

    delta_usd = now_avg - ref_avg
    delta_pct = (delta_usd / ref_avg) * 100

    if abs(delta_pct) >= threshold_pct or abs(delta_usd) >= threshold_usd:
        direction = "⬆️" if delta_usd > 0 else "⬇️"
        sign = "+" if delta_usd > 0 else ""
        return {
            "route": f"{pol}→{pod} {container}",
            "pol": pol,
            "pod": pod,
            "container": container,
            "prev": round(ref_avg),
            "now": round(now_avg),
            "delta_usd": round(delta_usd),
            "delta_pct": round(delta_pct, 1),
            "direction": direction,
            "sign": sign,
        }
    return None


def format_alert_message(alerts: list[dict]) -> str:
    """Format Telegram message for rate alerts."""
    today = date.today().strftime("%d/%m/%Y")
    lines = [f"📊 <b>Rate Alert — {today}</b>\n"]

    lines.append(f"{'Route':<22} {'Trước':>7} {'Sau':>7} {'Delta':>14}")
    lines.append("─" * 54)

    for a in alerts:
        route = a["route"][:22]
        prev = f"${a['prev']:,}"
        now_ = f"${a['now']:,}"
        delta = f"{a['sign']}${abs(a['delta_usd']):,} ({a['sign']}{a['delta_pct']}%) {a['direction']}"
        lines.append(f"{route:<22} {prev:>7} {now_:>7} {delta}")

    lines.append("")

    # Gợi ý action cho routes giảm giá mạnh
    drop_routes = [a for a in alerts if a["delta_pct"] < -ALERT_THRESHOLD_PCT]
    if drop_routes:
        pods = "/".join(set(a["pod"] for a in drop_routes))
        lines.append(f"💡 Cân nhắc gửi email update cho khách route {pods}?")
        lines.append(f'Gõ "campaign {drop_routes[0]["pod"]}" để trigger email.')

    return "\n".join(lines)


def send_telegram_alert(message: str, dry_run: bool = False) -> bool:
    """Send alert via send-telegram.py."""
    if dry_run:
        print("[DRY-RUN] Would send Telegram:")
        print(message)
        return True

    script = Path(__file__).parent / "send-telegram.py"
    if not script.exists():
        print(f"[ERROR] send-telegram.py not found at {script}", file=sys.stderr)
        return False

    import subprocess
    result = subprocess.run(
        [sys.executable, str(script), "--message", message, "--parse-mode", "HTML"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode == 0:
        return True
    else:
        print(f"[ERROR] Telegram send failed: {result.stderr}", file=sys.stderr)
        return False


def run_alert(routes: list[tuple] | None = None,
              threshold_pct: float = ALERT_THRESHOLD_PCT,
              threshold_usd: float = ALERT_THRESHOLD_USD,
              dry_run: bool = False) -> dict:
    """
    Main entry point. Returns summary dict.
    Thresholds passed explicitly — no global mutation.
    """
    routes = routes or DEFAULT_ROUTES
    parquet = str(PARQUET_FILE)

    alerts = []
    skipped = 0
    skipped_routes: list[str] = []
    for pol, pod, container in routes:
        result = check_route(parquet, pol, pod, container, threshold_pct, threshold_usd)
        if result:
            alerts.append(result)
        else:
            skipped += 1
            skipped_routes.append(f"{pol}→{pod} {container}")

    summary = {
        "checked": len(routes),
        "alerts": len(alerts),
        "skipped_no_data": skipped,
        "sent": False,
        "timestamp": datetime.now().isoformat(),
    }
    if skipped_routes:
        summary["skipped_routes"] = skipped_routes

    if alerts:
        message = format_alert_message(alerts)
        sent = send_telegram_alert(message, dry_run=dry_run)
        summary["sent"] = sent
        summary["alert_routes"] = [a["route"] for a in alerts]
    else:
        print(f"[rate-alert] No significant changes. Checked {len(routes)} routes.")

    return summary


def _parse_routes_arg(routes_str: str) -> list[tuple]:
    """Parse 'HPH-USLAX-40HQ,HCM-LAX-40HQ' into [(pol, pod, container), ...]"""
    result = []
    for entry in routes_str.split(","):
        parts = entry.strip().upper().split("-")
        if len(parts) == 3:
            pol, pod, container = parts
            # Normalize pod: strip US prefix for DuckDB LIKE query
            pod_norm = pod.replace("US", "", 1) if pod.startswith("US") else pod
            result.append((pol, pod_norm, container))
        else:
            print(f"[WARN] Skipping invalid route format: {entry}", file=sys.stderr)
    return result or DEFAULT_ROUTES


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Rate Alert — detect price changes post-import")
    p.add_argument("--routes", default="", help="Comma-separated routes: HPH-USLAX-40HQ,HCM-LAX-40HQ")
    p.add_argument("--threshold-pct", type=float, default=ALERT_THRESHOLD_PCT,
                   help=f"Alert if |delta%| >= this (default {ALERT_THRESHOLD_PCT})")
    p.add_argument("--threshold-usd", type=float, default=ALERT_THRESHOLD_USD,
                   help=f"Alert if |delta$| >= this (default {ALERT_THRESHOLD_USD})")
    p.add_argument("--dry-run", action="store_true", help="Print message, don't send Telegram")
    args = p.parse_args()

    routes = _parse_routes_arg(args.routes) if args.routes else DEFAULT_ROUTES
    result = run_alert(
        routes=routes,
        threshold_pct=args.threshold_pct,
        threshold_usd=args.threshold_usd,
        dry_run=args.dry_run,
    )
    try:
        from goclaw_reporter import report_to_fox
        report_to_fox("rate-alert", result)
    except Exception:
        pass
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    sys.exit(0 if result.get("alerts", 0) == 0 or result.get("sent") else 1)
