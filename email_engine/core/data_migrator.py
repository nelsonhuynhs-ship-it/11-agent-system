# data_migrator.py — Migrate cnee_master.xlsx 16→25 columns
import re
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
SRC = DATA_DIR / "cnee_master.xlsx"
DST = DATA_DIR / "cnee_master_v2.xlsx"

# CAMPAIGN_ID → INDUSTRY
CAMPAIGN_INDUSTRY = {
    "FURNITURE": "Furniture", "FLOORING": "Flooring", "CANDLE": "Candle",
    "PLASTIC": "Plastic", "GARMENT": "Garment", "SEAFOOD": "Seafood",
    "ELECTRONICS": "Electronics", "MALAYSIA": "General", "CAMBODIA": "General",
    "THAILAND": "General", "CHINA": "General",
}

# CAMPAIGN_ID → common DESTINATION when missing
CAMPAIGN_DEST = {
    "FURNITURE": "USLAX,USLGB", "FLOORING": "USLAX,USLGB",
    "CANDLE": "USLAX,USLGB,USEWR", "PLASTIC": "USLAX,USEWR",
    "GARMENT": "USEWR,USLAX", "SEAFOOD": "USLAX",
    "MALAYSIA": "USLAX,USLGB", "CAMBODIA": "USLAX,USLGB",
}

DOMAIN_COUNTRY = {
    ".vn": "VN", ".ca": "CA", ".uk": "UK", ".au": "AU", ".sg": "SG",
    ".de": "DE", ".fr": "FR", ".jp": "JP", ".cn": "CN", ".hk": "HK",
}

DEST_COUNTRY = {"US": "US", "CA": "CA", "USLAX": "US", "USLGB": "US",
                "USEWR": "US", "USSAV": "US", "USCHI": "US", "CAYVR": "CA",
                "CAYTO": "CA", "CAMTR": "CA"}


def _detect_country(row) -> str:
    email = str(row.get("EMAIL", "")).lower()
    dest = str(row.get("DESTINATION", "")).upper()

    for tld, cc in DOMAIN_COUNTRY.items():
        domain = email.split("@")[-1] if "@" in email else ""
        if domain.endswith(tld):
            return cc

    for prefix, cc in DEST_COUNTRY.items():
        if dest.startswith(prefix):
            return cc

    if ".com" in email:
        return "US"
    return ""


def migrate():
    if not SRC.exists():
        raise FileNotFoundError(f"Source not found: {SRC}")

    df = pd.read_excel(SRC)
    df.columns = df.columns.str.strip().str.upper()
    original_rows = len(df)

    stats = {
        "original_rows": original_rows,
        "original_cols": len(df.columns),
        "pol_filled": 0,
        "dest_filled": 0,
    }

    # --- Auto-fill POL ---
    missing_pol = df["POL"].isna() | (df["POL"].astype(str).str.strip() == "")
    stats["pol_filled"] = int(missing_pol.sum())
    df.loc[missing_pol, "POL"] = "HCM"

    # --- Auto-fill DESTINATION ---
    missing_dest = df["DESTINATION"].isna() | (df["DESTINATION"].astype(str).str.strip() == "")
    for idx in df[missing_dest].index:
        cid = str(df.at[idx, "CAMPAIGN_ID"]).upper() if pd.notna(df.at[idx, "CAMPAIGN_ID"]) else ""
        default_dest = CAMPAIGN_DEST.get(cid, "USLAX,USLGB")
        df.at[idx, "DESTINATION"] = default_dest
    stats["dest_filled"] = int(missing_dest.sum())

    # --- Add 9 new columns ---
    df["PIC_TITLE"] = ""
    df["PHONE"] = ""
    df["WHATSAPP_OK"] = False
    df["COUNTRY"] = df.apply(_detect_country, axis=1)
    df["ARB_ORIGINS"] = ""
    df["LEAD_SCORE"] = 50
    df["BOUNCE_COUNT"] = 0
    df["LAST_REPLY"] = pd.NaT
    df["EMAIL_STATUS"] = "VALID"
    df["INDUSTRY"] = df["CAMPAIGN_ID"].apply(
        lambda x: CAMPAIGN_INDUSTRY.get(str(x).upper(), "Other") if pd.notna(x) else "Other"
    )

    df.to_excel(DST, index=False)

    stats["final_cols"] = len(df.columns)
    stats["final_rows"] = len(df)
    stats["output_file"] = str(DST)
    return stats


if __name__ == "__main__":
    result = migrate()
    print("\n=== Migration Complete ===")
    for k, v in result.items():
        print(f"  {k}: {v}")
