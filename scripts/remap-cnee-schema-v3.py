"""
remap-cnee-schema-v3.py
========================
Apply schema v3 to cnee_master_v2_final.xlsx:
- Map old CAMPAIGN_ID → COMMODITY_CATEGORY (18 standardized)
- Detect ORIGIN_COUNTRY from campaign/source hints
- Detect DESTINATION_REGION (US/CA/MX)
- Preserve all existing fields

Writes cnee_master_v3.xlsx; original v2_final preserved.
"""
from __future__ import annotations
import shutil
from pathlib import Path
from datetime import datetime
import pandas as pd

MASTER_V2 = Path("D:/OneDrive/NelsonData/email/cnee_master_v2_final.xlsx")
MASTER_V3 = Path("D:/OneDrive/NelsonData/email/cnee_master_v3.xlsx")

# ─── COMMODITY_CATEGORY mapping (18 categories + OTHERS) ──────────────────
COMMODITY_MAP = {
    # Furniture family (default indoor — Sếp tune later if needed)
    "FURNITURE": "FURNITURE_INDOOR",
    "LCHFURNITURE": "FURNITURE_INDOOR",
    "WOODEN FURNITURE": "FURNITURE_INDOOR",
    "FURNITURE: CHAIR, SOFA": "FURNITURE_INDOOR",
    "FURNITURE C.A": "FURNITURE_INDOOR",
    "DATE CANADA CNEE FURNITURE FEB 2025": "FURNITURE_INDOOR",
    # Flooring
    "FLOORING": "FLOORING",
    "FLOORING LOC": "FLOORING",
    # Plywood
    "PLYWOOD": "PLYWOOD",
    "PLYWOOD LOC": "PLYWOOD",
    "DATA CANADA PLYWOOD": "PLYWOOD",
    # Wooden decor
    "POTTERY": "WOODEN_DECOR",
    "POTTERY LOC": "WOODEN_DECOR",
    "WOODEN": "WOODEN_DECOR",
    "STONE": "WOODEN_DECOR",
    # Plastic
    "PLASTIC": "PLASTIC",
    "LOC PLASTIC": "PLASTIC",
    "PLASTIC CANADA LOC": "PLASTIC",
    "PLASTIC C.A": "PLASTIC",
    # Packaging
    "PLASTIC BAG": "PACKAGING",
    "PLASTIC BAGS": "PACKAGING",
    "DATA CANADA WOVEN BAGS": "PACKAGING",
    # Rubber
    "RUBBER": "RUBBER",
    "RUBBER LOC": "RUBBER",
    # Candle
    "CANDLE": "CANDLE",
    # Food
    "FOODSTUFF": "FOOD_AMBIENT",
    "LCHFOOD": "FOOD_AMBIENT",
    "CANNED FOOD": "FOOD_AMBIENT",
    "DATA SHIPMENT THAILAND CANNED FOOD": "FOOD_AMBIENT",
    "DATA THAI LAN FOODSTUFF": "FOOD_AMBIENT",
    "FROZEN": "FOOD_FROZEN",
    "FRUIT JUICE": "FOOD_FRUIT",
    "SEAFOOD": "SEAFOOD",
    # Toy
    "TOY": "TOY",
    "DATA CANADA PLASTIC TOYS": "TOY",
    # Garment
    "GARMENT": "GARMENT",
    "GARMENT C.A": "GARMENT",
    "GARMENT BANGLADESH": "GARMENT",
    # Metal
    "STEEL RACK": "STEEL",
    "DATA US NAILS": "STEEL",
    # Light
    "LED LIGHT": "LED_LIGHT",
    # Junk / unclassified
    "TANJUNG PELEPAS LOC": "OTHERS",
    "MALAYSIA": "OTHERS",
    "SHIPPER MALAYSIA": "OTHERS",
    "USA_VERIFIED": "OTHERS",
    "DATA LỌC": "OTHERS",
    "CANNADA": "OTHERS",
    "UNCATEGORIZED": "OTHERS",
    "COÓ PHẢN HỒI HỔI GIÁ": "OTHERS",
}

