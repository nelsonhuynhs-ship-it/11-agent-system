# -*- coding: utf-8 -*-
"""
service_rules.py — Service Layer Architecture Rules
=====================================================
Checks for: cross-service DB access, god functions,
circular dependencies, and service boundary clarity.
"""
import os
import re
import ast
import glob

from architecture_rules import (
    API_DIR, BASE_DIR, apply_deduction, LayerScore
)


def check_god_functions(layers: dict[str, LayerScore]):
    """Find functions exceeding 100 lines in API modules."""
    if not os.path.isdir(API_DIR):
        return
    for pyfile in glob.glob(os.path.join(API_DIR, "**", "*.py"), recursive=True):
        try:
            source = open(pyfile, encoding="utf-8", errors="ignore").read()
            tree = ast.parse(source)
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body_lines = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 0
                if body_lines > 100:
                    apply_deduction(
                        layers, "god_function",
                        title=f"God function: {node.name}() is {body_lines} lines",
                        detail=f"Functions >100 lines are hard to test and maintain",
                        file_path=os.path.relpath(pyfile, BASE_DIR),
                        line_number=node.lineno,
                        suggestion="Split into smaller helper functions",
                    )


def check_circular_imports(layers: dict[str, LayerScore]):
    """Detect potential circular import patterns in API modules."""
    if not os.path.isdir(API_DIR):
        return
    imports_map: dict[str, set] = {}

    for pyfile in glob.glob(os.path.join(API_DIR, "*.py")):
        module_name = os.path.splitext(os.path.basename(pyfile))[0]
        try:
            source = open(pyfile, encoding="utf-8", errors="ignore").read()
            tree = ast.parse(source)
        except Exception:
            continue

        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
        imports_map[module_name] = imports

    # Detect cycles
    for mod_a, deps_a in imports_map.items():
        for mod_b in deps_a:
            if mod_b in imports_map and mod_a in imports_map.get(mod_b, set()):
                apply_deduction(
                    layers, "circular_dependency",
                    title=f"Circular import: {mod_a} ↔ {mod_b}",
                    detail=f"{mod_a} imports {mod_b} and {mod_b} imports {mod_a}",
                    suggestion="Extract shared logic into a separate module",
                )


def check_cross_service_access(layers: dict[str, LayerScore]):
    """Check if service modules directly access other services' data."""
    # Service modules reading other services' files directly
    service_files = {
        "quote": ["quote_store.py", "quote_intelligence.py"],
        "email": ["email_event_engine.py", "email_scanner.py"],
        "shipment": [],  # shipment is managed via quote_store currently
    }

    for service, files in service_files.items():
        for f in files:
            fpath = os.path.join(API_DIR, f)
            if not os.path.exists(fpath):
                continue
            try:
                content = open(fpath, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            # Check if this service reads another service's data file
            other_files_map = {
                "quote": ["shipment_state.json", "outlook_dataset.json"],
                "email": ["quotes.json"],
                "shipment": ["quotes.json"],
            }
            for other_file in other_files_map.get(service, []):
                if other_file in content and ("open(" in content or "json.load" in content):
                    apply_deduction(
                        layers, "cross_service_db_access",
                        title=f"{f} directly accesses {other_file}",
                        detail=f"Service '{service}' reads data belonging to another service",
                        file_path=f"api/{f}",
                        suggestion=f"Use API call or data_access.py instead of direct file read",
                    )


def run_all(layers: dict[str, LayerScore]):
    """Run all service layer checks."""
    check_god_functions(layers)
    check_circular_imports(layers)
    check_cross_service_access(layers)
