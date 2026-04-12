"""Re-import updated .bas files into ERP_Master_v14.xlsm.

Why this exists: VBA modules in the xlsm are binary-embedded. Editing the
`.bas` text files on OneDrive does NOT propagate to the live xlsm until
someone opens the workbook in Excel VBE and re-imports. This script
automates that step via xlwings / win32com.

Requires: Excel setting "Trust access to the VBA project object model"
ENABLED. If disabled, the import call raises an AccessError — fix in:
  File ->Options ->Trust Center ->Trust Center Settings ->Macro Settings →
  [x] Trust access to the VBA project object model

Usage:
    python scripts/reimport-erp-vba.py
    python scripts/reimport-erp-vba.py --xlsm path/to/ERP_Master_v14.xlsm
"""
from __future__ import annotations

import argparse
import gc
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Defaults ────────────────────────────────────────────────────────────────
MASTER_XLSM = Path("D:/OneDrive/NelsonData/erp/ERP_Master_v14.xlsm")
BAS_DIR = Path("D:/OneDrive/NelsonData/erp")
BACKUP_DIR = Path("D:/OneDrive/NelsonData/pricing/_backup/xlsm-reimport")

# VBA module name ->.bas file mapping (module name must match `Attribute VB_Name`)
MODULES = {
    "ERPv14Core":   "erp-v14-quick-wins.bas",
    "ERPv14Ribbon": "erp-v14-ribbon-callbacks.bas",
    "ERPv14Preset": "erp-v14-preset-dryreefer.bas",
    "CostBreakdown": "CostBreakdown.bas",
}

# ThisWorkbook event handler text (P1 — sheet activate auto-refresh).
# Injected into the xlsm's ThisWorkbook code module after Module imports.
# Idempotent: skipped if Workbook_SheetActivate already present.
THISWORKBOOK_EVENT_FILE = BAS_DIR / "erp-v14-thisworkbook.txt"
THISWORKBOOK_EVENT_MARKER = "Private Sub Workbook_SheetActivate"


def reinject_customui(xlsm_path: Path) -> bool:
    """Re-inject CustomUI14 ribbon XML into xlsm AFTER xlwings save.

    xlwings/Excel COM strips the customUI14 ZIP part on save (Excel doesn't
    know about 3rd-party ribbon extensibility parts injected via Python).
    Without this, the custom Pricing+Operations tabs disappear from the
    ribbon — Nelson sees only standard Excel tabs.

    Calls customui_utils.ensure_customui() which checks + restores in place.
    Returns True if injected/already-ok, False on error.
    """
    customui_xml = xlsm_path.parent / "CustomUI_v14.xml"
    customui_utils_py = xlsm_path.parent / "customui_utils.py"

    if not customui_xml.exists():
        print(f"[skip] CustomUI XML source not found at {customui_xml}")
        return False
    if not customui_utils_py.exists():
        print(f"[skip] customui_utils.py not found at {customui_utils_py}")
        return False

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("customui_utils", customui_utils_py)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod.ensure_customui(str(xlsm_path), str(customui_xml))
        if result.get("injected"):
            print(f"[customui] injected ribbon XML ->{xlsm_path.name}")
            return True
        if result.get("already_ok"):
            print(f"[customui] ribbon XML already present, no change")
            return True
        print(f"[ERROR] customui injection failed: {result.get('error')}")
        return False
    except Exception as e:
        print(f"[ERROR] Failed to reinject CustomUI: {e}")
        return False


