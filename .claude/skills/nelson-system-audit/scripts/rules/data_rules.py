# -*- coding: utf-8 -*-
"""
data_rules.py — Data Layer Architecture Rules
===============================================
Checks for: JSON-as-database, direct file access outside DAL,
multiple writers, hardcoded paths, missing PostgreSQL migration.
"""
import os
import re
import glob

from architecture_rules import (
    BASE_DIR, API_DIR, BOT_DIR, EMAIL_DIR,
    JSON_DATABASE_FILES, HARDCODED_PATH_PATTERNS,
    apply_deduction, LayerScore
)


def check_json_databases(layers: dict[str, LayerScore]):
    """Detect JSON files being used as databases (read+write)."""
    search_dirs = [API_DIR, BOT_DIR, EMAIL_DIR]
    for jf in JSON_DATABASE_FILES:
        writers = []
        for sd in search_dirs:
            if not os.path.isdir(sd):
                continue
            for pyfile in glob.glob(os.path.join(sd, "**", "*.py"), recursive=True):
                try:
                    content = open(pyfile, encoding="utf-8", errors="ignore").read()
                except Exception:
                    continue
                # Check for write patterns to this JSON file
                if jf in content:
                    has_write = (
                        'json.dump' in content or
                        '"w"' in content or
                        "mode='w'" in content or
                        '.write(' in content
                    )
                    if has_write:
                        writers.append(os.path.relpath(pyfile, BASE_DIR))
        if writers:
            apply_deduction(
                layers, "json_as_database",
                title=f"JSON file '{jf}' used as database",
                detail=f"Written by: {', '.join(writers[:5])}",
                suggestion=f"Migrate {jf} to PostgreSQL table",
            )


def check_hardcoded_paths(layers: dict[str, LayerScore]):
    """Find hardcoded Windows paths that should be env variables."""
    search_dirs = [API_DIR, BOT_DIR, os.path.join(BASE_DIR, "ERP"),
                   os.path.join(BASE_DIR, "Integration")]

    for sd in search_dirs:
        if not os.path.isdir(sd):
            continue
        for pyfile in glob.glob(os.path.join(sd, "**", "*.py"), recursive=True):
            try:
                lines = open(pyfile, encoding="utf-8", errors="ignore").readlines()
            except Exception:
                continue
            for i, line in enumerate(lines, 1):
                for pattern in HARDCODED_PATH_PATTERNS:
                    if re.search(pattern, line):
                        apply_deduction(
                            layers, "hardcoded_data_path",
                            title="Hardcoded filesystem path",
                            detail=f"Line {i}: {line.strip()[:80]}",
                            file_path=os.path.relpath(pyfile, BASE_DIR),
                            line_number=i,
                            suggestion="Use os.environ or .env config",
                        )
                        break  # one per line


def check_data_access_layer(layers: dict[str, LayerScore]):
    """Check if a centralized data_access.py exists."""
    dal_path = os.path.join(API_DIR, "data_access.py")
    services_dal = os.path.join(API_DIR, "services", "data_access.py")

    if not os.path.exists(dal_path) and not os.path.exists(services_dal):
        apply_deduction(
            layers, "no_data_access_layer",
            title="No Data Access Layer found",
            detail="Missing data_access.py — modules access data directly",
            suggestion="Create data_access.py as single point of access for all data",
        )


def check_multiple_writers(layers: dict[str, LayerScore]):
    """Detect multiple modules writing to the same data file."""
    target_files = ["shipment_state.json", "quotes.json"]
    search_dirs = [API_DIR, BOT_DIR, EMAIL_DIR]

    for target in target_files:
        writers = set()
        for sd in search_dirs:
            if not os.path.isdir(sd):
                continue
            for pyfile in glob.glob(os.path.join(sd, "**", "*.py"), recursive=True):
                try:
                    content = open(pyfile, encoding="utf-8", errors="ignore").read()
                except Exception:
                    continue
                if target in content and ('json.dump' in content or '"w"' in content
                                          or 'mode="w"' in content or ".write(" in content):
                    writers.add(os.path.relpath(pyfile, BASE_DIR))
        if len(writers) > 1:
            apply_deduction(
                layers, "multiple_writers_no_lock",
                title=f"Race condition: {len(writers)} writers for {target}",
                detail=f"Writers: {', '.join(sorted(writers))}",
                suggestion="Migrate to PostgreSQL with proper transactions",
            )


def run_all(layers: dict[str, LayerScore]):
    """Run all data layer checks."""
    check_json_databases(layers)
    check_hardcoded_paths(layers)
    check_data_access_layer(layers)
    check_multiple_writers(layers)
