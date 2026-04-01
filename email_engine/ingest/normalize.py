import pandas as pd
import re
from pathlib import Path

# =========================================================
# USER CONFIG
# =========================================================
USER_CHOICE = "all"  # furniture | foodstuff | all

# =========================================================
# PATH CONFIG
# =========================================================
BASE_DIR = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent
LOG_DIR = PROJECT_ROOT / "logs"

PANJIVA_FILES = list(BASE_DIR.glob("panjiva_raw_*.xlsx"))
if not PANJIVA_FILES:
    raise FileNotFoundError("Không tìm thấy file panjiva_raw_*.xlsx")

OUT_FILE = BASE_DIR / "data_from_panjiva_final.xlsx"
KNOWLEDGE_FILE = PROJECT_ROOT / "logs" / "email_knowledge.csv"

PORT_MAP_FILE = PROJECT_ROOT / "data" / "Port_Code_Mapping_Final.xlsx"
PORT_MAP_SHEET = "Port_Code_Mapping_Final"

# =========================================================
# UTIL: CMD NAME FROM FILE
# =========================================================
def extract_cmd_name(file_path: Path) -> str:
    name = file_path.stem.lower()
    if "panjiva_raw_" not in name:
        return ""
    return name.split("panjiva_raw_", 1)[1].upper()

AVAILABLE_FILES = {extract_cmd_name(f): f for f in PANJIVA_FILES}

if USER_CHOICE == "all":
    SELECTED_FILES = list(AVAILABLE_FILES.values())
else:
    key = USER_CHOICE.upper()
    if key not in AVAILABLE_FILES:
        raise ValueError(f"CMD_NAME không hợp lệ. Available: {list(AVAILABLE_FILES)}")
    SELECTED_FILES = [AVAILABLE_FILES[key]]

# =========================================================
# PORT MAPPING
# =========================================================
port_df = pd.read_excel(PORT_MAP_FILE, sheet_name=PORT_MAP_SHEET)
port_df.columns = port_df.columns.astype(str).str.strip().str.lower()

DESTINATION_MAP = (
    port_df[["portname", "portcode"]]
    .dropna()
    .assign(
        portname=lambda d: d["portname"].astype(str).str.upper().str.strip(),
        portcode=lambda d: d["portcode"].astype(str).str.upper().str.strip(),
        length=lambda d: d["portname"].str.len(),
    )
    .sort_values("length", ascending=False)
)

DESTINATION_MAP = list(zip(DESTINATION_MAP["portname"], DESTINATION_MAP["portcode"]))

def map_destination(text):
    if not isinstance(text, str) or not text.strip():
        return "UNMAPPED"
    t = text.upper()
    for name, code in DESTINATION_MAP:
        if name in t:
            return code
    return "UNMAPPED"

# =========================================================
# POL MAPPING
# =========================================================
POL_RULES = {
    "HOCHIMINH": "HCM",
    "HO CHI MINH": "HCM",
    "VUNG TAU": "HCM",
    "CAI MEP": "HCM",
    "HAI PHONG": "HPH",
}

def map_pol(text):
    if not isinstance(text, str):
        return ""
    t = text.upper()
    for k, v in POL_RULES.items():
        if k in t:
            return v
    return ""

# =========================================================
# EMAIL + PIC LOGIC (UPGRADED NORMALIZATION)
# =========================================================
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

FREE_EMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
}

GENERIC_LOCAL_PARTS = {
    "info",
    "sales",
    "contact",
    "import",
    "export",
    "admin",
    "support",
    "cs",
    "team",
}

def clean_email_prefix(email):
    if not isinstance(email, str) or "@" not in email:
        return ""
    email = email.lower().strip()
    local, domain = email.split("@", 1)

    # 🚀 NEW: remove leading punctuation
    local = local.lstrip(".,-")

    # 🚀 NEW: remove leading em / me / te
    for p in ("em", "me", "te"):
        if local.startswith(p) and len(local) > 4:
            local = local[len(p):]
            local = local.lstrip(".,-")

    return f"{local}@{domain}"

def normalize_email(email):
    if not isinstance(email, str) or "@" not in email:
        return ""
    email = email.lower().strip()
    email = clean_email_prefix(email)
    return email

def derive_pic_from_email(email: str) -> str:
    if not isinstance(email, str) or "@" not in email:
        return ""

    local, domain = email.split("@", 1)
    domain = domain.lower()

    if domain in FREE_EMAIL_DOMAINS:
        return ""

    tokens = re.split(r"[._\-]", local)
    tokens = [t for t in tokens if t.isalpha()]

    if not tokens or tokens[0] in GENERIC_LOCAL_PARTS:
        return ""

    if len(tokens) == 1:
        return tokens[0].capitalize()

    return f"{tokens[0].capitalize()} {tokens[-1].capitalize()}"

def extract_emails(*cells):
    emails = []
    for c in cells:
        if isinstance(c, str):
            for e in EMAIL_REGEX.findall(c):
                e = normalize_email(e)
                if e:
                    emails.append(e)
    return list(set(emails))

# =========================================================
# LOAD EMAIL KNOWLEDGE
# =========================================================
bad_emails = set()
if KNOWLEDGE_FILE.exists():
    k = pd.read_csv(KNOWLEDGE_FILE)
    k.columns = k.columns.astype(str).str.lower()
    if "email" in k.columns and "status" in k.columns:
        bad_emails = set(
            k[k["status"].isin(["bounce", "hard_bounce", "invalid"])]
            ["email"]
            .astype(str)
            .str.lower()
        )

# =========================================================
# MAIN PROCESS
# =========================================================
final_frames = []

