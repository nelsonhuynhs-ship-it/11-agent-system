# -*- coding: utf-8 -*-
"""
validate-data-contracts.py — Automated Data Contract Drift Validator
=====================================================================
Checks 7 contracts between layers of the Nelson Freight email system.

Exit codes:
    0 = all checks PASS (or SKIP)
    1 = any FAIL or ERROR

Usage:
    python scripts/validate-data-contracts.py
    python scripts/validate-data-contracts.py --verbose
"""
from __future__ import annotations

import ast
import re
import sys
import argparse
from pathlib import Path
from typing import Any

# ── Project root ───────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── Force UTF-8 output on Windows ────────────────────────────────────────────
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except AttributeError:
        pass  # Python < 3.7 fallback — no reconfigure available

# ── ANSI colors (disabled when not a TTY) ─────────────────────────────────────
_IS_TTY = sys.stdout.isatty()

def _c(code: str, text: str) -> str:
    if not _IS_TTY:
        return text
    return f"\033[{code}m{text}\033[0m"

GREEN  = lambda t: _c("32", t)
RED    = lambda t: _c("31;1", t)
YELLOW = lambda t: _c("33", t)
CYAN   = lambda t: _c("36", t)
BOLD   = lambda t: _c("1", t)

SYMBOLS = {"PASS": "✓", "FAIL": "✗", "SKIP": "○", "ERROR": "⚠", "UNKNOWN": "?"}
COLOR   = {"PASS": GREEN, "FAIL": RED, "SKIP": YELLOW, "ERROR": YELLOW}

VERBOSE = False


# ══════════════════════════════════════════════════════════════════════════════
#  Check 1 — Parquet schema
# ══════════════════════════════════════════════════════════════════════════════
def check_parquet_schema() -> dict[str, Any]:
    """Verify Parquet file has expected baseline columns (v1 canonical)."""
    # Baseline discovered 2026-04-22 from read_schema on real Parquet
    EXPECTED_COLS = {
        "POL", "POD", "Place", "Carrier", "Commodity", "Contract",
        "Eff", "Exp", "Note", "Group Rate", "Charge_Name",
        "Container_Type", "Amount", "Source_File", "Rate_Type",
        "Group_Code", "Charge_Meta",
    }

    try:
        import pyarrow.parquet as pq  # type: ignore
    except ImportError:
        return {"status": "SKIP", "reason": "pyarrow not installed"}

    try:
        from shared.paths import PARQUET_FILE  # type: ignore
        parquet_path = PARQUET_FILE
    except ImportError:
        parquet_path = Path(
            "D:/OneDrive/NelsonData/pricing/Cleaned_Master_History.parquet"
        )

    if not Path(parquet_path).exists():
        return {"status": "SKIP", "reason": f"Parquet not found at {parquet_path} (OneDrive not synced?)"}

    schema = pq.read_schema(parquet_path)
    actual = set(schema.names)
    missing = EXPECTED_COLS - actual
    extra   = actual - EXPECTED_COLS

    if missing:
        return {
            "status": "FAIL",
            "missing_cols": sorted(missing),
            "extra_cols":   sorted(extra),
            "total_cols":   len(actual),
        }

    return {"status": "PASS", "total_cols": len(actual), "extra_cols": sorted(extra)}


