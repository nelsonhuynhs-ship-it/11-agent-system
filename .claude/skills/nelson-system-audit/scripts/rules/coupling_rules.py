# -*- coding: utf-8 -*-
"""
coupling_rules.py — Client Isolation & Coupling Rules
======================================================
Checks for: Bot/ERP reading files directly, WebApp bypass,
client-side business logic, cache TTL inconsistency.
"""
import os
import re
import glob

from architecture_rules import (
    BASE_DIR, BOT_DIR, WEBAPP_DIR, FORBIDDEN_IN_CLIENTS,
    apply_deduction, LayerScore
)


def check_bot_file_access(layers: dict[str, LayerScore]):
    """Detect Bot modules reading data files directly instead of via API."""
    if not os.path.isdir(BOT_DIR):
        return
    patterns = FORBIDDEN_IN_CLIENTS.get("bot", [])

    for pyfile in glob.glob(os.path.join(BOT_DIR, "*.py")):
        basename = os.path.basename(pyfile)
        # Skip archived / test files
        if basename.startswith('_') or basename.startswith('test_'):
            continue
        try:
            lines = open(pyfile, encoding="utf-8", errors="ignore").readlines()
        except Exception:
            continue

        for i, line in enumerate(lines, 1):
            if line.strip().startswith('#'):
                continue
            for pattern in patterns:
                if re.search(pattern, line):
                    apply_deduction(
                        layers, "bot_bypasses_api",
                        title=f"Bot reads data directly: {basename}",
                        detail=f"Line {i}: {line.strip()[:70]}",
                        file_path=f"TelegramBot/{basename}",
                        line_number=i,
                        suggestion="Replace with API call via api_client.py",
                    )
                    break


def check_webapp_bypass(layers: dict[str, LayerScore]):
    """Check if WebApp frontend accesses backend data directly."""
    webapp_src = os.path.join(WEBAPP_DIR, "src")
    if not os.path.isdir(webapp_src):
        return
    patterns = FORBIDDEN_IN_CLIENTS.get("webapp", [])

    for tsfile in glob.glob(os.path.join(webapp_src, "**", "*.ts*"), recursive=True):
        try:
            content = open(tsfile, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        for pattern in patterns:
            if re.search(pattern, content):
                apply_deduction(
                    layers, "client_reads_file",
                    title=f"WebApp directly accesses filesystem",
                    detail=f"Pattern: {pattern}",
                    file_path=os.path.relpath(tsfile, BASE_DIR),
                    suggestion="All data access should go through /api/* endpoints",
                )


def check_cache_consistency(layers: dict[str, LayerScore]):
    """Detect inconsistent cache TTLs between Bot and API."""
    cache_ttls = {}

    # Check Bot cache
    for pyfile in glob.glob(os.path.join(BOT_DIR, "*.py")):
        try:
            content = open(pyfile, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        match = re.search(r'CACHE_TTL\w*\s*=\s*(\d+)', content)
        if match:
            basename = os.path.basename(pyfile)
            cache_ttls[f"Bot/{basename}"] = int(match.group(1))

    # Check API cache
    api_server = os.path.join(BASE_DIR, "api", "server.py")
    if os.path.exists(api_server):
        try:
            content = open(api_server, encoding="utf-8", errors="ignore").read()
        except Exception:
            content = ""
        match = re.search(r'CACHE_TTL\w*\s*=\s*(\d+)', content)
        if match:
            cache_ttls["API/server.py"] = int(match.group(1))

    # Check for inconsistency
    if len(cache_ttls) > 1:
        values = list(cache_ttls.values())
        if max(values) > min(values) * 2:  # More than 2x difference
            details = ", ".join(f"{k}: {v}s" for k, v in cache_ttls.items())
            apply_deduction(
                layers, "client_has_business_logic",
                title="Inconsistent cache TTLs — phantom data risk",
                detail=f"Cache TTLs differ significantly: {details}",
                suggestion="Use single cache via API, or align TTLs",
            )


def check_erp_direct_access(layers: dict[str, LayerScore]):
    """Check if ERP scripts access Parquet/JSON directly."""
    erp_scripts = os.path.join(BASE_DIR, "ERP", "scripts")
    if not os.path.isdir(erp_scripts):
        return

    for pyfile in glob.glob(os.path.join(erp_scripts, "*.py")):
        try:
            content = open(pyfile, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        if 'pd.read_parquet(' in content:
            apply_deduction(
                layers, "erp_direct_file_access",
                title=f"ERP script reads Parquet directly: {os.path.basename(pyfile)}",
                detail="Should use API endpoint /api/rates/matrix instead",
                file_path=os.path.relpath(pyfile, BASE_DIR),
                suggestion="Create erp_api_bridge.py that calls API instead of reading files",
            )


def run_all(layers: dict[str, LayerScore]):
    """Run all coupling checks."""
    check_bot_file_access(layers)
    check_webapp_bypass(layers)
    check_cache_consistency(layers)
    check_erp_direct_access(layers)
