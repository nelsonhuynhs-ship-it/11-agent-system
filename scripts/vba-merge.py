#!/usr/bin/env python3
"""
VBA Module Merge — Inject Missing Functions via COM
=====================================================
Fixes the missing VBA functions in ERP_Master_v14.xlsm.

Problem:
- xlsm ERPv14Core is MISSING: CheckReQuoteAlerts, ApplyQuoteRowTimeColors
- xlsm ERPv14Ribbon is MISSING: OnAction_RequoteAlert + 12 others (14 total)

Root cause: COM VBProject.Import() creates new module instead of merging.
Solution: Import as temp module, then AddFromString into target, then delete temp.

Usage:
    python vba-merge.py [--dry-run] [--check-only]
"""

import os, sys, re, shutil, zipfile, io, win32com.client
import time
from oletools import olevba

ERP = r"D:\OneDrive\NelsonData\erp\ERP_Master_v14.xlsm"
BACKUP_DIR = r"D:\OneDrive\NelsonData\erp\_backup_vba_merge"
TMP_BAS_DIR = r"D:\OneDrive\NelsonData\erp\tmp_bas"

# What needs to be added to ERPv14Core
CORE_FUNCS = [
    'CheckReQuoteAlerts',
    'ApplyQuoteRowTimeColors',
]

# What needs to be added to ERPv14Ribbon
RIBBON_FUNCS = [
    'OnAction_RequoteAlert',
    'CacheSearchState',
    'TryRestoreSearchState',
    'ClearCachedState',
    'SetSearchCarrier',
    'SetSearchPOL',
    'SetSearchPOD',
    'SetSearchPlace',
    'TestE2E_RunMix',
    'TestE2E_FindSourceRow',
    'QuoteImage_CollectLatestGroup',
    'QuoteImage_CollectFromSelection',
    'QuoteImage_RenderRows',
]

DRY_RUN = '--dry-run' in sys.argv or '--check-only' in sys.argv


