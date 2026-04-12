"""
cleanup_master.py — One-time cleanup of cnee_master_v2_final.xlsx
Applies blacklist to remove competitor contacts from SEND queue.
Run: python3 -m pipeline.cleanup_master
"""
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

from .blacklist import apply_blacklist

DATA_DIR = Path("/opt/nelson/data/email")
MASTER_FILE = DATA_DIR / "cnee_master_v2_final.xlsx"


def run():
    print(f"=== CNEE Master Cleanup — {datetime.now().isoformat()} ===\n")

    if not MASTER_FILE.exists():
        print(f"ERROR: {MASTER_FILE} not found")
        return

    # Backup original
    backup = DATA_DIR / f"cnee_master_v2_final.backup-{datetime.now().strftime('%Y%m%d-%H%M')}.xlsx"
    shutil.copy2(MASTER_FILE, backup)
    print(f"Backup: {backup}\n")

    # Load
    df = pd.read_excel(MASTER_FILE)
    total = len(df)
    send_now_before = (df["ACTION"] == "SEND_NOW").sum() if "ACTION" in df.columns else 0
    print(f"Total rows: {total}")
    print(f"SEND_NOW before: {send_now_before}\n")

    # Apply blacklist
    print("Applying blacklist...")
    df = apply_blacklist(df, email_col="EMAIL", company_col="COMPANY")

    blacklisted = (df["ACTION"] == "BLACKLISTED").sum()
    send_now_after = (df["ACTION"] == "SEND_NOW").sum()
    print(f"\nBlacklisted: {blacklisted}")
    print(f"SEND_NOW after: {send_now_after}")
    print(f"Removed from queue: {send_now_before - send_now_after}")

    # Save
    df.to_excel(MASTER_FILE, index=False)
    print(f"\nSaved: {MASTER_FILE}")
    print("=== Done ===")


if __name__ == "__main__":
    run()
