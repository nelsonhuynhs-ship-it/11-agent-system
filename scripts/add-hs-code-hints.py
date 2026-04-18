"""
add-hs-code-hints.py
=====================
Add HS_CODE_HINT column to cnee_master_v2_final.xlsx schema v3.
Maps COMMODITY_CATEGORY → standard HS codes per WCO Harmonized System.

Nelson uses this to filter Panjiva search by HS code chapter/heading,
which returns 2-5K high-intent CNEEs vs 28K blind raw list.

Source: WCO HS Nomenclature 2022, verified against US HTS.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

MASTER = Path("D:/OneDrive/NelsonData/email/cnee_master_v2_final.xlsx")

# COMMODITY_CATEGORY → {primary: "####", secondary: "####,####"}
# primary = the strongest HS code to filter on (most specific)
# secondary = additional codes to widen search if needed
HS_CODE_MAP: dict[str, dict] = {
    "FURNITURE_INDOOR": {
        "primary": "9403",
        "secondary": "9401",
        "desc": "Other furniture (9403); seats/chairs (9401)",
    },
    "FURNITURE_OUTDOOR": {
        "primary": "9401",
        "secondary": "9403",
        "desc": "Seats incl. convertible (9401); other furniture (9403)",
    },
    "FLOORING": {
        "primary": "4418",
        "secondary": "4409",
        "desc": "Builders' joinery - floors, parquet (4418); wood continuously shaped (4409)",
    },
    "PLYWOOD": {
        "primary": "4412",
        "secondary": "4410,4411",
        "desc": "Plywood, veneered panels (4412); particle board (4410); fibreboard (4411)",
    },
    "WOODEN_DECOR": {
        "primary": "4420",
        "secondary": "6913,4414",
        "desc": "Wood marquetry, decorative articles (4420); ceramic ornaments (6913); picture frames (4414)",
    },
    "CANDLE": {
        "primary": "3406",
        "secondary": "",
        "desc": "Candles, tapers and the like (3406)",
    },
    "GARMENT": {
        "primary": "6101-6117",
        "secondary": "6201-6217",
        "desc": "Knitted apparel (61); non-knitted apparel (62)",
    },
    "PLASTIC": {
        "primary": "3923",
        "secondary": "3924,3926",
        "desc": "Plastic packaging articles (3923); tableware (3924); other plastic articles (3926)",
    },
    "RUBBER": {
        "primary": "4016",
        "secondary": "4014,4015",
        "desc": "Other articles of vulcanized rubber (4016); hygienic/medical (4014); clothing (4015)",
    },
    "FOOD_AMBIENT": {
        "primary": "2005",
        "secondary": "2103,2106",
        "desc": "Vegetables preserved (2005); sauces (2103); food preparations NES (2106)",
    },
    "FOOD_FROZEN": {
        "primary": "0304",
        "secondary": "0207,0210",
        "desc": "Fish fillets frozen (0304); poultry frozen (0207); meat preserved (0210)",
    },
    "FOOD_FRUIT": {
        "primary": "2008",
        "secondary": "2009,0811",
        "desc": "Fruits preserved (2008); fruit juices (2009); frozen fruit (0811)",
    },
    "SEAFOOD": {
        "primary": "0304",
        "secondary": "0301-0308,1605",
        "desc": "Fish fillets (0304); live/fresh fish (0301-0308); crustaceans preserved (1605)",
    },
    "TOY": {
        "primary": "9503",
        "secondary": "9504,9505",
        "desc": "Toys, tricycles (9503); games (9504); festive articles (9505)",
    },
    "STEEL": {
        "primary": "7308",
        "secondary": "7314,7326",
        "desc": "Structures of iron/steel (7308); steel mesh (7314); other articles (7326)",
    },
    "LED_LIGHT": {
        "primary": "9405",
        "secondary": "8539",
        "desc": "Lamps and lighting fittings (9405); LED/discharge lamps (8539)",
    },
    "PACKAGING": {
        "primary": "4819",
        "secondary": "3923,6305",
        "desc": "Cartons, boxes of paper (4819); plastic packaging (3923); woven bags (6305)",
    },
    "OTHERS": {
        "primary": "",
        "secondary": "",
        "desc": "Unclassified — run Panjiva text search on COMPANY name",
    },
}


def main():
    print(f"Loading {MASTER} ...")
    df = pd.read_excel(MASTER)
    print(f"Rows: {len(df):,}, Cols before: {len(df.columns)}")

    if "COMMODITY_CATEGORY" not in df.columns:
        raise SystemExit("COMMODITY_CATEGORY missing — run remap-cnee-schema-v3.py first")

    # Add 2 columns: HS_CODE_PRIMARY + HS_CODE_SECONDARY
    df["HS_CODE_PRIMARY"] = df["COMMODITY_CATEGORY"].map(
        lambda c: HS_CODE_MAP.get(c, {}).get("primary", "")
    )
    df["HS_CODE_SECONDARY"] = df["COMMODITY_CATEGORY"].map(
        lambda c: HS_CODE_MAP.get(c, {}).get("secondary", "")
    )

    # Distribution report
    print()
    print("=== HS code coverage ===")
    has_primary = df["HS_CODE_PRIMARY"].astype(str).str.len() > 0
    print(f"With HS_CODE_PRIMARY: {has_primary.sum():,} ({has_primary.sum()*100/len(df):.1f}%)")
    print(f"Without (OTHERS): {(~has_primary).sum():,}")

    print()
    print("=== Top HS codes ===")
    for hs, c in df["HS_CODE_PRIMARY"].value_counts().head(20).items():
        if not hs: continue
        cat = next((k for k, v in HS_CODE_MAP.items() if v["primary"] == hs), "?")
        desc = HS_CODE_MAP.get(cat, {}).get("desc", "")
        print(f"  HS {hs:10} {c:6,}   {cat:20} {desc[:60]}")

    df.to_excel(MASTER, index=False)
    print()
    print(f"✅ Updated {MASTER}")
    print(f"   Cols now: {len(df.columns)} (added HS_CODE_PRIMARY + HS_CODE_SECONDARY)")


if __name__ == "__main__":
    main()
