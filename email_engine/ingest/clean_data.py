import pandas as pd
from pathlib import Path
from datetime import datetime
import csv
import shutil
import re

# =========================================================
# FILE PATH
# =========================================================
from pathlib import Path

BASE_DIR = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

DATA_FILE = PROJECT_ROOT / "data.xlsx"
KNOWLEDGE_FILE = PROJECT_ROOT / "logs" / "email_knowledge.csv"
BACKUP_DIR = PROJECT_ROOT / "backup"

BACKUP_DIR.mkdir(exist_ok=True)

# =========================================================
# HARD RULES (EMAIL CHẮC CHẮN SAI)
# =========================================================
BAD_PATTERNS = [
    "mailer-daemon",
    "no-reply",
    "postmaster",
    "os8pr",
    "apcprd",
    ".local",
]

# Statuses từ read_email1.py cần bị xóa khỏi data.xlsx
DEAD_STATUSES = {"hard_bounce", "policy_reject", "spam_block", "invalid"}


def is_hard_bad_email(email: str) -> bool:
    if not isinstance(email, str):
        return True
    email = email.lower()
    if "@" not in email or "." not in email:
        return True
    for p in BAD_PATTERNS:
        if p in email:
            return True
    return False

def extract_domain(email: str) -> str:
    try:
        return email.split("@")[1].lower()
    except Exception:
        return ""

# =========================================================
# KNOWLEDGE HANDLER
# =========================================================
def load_knowledge():
    """
    Đọc email_knowledge.csv — hỗ trợ cả schema cũ (REASON) và mới (STATUS).
    Trả về set các email bị đánh dấu là DEAD (hard_bounce / policy_reject / spam_block).
    """
    if not KNOWLEDGE_FILE.exists():
        return pd.DataFrame(), set()

    df = pd.read_csv(KNOWLEDGE_FILE, encoding="utf-8-sig")
    df.columns = df.columns.str.upper().str.strip()
    df["EMAIL"] = df["EMAIL"].astype(str).str.lower().str.strip()

    # Hỗ trợ cả STATUS (schema mới) lẫn REASON (schema cũ)
    status_col = "STATUS" if "STATUS" in df.columns else "REASON"
    df["_STATUS"] = df[status_col].astype(str).str.lower().str.strip()

    dead_set = set(df[df["_STATUS"].isin(DEAD_STATUSES)]["EMAIL"].unique())
    return df, dead_set

# =========================================================
# MAIN CLEAN LOGIC
# =========================================================
def main():
    print("=" * 60)
    print("  CLEAN DATA — Pattern + Knowledge-Aware")
    print("=" * 60)

    # Backup data
    shutil.copy(DATA_FILE, BACKUP_DIR / f"data_{datetime.now():%Y%m%d_%H%M}.xlsx")
    print(f"  Backup saved to backup/")

    df = pd.read_excel(DATA_FILE)
    df.columns = df.columns.str.strip().str.upper().str.replace(" ", "_")
    print(f"  Loaded {len(df)} rows from data.xlsx")

    df_kn, dead_set = load_knowledge()
    print(f"  Knowledge: {len(dead_set)} dead emails (hard_bounce / policy / spam)")

    rule1_removed = []   # hard pattern
    rule2_removed = []   # dead in knowledge (bounce scanner)

    for idx, row in df.iterrows():
        for role in ["CNEE", "SHIPPER"]:
            email_col   = f"{role}_EMAIL"

            email = row.get(email_col)
            if not isinstance(email, str) or not email.strip():
                continue

            email_lc = email.strip().lower()

            # Rule 1: obviously bad format / system address
            if is_hard_bad_email(email_lc):
                df.at[idx, email_col] = ""
                rule1_removed.append(email_lc)
                continue

            # Rule 2: confirmed dead by bounce scanner (read_email1.py)
            if email_lc in dead_set:
                df.at[idx, email_col] = ""
                rule2_removed.append(email_lc)
                continue

    # Save cleaned data
    df.to_excel(DATA_FILE, index=False)

    print()
    print("  RESULTS:")
    print(f"  Rule 1 (bad pattern)  : {len(set(rule1_removed))} emails cleared")
    print(f"  Rule 2 (bounce/dead)  : {len(set(rule2_removed))} emails cleared from knowledge")
    print(f"  Total unique cleared  : {len(set(rule1_removed) | set(rule2_removed))}")
    print()
    if rule2_removed:
        print("  Sample dead emails removed:")
        for e in list(set(rule2_removed))[:5]:
            print(f"    - {e}")
    print("=" * 60)
    print("  TIP: Để cập nhật knowledge mới nhất, chạy 'read_email1.py' trước.")
    print("=" * 60)


# =========================================================
if __name__ == "__main__":
    main()