# ─── ORIGIN_COUNTRY detection rules (keyword → country code) ──────────────
ORIGIN_RULES = [
    # keyword lookup in CAMPAIGN_ID / SOURCE_FILE
    (["THAILAND", "THAI LAN", "THAI"], "TH"),
    (["MALAYSIA", "SHIPPER MALAYSIA"], "MY"),
    (["BANGLADESH"], "BD"),
    (["TANJUNG PELEPAS", "TANJUNG", "LOC "], "MY"),  # Tanjung Pelepas is MY port
    (["CAMBODIA", "KH "], "KH"),
    (["INDONESIA"], "ID"),
    (["CHINA", "CN "], "CN"),
    (["INDIA"], "IN"),
]
ORIGIN_DEFAULT = "VN"  # Nelson Freight is Vietnam-based

# ─── DESTINATION_REGION detection (keyword → region) ───────────────────────
DEST_RULES = [
    (["CANADA", "CANNADA", "C.A"], "CA"),
    (["MEXICO"], "MX"),
    (["USA", "US ", "UNITED STATES", "DATA US"], "US"),
]
DEST_DEFAULT = "US"


def _s(x) -> str:
    """Safely coerce to upper string (handles NaN/float)."""
    if x is None:
        return ""
    try:
        if pd.isna(x):
            return ""
    except Exception:
        pass
    return str(x).strip().upper()


def classify_commodity(campaign, source) -> str:
    c = _s(campaign)
    if c in COMMODITY_MAP:
        return COMMODITY_MAP[c]
    s = _s(source)
    for key, val in COMMODITY_MAP.items():
        if key in s:
            return val
    return "OTHERS"


def detect_origin(campaign, source) -> str:
    text = f"{_s(campaign)} {_s(source)}"
    for keywords, country in ORIGIN_RULES:
        for kw in keywords:
            if kw in text:
                return country
    return ORIGIN_DEFAULT


def detect_destination(campaign, source) -> str:
    text = f"{_s(campaign)} {_s(source)}"
    for keywords, region in DEST_RULES:
        for kw in keywords:
            if kw in text:
                return region
    return DEST_DEFAULT


def main():
    print(f"Loading {MASTER_V2} ...")
    df = pd.read_excel(MASTER_V2)
    print(f"Rows: {len(df):,}")
    print()

    # Apply 3 new columns
    df["COMMODITY_CATEGORY"] = df.apply(
        lambda r: classify_commodity(r.get("CAMPAIGN_ID", ""), r.get("SOURCE_FILE", "")),
        axis=1,
    )
    df["ORIGIN_COUNTRY"] = df.apply(
        lambda r: detect_origin(r.get("CAMPAIGN_ID", ""), r.get("SOURCE_FILE", "")),
        axis=1,
    )
    df["DESTINATION_REGION"] = df.apply(
        lambda r: detect_destination(r.get("CAMPAIGN_ID", ""), r.get("SOURCE_FILE", "")),
        axis=1,
    )

    print("=== COMMODITY_CATEGORY distribution ===")
    for cat, c in df["COMMODITY_CATEGORY"].value_counts().items():
        print(f"  {cat:20} {c:6,}")
    print()
    print("=== ORIGIN_COUNTRY distribution ===")
    for o, c in df["ORIGIN_COUNTRY"].value_counts().items():
        print(f"  {o:5} {c:6,}")
    print()
    print("=== DESTINATION_REGION distribution ===")
    for d, c in df["DESTINATION_REGION"].value_counts().items():
        print(f"  {d:5} {c:6,}")
    print()

    # Write v3
    df.to_excel(MASTER_V3, index=False)
    print(f"✅ Wrote {MASTER_V3}")
    print(f"   {len(df):,} rows · {len(df.columns)} columns (v2 had 21)")
    print()
    print("New columns: COMMODITY_CATEGORY, ORIGIN_COUNTRY, DESTINATION_REGION")


if __name__ == "__main__":
    main()