for RAW_FILE in SELECTED_FILES:
    CMD_NAME = extract_cmd_name(RAW_FILE)

    xls = pd.ExcelFile(RAW_FILE)
    sheet_name = next((s for s in xls.sheet_names if "import" in s.lower()), None)
    df = pd.read_excel(RAW_FILE, sheet_name=sheet_name)

    df.columns = (
        df.columns.astype(str)
        .str.replace("\ufeff", "", regex=False)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("/", "_")
        .str.replace("-", "_")
    )

    def find_col(keys):
        for c in df.columns:
            if all(k in c for k in keys):
                return c
        return None

    COL_CNEE = find_col(["consignee"])
    COL_SHIPPER = find_col(["shipper"])
    COL_CARRIER = find_col(["carrier"])
    COL_DEST = find_col(["destination"])
    COL_POL_SRC = find_col(["place", "receipt"])

    CNEE_EMAIL_COLS = [c for c in df.columns if "consignee" in c and "email" in c]
    SHIPPER_EMAIL_COLS = [c for c in df.columns if "shipper" in c and "email" in c]

    rows = []

    for _, r in df.iterrows():
        cnee = str(r.get(COL_CNEE, "")).strip().upper()
        shipper = str(r.get(COL_SHIPPER, "")).strip().upper()

        cnee_emails = extract_emails(*(r.get(c, "") for c in CNEE_EMAIL_COLS))
        shipper_emails = extract_emails(*(r.get(c, "") for c in SHIPPER_EMAIL_COLS))

        for ce in cnee_emails:
            for se in shipper_emails or [""]:
                rows.append(
                    {
                        "CNEE_NAME": cnee,
                        "CNEE_EMAIL": ce,
                        "CNEE_PIC": derive_pic_from_email(ce),
                        "SHIPPER_NAME": shipper,
                        "SHIPPER_EMAIL": se,
                        "SHIPPER_PIC": derive_pic_from_email(se),
                        "CARRIER": str(r.get(COL_CARRIER, "")).strip().upper(),
                        "DESTINATION": map_destination(str(r.get(COL_DEST, ""))),
                        "POL": map_pol(str(r.get(COL_POL_SRC, ""))),
                        "STATUS": "BLOCKED" if ce in bad_emails else "",
                    }
                )

    df_exp = pd.DataFrame(rows)

    def norm_name(x):
        return " ".join(str(x).upper().strip().split())

    def norm_email(x):
        return normalize_email(str(x))

    for col in ["CNEE_NAME", "SHIPPER_NAME"]:
        df_exp[col + "_N"] = df_exp[col].apply(norm_name)

    for col in ["CNEE_EMAIL", "SHIPPER_EMAIL"]:
        df_exp[col + "_N"] = df_exp[col].apply(norm_email)

    agg = (
        df_exp.groupby(
            [
                "CNEE_NAME_N",
                "CNEE_EMAIL_N",
                "CNEE_PIC",
                "SHIPPER_NAME_N",
                "SHIPPER_EMAIL_N",
                "SHIPPER_PIC",
            ],
            dropna=False,
        )
        .agg(
            TOTAL_SHIPMENT=("CNEE_EMAIL", "count"),
            DESTINATION=("DESTINATION", lambda x: ",".join(sorted(set(filter(None, x))))),
            POL=("POL", lambda x: ",".join(sorted(set(filter(None, x))))),
            CARRIER=("CARRIER", lambda x: ",".join(sorted(set(filter(None, x))))),
            STATUS=("STATUS", "max"),
        )
        .reset_index()
    )

    agg.rename(
        columns={
            "CNEE_NAME_N": "CNEE_NAME",
            "CNEE_EMAIL_N": "CNEE_EMAIL",
            "SHIPPER_NAME_N": "SHIPPER_NAME",
            "SHIPPER_EMAIL_N": "SHIPPER_EMAIL",
        },
        inplace=True,
    )

    # =====================================================
    # MERGE BY CNEE_EMAIL (LOGIC CŨ – GIỮ NGUYÊN)
    # =====================================================
    def merge_by_cnee_email(df):
        merged = []
        for email, g in df.groupby("CNEE_EMAIL"):
            with_se = g[g["SHIPPER_EMAIL"].astype(str).str.strip() != ""]
            if len(with_se) <= 1:
                base = with_se.iloc[0] if len(with_se) == 1 else g.iloc[0]
                row = base.copy()
                row["TOTAL_SHIPMENT"] = g["TOTAL_SHIPMENT"].sum()

                for col in ["DESTINATION", "POL", "CARRIER"]:
                    vals = set()
                    for v in g[col]:
                        if isinstance(v, str) and v:
                            vals.update(v.split(","))
                    row[col] = ",".join(sorted(vals))

                merged.append(row.to_dict())
            else:
                merged.extend(g.to_dict("records"))
        return pd.DataFrame(merged)

    agg = merge_by_cnee_email(agg)

    agg["CMD_NAME"] = CMD_NAME
    final_frames.append(agg)

# =========================================================
# FINAL OUTPUT
# =========================================================
final_df = pd.concat(final_frames, ignore_index=True)

final_cols = [
    "CNEE_NAME",
    "CNEE_EMAIL",
    "CNEE_PIC",
    "SHIPPER_NAME",
    "SHIPPER_EMAIL",
    "SHIPPER_PIC",
    "CMD_NAME",
    "POL",
    "CARRIER",
    "DESTINATION",
    "TOTAL_SHIPMENT",
    "STATUS",
]

final_df[final_cols].to_excel(OUT_FILE, index=False)
print(f"\nDONE – {len(final_df)} rows written to {OUT_FILE.name}")
