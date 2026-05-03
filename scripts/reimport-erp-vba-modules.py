"""
reimport-erp-vba-modules.py — Re-import updated .bas files into ERP_Master_v14.xlsm

Use after editing any of the exported .bas files in OneDrive ERP folder.
Replaces existing modules in the xlsm's VBA project (VBE Trust required).

Trust required: File > Options > Trust Center > Trust Center Settings >
Macro Settings > ENABLE "Trust access to the VBA project object model".

Usage:
    python scripts/reimport-erp-vba-modules.py

Modules re-imported (by default, all .bas files in ERP folder):
    erp-v14-ribbon-callbacks.bas
    erp-v14-jobs-automation.bas
    erp-v14-preset-dryreefer.bas
    erp-v14-quick-wins.bas
    CostBreakdown.bas
"""
from __future__ import annotations

import sys
from pathlib import Path

ERP_FOLDER = Path("D:/OneDrive/NelsonData/erp")
XLSM = ERP_FOLDER / "ERP_Master_v14.xlsm"
BAS_FILES = [
    "erp-v14-ribbon-callbacks.bas",
    "erp-v14-jobs-automation.bas",
    "erp-v14-preset-dryreefer.bas",
    "erp-v14-quick-wins.bas",
    "CostBreakdown.bas",
    "erp-v14-test-e2e.bas",
]


def module_name_from_bas(bas_path: Path) -> str:
    """Read the Attribute VB_Name from the .bas file header."""
    with open(bas_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line.startswith("Attribute VB_Name"):
                # Attribute VB_Name = "ModuleName"
                return line.split("=", 1)[1].strip().strip('"')
    # Fallback: use filename stem
    return bas_path.stem.replace("-", "_").replace(" ", "_")


def main() -> int:
    if not XLSM.exists():
        print(f"[ERR] xlsm not found: {XLSM}")
        return 2
    missing = [f for f in BAS_FILES if not (ERP_FOLDER / f).exists()]
    if missing:
        print(f"[WARN] missing .bas files (skipped): {missing}")

    import win32com.client
    import pywintypes

    print(f"Opening {XLSM}...")
    excel = win32com.client.Dispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    try:
        wb = excel.Workbooks.Open(str(XLSM))
    except pywintypes.com_error as exc:
        print(f"[ERR] cannot open xlsm: {exc}")
        excel.Quit()
        return 3

    try:
        vbp = wb.VBProject
    except pywintypes.com_error:
        print(
            "[ERR] VBProject access denied.\n"
            "  Enable: File > Options > Trust Center > Trust Center Settings >\n"
            "          Macro Settings > 'Trust access to the VBA project object model'."
        )
        wb.Close(SaveChanges=False)
        excel.Quit()
        return 4

    replaced = 0
    for bas_name in BAS_FILES:
        bas_path = ERP_FOLDER / bas_name
        if not bas_path.exists():
            continue
        mod_name = module_name_from_bas(bas_path)
        print(f"  [{bas_name}] target module: {mod_name}")

        # Remove existing module if present
        for comp in list(vbp.VBComponents):
            if comp.Name == mod_name:
                try:
                    vbp.VBComponents.Remove(comp)
                    print(f"    removed existing module {mod_name}")
                except pywintypes.com_error as exc:
                    print(f"    [WARN] could not remove old {mod_name}: {exc}")

        # Import the fresh .bas
        try:
            vbp.VBComponents.Import(str(bas_path))
            print(f"    imported {bas_name} as {mod_name}  OK")
            replaced += 1
        except pywintypes.com_error as exc:
            print(f"    [ERR] import failed for {bas_name}: {exc}")

    print(f"Saving workbook...")
    wb.Save()
    wb.Close(SaveChanges=False)
    excel.Quit()

    print(f"Done. Re-imported {replaced}/{len(BAS_FILES)} modules.")
    return 0 if replaced > 0 else 5


if __name__ == "__main__":
    sys.exit(main())
