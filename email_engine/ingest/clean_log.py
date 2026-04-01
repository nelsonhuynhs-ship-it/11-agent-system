"""
clean_log.py — One-off fix for corrupt email_log.csv status entries
====================================================================
Reads email_log.csv, fixes any rows where status is not in the known
valid set, sets them to 'SENT', and saves back.
"""

import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent
EMAIL_LOG_FILE = PROJECT_ROOT / "logs" / "email_log.csv"

VALID_STATUSES = {"SENT", "REPLIED", "BOUNCED", "BLOCKED", "REPLIED_1", "REPLIED_2", "REPLIED_3"}

def main():
    print("=" * 60)
    print("  CLEAN EMAIL LOG — Fix Corrupt Status Entries")
    print("=" * 60)

    df = pd.read_csv(EMAIL_LOG_FILE)
    df.columns = df.columns.str.strip().str.lower()
    total = len(df)
    print(f"  Total rows: {total}")

    # Normalize status to uppercase for comparison
    df["status"] = df["status"].astype(str).str.strip()

    # Find corrupt entries
    mask = ~df["status"].str.upper().isin(VALID_STATUSES)
    corrupt = df[mask].copy()
    corrupt_count = len(corrupt)

    if corrupt_count == 0:
        print("  No corrupt entries found. Nothing to fix.")
        return

    # Show what we're fixing
    print(f"\n  Corrupt entries found: {corrupt_count}")
    print("  Corrupt status values:")
    for val, cnt in corrupt["status"].value_counts().items():
        print(f"    '{val}': {cnt} rows")

    # Fix: set all corrupt statuses to SENT
    df.loc[mask, "status"] = "SENT"

    # Also ensure cycle_id column exists (root cause of the column shift)
    if "cycle_id" not in df.columns:
        df["cycle_id"] = ""
        print("\n  Added missing 'cycle_id' column.")

    # Save back
    df.to_csv(EMAIL_LOG_FILE, index=False, encoding="utf-8")

    print(f"\n  Fixed {corrupt_count} corrupt rows -> status set to 'SENT'")
    print(f"  Saved to: {EMAIL_LOG_FILE}")

    # Verify
    df2 = pd.read_csv(EMAIL_LOG_FILE)
    df2.columns = df2.columns.str.strip().str.lower()
    print(f"\n  Verification — status distribution after fix:")
    for val, cnt in df2["status"].astype(str).str.upper().value_counts().items():
        print(f"    {val:15s}: {cnt}")
    print("=" * 60)


if __name__ == "__main__":
    main()