def inject_thisworkbook_event(vbp) -> bool:
    """Inject the Workbook_SheetActivate event into ThisWorkbook code module.

    Idempotent: if the event sub already exists in the module text, skip.
    Returns True if injected, False if skipped.
    """
    if not THISWORKBOOK_EVENT_FILE.exists():
        print(f"[skip] no ThisWorkbook event file at {THISWORKBOOK_EVENT_FILE.name}")
        return False

    new_code = THISWORKBOOK_EVENT_FILE.read_text(encoding="utf-8")

    try:
        # ThisWorkbook is a Document component, accessed by name
        twb = vbp.VBComponents("ThisWorkbook")
        cm = twb.CodeModule
        existing = cm.Lines(1, cm.CountOfLines) if cm.CountOfLines > 0 else ""
    except Exception as e:
        print(f"[ERROR] Cannot access ThisWorkbook module: {e}")
        return False

    if THISWORKBOOK_EVENT_MARKER in existing:
        print("[skip] Workbook_SheetActivate already present in ThisWorkbook")
        return False

    # Append our event handler at the bottom of ThisWorkbook
    try:
        cm.AddFromString(new_code)
        print(f"[inject] Workbook_SheetActivate ->ThisWorkbook ({len(new_code.splitlines())} lines)")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to inject ThisWorkbook event: {e}")
        return False


def _backup_xlsm(src: Path) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = BACKUP_DIR / f"{src.stem}-{ts}{src.suffix}"
    shutil.copy2(src, dst)
    print(f"[backup] {src.name} ->{dst}")
    return dst


def reimport_modules(xlsm_path: Path, bas_dir: Path) -> int:
    """Re-import each .bas listed in MODULES. Returns module count imported."""
    import xlwings as xw  # lazy import so --help works without xlwings

    if not xlsm_path.exists():
        print(f"[ERROR] xlsm not found: {xlsm_path}", file=sys.stderr)
        return 1

    _backup_xlsm(xlsm_path)

    print(f"[open] starting headless Excel for {xlsm_path.name}")
    with xw.App(visible=False, add_book=False) as app:
        app.display_alerts = False
        wb = app.books.open(str(xlsm_path), update_links=False)
        try:
            # Access VBA project object model (requires user trust setting)
            try:
                vbp = wb.api.VBProject
            except Exception as e:
                print(
                    "[ERROR] Cannot access VBProject. Enable Excel setting:\n"
                    "  File ->Options ->Trust Center ->Trust Center Settings →\n"
                    "  Macro Settings ->[x] Trust access to the VBA project object model\n"
                    f"Inner error: {e}",
                    file=sys.stderr,
                )
                return 2

            components = vbp.VBComponents
            imported = 0
            for module_name, bas_filename in MODULES.items():
                bas_path = bas_dir / bas_filename
                if not bas_path.exists():
                    print(f"[skip] {bas_filename} not found, skipping")
                    continue

                # Remove existing module if present, then import fresh
                try:
                    existing = components(module_name)
                    components.Remove(existing)
                    print(f"[remove] existing module: {module_name}")
                except Exception:
                    # Module didn't exist or couldn't be removed — continue
                    pass

                gc.collect()
                time.sleep(0.1)

                try:
                    components.Import(str(bas_path))
                    print(f"[import] {bas_filename} ->module {module_name}")
                    imported += 1
                except Exception as e:
                    print(f"[ERROR] Import failed for {bas_filename}: {e}", file=sys.stderr)
                    return 3

            # Inject ThisWorkbook event handler if a source text file exists
            inject_thisworkbook_event(vbp)

            # Save the workbook with .xlsm format (52 = xlOpenXMLWorkbookMacroEnabled)
            wb.save()
            print(f"[save] {xlsm_path.name} saved with {imported} modules")
        finally:
            try:
                wb.close()
            except Exception:
                pass

    # ── CRITICAL: re-inject CustomUI AFTER Excel released the file ──
    # xlwings/Excel COM strips customUI14.xml on save (Excel doesn't know
    # about 3rd-party ribbon extensibility parts injected via Python).
    # Without this, the custom Pricing+Operations ribbon tabs disappear
    # and Nelson sees only standard Excel tabs.
    reinject_customui(xlsm_path)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--xlsm",
        type=Path,
        default=MASTER_XLSM,
        help=f"Path to xlsm (default: {MASTER_XLSM})",
    )
    parser.add_argument(
        "--bas-dir",
        type=Path,
        default=BAS_DIR,
        help=f"Directory containing .bas files (default: {BAS_DIR})",
    )
    args = parser.parse_args()

    return reimport_modules(args.xlsm, args.bas_dir)


if __name__ == "__main__":
    sys.exit(main())
