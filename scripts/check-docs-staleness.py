#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
check-docs-staleness.py — Warn when docs lag behind code.

Run by pre-commit hook or manually. Exits 0 (does not block commit) but
prints colored warnings when docs have not been updated within THRESHOLD_DAYS
of a recent code change.

Logic:
    For each (code_file, docs_files) in DOCS_DEPENDENCIES:
        if code_file modified within THRESHOLD_DAYS:
            for doc_file in docs_files:
                if doc_file NOT modified within THRESHOLD_DAYS:
                    warn

Uses git log to get last commit date per file; falls back to stat().st_mtime.

Usage:
    python scripts/check-docs-staleness.py
    python scripts/check-docs-staleness.py --threshold 14
    python scripts/check-docs-staleness.py --verbose
    python scripts/check-docs-staleness.py --json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Project root ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Force UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except AttributeError:
        pass

# ── ANSI colors (disabled when not a TTY) ─────────────────────────────────────
_IS_TTY = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    if not _IS_TTY:
        return text
    return f"\033[{code}m{text}\033[0m"


def C_YELLOW(t: str) -> str:
    return _c("33", t)


def C_RED(t: str) -> str:
    return _c("31", t)


def C_GREEN(t: str) -> str:
    return _c("32", t)


def C_DIM(t: str) -> str:
    return _c("2", t)


def C_BOLD(t: str) -> str:
    return _c("1", t)


def C_RESET(t: str) -> str:
    return t  # reset is implicit at end of _c


# ── Mapping: code file/dir → docs files that must stay current ────────────────
DOCS_DEPENDENCIES: dict[str, list[str]] = {
    # Email pipeline layer
    "email_engine/web_server.py": [
        "docs/DATA_FLOW.md",
        "docs/EMAIL_DASHBOARD_V7.md",
        "docs/EMAIL_PIPELINE_SOURCE_OF_TRUTH.md",
    ],
    "email_engine/core/rule_engine.py": [
        "docs/ARB_ORIGIN_MAPPING.md",
        "docs/DATA_FLOW.md",
    ],
    "email_engine/core/rotation_engine.py": [
        "docs/DAILY_ROTATION_ENGINE.md",
        "docs/DATA_FLOW.md",
    ],
    "email_engine/core/rotation_helpers.py": [
        "docs/DAILY_ROTATION_ENGINE.md",
    ],
    "email_engine/core/smart_send_window.py": [
        "docs/EMAIL_DASHBOARD_V7.md",
    ],
    "email_engine/core/typo_shield.py": [
        "docs/EMAIL_DASHBOARD_V7.md",
    ],
    "email_engine/core/bounce_harvest_v2.py": [
        "docs/EMAIL_DASHBOARD_V7.md",
    ],
    "email_engine/api/routes/rotation_router.py": [
        "docs/DAILY_ROTATION_ENGINE.md",
    ],
    "email_engine/api/routes/contacts_router.py": [
        "docs/EMAIL_DASHBOARD_V7.md",
    ],
    # Scripts layer
    "scripts/panjiva_clean_v3.py": [
        "docs/PANJIVA_EXPORT_GUIDE.md",
        "docs/MASTER_V7_SCHEMA.md",
    ],
    "scripts/migrate-to-unified-v7.py": [
        "docs/MASTER_V7_SCHEMA.md",
        "docs/DATA_FLOW.md",
    ],
    "scripts/validate-data-contracts.py": [
        "docs/DATA_FLOW.md",
    ],
    # ARB config
    "email_engine/data/arb_rates.yaml": [
        "docs/ARB_ORIGIN_MAPPING.md",
    ],
    # ERP layer
    "ERP/intelligence/carrier_alias.py": [
        "docs/erp-v14-source-of-truth.md",
        "docs/ERP_STANDARDS.md",
    ],
}

DEFAULT_THRESHOLD_DAYS = 7


# ── Git / mtime helpers ────────────────────────────────────────────────────────

def git_last_modified(path: Path) -> datetime | None:
    """
    Return the last commit timestamp of a file via git log.
    Falls back to stat().st_mtime if git log returns nothing (untracked file).
    Returns None if file does not exist at all.
    """
    if not path.exists():
        return None

    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", str(path)],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        raw = result.stdout.strip()
        if result.returncode == 0 and raw:
            # git outputs ISO 8601 with timezone offset, e.g. 2026-04-22T14:30:00+07:00
            return datetime.fromisoformat(raw)
    except Exception:
        pass

    # Fallback: filesystem mtime (untracked or git unavailable)
    try:
        mtime = path.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc).astimezone()
    except Exception:
        return None


def _age_days(dt: datetime, now: datetime) -> int:
    return max(0, (now - dt).days)


# ── Core staleness check ───────────────────────────────────────────────────────