def read_file(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


def extract_function(source: str, func_name: str) -> str:
    """Extract a single function/sub from VBA source code."""
    # Match Sub or Function with exact name
    pattern = rf'^(?:Public |Private )?(Sub|Function)\s+{re.escape(func_name)}\b.*?^(?:End Sub|End Function)'
    m = re.search(pattern, source, re.MULTILINE | re.DOTALL)
    if m:
        return m.group(0)
    return None


def get_current_functions(xlsm_path):
    """Use olevba to get current function list from each module."""
    vp = olevba.VBA_Parser(xlsm_path)
    result = {}
    for (_, _, vba_fname, code) in vp.extract_all_macros():
        funcs = re.findall(r'^(?:Public |Private )?(?:Sub|Function)\s+(\w+)', code, re.MULTILINE)
        result[vba_fname] = set(funcs)
    vp.close()
    return result


def check_status(xlsm_path):
    """Check which functions are missing."""
    print(f"\n{'='*60}")
    print(f"Checking missing functions in: {xlsm_path}")
    print(f"{'='*60}")

    core_src = read_file(r"D:\OneDrive\NelsonData\erp\erp-v14-quick-wins.bas")
    ribbon_src = read_file(r"D:\OneDrive\NelsonData\erp\erp-v14-ribbon-callbacks.bas")

    core_funcs = set(re.findall(r'^(?:Public |Private )?(?:Sub|Function)\s+(\w+)', core_src, re.MULTILINE))
    ribbon_funcs = set(re.findall(r'^(?:Public |Private )?(?:Sub|Function)\s+(\w+)', ribbon_src, re.MULTILINE))

    current = get_current_functions(xlsm_path)
    xlsm_core = current.get('ERPv14Core.bas', set())
    xlsm_ribbon = current.get('ERPv14Ribbon.bas', set())

    print(f"\nERPv14Core — source has {len(core_funcs)}, xlsm has {len(xlsm_core)}")
    missing_core = [f for f in CORE_FUNCS if f not in xlsm_core]
    if missing_core:
        print(f"  MISSING: {missing_core}")
    else:
        print(f"  OK — all target functions present")

    print(f"\nERPv14Ribbon — source has {len(ribbon_funcs)}, xlsm has {len(xlsm_ribbon)}")
    missing_ribbon = [f for f in RIBBON_FUNCS if f not in xlsm_ribbon]
    if missing_ribbon:
        print(f"  MISSING: {missing_ribbon}")
    else:
        print(f"  OK — all target functions present")

    return len(missing_core) == 0 and len(missing_ribbon) == 0


def merge_vba(xlsm_path, backup_dir):
    """Perform the actual merge via COM."""
    print(f"\n{'='*60}")
    print(f"Starting VBA merge for: {xlsm_path}")
    print(f"{'='*60}")

    # Backup
    os.makedirs(backup_dir, exist_ok=True)
    backup = os.path.join(backup_dir, f"ERP_Master_v14.xlsm.bak.{int(time.time())}")
    shutil.copy2(xlsm_path, backup)
    print(f"Backup: {backup}")

    # Read source files
    core_src = read_file(r"D:\OneDrive\NelsonData\erp\erp-v14-quick-wins.bas")
    ribbon_src = read_file(r"D:\OneDrive\NelsonData\erp\erp-v14-ribbon-callbacks.bas")

    # Create temp dir
    if os.path.exists(TMP_BAS_DIR):
        shutil.rmtree(TMP_BAS_DIR)
    os.makedirs(TMP_BAS_DIR)

    # Create temp .bas file with the MISSING functions only
    # ERPv14QuickWinsTemp will be the temp module
    tmp_bas_path = os.path.join(TMP_BAS_DIR, "ERPv14QuickWinsTemp.bas")
    with open(tmp_bas_path, 'w', encoding='utf-8') as f:
        f.write('Attribute VB_Name = "ERPv14QuickWinsTemp"\n')
        f.write('Option Explicit\n\n')
        for fn in CORE_FUNCS:
            code = extract_function(core_src, fn)
            if code:
                f.write(code + '\n\n')
        for fn in RIBBON_FUNCS:
            code = extract_function(ribbon_src, fn)
            if code:
                f.write(code + '\n\n')
    print(f"Created temp .bas at {tmp_bas_path}")

    if DRY_RUN:
        print("[DRY RUN] Skipping COM operations")
        return True

    # Start Excel COM
    print("\nConnecting to Excel COM...")
    excel = win32com.client.Dispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    excel.AskToUpdateLinks = False

    try:
        wb = excel.Workbooks.Open(os.path.abspath(xlsm_path))
        vba = wb.VBProject.VBComponents

        # Import temp module
        print("Importing temp module...")
        vba.Import(tmp_bas_path)
        time.sleep(0.5)

        # Verify temp module exists
        temp_module = None
        for i in range(1, vba.Count + 1):
            comp = vba.Item(i)
            if comp.Name == 'ERPv14QuickWinsTemp':
                temp_module = comp
                break

        if not temp_module:
            print("[ERROR] Temp module not found after import!")
            return False

        print(f"Temp module has {temp_module.CodeModule.CountOfLines} lines")

        # Get the target modules
        erp_core = None
        erp_ribbon = None
        for i in range(1, vba.Count + 1):
            comp = vba.Item(i)
            if comp.Name == 'ERPv14Core':
                erp_core = comp
            elif comp.Name == 'ERPv14Ribbon':
                erp_ribbon = comp

        if not erp_core:
            print("[ERROR] ERPv14Core not found!")
            return False
        if not erp_ribbon:
            print("[ERROR] ERPv14Ribbon not found!")
            return False

        print(f"ERPv14Core: {erp_core.CodeModule.CountOfLines} lines")
        print(f"ERPv14Ribbon: {erp_ribbon.CodeModule.CountOfLines} lines")

        # Get source code for all missing functions
        print("\nExtracting missing function source code...")
        all_missing_funcs = [(fn, func_type, extract_function(core_src, fn), 'core')
                             for fn, func_type in [(f, 'Sub') for f in CORE_FUNCS]]
        all_missing_funcs += [(fn, 'Sub', extract_function(ribbon_src, fn), 'ribbon')
                              for fn in RIBBON_FUNCS]
        all_missing_funcs = [(fn, ft, code, tgt) for fn, ft, code, tgt in all_missing_funcs if code]

        print(f"  Found {len(all_missing_funcs)} missing functions to inject")

        # Add each function to its target module
        print("\nAdding functions to target modules...")
        for func_name, func_type, func_body, target in all_missing_funcs:
            if target == 'core':
                target_mod = erp_core
            else:
                target_mod = erp_ribbon

            try:
                target_mod.CodeModule.AddFromString(func_body)
                print(f"  [OK] {func_name} -> {target.upper()}")
            except Exception as e:
                print(f"  [ERROR] {func_name}: {e}")

        print(f"\n  Total functions added: {len(all_missing_funcs)}")

        # Remove temp module
        print("\nRemoving temp module...")
        vba.Remove(temp_module)
        print("  [OK] Temp module removed")

        # Save and close
        print("\nSaving workbook...")
        wb.Save()
        wb.Close(SaveChanges=False)
        excel.Quit()
        print("  [OK] Done!")

        # Clean up temp dir
        shutil.rmtree(TMP_BAS_DIR)

        # Validate
        print("\nValidating...")
        time.sleep(1)
        ok = check_status(xlsm_path)
        if ok:
            print("\n✅ SUCCESS — All missing functions added!")
        else:
            print("\n⚠ PARTIAL — Some functions may still be missing")
        return ok

    except Exception as e:
        print(f"[ERROR] {e}")
        try:
            excel.Quit()
        except:
            pass
        return False


if __name__ == '__main__':
    if '--check-only' in sys.argv:
        ok = check_status(ERP)
        sys.exit(0 if ok else 1)

    print("VBA Module Merge")
    print("=" * 60)
    print(f"ERP file : {ERP}")
    print(f"Backup   : {BACKUP_DIR}")
    print(f"Dry run  : {DRY_RUN}")

    ok = check_status(ERP)
    if ok:
        print("\n✅ All functions present — no merge needed")
        sys.exit(0)

    if DRY_RUN:
        print("\n[DRY RUN] Merge would add the missing functions")
    else:
        success = merge_vba(ERP, BACKUP_DIR)
        sys.exit(0 if success else 1)