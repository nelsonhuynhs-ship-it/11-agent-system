# -*- coding: utf-8 -*-
"""
tech_debt_scanner.py — Technical Debt Detection
=================================================
Scans codebase for: large files, duplicate code patterns,
legacy storage, unused modules, dead code, missing tests.
"""
import os
import re
import glob
import ast
from dataclasses import dataclass, field

from architecture_rules import BASE_DIR, API_DIR, BOT_DIR, Severity


@dataclass
class DebtItem:
    category:   str
    severity:   Severity
    title:      str
    detail:     str
    file_path:  str = ""
    suggestion: str = ""


@dataclass
class TechDebtReport:
    items: list[DebtItem] = field(default_factory=list)

    @property
    def critical_items(self) -> list[DebtItem]:
        return [i for i in self.items if i.severity == Severity.CRITICAL]

    @property
    def high_items(self) -> list[DebtItem]:
        return [i for i in self.items if i.severity == Severity.HIGH]

    @property
    def total_count(self) -> int:
        return len(self.items)

    @property
    def debt_score(self) -> float:
        """0=no debt, 10=maximum debt. Lower is better."""
        weights = {Severity.CRITICAL: 3.0, Severity.HIGH: 1.5,
                   Severity.MEDIUM: 0.5, Severity.LOW: 0.1}
        raw = sum(weights.get(i.severity, 0) for i in self.items)
        return min(10.0, round(raw, 1))

    def add(self, item: DebtItem):
        self.items.append(item)


def scan_large_files(report: TechDebtReport):
    """Find excessively large Python files."""
    thresholds = {"bot_v5.py": 2000, "server.py": 500, "default": 500}
    search_dirs = [API_DIR, BOT_DIR, os.path.join(BASE_DIR, "ERP", "scripts")]

    for sd in search_dirs:
        if not os.path.isdir(sd):
            continue
        for pyfile in glob.glob(os.path.join(sd, "**", "*.py"), recursive=True):
            basename = os.path.basename(pyfile)
            if basename.startswith('_'):
                continue
            threshold = thresholds.get(basename, thresholds["default"])
            try:
                line_count = sum(1 for _ in open(pyfile, encoding="utf-8", errors="ignore"))
            except Exception:
                continue
            if line_count > threshold:
                severity = Severity.CRITICAL if line_count > 2000 else (
                    Severity.HIGH if line_count > 1000 else Severity.MEDIUM)
                report.add(DebtItem(
                    category="Large File",
                    severity=severity,
                    title=f"{basename}: {line_count:,} lines (limit: {threshold})",
                    detail=f"Large files increase maintenance cost and merge conflicts",
                    file_path=os.path.relpath(pyfile, BASE_DIR),
                    suggestion="Split into focused modules with clear responsibilities",
                ))


