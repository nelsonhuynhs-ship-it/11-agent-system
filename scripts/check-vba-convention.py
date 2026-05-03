#!/usr/bin/env python3
"""
check-vba-convention.py
Pre-commit hook: verify every bas<Feature>.bas has TestModule_<Feature>.bas

Run: python scripts/check-vba-convention.py
Exit 0 = pass, Exit 1 = fail
"""
import sys
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
VBA_MIRROR = REPO_ROOT / "ERP" / "vba-v14-mirror"

# Use ASCII-friendly icons for Windows compatibility
PASS_ICON = "[PASS]"
FAIL_ICON = "[FAIL]"


def get_staged_bas_files():
    """Get .bas files that are staged (added/modified) in git."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
            capture_output=True, text=True, cwd=REPO_ROOT
        )
        files = [f.strip() for f in result.stdout.splitlines() if f.strip().endswith(".bas")]
        return files
    except Exception:
        return []


def get_changed_bas_files():
    """Get .bas files that are staged, unstaged, or untracked in VBA mirror."""
    staged = []
    unstaged_or_untracked = []
    vba_str = str(VBA_MIRROR).replace("\\", "/")

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, cwd=REPO_ROOT
        )
        staged = [f.strip() for f in result.stdout.splitlines()
                  if f.strip().endswith(".bas") and vba_str in f.replace("\\", "/")]
    except Exception:
        pass
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True, text=True, cwd=REPO_ROOT
        )
        unstaged_or_untracked = [f.strip() for f in result.stdout.splitlines()
                                 if f.strip().endswith(".bas") and vba_str in f.replace("\\", "/")]
    except Exception:
        pass
    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "--", "*.bas"],
            capture_output=True, text=True, cwd=REPO_ROOT
        )
        untracked = [f.strip() for f in result.stdout.splitlines()
                     if f.strip().endswith(".bas") and vba_str in f.replace("\\", "/")]
        unstaged_or_untracked.extend(untracked)
    except Exception:
        pass

    # Combine and dedupe
    all_files = list(set(staged + unstaged_or_untracked))
    return all_files


def check_convention():
    """
    bas<Feature>.bas must have TestModule_<Feature>.bas in same directory.
    Only checks files in ERP/vba-v14-mirror/.
    """
    errors = []

    # Get changed bas files (staged or unstaged)
    changed_files = get_changed_bas_files()
    if not changed_files:
        print("No .bas files changed — convention check passed")
        return errors

    # Filter to only VBA mirror files
    vba_mirror_str = str(VBA_MIRROR).replace("\\", "/")
    vba_files = [f for f in changed_files if vba_mirror_str in f.replace("\\", "/")]

    if not vba_files:
        print(f"No .bas files in {VBA_MIRROR} — convention check passed")
        return errors

    for filepath in vba_files:
        filename = Path(filepath).name

        # Skip TestModule files themselves
        if filename.startswith("TestModule_"):
            continue

        # Only check bas<Feature>.bas pattern (not basShared.bas, not CostBreakdown.bas)
        if not (filename.startswith("bas") and not filename.startswith("TestModule_")):
            continue

        # Extract feature name: basFoo.bas -> Foo, basFastId.bas -> FastId
        if filename.startswith("bas"):
            base = filename[3:]  # Remove "bas" prefix
            feature_name = base[:-4]  # Remove ".bas" suffix
        else:
            continue

        # Check if TestModule_<Feature>.bas exists
        expected_test = f"TestModule_{feature_name}.bas"
        test_path = VBA_MIRROR / expected_test

        if not test_path.exists():
            errors.append(f"MISSING: {expected_test} (for {filename})")

    return errors


def main():
    print("=== VBA Convention Check ===")
    print(f"Scanning: {VBA_MIRROR}")
    print()

    errors = check_convention()

    if errors:
        print("FAIL: VBA convention violations detected:")
        for err in errors:
            print(f"  [X] {err}")
        print()
        print("Rule: Every bas<Feature>.bas must have a TestModule_<Feature>.bas")
        print("Fix: Create the missing TestModule file or rename your feature module.")
        sys.exit(1)
    else:
        print(f"{PASS_ICON} All VBA convention checks passed")
        sys.exit(0)


if __name__ == "__main__":
    main()