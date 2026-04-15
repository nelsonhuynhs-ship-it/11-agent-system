"""Verify ERP xlsm has customUI14.xml + vbaProject.bin intact."""
import sys
import zipfile
from pathlib import Path

ERP = Path(sys.argv[1] if len(sys.argv) > 1
           else r"D:\OneDrive\NelsonData\erp\ERP_Master_v14.xlsm")

if not ERP.exists():
    print(f"[FAIL] File not found: {ERP}")
    sys.exit(1)

with zipfile.ZipFile(ERP) as z:
    names = set(z.namelist())
    has_ui = "customUI/customUI14.xml" in names
    has_vba = "xl/vbaProject.bin" in names

print(f"  customUI14.xml : {'OK' if has_ui else 'MISSING'}")
print(f"  vbaProject.bin : {'OK' if has_vba else 'MISSING'}")

if not (has_ui and has_vba):
    print("[FAIL] ribbon or VBA missing -- re-inject CustomUI_v14.xml")
    sys.exit(1)

print("STRUCTURE: OK")
sys.exit(0)
