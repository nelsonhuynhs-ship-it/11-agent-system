# -*- coding: utf-8 -*-
"""
api_rules.py — API Layer Architecture Rules
=============================================
Checks for: monolith server, large files, missing error handlers,
input validation, and target API structure compliance.
"""
import os
import re
import glob

from architecture_rules import (
    API_DIR, BASE_DIR, MAX_FILE_LINES, TARGET_API_STRUCTURE,
    apply_deduction, LayerScore
)


def check_monolith_server(layers: dict[str, LayerScore]):
    """Check if server.py exceeds target line count (should be split)."""
    server_path = os.path.join(API_DIR, "server.py")
    if not os.path.exists(server_path):
        return
    try:
        line_count = sum(1 for _ in open(server_path, encoding="utf-8", errors="ignore"))
    except Exception:
        return

    max_lines = MAX_FILE_LINES.get("server.py", 300)
    if line_count > max_lines:
        apply_deduction(
            layers, "monolith_server",
            title=f"server.py is monolith ({line_count:,} lines)",
            detail=f"Target: <{max_lines} lines. Currently {line_count:,} lines with all endpoints in 1 file.",
            file_path="api/server.py",
            suggestion="Split into APIRouter modules: rate_router, quote_router, shipment_router, etc.",
        )


def check_large_files(layers: dict[str, LayerScore]):
    """Find Python files exceeding line limits."""
    search_dirs = [API_DIR, os.path.join(BASE_DIR, "ERP", "scripts")]
    default_max = MAX_FILE_LINES.get("default", 500)

    for sd in search_dirs:
        if not os.path.isdir(sd):
            continue
        for pyfile in glob.glob(os.path.join(sd, "**", "*.py"), recursive=True):
            basename = os.path.basename(pyfile)
            max_lines = MAX_FILE_LINES.get(basename, default_max)
            try:
                line_count = sum(1 for _ in open(pyfile, encoding="utf-8", errors="ignore"))
            except Exception:
                continue

            if line_count > max_lines:
                apply_deduction(
                    layers, "file_too_large",
                    title=f"{basename} exceeds {max_lines} line limit ({line_count} lines)",
                    detail=f"Large files are harder to maintain and test",
                    file_path=os.path.relpath(pyfile, BASE_DIR),
                    suggestion=f"Consider splitting into smaller modules",
                )


def check_error_handling(layers: dict[str, LayerScore]):
    """Check API endpoints for missing error handling."""
    server_path = os.path.join(API_DIR, "server.py")
    if not os.path.exists(server_path):
        return
    try:
        content = open(server_path, encoding="utf-8", errors="ignore").read()
    except Exception:
        return

    # Count endpoints vs try/except blocks
    endpoint_count = len(re.findall(r'@app\.(get|post|put|patch|delete)\(', content))
    try_count = len(re.findall(r'\btry\s*:', content))

    if endpoint_count > 0 and try_count < endpoint_count * 0.5:
        apply_deduction(
            layers, "no_error_handler",
            title=f"Insufficient error handling in API ({try_count} try blocks for {endpoint_count} endpoints)",
            detail="Less than 50% of endpoints have try/except",
            file_path="api/server.py",
            suggestion="Add try/except with proper HTTPException responses to all endpoints",
        )


def check_target_structure(layers: dict[str, LayerScore]):
    """Check if API has been split into target structure."""
    missing = []
    for target_file, purpose in TARGET_API_STRUCTURE.items():
        full_path = os.path.join(API_DIR, target_file)
        if not os.path.exists(full_path):
            missing.append(f"{target_file} ({purpose})")

    if missing and len(missing) > len(TARGET_API_STRUCTURE) * 0.5:
        apply_deduction(
            layers, "missing_service_boundary",
            title=f"Target API structure not yet implemented ({len(missing)} files missing)",
            detail=f"Missing: {', '.join(missing[:5])}{'...' if len(missing) > 5 else ''}",
            suggestion="Gradually split server.py into target router structure",
        )


def run_all(layers: dict[str, LayerScore]):
    """Run all API layer checks."""
    check_monolith_server(layers)
    check_large_files(layers)
    check_error_handling(layers)
    check_target_structure(layers)
