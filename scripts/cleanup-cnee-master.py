"""
cleanup-cnee-master.py
=======================
Apply competitor_blacklist.json to cnee_master_v2_final.xlsx.
Split rows into:
  - KEEP (clean) → overwrite cnee_master_v2_final.xlsx
  - BLOCKED     → archive to cnee_blocked_{YYYYMMDD}.xlsx
Backup original before modifying.

Usage: python scripts/cleanup-cnee-master.py [--dry-run]
"""
from __future__ import annotations
import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path
from collections import Counter

import pandas as pd

# ensure web_server importable
sys.path.insert(0, str(Path(__file__).parent.parent / "email_engine"))
from web_server import is_competitor, COMPETITOR_BL

MASTER_PATH = Path("D:/OneDrive/NelsonData/email/cnee_master_v2_final.xlsx")
TODAY = datetime.now().strftime("%Y%m%d")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Count only, don't write changes")
    args = ap.parse_args()

    if not MASTER_PATH.exists():
        raise SystemExit(f"Master file not found: {MASTER_PATH}")

    print(f"Loading {MASTER_PATH} ...")
    df = pd.read_excel(MASTER_PATH)
    total = len(df)
    print(f"Total rows: {total:,}")
    print(f"Blacklist: {len(COMPETITOR_BL['domains'])} domains, "
          f"{len(COMPETITOR_BL['keywords'])} keywords, "
          f"whitelist {len(COMPETITOR_BL.get('whitelist_domains', set()))}")
    print()

    # Apply filter
    keep_mask = []
    block_reasons = []
    for _, row in df.iterrows():
        em = str(row.get("EMAIL", "")).strip()
        co = str(row.get("COMPANY", row.get("CNEE_NAME", ""))).strip()
        blocked, reason = is_competitor(em, co)
        keep_mask.append(not blocked)
        block_reasons.append(reason if blocked else "")

    df["_block_reason"] = block_reasons
    clean_df = df[keep_mask].drop(columns=["_block_reason"])
    blocked_df = df[[not k for k in keep_mask]]

    clean_n = len(clean_df)
    blocked_n = len(blocked_df)
    print(f"Result: KEEP {clean_n:,} ({clean_n*100/total:.1f}%) | BLOCKED {blocked_n:,} ({blocked_n*100/total:.1f}%)")
    print()

    # Top block reasons
    reasons_counter = Counter(r for r in block_reasons if r)
    print("Top 15 block reasons:")
    for r, c in reasons_counter.most_common(15):
        print(f"  {c:5,} x {r}")
    print()

    if args.dry_run:
        print("[DRY-RUN] No file changes.")
        return

    # Backup original
    backup_path = MASTER_PATH.parent / f"cnee_master_v2_backup_{TODAY}.xlsx"
    shutil.copy2(MASTER_PATH, backup_path)
    print(f"Backup → {backup_path}")

    # Write clean
    clean_df.to_excel(MASTER_PATH, index=False)
    print(f"Clean  → {MASTER_PATH} ({clean_n:,} rows)")

    # Archive blocked with block_reason column
    blocked_path = MASTER_PATH.parent / f"cnee_blocked_{TODAY}.xlsx"
    blocked_df.to_excel(blocked_path, index=False)
    print(f"Blocked archive → {blocked_path} ({blocked_n:,} rows)")

    print()
    print("DONE. Cleanup applied.")


if __name__ == "__main__":
    main()
