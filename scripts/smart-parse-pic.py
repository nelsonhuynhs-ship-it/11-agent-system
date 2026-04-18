"""
smart-parse-pic.py
===================
Improve PIC quality for cnee_master_v2_final.xlsx:
- Dot / underscore / dash in email prefix → split + Title Case
- Leading/trailing digits → strip
- Role keywords (info/sales/orders/etc) → "Team" fallback
- Preserve existing PIC if manually enriched (has space = likely manual)

Example transformations:
  john.smith@abc.com          → "John Smith"    (was "John.Smith" elsewhere)
  alex_liu@abc.com            → "Alex Liu"      (was "Alex_Liu")
  0301caozuo@abc.com          → "Caozuo"        (was "0301caozuo")
  sales@abc.com               → "Team"          (was "Sales")
  info@abc.com                → "Team"          (was "Info")
  breakbulk@abc.com           → "Team"          (was "Breakbulk")
  ahendrix@abc.com            → "Ahendrix"      (unchanged, 1 word no separator)
"""
from __future__ import annotations
import re
from pathlib import Path
import pandas as pd

MASTER = Path("D:/OneDrive/NelsonData/email/cnee_master_v2_final.xlsx")

ROLE_KEYWORDS = {
    "info", "sales", "contact", "support", "orders", "order", "hello",
    "hr", "admin", "help", "service", "team", "office", "mail", "email",
    "shipping", "logistics", "inquiry", "enquiry", "marketing", "billing",
    "accounts", "accounting", "finance", "purchase", "purchasing",
    "breakbulk", "customerservice", "import", "export", "noreply", "no-reply",
    "reply", "dept", "department", "warehouse", "receiving", "traffic",
    "procurement", "operations", "ops", "webmaster", "postmaster",
}


def _auto_derive(email: str) -> str:
    """Simple auto-derivation: capitalize the email prefix as-is."""
    if not email or "@" not in email:
        return ""
    prefix = email.split("@")[0].strip().lower()
    return prefix.capitalize()


def parse_pic_smart(email, existing_pic=None) -> str:
    """Parse PIC intelligently from email. Conservative: preserve manual entries."""
    ex = existing_pic.strip() if isinstance(existing_pic, str) else ""
    ex_lower = ex.lower()

    # CONSERVATIVE: preserve existing PIC unless it's clearly auto-derived garbage.
    # Detect "ugly auto" = PIC equals simple capitalize(email_prefix) lowercased.
    auto_simple = _auto_derive(email).lower() if email else ""

    is_nan_or_empty = not ex or ex_lower in ("nan", "none", "")
    is_ugly_auto = bool(auto_simple) and ex_lower == auto_simple  # e.g. PIC="Ahendrix" for ahendrix@
    has_space = " " in ex

    # Keep existing if it looks manual (has space, or short name != auto pattern)
    if ex and not is_nan_or_empty and not is_ugly_auto:
        # Manual entry detected — keep as-is
        return ex

    # Need to (re-)derive
    if not email or not isinstance(email, str) or "@" not in email:
        return ex or "Team"

    prefix = email.split("@")[0].strip().lower()
    prefix = re.sub(r"^\d+", "", prefix)
    prefix = re.sub(r"\d+$", "", prefix)
    if not prefix:
        return "Team"

    if prefix in ROLE_KEYWORDS:
        return "Team"

    parts = re.split(r"[._\-]+", prefix)
    parts = [p for p in parts if p]

    # Only re-parse when the prefix had separators (reliable split signal).
    # If no separator and existing PIC is ugly-auto, leave it alone rather than
    # creating false names like "Ronlaw" from "ronlaw".
    if len(parts) == 1 and is_ugly_auto and not is_nan_or_empty:
        return ex  # keep ugly-but-not-wronger

    non_role = [p for p in parts if p not in ROLE_KEYWORDS]
    if not non_role:
        return "Team"

    return " ".join(p.capitalize() for p in non_role)


def main():
    print(f"Loading {MASTER} ...")
    df = pd.read_excel(MASTER)
    print(f"Rows: {len(df):,}")

    old_pic = df["PIC"].copy()
    df["PIC"] = df.apply(
        lambda r: parse_pic_smart(r.get("EMAIL"), r.get("PIC")),
        axis=1,
    )
    # Also refresh GREETING based on new PIC
    df["GREETING"] = df["PIC"].apply(lambda p: f"Hi {p}" if p and p != "Team" else "Hi Team")

    changed = (old_pic != df["PIC"]).sum()
    print(f"PIC changed: {changed:,} rows ({changed*100/len(df):.1f}%)")
    print()

    # Show sample changes
    print("=== Sample changes (first 20) ===")
    cnt = 0
    for i in range(len(df)):
        if old_pic.iloc[i] != df["PIC"].iloc[i]:
            em = df["EMAIL"].iloc[i]
            old = old_pic.iloc[i]
            new = df["PIC"].iloc[i]
            print(f"  {em[:40]:40} | OLD: {str(old)[:20]:20} → NEW: {new}")
            cnt += 1
            if cnt >= 20:
                break

    # Save back
    df.to_excel(MASTER, index=False)
    print()
    print(f"✅ Updated {MASTER}")

    # Team rate
    team_count = (df["PIC"] == "Team").sum()
    print(f"Team fallback: {team_count:,} ({team_count*100/len(df):.1f}%)")
    print(f"With real name: {len(df) - team_count:,} ({(len(df)-team_count)*100/len(df):.1f}%)")


if __name__ == "__main__":
    main()
