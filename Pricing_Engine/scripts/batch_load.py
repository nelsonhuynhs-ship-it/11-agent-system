# -*- coding: utf-8 -*-
"""
batch_load.py — Incremental batch loader for historical FAK files

Copies N files at a time from raw/ → data/, runs master_loader_v2,
then removes temp copies. Parquet accumulates via incremental append.

Usage:
  python batch_load.py                    # Process all unloaded FAK files, batch of 5
  python batch_load.py --batch-size 3     # Batch of 3
  python batch_load.py --dry-run          # Show plan without executing
  python batch_load.py --resume           # Skip already-processed files
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import shutil
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent  # Pricing_Engine
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROGRESS_FILE = SCRIPT_DIR / ".batch_progress.json"
LOADER_SCRIPT = SCRIPT_DIR / "master_loader_v2.py"

EXCLUDE_FROM_DATA = ['PUC_SOC', 'Port_Code', 'Schedule', 'Master', 'Group_Code']


def get_raw_fak_files():
    """Get all FAK files from raw/ directory."""
    if not RAW_DIR.exists():
        print(f"[!] raw/ directory not found: {RAW_DIR}")
        return []
    files = sorted([
        f.name for f in RAW_DIR.glob("FAK*.xlsx")
        if not f.name.startswith('~$')
    ])
    return files


def load_progress():
    """Load progress tracker (which files have been processed)."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {"processed": [], "started": None, "last_batch": 0}


def save_progress(progress):
    """Save progress tracker."""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2, default=str)


def get_existing_data_fak():
    """Get FAK files currently in data/ (permanent ones, not batch copies)."""
    return [
        f.name for f in DATA_DIR.glob("FAK*.xlsx")
        if not f.name.startswith('~$')
    ]


def run_loader():
    """Run master_loader_v2.py and return success/failure."""
    result = subprocess.run(
        [sys.executable, str(LOADER_SCRIPT)],
        capture_output=True, text=True, encoding='utf-8', errors='replace'
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"[!] Loader error:\n{result.stderr}")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description='Batch load historical FAK files')
    parser.add_argument('--batch-size', '-b', type=int, default=5, help='Files per batch (default: 5)')
    parser.add_argument('--dry-run', action='store_true', help='Show plan without executing')
    parser.add_argument('--resume', action='store_true', help='Skip already-processed files (default)')
    parser.add_argument('--reset', action='store_true', help='Reset progress and start fresh')
    args = parser.parse_args()

    print("=" * 70)
    print("🔄 BATCH LOADER — Historical FAK Files")
    print("=" * 70)

    # Get all raw FAK files
    all_raw = get_raw_fak_files()
    if not all_raw:
        print("[!] No FAK files found in raw/")
        return

    # Load/reset progress
    if args.reset and PROGRESS_FILE.exists():
        os.remove(PROGRESS_FILE)
        print("[!] Progress reset")

    progress = load_progress()
    processed = set(progress.get("processed", []))

    # Filter out already processed
    pending = [f for f in all_raw if f not in processed]

    # Also exclude FAK files already in data/ (permanent ones)
    existing_data = set(get_existing_data_fak())

    print(f"\n📊 Status:")
    print(f"   Total raw FAK files: {len(all_raw)}")
    print(f"   Already processed:   {len(processed)}")
    print(f"   Pending:             {len(pending)}")
    print(f"   Existing in data/:   {', '.join(existing_data) or 'none'}")
    print(f"   Batch size:          {args.batch_size}")
    print(f"   Total batches:       {(len(pending) + args.batch_size - 1) // args.batch_size}")

    if not pending:
        print("\n✅ All files have been processed!")
        return

    # Create batches
    batches = []
    for i in range(0, len(pending), args.batch_size):
        batches.append(pending[i:i + args.batch_size])

    if args.dry_run:
        print(f"\n📋 DRY RUN — Planned batches:")
        for i, batch in enumerate(batches, 1):
            print(f"\n   Batch {i}/{len(batches)}:")
            for f in batch:
                print(f"     • {f}")
        print(f"\n   Total: {len(pending)} files in {len(batches)} batches")
        return

    # Execute batches
    print(f"\n🚀 Starting batch processing...")
    progress["started"] = datetime.now().isoformat()
    total_start = datetime.now()

    for batch_idx, batch in enumerate(batches, 1):
        batch_start = datetime.now()
        print(f"\n{'='*70}")
        print(f"📦 BATCH {batch_idx}/{len(batches)} — {len(batch)} files")
        print(f"{'='*70}")

        copied_files = []

        try:
            # Step 1: Copy batch files to data/
            for fname in batch:
                src = RAW_DIR / fname
                dst = DATA_DIR / fname
                if dst.exists():
                    print(f"   ⚠️ {fname} already in data/, skipping copy")
                else:
                    shutil.copy2(src, dst)
                    copied_files.append(fname)
                    print(f"   📄 Copied: {fname}")

            # Step 2: Run loader
            print(f"\n   🔄 Running master_loader_v2...")
            success = run_loader()

            if success:
                # Step 3: Mark as processed
                for fname in batch:
                    progress["processed"].append(fname)
                progress["last_batch"] = batch_idx
                save_progress(progress)

                batch_time = (datetime.now() - batch_start).total_seconds()
                remaining = len(batches) - batch_idx
                est_remaining = remaining * batch_time
                print(f"\n   ✅ Batch {batch_idx} complete! ({batch_time:.0f}s)")
                print(f"   ⏳ Estimated remaining: {est_remaining/60:.1f} min ({remaining} batches)")
            else:
                print(f"\n   ❌ Batch {batch_idx} FAILED! Stopping.")
                break

        finally:
            # Step 4: Cleanup — remove copied files from data/
            for fname in copied_files:
                dst = DATA_DIR / fname
                if dst.exists():
                    os.remove(dst)
                    print(f"   🗑️ Removed temp: {fname}")

    total_time = (datetime.now() - total_start).total_seconds()
    processed_count = len(progress.get("processed", []))
    print(f"\n{'='*70}")
    print(f"🏁 BATCH LOADING COMPLETE")
    print(f"   Total processed: {processed_count}/{len(all_raw)} files")
    print(f"   Total time: {total_time/60:.1f} min")
    print(f"   Progress saved to: {PROGRESS_FILE}")
    print(f"{'='*70}")

    # Check parquet size
    parquet = DATA_DIR / "Cleaned_Master_History.parquet"
    if parquet.exists():
        import pandas as pd
        df = pd.read_parquet(parquet)
        print(f"\n📊 Parquet status:")
        print(f"   Rows: {len(df):,}")
        print(f"   Size: {parquet.stat().st_size / 1024 / 1024:.1f} MB")
        if 'Rate_Type' in df.columns:
            print(f"   Rate types: {df['Rate_Type'].value_counts().to_dict()}")


if __name__ == '__main__':
    main()
