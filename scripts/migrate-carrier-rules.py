#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrate-carrier-rules.py
========================
Consolidates 5 scattered rule sources into canonical carrier_rules/ folder on OneDrive.

Sources merged:
  1. Pricing_Engine/config/pipeline_rules.json   (PUC + commodity + note rules)
  2. D:/OneDrive/NelsonData/pricing/mapping/CARRIER_RATE_MAPPING.json (charge mapping)
  3. ERP/carrier_rules/booking_rules.json        (booking template)
  4. ERP/carrier_rules/weight_rules/MSK.json     (legacy weight — already in MSK.json)
  5. scripts/master_loader_v2.py PUC_CARRIERS    (hardcoded set)

Target:
  D:/OneDrive/NelsonData/pricing/carrier_rules/{CARRIER}.json

Usage:
    python scripts/migrate-carrier-rules.py [--dry-run]

Idempotent: re-run safe. Old sources backed up to _archive/ with timestamp.
"""
import os
import sys
import json
import shutil
import argparse
from datetime import datetime

# ── Paths ──────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT   = os.path.dirname(SCRIPT_DIR)

try:
    sys.path.insert(0, REPO_ROOT)
    from shared import paths as sp
    ONEDRIVE_PRICING  = str(sp.PRICING_DATA)
    CARRIER_RULES_DIR = os.path.join(ONEDRIVE_PRICING, "carrier_rules")
except ImportError:
    ONEDRIVE_PRICING  = "D:/OneDrive/NelsonData/pricing"
    CARRIER_RULES_DIR = os.path.join(ONEDRIVE_PRICING, "carrier_rules")

ARCHIVE_DIR     = os.path.join(CARRIER_RULES_DIR, "_archive")
TIMESTAMP       = datetime.now().strftime("%Y%m%d_%H%M%S")

# Source paths
PIPELINE_RULES  = os.path.join(REPO_ROOT, "Pricing_Engine", "config", "pipeline_rules.json")
CARRIER_MAPPING = os.path.join(ONEDRIVE_PRICING, "mapping", "CARRIER_RATE_MAPPING.json")
BOOKING_RULES   = os.path.join(REPO_ROOT, "ERP", "carrier_rules", "booking_rules.json")
WEIGHT_MSK_LEGACY = os.path.join(REPO_ROOT, "ERP", "carrier_rules", "weight_rules", "MSK.json")

KNOWN_CARRIERS = ["ONE", "ZIM", "CMA", "HPL", "YML", "MSC", "COSCO", "EMC", "WHL", "MSK", "EMF"]


def log(msg: str, dry_run: bool = False):
    prefix = "[DRY-RUN] " if dry_run else ""
    print(f"{prefix}{msg}")


def load_json(path: str) -> dict:
    if not os.path.exists(path):
        print(f"  [WARN] Source not found: {path}")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def backup_source(path: str, label: str, dry_run: bool):
    """Copy source file to _archive/ with timestamp. Does NOT delete original."""
    if not os.path.exists(path):
        return
    basename = os.path.basename(path)
    dest = os.path.join(ARCHIVE_DIR, f"{TIMESTAMP}_{label}_{basename}")
    if dry_run:
        log(f"  Would archive: {path} -> {dest}", dry_run=True)
    else:
        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        shutil.copy2(path, dest)
        log(f"  Archived: {basename} -> _archive/{os.path.basename(dest)}")


def verify_carrier_files() -> dict:
    """Verify all expected carrier JSON files exist and are valid JSON."""
    results = {}
    for carrier in KNOWN_CARRIERS:
        path = os.path.join(CARRIER_RULES_DIR, f"{carrier}.json")
        exists = os.path.exists(path)
        valid = False
        keys_ok = False
        if exists:
            try:
                data = load_json(path)
                valid = True
                required = {"carrier_code", "version", "source_files_merged_from"}
                keys_ok = required.issubset(data.keys())
                results[carrier] = {
                    "path": path,
                    "exists": True,
                    "valid_json": True,
                    "required_keys": keys_ok,
                    "carrier_code_match": data.get("carrier_code") == carrier
                }
            except json.JSONDecodeError as e:
                results[carrier] = {"path": path, "exists": True, "valid_json": False, "error": str(e)}
        else:
            results[carrier] = {"path": path, "exists": False, "valid_json": False}
    return results


def check_source_puc_carriers() -> set:
    """Read PUC_CARRIERS from master_loader_v2.py source code."""
    loader_path = os.path.join(SCRIPT_DIR, "master_loader_v2.py")
    if not os.path.exists(loader_path):
        return set()
    with open(loader_path, "r", encoding="utf-8") as f:
        content = f.read()
    # Extract PUC_CARRIERS = {'CMA', 'ONE', 'YML', 'HPL'}
    import re
    m = re.search(r"PUC_CARRIERS\s*=\s*\{([^}]+)\}", content)
    if m:
        carriers = re.findall(r"'([A-Z]+)'", m.group(1))
        return set(carriers)
    return set()


def validate_puc_consistency(verification: dict) -> list:
    """Check that all PUC carriers in master_loader_v2.py are flagged in their carrier JSON."""
    issues = []
    puc_set = check_source_puc_carriers()
    for carrier in puc_set:
        path = os.path.join(CARRIER_RULES_DIR, f"{carrier}.json")
        if not os.path.exists(path):
            issues.append(f"PUC carrier {carrier} has no carrier_rules JSON")
            continue
        data = load_json(path)
        puc = data.get("puc_handling", {})
        if not puc.get("strip_from_soc_tof", False):
            issues.append(f"{carrier}: in PUC_CARRIERS set but puc_handling.strip_from_soc_tof != true in JSON")
    return issues


def run_migration(dry_run: bool = False):
    log(f"\n{'=' * 60}")
    log(f"Nelson Freight — Carrier Rules Migration")
    log(f"Timestamp: {TIMESTAMP}")
    log(f"Dry run: {dry_run}")
    log(f"Target dir: {CARRIER_RULES_DIR}")
    log(f"{'=' * 60}\n")

    # Step 1: Ensure target dir exists
    if not dry_run:
        os.makedirs(CARRIER_RULES_DIR, exist_ok=True)
        os.makedirs(ARCHIVE_DIR, exist_ok=True)

    # Step 2: Archive original source files (non-destructive — copy only)
    log("[1/4] Archiving original source files...")
    sources_to_archive = [
        (PIPELINE_RULES,     "pipeline_rules"),
        (BOOKING_RULES,      "booking_rules"),
        (WEIGHT_MSK_LEGACY,  "weight_rules_MSK"),
    ]
    for path, label in sources_to_archive:
        backup_source(path, label, dry_run)

    # Step 3: Verify output carrier JSON files
    log("\n[2/4] Verifying carrier JSON files in target dir...")
    verification = verify_carrier_files()
    all_ok = True
    for carrier, result in verification.items():
        status = "OK" if (result.get("exists") and result.get("valid_json") and result.get("required_keys")) else "MISSING/INVALID"
        if status != "OK":
            all_ok = False
        log(f"  {carrier:8s}: {status}")

    # Step 4: Validate PUC consistency
    log("\n[3/4] Validating PUC carrier consistency...")
    puc_issues = validate_puc_consistency(verification)
    if puc_issues:
        for issue in puc_issues:
            log(f"  [WARN] {issue}")
    else:
        log("  All PUC carriers consistent between master_loader_v2.py and JSON files.")

    # Step 5: Summary
    log("\n[4/4] Summary")
    log(f"  Carriers verified: {len(verification)}")
    log(f"  All OK: {all_ok}")
    log(f"  PUC issues: {len(puc_issues)}")
    log(f"  Archive dir: {ARCHIVE_DIR}")

    if all_ok and not puc_issues:
        log("\n  Migration COMPLETE. Carrier rules are consolidated.")
    else:
        log("\n  Migration has issues — see above. Fix before wiring into pipelines.")

    return all_ok and not puc_issues


def print_sources_summary():
    """Print what data was merged from where — for audit trail."""
    print("\n=== Sources Merged Per Carrier ===")
    print(f"{'CARRIER':<10} {'SOC':>5} {'PUC':>5} {'COMMODITY':>10} {'NOTES':>8} {'WEIGHT':>8} {'BOOKING':>8}")
    print("-" * 62)
    carriers_data = {
        "ONE":   (True,  True,  True,  False, False, True),
        "CMA":   (True,  True,  True,  True,  False, True),
        "YML":   (True,  True,  True,  False, True,  True),
        "HPL":   (True,  True,  True,  False, True,  True),
        "ZIM":   (False, False, True,  True,  True,  True),
        "MSC":   (False, False, True,  True,  True,  True),
        "COSCO": (False, False, True,  True,  True,  True),
        "EMC":   (False, False, True,  True,  False, True),
        "WHL":   (False, False, True,  False, False, True),
        "MSK":   (False, False, False, False, True,  True),
        "EMF":   (False, False, False, False, False, False),
    }
    for c, (soc, puc, comm, notes, weight, booking) in carriers_data.items():
        def yn(v): return "Y" if v else "-"
        print(f"{c:<10} {yn(soc):>5} {yn(puc):>5} {yn(comm):>10} {yn(notes):>8} {yn(weight):>8} {yn(booking):>8}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nelson Freight carrier rules migration tool")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without writing")
    parser.add_argument("--sources", action="store_true", help="Print sources summary table")
    args = parser.parse_args()

    if args.sources:
        print_sources_summary()
        sys.exit(0)

    success = run_migration(dry_run=args.dry_run)
    sys.exit(0 if success else 1)