def scan_duplicate_regex(report: TechDebtReport):
    """Find duplicate regex patterns across modules."""
    pattern_locations: dict[str, list[str]] = {}
    search_dirs = [API_DIR, BOT_DIR]

    for sd in search_dirs:
        if not os.path.isdir(sd):
            continue
        for pyfile in glob.glob(os.path.join(sd, "**", "*.py"), recursive=True):
            try:
                content = open(pyfile, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            # Find regex patterns (r'...' or r"...")
            regexes = re.findall(r"re\.(?:compile|search|findall|match)\(['\"](.{10,}?)['\"]", content)
            for rx in regexes:
                if rx not in pattern_locations:
                    pattern_locations[rx] = []
                pattern_locations[rx].append(os.path.relpath(pyfile, BASE_DIR))

    for rx, files in pattern_locations.items():
        if len(files) > 1:
            unique_dirs = set(f.split(os.sep)[0] for f in files)
            if len(unique_dirs) > 1:  # Duplicated across different modules
                report.add(DebtItem(
                    category="Duplicate Regex",
                    severity=Severity.MEDIUM,
                    title=f"Regex pattern used in {len(files)} files",
                    detail=f"Pattern: {rx[:50]}... in {', '.join(files[:3])}",
                    suggestion="Extract into shared constants module",
                ))


def scan_legacy_json_storage(report: TechDebtReport):
    """Find JSON files still used as mutable data storage."""
    json_databases = ["quotes.json", "shipment_state.json",
                      "outlook_dataset.json", "sync_state.json"]

    for jf in json_databases:
        # Check if file exists
        possible_paths = [
            os.path.join(API_DIR, "data", jf),
            os.path.join(BASE_DIR, jf),
            os.path.join(os.environ.get("NELSON_EMAIL_DIR", r"D:\NELSON\email_engine"), jf),
        ]
        for p in possible_paths:
            if os.path.exists(p):
                try:
                    size = os.path.getsize(p)
                except Exception:
                    size = 0
                report.add(DebtItem(
                    category="Legacy Storage",
                    severity=Severity.CRITICAL if size > 10000 else Severity.HIGH,
                    title=f"JSON database still in use: {jf}",
                    detail=f"Size: {size:,} bytes at {os.path.relpath(p, BASE_DIR) if p.startswith(BASE_DIR) else p}",
                    file_path=p,
                    suggestion=f"Migrate to PostgreSQL table",
                ))
                break


def scan_unused_imports(report: TechDebtReport):
    """Find Python files with potentially unused imports (heuristic)."""
    for pyfile in glob.glob(os.path.join(API_DIR, "*.py")):
        try:
            source = open(pyfile, encoding="utf-8", errors="ignore").read()
            tree = ast.parse(source)
        except Exception:
            continue

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split('.')[0]
                    imports.append((name, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                if node.names:
                    for alias in node.names:
                        name = alias.asname or alias.name
                        imports.append((name, node.lineno))

        # Heuristic: check if imported name appears elsewhere in source
        unused = []
        for name, lineno in imports:
            if name == '*':
                continue
            # Count occurrences (excluding the import line itself)
            count = source.count(name)
            if count <= 1:
                unused.append(name)

        if len(unused) > 3:
            report.add(DebtItem(
                category="Unused Imports",
                severity=Severity.LOW,
                title=f"{os.path.basename(pyfile)}: {len(unused)} potentially unused imports",
                detail=f"Unused: {', '.join(unused[:5])}{'...' if len(unused) > 5 else ''}",
                file_path=os.path.relpath(pyfile, BASE_DIR),
                suggestion="Remove unused imports to reduce coupling",
            ))


def scan_missing_tests(report: TechDebtReport):
    """Check for core modules without test files."""
    core_modules = [
        "quote_store.py", "quote_intelligence.py",
        "email_event_engine.py", "email_scanner.py",
    ]
    test_dir = os.path.join(API_DIR, "tests")
    test_files_exist = os.path.isdir(test_dir)

    for module in core_modules:
        module_path = os.path.join(API_DIR, module)
        if not os.path.exists(module_path):
            continue
        test_name = f"test_{module}"
        test_path = os.path.join(test_dir, test_name) if test_files_exist else None
        alt_test = os.path.join(API_DIR, test_name)

        if not (test_path and os.path.exists(test_path)) and not os.path.exists(alt_test):
            report.add(DebtItem(
                category="Missing Tests",
                severity=Severity.MEDIUM,
                title=f"No test file for {module}",
                detail=f"Critical module without automated tests",
                file_path=f"api/{module}",
                suggestion=f"Create {test_name} with basic CRUD/logic tests",
            ))


def run_tech_debt_scan() -> TechDebtReport:
    """Run all technical debt scanning checks."""
    report = TechDebtReport()
    scan_large_files(report)
    scan_duplicate_regex(report)
    scan_legacy_json_storage(report)
    scan_unused_imports(report)
    scan_missing_tests(report)
    return report
