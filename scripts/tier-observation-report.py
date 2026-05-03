"""
Tier Observation Report — Phase 5.3 of customer-tier-margin plan.

Usage: python tier-observation-report.py [days_back]
  days_back  — integer, look-back window (default 7)
"""

import sys
from pathlib import Path

import pandas as pd

# ── Constants ────────────────────────────────────────────────────────────────
ERP_PATH = Path("D:/OneDrive/NelsonData/erp/ERP_Master_v14.xlsm")
SHEET = "Quotes"
DATE_COL = "Date"
TIER_COL = "Tier_Applied"
STATUS_COL = "Status"
DAYS_DEFAULT = 7

# ── Helpers ──────────────────────────────────────────────────────────────────
def load_quotes(path: Path, days_back: int) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=SHEET, engine="openpyxl")
    df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")
    cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=days_back - 1)
    return df[df[DATE_COL] >= cutoff]


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    grp = df.groupby(TIER_COL)[STATUS_COL]
    wins = grp.apply(lambda s: (s == "WIN").sum())
    lost = grp.apply(lambda s: (s == "LOST").sum())
    pending = grp.apply(lambda s: (s == "PENDING").sum())
    total = grp.count()
    win_rate = wins / (wins + lost)
    win_rate = win_rate.where((wins + lost) > 0, float("nan"))

    summary = pd.DataFrame(
        {"total": total, "wins": wins, "lost": lost, "pending": pending, "win_rate": win_rate}
    )
    summary["win_rate"] = summary["win_rate"].map(lambda x: f"{x:.1%}" if pd.notna(x) else "N/A")
    return summary


def margin_dist(df: pd.DataFrame) -> pd.Series | None:
    margin_cols = [c for c in df.columns if "Margin" in c]
    if not margin_cols:
        return None
    return df[margin_cols[0]].describe()


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    days = int(sys.argv[1]) if len(sys.argv) > 1 else DAYS_DEFAULT

    if not ERP_PATH.exists():
        print(f"ERROR: file not found: {ERP_PATH}", file=sys.stderr)
        sys.exit(1)

    try:
        df = load_quotes(ERP_PATH, days)
    except Exception as e:
        print(f"ERROR reading workbook: {e}", file=sys.stderr)
        sys.exit(1)

    if TIER_COL not in df.columns:
        print(f"WARNING: column '{TIER_COL}' not found in sheet '{SHEET}'", file=sys.stderr)
        sys.exit(0)

    if df.empty:
        print("No quotes found")
        sys.exit(0)

    print(f"=== Tier Observation Report (last {days} days) ===")
    print(f"Total quotes: {len(df)}")
    print()
    print(summarise(df).to_string())
    print()

    margins = margin_dist(df)
    if margins is not None:
        print(f"Margin distribution per tier:")
        print(margins.to_string())
    else:
        print("No Margin column found")

    print()
    print(f"Generated: {pd.Timestamp.now()}")


if __name__ == "__main__":
    main()
