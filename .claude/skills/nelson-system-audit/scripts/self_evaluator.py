# -*- coding: utf-8 -*-
"""
self_evaluator.py — System Self-Evaluation Engine
===================================================
Runtime health checks: API responsiveness, worker status,
event pipeline, database integrity, rate query latency.
Designed to run daily and store results.
"""
import os
import json
import time
import sqlite3
from datetime import datetime, date
from dataclasses import dataclass, field

from architecture_rules import BASE_DIR, API_DIR, EMAIL_DIR


@dataclass
class HealthCheck:
    name:    str
    status:  str  # "PASS" | "WARN" | "FAIL"
    value:   str
    detail:  str = ""
    latency_ms: float = 0


@dataclass
class SelfEvalReport:
    timestamp:          str = ""
    architecture_score: float = 0
    performance_score:  float = 0
    reliability_score:  float = 0
    risk_flags:         list[str] = field(default_factory=list)
    checks:             list[HealthCheck] = field(default_factory=list)

    def __post_init__(self):
        self.timestamp = datetime.now().isoformat()

    def add_check(self, check: HealthCheck):
        self.checks.append(check)

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "PASS")

    @property
    def total_checks(self) -> int:
        return len(self.checks)


def check_api_health(report: SelfEvalReport):
    """Check if FastAPI server is responding."""
    try:
        import httpx
        start = time.time()
        r = httpx.get("http://localhost:8000/api/status", timeout=5)
        latency = (time.time() - start) * 1000
        if r.status_code == 200:
            report.add_check(HealthCheck("API Server", "PASS", f"{latency:.0f}ms", latency_ms=latency))
        else:
            report.add_check(HealthCheck("API Server", "WARN", f"Status {r.status_code}", latency_ms=latency))
    except ImportError:
        # Fallback to urllib
        try:
            import urllib.request
            start = time.time()
            r = urllib.request.urlopen("http://localhost:8000/api/status", timeout=5)
            latency = (time.time() - start) * 1000
            report.add_check(HealthCheck("API Server", "PASS", f"{latency:.0f}ms", latency_ms=latency))
        except Exception as e:
            report.add_check(HealthCheck("API Server", "FAIL", str(e)[:80]))
            report.risk_flags.append("API server not responding")
    except Exception as e:
        report.add_check(HealthCheck("API Server", "FAIL", str(e)[:80]))
        report.risk_flags.append("API server not responding")


def check_webapp_health(report: SelfEvalReport):
    """Check if WebApp dev server is responding."""
    try:
        import urllib.request
        start = time.time()
        r = urllib.request.urlopen("http://localhost:3000", timeout=5)
        latency = (time.time() - start) * 1000
        report.add_check(HealthCheck("WebApp", "PASS", f"{latency:.0f}ms", latency_ms=latency))
    except Exception as e:
        report.add_check(HealthCheck("WebApp", "WARN", f"Not running: {str(e)[:50]}"))


def check_parquet_freshness(report: SelfEvalReport):
    """Check if Parquet pricing data is fresh."""
    parquet_path = os.path.join(BASE_DIR, "Pricing_Engine", "data", "Cleaned_Master_History.parquet")
    if os.path.exists(parquet_path):
        mtime = datetime.fromtimestamp(os.path.getmtime(parquet_path))
        age_days = (datetime.now() - mtime).days
        if age_days > 7:
            report.add_check(HealthCheck("Parquet Data", "WARN",
                f"Last updated {age_days} days ago", "May contain stale rates"))
            report.risk_flags.append(f"Parquet data is {age_days} days old")
        else:
            report.add_check(HealthCheck("Parquet Data", "PASS", f"Updated {age_days}d ago"))
    else:
        report.add_check(HealthCheck("Parquet Data", "FAIL", "File not found"))
        report.risk_flags.append("Parquet file missing")


def check_shipment_state(report: SelfEvalReport):
    """Check shipment_state.json integrity."""
    state_path = os.path.join(EMAIL_DIR, "shipment_state.json")
    if not os.path.exists(state_path):
        report.add_check(HealthCheck("Shipment State", "FAIL", "File not found"))
        report.risk_flags.append("shipment_state.json missing")
        return

    try:
        with open(state_path, encoding="utf-8") as f:
            data = json.load(f)
        count = len(data) if isinstance(data, (list, dict)) else 0
        size_kb = os.path.getsize(state_path) / 1024
        mtime = datetime.fromtimestamp(os.path.getmtime(state_path))
        age_hours = (datetime.now() - mtime).total_seconds() / 3600

        if age_hours > 48:
            report.add_check(HealthCheck("Shipment State", "WARN",
                f"{count} entries, {size_kb:.0f}KB, {age_hours:.0f}h old",
                "Data may be stale"))
        else:
            report.add_check(HealthCheck("Shipment State", "PASS",
                f"{count} entries, {size_kb:.0f}KB"))
    except json.JSONDecodeError:
        report.add_check(HealthCheck("Shipment State", "FAIL", "JSON parse error"))
        report.risk_flags.append("shipment_state.json is corrupted")


