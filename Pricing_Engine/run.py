# -*- coding: utf-8 -*-
"""
run.py — Pricing Engine CLI Entry Point

Usage:
  python run.py pricing          # Build parquet + MasterFullPricing
  python run.py convert-scfi     # Convert raw SCFI file
  python run.py convert-special  # Convert raw Special Rate file
  python run.py custeam          # Parse weekly Product Update
  python run.py full             # Full: loader + dashboard + ERP sync
  python run.py status           # Show system status
  python run.py batch            # Batch load historical FAK
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent
SCRIPTS = ROOT / "scripts"
DATA = ROOT / "data"


def run_script(name, args=None):
    """Run a script from the scripts/ directory."""
    script = SCRIPTS / name
    cmd = [sys.executable, str(script)]
    if args:
        cmd.extend(args)
    print(f"\n{'─'*60}")
    print(f"▶ {name} {' '.join(args or [])}")
    print(f"{'─'*60}")
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print(f"\n❌ {name} failed (exit code {result.returncode})")
        return False
    return True


def cmd_pricing(args):
    """Workflow 1: Build parquet → MasterFullPricing"""
    print("🔄 PRICING UPDATE — loader + dashboard")
    if not run_script("master_loader_v2.py"):
        return
    run_script("create_master_dashboard.py")


def cmd_convert_scfi(args):
    """Convert raw SCFI file"""
    if not args.input:
        # Auto-detect in data/Origin/
        origin = DATA / "Origin"
        scfi_files = list(origin.glob("*SCFI*")) + list(origin.glob("*scfi*"))
        if scfi_files:
            args.input = str(scfi_files[0])
            print(f"📄 Auto-detected: {args.input}")
        else:
            print("❌ No SCFI file found. Use: python run.py convert-scfi -i FILE")
            return
    out = args.output or str(DATA / f"HPL_SCFI_converted.xlsx")
    run_script("convert_pricing.py", ["--scfi", args.input, "-o", out])


def cmd_convert_special(args):
    """Convert raw Special Rate file"""
    if not args.input:
        origin = DATA / "Origin"
        fix_files = list(origin.glob("*Fixed Rate*")) + list(origin.glob("*Special*"))
        if fix_files:
            args.input = str(fix_files[0])
            print(f"📄 Auto-detected: {args.input}")
        else:
            print("❌ No Special Rate file found. Use: python run.py convert-special -i FILE")
            return
    out = args.output or str(DATA / f"SPECIAL_RATE_converted.xlsx")
    run_script("convert_pricing.py", ["--special", args.input, "-o", out])


def cmd_custeam(args):
    """Workflow 2: Parse Custeam Product Update"""
    print("📋 CUSTEAM UPDATE — parsing product reports")
    run_script("parse_product_update.py", ["--all"])
    print()
    run_script("parse_product_update.py", ["--show"])


def cmd_full(args):
    """Full rebuild: loader + dashboard + ERP"""
    print("🚀 FULL REBUILD — loader + dashboard + ERP")
    if not run_script("master_loader_v2.py"):
        return
    if not run_script("create_master_dashboard.py"):
        return
    run_script("sync_erp.py")


def cmd_batch(args):
    """Batch load historical FAK"""
    extra = []
    if args.dry_run:
        extra.append("--dry-run")
    if args.batch_size:
        extra.extend(["-b", str(args.batch_size)])
    run_script("batch_load.py", extra or None)


def cmd_status(args):
    """Show system status"""
    import pandas as pd

    print("📊 PRICING ENGINE STATUS")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()

    # Parquet
    parquet = DATA / "Cleaned_Master_History.parquet"
    if parquet.exists():
        df = pd.read_parquet(parquet)
        size_mb = parquet.stat().st_size / 1024 / 1024
        print(f"   📦 Parquet: {len(df):,} rows ({size_mb:.1f} MB)")
        if 'Rate_Type' in df.columns:
            for rt, cnt in df['Rate_Type'].value_counts().items():
                print(f"      {rt}: {cnt:,}")
        if 'Eff' in df.columns:
            dates = pd.to_datetime(df['Eff'], errors='coerce')
            print(f"      Date range: {dates.min().strftime('%Y-%m-%d')} → {dates.max().strftime('%Y-%m-%d')}")
    else:
        print("   📦 Parquet: NOT FOUND")

    # MasterFullPricing
    master = DATA / "MasterFullPricing.xlsx"
    if master.exists():
        mod_time = datetime.fromtimestamp(master.stat().st_mtime)
        size_mb = master.stat().st_size / 1024 / 1024
        print(f"\n   📊 MasterFullPricing: {size_mb:.1f} MB")
        print(f"      Last modified: {mod_time.strftime('%Y-%m-%d %H:%M')}")
    else:
        print("\n   📊 MasterFullPricing: NOT FOUND")

    # Custeam
    custeam_parquet = DATA / "custeam" / "custeam_history.parquet"
    if custeam_parquet.exists():
        cdf = pd.read_parquet(custeam_parquet)
        print(f"\n   📋 Custeam: {len(cdf)} records (W{cdf['Week_Num'].min()}→W{cdf['Week_Num'].max()})")
    else:
        print(f"\n   📋 Custeam: no data yet")

    # Data files
    print(f"\n   📂 Data files:")
    xlsx_files = [f for f in DATA.glob("*.xlsx") if not f.name.startswith('~$')]
    for f in sorted(xlsx_files):
        size = f.stat().st_size / 1024
        print(f"      {f.name} ({size:.0f} KB)")

    # Scripts
    print(f"\n   📜 Active scripts:")
    for f in sorted(SCRIPTS.glob("*.py")):
        if f.name.startswith('_') or f.name.startswith('.'):
            continue
        print(f"      {f.name}")


def main():
    parser = argparse.ArgumentParser(
        description='🚢 Pricing Engine CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Workflows:
  pricing          Build parquet + MasterFullPricing (daily)
  convert-scfi     Convert raw SCFI file
  convert-special  Convert raw Special Rate file
  custeam          Parse weekly Custeam Product Update
  full             Full rebuild: loader + dashboard + ERP
  batch            Batch load historical FAK files
  status           Show system status
        """
    )
    sub = parser.add_subparsers(dest='command')

    # pricing
    sub.add_parser('pricing', help='Build parquet + MasterFullPricing')

    # convert-scfi
    p_scfi = sub.add_parser('convert-scfi', help='Convert raw SCFI')
    p_scfi.add_argument('-i', '--input', help='Input file path')
    p_scfi.add_argument('-o', '--output', help='Output file path')

    # convert-special
    p_fix = sub.add_parser('convert-special', help='Convert raw Special Rate')
    p_fix.add_argument('-i', '--input', help='Input file path')
    p_fix.add_argument('-o', '--output', help='Output file path')

    # custeam
    sub.add_parser('custeam', help='Parse Custeam Product Update')

    # full
    sub.add_parser('full', help='Full rebuild: loader + dashboard + ERP')

    # batch
    p_batch = sub.add_parser('batch', help='Batch load historical FAK')
    p_batch.add_argument('-b', '--batch-size', type=int, default=5)
    p_batch.add_argument('--dry-run', action='store_true')

    # status
    sub.add_parser('status', help='Show system status')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        'pricing': cmd_pricing,
        'convert-scfi': cmd_convert_scfi,
        'convert-special': cmd_convert_special,
        'custeam': cmd_custeam,
        'full': cmd_full,
        'batch': cmd_batch,
        'status': cmd_status,
    }

    commands[args.command](args)


if __name__ == '__main__':
    main()
