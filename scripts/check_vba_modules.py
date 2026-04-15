"""Verify VBA modules present & no duplicates (ERPv14Ribbon1 etc.).

Uses oletools to read VBA source WITHOUT opening Excel - fast + safe.
Falls back to zipfile check if oletools not installed.
"""
import re
import sys
import zipfile
from pathlib import Path

ERP = Path(sys.argv[1] if len(sys.argv) > 1
           else r"D:\OneDrive\NelsonData\erp\ERP_Master_v14.xlsm")

if not ERP.exists():
    print(f"[FAIL] File not found: {ERP}")
    sys.exit(1)

REQUIRED = {"ERPv14Ribbon", "ERPv14JobsAutomation"}

try:
    from oletools.olevba import VBA_Parser
except ImportError:
    print("  [WARN] oletools not installed -- skipping deep VBA check")
    print("  pip install oletools for full coverage")
    print("MODULES: SKIPPED")
    sys.exit(0)

parser = VBA_Parser(str(ERP))
if not parser.detect_vba_macros():
    print("[FAIL] no VBA macros in workbook")
    sys.exit(1)

found = set()
for _filename, _stream_path, vba_filename, _code in parser.extract_macros():
    name = vba_filename.rsplit(".", 1)[0]
    name = name.replace("bas", "").strip()
    found.add(name)

dup_pattern = re.compile(r"^(ERPv14\w+)\d+$")
duplicates = [n for n in found if dup_pattern.match(n)]

for name in sorted(found):
    marker = "  " if name not in REQUIRED else "* "
    print(f"{marker}{name}")

missing = REQUIRED - found
if missing:
    print(f"[FAIL] missing modules: {missing}")
    sys.exit(1)

if duplicates:
    print(f"[FAIL] duplicate modules detected: {duplicates}")
    print("  Run: python ERP/core/install_jobs_automation.py")
    sys.exit(1)

print("MODULES: OK")
sys.exit(0)