def check_staleness(threshold_days: int = DEFAULT_THRESHOLD_DAYS) -> list[dict]:
    """
    Scan all mappings and return a list of warning dicts for stale docs.

    Each warning dict:
        code_file     : str
        code_modified : str (ISO date YYYY-MM-DD)
        code_age_days : int
        stale_docs    : list[{path, reason, age_days|None}]
    """
    now = datetime.now().astimezone()
    threshold = now - timedelta(days=threshold_days)
    warnings: list[dict] = []

    for code_file, docs_files in DOCS_DEPENDENCIES.items():
        code_path = PROJECT_ROOT / code_file
        code_mtime = git_last_modified(code_path)

        if code_mtime is None:
            # File missing from disk — skip silently (e.g. not yet created)
            continue

        # Only flag if code was changed recently
        if code_mtime < threshold:
            continue

        stale_docs: list[dict] = []
        for docs_file in docs_files:
            docs_path = PROJECT_ROOT / docs_file
            docs_mtime = git_last_modified(docs_path)

            if docs_mtime is None:
                stale_docs.append({
                    "path": docs_file,
                    "reason": "missing",
                    "age_days": None,
                })
            elif docs_mtime < threshold:
                stale_docs.append({
                    "path": docs_file,
                    "reason": "stale",
                    "age_days": _age_days(docs_mtime, now),
                })

        if stale_docs:
            warnings.append({
                "code_file": code_file,
                "code_modified": code_mtime.isoformat()[:10],
                "code_age_days": _age_days(code_mtime, now),
                "stale_docs": stale_docs,
            })

    return warnings


# ── Verbose all-mappings listing ───────────────────────────────────────────────

def print_verbose_mappings(threshold_days: int) -> None:
    """Print every mapping and its current status (for --verbose)."""
    now = datetime.now().astimezone()
    threshold = now - timedelta(days=threshold_days)

    print(C_BOLD(f"\n  All mappings (threshold = {threshold_days}d):"))
    print()

    for code_file, docs_files in DOCS_DEPENDENCIES.items():
        code_path = PROJECT_ROOT / code_file
        code_mtime = git_last_modified(code_path)

        if code_mtime is None:
            code_label = C_DIM("(missing)")
            code_recent = False
        else:
            age = _age_days(code_mtime, now)
            code_recent = code_mtime >= threshold
            indicator = C_YELLOW("RECENT") if code_recent else C_DIM("old")
            code_label = f"{code_mtime.isoformat()[:10]}  [{indicator}]  {age}d ago"

        print(f"  {C_BOLD(code_file)}")
        print(f"    code  : {code_label}")

        for docs_file in docs_files:
            docs_path = PROJECT_ROOT / docs_file
            docs_mtime = git_last_modified(docs_path)

            if docs_mtime is None:
                status = C_RED("MISSING")
                detail = ""
            else:
                age = _age_days(docs_mtime, now)
                if code_recent and docs_mtime < threshold:
                    status = C_YELLOW("STALE")
                else:
                    status = C_GREEN("ok")
                detail = f"  ({docs_mtime.isoformat()[:10]}, {age}d ago)"

            print(f"    docs  : [{status}]  {docs_file}{detail}")
        print()


# ── Report printer ─────────────────────────────────────────────────────────────

def print_report(warnings: list[dict], threshold_days: int) -> None:
    """Pretty-print stale docs warnings to stdout."""
    if not warnings:
        print(C_GREEN(f"  Docs staleness check: all tracked docs up-to-date (threshold={threshold_days}d)"))
        return

    sep = C_YELLOW("━" * 57)
    print(sep)
    print(C_YELLOW(f"  DOCS STALENESS WARNINGS  ({len(warnings)} code file(s))"))
    print(sep)
    print()

    for w in warnings:
        age_str = f"{w['code_age_days']}d ago" if w['code_age_days'] > 0 else "today"
        print(f"{C_RED('  !')}  {C_BOLD(w['code_file'])}")
        print(f"       {C_DIM('modified ' + w['code_modified'] + '  (' + age_str + ')')}")
        print(f"       {C_YELLOW('update these docs:')}")

        for doc in w["stale_docs"]:
            if doc["reason"] == "missing":
                marker = C_RED("  x")
                label = C_RED("MISSING")
                print(f"{marker}  {doc['path']}  {C_DIM('(' + label + ')')}")
            else:
                marker = C_YELLOW("  ~")
                print(
                    f"{marker}  {doc['path']}  "
                    f"{C_DIM('(' + str(doc['age_days']) + 'd since last update)')}"
                )
        print()

    print(C_DIM(f"  Threshold: {threshold_days} days.  Run anytime: python scripts/check-docs-staleness.py"))
    print(C_DIM("  Not blocking commit.  Emergency bypass: git commit --no-verify"))


# ── JSON output ────────────────────────────────────────────────────────────────

def print_json(warnings: list[dict], threshold_days: int) -> None:
    payload = {
        "threshold_days": threshold_days,
        "warning_count": len(warnings),
        "warnings": warnings,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


# ── CLI entry point ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Nelson Freight — docs staleness checker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/check-docs-staleness.py\n"
            "  python scripts/check-docs-staleness.py --threshold 14\n"
            "  python scripts/check-docs-staleness.py --verbose\n"
            "  python scripts/check-docs-staleness.py --json\n"
        ),
    )
    parser.add_argument(
        "--threshold",
        "-t",
        type=int,
        default=DEFAULT_THRESHOLD_DAYS,
        metavar="DAYS",
        help=f"Days within which a modified code file must have corresponding docs update (default: {DEFAULT_THRESHOLD_DAYS})",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show all mappings including up-to-date ones",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output machine-readable JSON instead of colored report",
    )
    args = parser.parse_args()

    warnings = check_staleness(threshold_days=args.threshold)

    if args.json_output:
        print_json(warnings, args.threshold)
    else:
        if args.verbose:
            print_verbose_mappings(args.threshold)
        print_report(warnings, args.threshold)

    # Always exit 0 — reminder only, never blocks commit
    sys.exit(0)


if __name__ == "__main__":
    main()
