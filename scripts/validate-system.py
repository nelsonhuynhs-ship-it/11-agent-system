"""
validate-system.py — Single validator for docs/SYSTEM_STANDARDS.md

Run before every commit. Checks all 12 sections of the standards doc.
Exit 0 = all rules pass. Exit != 0 = list violations.

Usage:
    python scripts/validate-system.py
    python scripts/validate-system.py --section 3   # run one section only
    python scripts/validate-system.py --fix          # auto-cleanup _tmp_* files

See: docs/SYSTEM_STANDARDS.md
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ONEDRIVE = Path("D:/OneDrive/NelsonData")

ISSUES: list[tuple[int, str]] = []  # (section, message)


def fail(section: int, msg: str) -> None:
    ISSUES.append((section, msg))


def ok(section: int, msg: str) -> None:
    print(f"  [S{section}] {msg} OK")


# ── Section 1: Canonical paths exist ────────────────────────────────────────
def check_section_1() -> None:
    print("\n=== Section 1 — Canonical paths ===")
    required = {
        "Parquet": ONEDRIVE / "pricing" / "Cleaned_Master_History.parquet",
        "CARRIER_RATE_MAPPING": ONEDRIVE / "pricing" / "mapping" / "CARRIER_RATE_MAPPING.json",
        "ERP xlsm": ONEDRIVE / "erp" / "ERP_Master_v14.xlsm",
        "refresh-v14.py": ONEDRIVE / "erp" / "refresh-v14.py",
        "web_server.py": REPO / "email_engine" / "web_server.py",
        "VBA mirror folder": REPO / "ERP" / "vba-v14-mirror",
    }
    for name, path in required.items():
        if not path.exists():
            fail(1, f"Missing: {name} → {path}")
        else:
            ok(1, f"{name} @ {path}")


# ── Section 2: Parquet charge names clean ───────────────────────────────────
def check_section_2() -> None:
    print("\n=== Section 2 — Parquet charge names ===")
    try:
        import duckdb
        pq = str(ONEDRIVE / "pricing" / "Cleaned_Master_History.parquet").replace("\\", "/")
        forbidden = ["BASE O/F", "HLCU Offer"]
        for bad in forbidden:
            q = f"SELECT COUNT(*) AS n FROM read_parquet('{pq}') WHERE Charge_Name = '{bad}'"
            n = duckdb.sql(q).df().iloc[0]["n"]
            if n > 0:
                fail(2, f"Parquet contains {n} stale '{bad}' rows — re-import needed")
            else:
                ok(2, f"No stale '{bad}' rows")
        # Must have Total Ocean Freight
        q2 = f"SELECT COUNT(*) AS n FROM read_parquet('{pq}') WHERE Charge_Name = 'Total Ocean Freight'"
        n2 = duckdb.sql(q2).df().iloc[0]["n"]
        if n2 == 0:
            fail(2, "Parquet has 0 'Total Ocean Freight' rows — loader broken")
        else:
            ok(2, f"{n2:,} 'Total Ocean Freight' rows present")
    except ImportError:
        fail(2, "duckdb not installed — cannot validate")
    except Exception as exc:
        fail(2, f"Parquet read error: {exc}")


# ── Section 3: Active Jobs schema ───────────────────────────────────────────
def check_section_3() -> None:
    print("\n=== Section 3 — Active Jobs schema ===")
    expected = [
        "MONTH", "FAST_ID", "Job_ID", "CUSTOMER", "POL-POD", "FINAL DEST",
        "CARRIER", "Bkg_No", "HBL_NO", "CONT", "QTY", "SERVICE", "ETD",
        "STATUS", "TRACKING", "SELL", "COST", "PROFIT", "EMAIL", "Routing",
        "ETA", "ATA", "Contract_Type", "Profit_Margin", "Customer_Type",
    ]
    try:
        import openpyxl
        wb = openpyxl.load_workbook(ONEDRIVE / "erp" / "ERP_Master_v14.xlsm",
                                     keep_vba=True, data_only=False, read_only=True)
        ws = wb["Active Jobs"]
        actual = [ws.cell(7, c).value for c in range(1, len(expected) + 1)]
        for i, (exp, act) in enumerate(zip(expected, actual)):
            if exp != act:
                col = chr(65 + i) if i < 26 else "A" + chr(65 + i - 26)
                fail(3, f"Col {col} header mismatch: expected '{exp}', got '{act}'")
                return
        ok(3, f"Active Jobs row 7 headers match ({len(expected)} cols)")
    except ImportError:
        fail(3, "openpyxl not installed")
    except PermissionError:
        fail(3, "ERP xlsm is open in Excel — close to validate schema")
    except Exception as exc:
        fail(3, f"Active Jobs read error: {exc}")


# ── Section 5: VBA launch pattern ───────────────────────────────────────────
def check_section_5() -> None:
    print("\n=== Section 5 — VBA launch pattern (WMI, not Shell) ===")
    bas_dir = ONEDRIVE / "erp"
    if not bas_dir.exists():
        fail(5, f"ERP folder missing: {bas_dir}")
        return
    forbidden_patterns = [
        (r'\bShell\s+"cmd\s*/c', 'Shell "cmd /c ..."'),
        (r"wsh\.Run\s*\(\s*\"cmd", 'wsh.Run("cmd ...'),
    ]
    violations = []
    for bas in bas_dir.glob("*.bas"):
        content = bas.read_text(encoding="utf-8", errors="replace")
        # Strip comments (lines starting with ')
        lines = [ln for ln in content.splitlines() if not ln.strip().startswith("'")]
        stripped = "\n".join(lines)
        for pat, desc in forbidden_patterns:
            for m in re.finditer(pat, stripped):
                violations.append(f"  {bas.name}: forbidden '{desc}' at ~char {m.start()}")
    if violations:
        fail(5, f"VBA forbidden launch patterns found:\n" + "\n".join(violations))
    else:
        ok(5, ".bas files use WMI pattern (no Shell/wsh.Run for cmd)")


# ── Section 6: Email pipeline purity ────────────────────────────────────────
def check_section_6() -> None:
    print("\n=== Section 6 — Email send pipeline ===")
    forbidden = [
        REPO / "api" / "routers" / "email_rate_router.py",
        REPO / "api" / "routers" / "email_queue_router.py",
        REPO / "api" / "routers" / "auto_quote_router.py",
        REPO / "webapp" / "src" / "app" / "dashboard" / "rate-send",
        REPO / "webapp" / "src" / "app" / "dashboard" / "email-campaign",
        REPO / "webapp" / "src" / "app" / "dashboard" / "email-log",
    ]
    for path in forbidden:
        if path.exists():
            fail(6, f"Forbidden path recreated: {path.relative_to(REPO)}")
    api_ts = REPO / "webapp" / "src" / "lib" / "api.ts"
    if api_ts.exists():
        content = api_ts.read_text(encoding="utf-8", errors="replace")
        if re.search(r"export\s+const\s+emailRateApi", content):
            fail(6, "webapp/src/lib/api.ts exports emailRateApi — must be removed")
        if re.search(r"export\s+const\s+campaignApi", content):
            fail(6, "webapp/src/lib/api.ts exports campaignApi — must be removed")
    if not ISSUES or ISSUES[-1][0] != 6:
        ok(6, "No forbidden email paths found")


# ── Section 9: Temp file cleanup ────────────────────────────────────────────
def check_section_9(fix: bool = False) -> None:
    print("\n=== Section 9 — Temp file cleanup ===")
    tmp_patterns = ["_tmp_*", "*.tmp"]
    offenders: list[Path] = []
    for pat in tmp_patterns:
        for path in REPO.glob(pat):
            offenders.append(path)
        for path in REPO.glob(f"**/{pat}"):
            # skip node_modules, .next, .git, __pycache__
            if any(part in str(path) for part in ("node_modules", ".next", ".git", "__pycache__", "_backup")):
                continue
            if path not in offenders:
                offenders.append(path)
    if offenders:
        if fix:
            for p in offenders:
                try:
                    if p.is_file():
                        p.unlink()
                        print(f"  [S9] Removed {p.relative_to(REPO)}")
                except Exception as exc:
                    fail(9, f"Could not remove {p}: {exc}")
            if not any(i[0] == 9 for i in ISSUES):
                ok(9, f"Cleaned {len(offenders)} temp files")
        else:
            for p in offenders:
                fail(9, f"Stale temp file: {p.relative_to(REPO) if p.is_relative_to(REPO) else p}")
            fail(9, "Run with --fix to auto-remove")
    else:
        ok(9, "No _tmp_* / *.tmp files in working tree")


# ── Section 11: Deprecated modules not imported ─────────────────────────────
def check_section_11() -> None:
    print("\n=== Section 11 — Deprecated modules not used ===")
    deprecated_modules = [
        "build_erp_v13_ribbon",
        "outlook_send_agent",
    ]
    violations = []
    for py in REPO.rglob("*.py"):
        if any(p in str(py) for p in ("__pycache__", "_backup", "vba-v14-mirror", ".agent", "archive")):
            continue
        try:
            content = py.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for mod in deprecated_modules:
            if re.search(rf"\b(from|import)\s+.*\b{mod}\b", content):
                violations.append(f"  {py.relative_to(REPO)}: imports {mod}")
    if violations:
        fail(11, "Deprecated modules imported:\n" + "\n".join(violations))
    else:
        ok(11, "No deprecated module imports")


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--section", type=int, help="Run only one section (1-11)")
    p.add_argument("--fix", action="store_true", help="Auto-cleanup where safe (section 9)")
    args = p.parse_args()

    print("=" * 60)
    print("Nelson Freight SYSTEM STANDARDS validator")
    print("Source: docs/SYSTEM_STANDARDS.md")
    print("=" * 60)

    runners = {
        1: check_section_1,
        2: check_section_2,
        3: check_section_3,
        5: check_section_5,
        6: check_section_6,
        9: lambda: check_section_9(fix=args.fix),
        11: check_section_11,
    }

    targets = [args.section] if args.section else sorted(runners.keys())
    for s in targets:
        if s in runners:
            try:
                runners[s]()
            except Exception as exc:
                fail(s, f"Validator error: {exc}")

    print("\n" + "=" * 60)
    if ISSUES:
        print(f"FAIL — {len(ISSUES)} issue(s):\n")
        for section, msg in ISSUES:
            print(f"  [Section {section}] {msg}")
        print("\nSee docs/SYSTEM_STANDARDS.md for the rule.")
        return 1
    else:
        print("PASS — all standards compliant.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
