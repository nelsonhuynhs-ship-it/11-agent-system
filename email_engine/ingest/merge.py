import pandas as pd
from pathlib import Path
from datetime import datetime

# =========================================================
# PATH CONFIG
# =========================================================
BASE_DIR = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent

MASTER_FILE = BASE_DIR / "data.xlsx"
PANJIVA_FILE = BASE_DIR / "data_from_panjiva_final.xlsx"

BACKUP_DIR = PROJECT_ROOT / "backup"
BACKUP_DIR.mkdir(exist_ok=True)

BACKUP_FILE = BACKUP_DIR / f"data_backup_{datetime.now():%Y%m%d_%H%M%S}.xlsx"

# =========================================================
# UTIL
# =========================================================
def norm(x):
    if not isinstance(x, str):
        return ""
    return x.strip().lower()

# =========================================================
# LOAD DATA
# =========================================================
if not MASTER_FILE.exists():
    raise FileNotFoundError("Không tìm thấy data.xlsx")

if not PANJIVA_FILE.exists():
    raise FileNotFoundError("Không tìm thấy data_from_panjiva_final.xlsx")

df_master = pd.read_excel(MASTER_FILE)
df_new = pd.read_excel(PANJIVA_FILE)

print(f"Master rows before: {len(df_master)}")
print(f"Panjiva rows: {len(df_new)}")

# =========================================================
# ALIGN SCHEMA
# =========================================================
for col in df_master.columns:
    if col not in df_new.columns:
        df_new[col] = ""

for col in df_new.columns:
    if col not in df_master.columns:
        df_master[col] = ""

df_new = df_new[df_master.columns]

# =========================================================
# BACKUP MASTER
# =========================================================
df_master.to_excel(BACKUP_FILE, index=False)
print(f"Backup created: {BACKUP_FILE.name}")

# =========================================================
# APPEND
# =========================================================
df_all = pd.concat([df_master, df_new], ignore_index=True)
print(f"Rows after append: {len(df_all)}")

# =========================================================
# STEP 1: REMOVE FULL DUPLICATES (CNEE + SHIPPER)
# =========================================================
df_all["_CNEE_EMAIL_N"] = df_all["CNEE_EMAIL"].apply(norm)
df_all["_SHIPPER_EMAIL_N"] = df_all["SHIPPER_EMAIL"].apply(norm)
df_all["_SHIPPER_NAME_N"] = df_all["SHIPPER_NAME"].apply(norm)

before = len(df_all)

df_all = df_all.drop_duplicates(
    subset=["_CNEE_EMAIL_N", "_SHIPPER_EMAIL_N", "_SHIPPER_NAME_N"],
    keep="first",
)

print(f"Removed full duplicate rows: {before - len(df_all)}")

# =========================================================
# STEP 2: CLEAR DUPLICATED CNEE EMAIL (KEEP ROWS)
# =========================================================
seen_cnee = set()
rows_clear_email = []

for idx, email in df_all["_CNEE_EMAIL_N"].items():
    if not email:
        continue
    if email in seen_cnee:
        rows_clear_email.append(idx)
    else:
        seen_cnee.add(email)

df_all.loc[rows_clear_email, "CNEE_EMAIL"] = ""

print(f"Cleared duplicated CNEE_EMAIL on rows: {len(rows_clear_email)}")

# =========================================================
# CLEAN TEMP COLS
# =========================================================
df_all.drop(
    columns=["_CNEE_EMAIL_N", "_SHIPPER_EMAIL_N", "_SHIPPER_NAME_N"],
    inplace=True,
)

# =========================================================
# SAVE
# =========================================================
df_all.to_excel(MASTER_FILE, index=False)

print("DONE – Data cleaned:")
print("✔ Full duplicate rows removed")
print("✔ CNEE email deduplicated without losing shipper rows")