def check_quotes_integrity(report: SelfEvalReport):
    """Check quotes.json integrity."""
    quotes_path = os.path.join(API_DIR, "data", "quotes.json")
    if not os.path.exists(quotes_path):
        # Also check email_engine path
        quotes_path = os.path.join(EMAIL_DIR, "quotes.json")
    if not os.path.exists(quotes_path):
        report.add_check(HealthCheck("Quotes Data", "WARN", "No quotes.json found"))
        return

    try:
        with open(quotes_path, encoding="utf-8") as f:
            data = json.load(f)
        count = len(data) if isinstance(data, list) else (
            len(data.get("quotes", [])) if isinstance(data, dict) else 0)
        report.add_check(HealthCheck("Quotes Data", "PASS", f"{count} quotes"))
    except Exception as e:
        report.add_check(HealthCheck("Quotes Data", "FAIL", str(e)[:60]))


def check_email_dataset(report: SelfEvalReport):
    """Check if email dataset exists and is fresh."""
    dataset_path = os.path.join(EMAIL_DIR, "outlook_dataset.json")
    if os.path.exists(dataset_path):
        mtime = datetime.fromtimestamp(os.path.getmtime(dataset_path))
        age_hours = (datetime.now() - mtime).total_seconds() / 3600
        size_kb = os.path.getsize(dataset_path) / 1024
        status = "PASS" if age_hours < 24 else "WARN"
        report.add_check(HealthCheck("Email Dataset", status,
            f"{size_kb:.0f}KB, {age_hours:.0f}h old"))
    else:
        report.add_check(HealthCheck("Email Dataset", "WARN", "Not found"))


def check_sqlite_database(report: SelfEvalReport):
    """Check Bot SQLite database integrity."""
    db_path = os.path.join(BOT_DIR, "data", "freight_bot.db") if os.path.exists(
        os.path.join(BASE_DIR, "TelegramBot", "data", "freight_bot.db")) else None
    bot_db = os.path.join(BASE_DIR, "TelegramBot", "data", "freight_bot.db")

    if os.path.exists(bot_db):
        try:
            conn = sqlite3.connect(bot_db)
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            report.add_check(HealthCheck("SQLite DB", "PASS",
                f"{len(tables)} tables: {', '.join(tables[:5])}"))
        except Exception as e:
            report.add_check(HealthCheck("SQLite DB", "FAIL", str(e)[:60]))
    else:
        report.add_check(HealthCheck("SQLite DB", "WARN", "Not found at expected path"))


def check_erp_file(report: SelfEvalReport):
    """Check ERP_Master.xlsm accessibility."""
    erp_path = os.path.join(BASE_DIR, "ERP", "data", "ERP_Master.xlsm")
    if os.path.exists(erp_path):
        size_mb = os.path.getsize(erp_path) / (1024 * 1024)
        mtime = datetime.fromtimestamp(os.path.getmtime(erp_path))
        report.add_check(HealthCheck("ERP File", "PASS",
            f"{size_mb:.1f}MB, modified {mtime.strftime('%d-%b %H:%M')}"))
    else:
        report.add_check(HealthCheck("ERP File", "WARN", "Not found"))


def calculate_scores(report: SelfEvalReport, architecture_score: float = 0):
    """Calculate composite scores from health checks."""
    report.architecture_score = architecture_score

    # Performance: based on API latency
    api_checks = [c for c in report.checks if c.latency_ms > 0]
    if api_checks:
        avg_latency = sum(c.latency_ms for c in api_checks) / len(api_checks)
        report.performance_score = max(0, min(10, 10 - (avg_latency / 100)))
    else:
        report.performance_score = 5.0  # neutral if no latency data

    # Reliability: based on pass rate
    if report.total_checks > 0:
        pass_rate = report.pass_count / report.total_checks
        report.reliability_score = round(pass_rate * 10, 1)
    else:
        report.reliability_score = 0

    report.performance_score = round(report.performance_score, 1)


BOT_DIR = os.path.join(BASE_DIR, "TelegramBot")


def run_self_evaluation(architecture_score: float = 0) -> SelfEvalReport:
    """Run all self-evaluation health checks."""
    report = SelfEvalReport()

    check_api_health(report)
    check_webapp_health(report)
    check_parquet_freshness(report)
    check_shipment_state(report)
    check_quotes_integrity(report)
    check_email_dataset(report)
    check_sqlite_database(report)
    check_erp_file(report)

    calculate_scores(report, architecture_score)
    return report
