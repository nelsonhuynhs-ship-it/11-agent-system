# -*- coding: utf-8 -*-
"""
drift_detector.py — Architecture Drift Detection
==================================================
Scans the entire codebase to find patterns that violate
the Architecture Blueprint. Reports drift severity.
"""
import os
import re
import glob
from dataclasses import dataclass, field

from architecture_rules import (
    BASE_DIR, API_DIR, BOT_DIR, WEBAPP_DIR, EMAIL_DIR,
    FORBIDDEN_IN_CLIENTS, JSON_DATABASE_FILES,
    HARDCODED_PATH_PATTERNS, Severity
)


@dataclass
class DriftViolation:
    category:    str
    severity:    Severity
    file_path:   str
    line_number: int
    description: str
    pattern:     str = ""
    suggestion:  str = ""


@dataclass
class DriftReport:
    violations: list[DriftViolation] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == Severity.HIGH)

    @property
    def medium_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == Severity.MEDIUM)

    @property
    def total_count(self) -> int:
        return len(self.violations)

    def add(self, violation: DriftViolation):
        self.violations.append(violation)


def _scan_files(directory: str, extensions: list[str] = None) -> list[str]:
    """Recursively find files in directory."""
    if extensions is None:
        extensions = [".py"]
    result = []
    if not os.path.isdir(directory):
        return result
    for ext in extensions:
        result.extend(glob.glob(os.path.join(directory, "**", f"*{ext}"), recursive=True))
    return result


def detect_bot_drift(report: DriftReport):
    """Detect Bot modules accessing data outside API."""
    patterns_with_desc = [
        (r'pd\.read_parquet\(',       "Bot loading Parquet directly"),
        (r'json\.load\(',             "Bot loading JSON file directly"),
        (r'openpyxl\.load_workbook\(', "Bot reading Excel directly"),
        (r'shipment_state\.json',     "Bot referencing shipment_state.json"),
        (r'quotes\.json',            "Bot referencing quotes.json"),
        (r'outlook_dataset\.json',   "Bot referencing outlook_dataset.json"),
    ]

    for pyfile in _scan_files(BOT_DIR):
        basename = os.path.basename(pyfile)
        if basename.startswith('_') or basename.startswith('test_'):
            continue
        # Allow api_client.py (it's the bridge)
        if basename == 'api_client.py':
            continue
        try:
            lines = open(pyfile, encoding="utf-8", errors="ignore").readlines()
        except Exception:
            continue

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            for pattern, desc in patterns_with_desc:
                if re.search(pattern, line):
                    report.add(DriftViolation(
                        category="Client Isolation",
                        severity=Severity.CRITICAL,
                        file_path=os.path.relpath(pyfile, BASE_DIR),
                        line_number=i,
                        description=desc,
                        pattern=pattern,
                        suggestion="Replace with API call via api_client.py",
                    ))
                    break  # one finding per line


def detect_hardcoded_paths(report: DriftReport):
    """Find hardcoded Windows paths across codebase."""
    search_dirs = [API_DIR, BOT_DIR, EMAIL_DIR,
                   os.path.join(BASE_DIR, "ERP", "scripts"),
                   os.path.join(BASE_DIR, "Integration")]

    for sd in search_dirs:
        for pyfile in _scan_files(sd):
            try:
                lines = open(pyfile, encoding="utf-8", errors="ignore").readlines()
            except Exception:
                continue
            for i, line in enumerate(lines, 1):
                if line.strip().startswith('#'):
                    continue
                for pattern in HARDCODED_PATH_PATTERNS:
                    if re.search(pattern, line):
                        report.add(DriftViolation(
                            category="Configuration",
                            severity=Severity.MEDIUM,
                            file_path=os.path.relpath(pyfile, BASE_DIR),
                            line_number=i,
                            description=f"Hardcoded path: {line.strip()[:60]}",
                            pattern=pattern,
                            suggestion="Use os.environ or .env config",
                        ))
                        break


def detect_json_database_usage(report: DriftReport):
    """Find modules still using JSON files as mutable databases."""
    search_dirs = [API_DIR, BOT_DIR, EMAIL_DIR]

    for jf in JSON_DATABASE_FILES:
        for sd in search_dirs:
            for pyfile in _scan_files(sd):
                try:
                    content = open(pyfile, encoding="utf-8", errors="ignore").read()
                except Exception:
                    continue
                if jf in content and ('json.dump' in content or '"w"' in content):
                    report.add(DriftViolation(
                        category="Data Layer",
                        severity=Severity.CRITICAL,
                        file_path=os.path.relpath(pyfile, BASE_DIR),
                        line_number=0,
                        description=f"Writes to JSON database: {jf}",
                        suggestion=f"Migrate {jf} to PostgreSQL",
                    ))


def detect_duplicate_logic(report: DriftReport):
    """Find duplicate function definitions across Bot and API."""
    function_map: dict[str, list[str]] = {}  # func_name -> [files]

    for sd in [API_DIR, BOT_DIR]:
        for pyfile in _scan_files(sd):
            try:
                content = open(pyfile, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            funcs = re.findall(r'def\s+(\w+)\s*\(', content)
            for f in funcs:
                if f.startswith('_') or f in ('__init__', 'main', 'run', 'test'):
                    continue
                key = f
                if key not in function_map:
                    function_map[key] = []
                function_map[key].append(os.path.relpath(pyfile, BASE_DIR))

    for func_name, file_list in function_map.items():
        # Only flag if same function appears in BOTH bot and api directories
        dirs = set(f.split(os.sep)[0] for f in file_list)
        if len(dirs) > 1 and len(file_list) > 1:
            report.add(DriftViolation(
                category="Duplication",
                severity=Severity.HIGH,
                file_path=file_list[0],
                line_number=0,
                description=f"Duplicate function '{func_name}' across: {', '.join(file_list[:3])}",
                suggestion="Extract shared logic into a common module or use API calls",
            ))


def run_drift_detection() -> DriftReport:
    """Run all drift detection checks."""
    report = DriftReport()
    detect_bot_drift(report)
    detect_hardcoded_paths(report)
    detect_json_database_usage(report)
    detect_duplicate_logic(report)
    return report