# ══════════════════════════════════════════════════════════════════════════════
#  Check 2 — CNEE v6 schema (contact_unified_v6.xlsx)
# ══════════════════════════════════════════════════════════════════════════════
def check_cnee_v6_schema() -> dict[str, Any]:
    """Verify v6 master CNEE sheet has 5-col LOCK + required columns."""
    REQUIRED_COLS = {
        # Core identity
        "EMAIL", "COMPANY", "PIC", "POL", "DESTINATION",
        # Segmentation
        "COMMODITY_CATEGORY", "TIER", "ORIGIN_COUNTRY",
        # 5-col LOCK (state machine)
        "EMAIL_STATUS", "SEND_COUNT", "LAST_SENT_DATE", "REPLY_STATUS", "SEQ_STEP",
    }
    REQUIRED_SHEETS = {"CNEE"}

    try:
        import pandas as pd  # type: ignore
    except ImportError:
        return {"status": "SKIP", "reason": "pandas not installed"}

    xlsx_path = Path("D:/OneDrive/NelsonData/email/contact_unified_v6.xlsx")
    if not xlsx_path.exists():
        return {"status": "SKIP", "reason": f"v6 master not found at {xlsx_path}"}

    try:
        xl = pd.ExcelFile(xlsx_path)
        actual_sheets = set(xl.sheet_names)
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

    missing_sheets = REQUIRED_SHEETS - actual_sheets
    if missing_sheets:
        return {"status": "FAIL", "missing_sheets": sorted(missing_sheets), "found_sheets": sorted(actual_sheets)}

    df = pd.read_excel(xlsx_path, sheet_name="CNEE", nrows=1)
    actual_cols = set(df.columns)
    missing = REQUIRED_COLS - actual_cols

    if missing:
        return {
            "status": "FAIL",
            "missing_cols": sorted(missing),
            "total_cols": len(actual_cols),
        }

    return {
        "status": "PASS",
        "total_cols": len(actual_cols),
        "sheets": sorted(actual_sheets),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Check 3 — rule_engine ARB_MAPPING completeness
# ══════════════════════════════════════════════════════════════════════════════
def check_rule_engine_mapping() -> dict[str, Any]:
    """Verify ARB_MAPPING has all 5 core countries + required sub-keys."""
    REQUIRED_COUNTRIES = {"VN", "MY", "TH", "CN", "KH"}
    REQUIRED_KEYS = {"pol_default", "arb_key"}

    try:
        from email_engine.core.rule_engine import ARB_MAPPING  # type: ignore
    except ImportError as e:
        return {"status": "ERROR", "error": f"Cannot import rule_engine: {e}"}

    actual_countries = set(ARB_MAPPING.keys())
    missing_countries = REQUIRED_COUNTRIES - actual_countries

    bad_entries: list[str] = []
    for country, rule in ARB_MAPPING.items():
        missing_keys = REQUIRED_KEYS - set(rule.keys())
        if missing_keys:
            bad_entries.append(f"{country}: missing keys {sorted(missing_keys)}")

    if missing_countries or bad_entries:
        result: dict[str, Any] = {"status": "FAIL"}
        if missing_countries:
            result["missing_countries"] = sorted(missing_countries)
        if bad_entries:
            result["bad_entries"] = bad_entries
        return result

    return {
        "status": "PASS",
        "countries": sorted(actual_countries),
        "total": len(actual_countries),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Check 4 — ARB yaml references
# ══════════════════════════════════════════════════════════════════════════════
def check_arb_yaml_refs() -> dict[str, Any]:
    """Verify arb_rates.yaml has entries for all arb_keys referenced by rule_engine."""
    try:
        import yaml  # type: ignore
    except ImportError:
        return {"status": "SKIP", "reason": "PyYAML not installed"}

    try:
        from email_engine.core.rule_engine import ARB_MAPPING  # type: ignore
    except ImportError as e:
        return {"status": "ERROR", "error": f"Cannot import rule_engine: {e}"}

    yaml_path = PROJECT_ROOT / "email_engine" / "data" / "arb_rates.yaml"
    if not yaml_path.exists():
        return {"status": "FAIL", "reason": f"arb_rates.yaml not found at {yaml_path}"}

    try:
        with open(yaml_path, encoding="utf-8") as f:
            arb_data = yaml.safe_load(f)
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

    referenced = {
        rule["arb_key"]
        for rule in ARB_MAPPING.values()
        if rule.get("arb_key")
    }
    yaml_keys = set(arb_data.keys()) if arb_data else set()
    missing_in_yaml = referenced - yaml_keys

    if missing_in_yaml:
        return {
            "status": "FAIL",
            "missing_in_yaml": sorted(missing_in_yaml),
            "yaml_keys": sorted(yaml_keys),
        }

    return {
        "status": "PASS",
        "verified_arb_keys": sorted(referenced),
        "yaml_total_keys": len(yaml_keys),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Check 5 — web_server.py + routers endpoint signatures
# ══════════════════════════════════════════════════════════════════════════════
def check_api_endpoints() -> dict[str, Any]:
    """Verify key API endpoints exist across web_server.py + mounted routers."""
    # Endpoints in web_server.py (direct @app.xxx decorators)
    WEB_SERVER_REQUIRED = {
        "/api/send-stats",
        "/api/send",
        "/api/campaigns",
        "/api/contacts",
        "/api/rate-preview",
        "/api/arb-rates",
        "/api/history",
    }
    # Endpoints in rotation_router.py (mounted under no prefix or /api/rotation)
    ROTATION_REQUIRED = {"/today", "/progress", "/run-today", "/preview-sample"}
    # Endpoints in contacts_router.py
    CONTACTS_REQUIRED = {"", "/refresh-master", "/typo-suspects"}

    def _extract_routes(filepath: Path) -> set[str]:
        """Parse Python AST to find @app.xxx / @router.xxx decorated routes."""
        if not filepath.exists():
            return set()
        try:
            tree = ast.parse(filepath.read_text(encoding="utf-8"))
        except SyntaxError:
            return set()

        routes: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for decorator in node.decorator_list:
                # Match: @app.get("/path") or @router.post("/path")
                if not isinstance(decorator, ast.Call):
                    continue
                func = decorator.func
                if not isinstance(func, ast.Attribute):
                    continue
                if func.attr not in {"get", "post", "put", "delete", "patch"}:
                    continue
                if decorator.args and isinstance(decorator.args[0], ast.Constant):
                    routes.add(str(decorator.args[0].value))
        return routes

    web_server_path  = PROJECT_ROOT / "email_engine" / "web_server.py"
    rotation_path    = PROJECT_ROOT / "email_engine" / "api" / "routes" / "rotation_router.py"
    contacts_path    = PROJECT_ROOT / "email_engine" / "api" / "routes" / "contacts_router.py"

    ws_routes  = _extract_routes(web_server_path)
    rot_routes = _extract_routes(rotation_path)
    con_routes = _extract_routes(contacts_path)

    missing_ws  = WEB_SERVER_REQUIRED - ws_routes
    missing_rot = ROTATION_REQUIRED - rot_routes
    missing_con = CONTACTS_REQUIRED - con_routes

    if missing_ws or missing_rot or missing_con:
        result: dict[str, Any] = {"status": "FAIL"}
        if missing_ws:
            result["missing_in_web_server"] = sorted(missing_ws)
        if missing_rot:
            result["missing_in_rotation_router"] = sorted(missing_rot)
        if missing_con:
            result["missing_in_contacts_router"] = sorted(missing_con)
        return result

    return {
        "status": "PASS",
        "web_server_routes": len(ws_routes),
        "rotation_routes":   len(rot_routes),
        "contacts_routes":   len(con_routes),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Check 6 — auto_rate_builder return schema
# ══════════════════════════════════════════════════════════════════════════════
def check_rate_builder_output() -> dict[str, Any]:
    """Verify build_rate_table_for_customer returns expected keys."""
    REQUIRED_KEYS = {"routes_found", "total_rates", "html"}

    try:
        from email_engine.core.auto_rate_builder import (  # type: ignore
            build_rate_table_for_customer,
        )
    except ImportError as e:
        return {"status": "ERROR", "error": f"Cannot import auto_rate_builder: {e}"}

    try:
        result = build_rate_table_for_customer(
            pol="HPH",
            destinations="USLAX",
            markup=20,
        )
    except Exception as e:
        return {"status": "FAIL", "reason": f"Function raised: {e}"}

    if not isinstance(result, dict):
        return {"status": "FAIL", "reason": f"Expected dict, got {type(result).__name__}"}

    missing = REQUIRED_KEYS - set(result.keys())
    if missing:
        return {
            "status": "FAIL",
            "missing_keys": sorted(missing),
            "actual_keys":  sorted(result.keys()),
        }

    return {
        "status": "PASS",
        "return_keys": sorted(result.keys()),
        "routes_found": result.get("routes_found", 0),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Check 7 — email subject template placeholders
# ══════════════════════════════════════════════════════════════════════════════
def check_subject_templates() -> dict[str, Any]:
    """Verify SUBJECT_TEMPLATES only use defined placeholder names."""
    ALLOWED_PLACEHOLDERS = {"pol", "region", "week", "commodity"}

    try:
        from email_engine.core.rule_engine import SUBJECT_TEMPLATES  # type: ignore
    except ImportError as e:
        return {"status": "ERROR", "error": f"Cannot import rule_engine: {e}"}

    if not SUBJECT_TEMPLATES:
        return {"status": "FAIL", "reason": "SUBJECT_TEMPLATES is empty"}

    violations: list[dict[str, Any]] = []
    for tpl in SUBJECT_TEMPLATES:
        placeholders = set(re.findall(r"\{(\w+)\}", tpl))
        invalid = placeholders - ALLOWED_PLACEHOLDERS
        if invalid:
            violations.append({"template": tpl, "invalid_placeholders": sorted(invalid)})

    if violations:
        return {"status": "FAIL", "violations": violations}

    return {
        "status": "PASS",
        "templates_checked": len(SUBJECT_TEMPLATES),
        "allowed_placeholders": sorted(ALLOWED_PLACEHOLDERS),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Runner
# ══════════════════════════════════════════════════════════════════════════════
CHECKS = [
    ("parquet",          check_parquet_schema,      "Parquet column baseline"),
    ("cnee_v6",          check_cnee_v6_schema,       "CNEE v6 master schema"),
    ("rule_engine",      check_rule_engine_mapping,  "ARB_MAPPING completeness"),
    ("arb_yaml",         check_arb_yaml_refs,        "arb_rates.yaml references"),
    ("api_endpoints",    check_api_endpoints,        "API endpoint signatures"),
    ("rate_builder",     check_rate_builder_output,  "build_rate_table return keys"),
    ("subject_templates", check_subject_templates,   "Subject template placeholders"),
]


def _print_result(name: str, desc: str, result: dict[str, Any]) -> None:
    status  = result.get("status", "UNKNOWN")
    symbol  = SYMBOLS.get(status, "?")
    colorize = COLOR.get(status, BOLD)
    label   = colorize(f"{symbol} {status}")
    print(f"  {label:<22}  {BOLD(name):<24}  {desc}")
    if VERBOSE or status in ("FAIL", "ERROR"):
        detail = {k: v for k, v in result.items() if k != "status"}
        if detail:
            for k, v in detail.items():
                print(f"    {CYAN(k)}: {v}")


def main() -> None:
    global VERBOSE
    parser = argparse.ArgumentParser(description="Nelson Freight — data contract validator")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all check details")
    args = parser.parse_args()
    VERBOSE = args.verbose

    print()
    print(BOLD("═" * 62))
    print(BOLD("  DATA CONTRACT VALIDATION  —  Nelson Freight"))
    print(BOLD("═" * 62))
    print()

    results: dict[str, dict[str, Any]] = {}

    for name, fn, desc in CHECKS:
        try:
            results[name] = fn()
        except Exception as exc:
            results[name] = {"status": "ERROR", "error": str(exc)}
        _print_result(name, desc, results[name])

    # ── Summary ───────────────────────────────────────────────────────────────
    failures = [n for n, r in results.items() if r.get("status") == "FAIL"]
    errors   = [n for n, r in results.items() if r.get("status") == "ERROR"]
    skipped  = [n for n, r in results.items() if r.get("status") == "SKIP"]
    passed   = [n for n, r in results.items() if r.get("status") == "PASS"]

    print()
    print(BOLD("─" * 62))
    total = len(results)
    print(
        f"  {GREEN(f'{len(passed)} PASS')}  "
        f"{RED(f'{len(failures)} FAIL') if failures else '0 FAIL'}  "
        f"{YELLOW(f'{len(errors)} ERROR') if errors else '0 ERROR'}  "
        f"{YELLOW(f'{len(skipped)} SKIP') if skipped else '0 SKIP'}  "
        f"/ {total} total"
    )

    if failures or errors:
        print()
        if failures:
            print(RED(f"  FAILED checks: {', '.join(failures)}"))
        if errors:
            print(YELLOW(f"  ERROR checks:  {', '.join(errors)}"))
        print()
        sys.exit(1)

    print()
    print(GREEN(f"  All {len(passed)} active checks PASS") + (f"  ({len(skipped)} skipped)" if skipped else ""))
    print()
    sys.exit(0)


if __name__ == "__main__":
    main()
