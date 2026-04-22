#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
panjiva_clean.py — Panjiva ETL Pipeline (A5)
=============================================
Clean + merge raw Panjiva .xlsx file into cnee_master_v2_final.xlsx.

6-step pipeline:
  Step 1 — READ & normalize raw Panjiva columns
  Step 2 — BLACKLIST filter (domains + keywords)
  Step 3 — LLM CLASSIFY commodity into 18 buckets
  Step 4 — PARSE STATE from Shipment Destination
  Step 5 — DEDUP against existing cnee_master
  Step 6 — FILTER hard-bounce emails

Returns a report dict. Writes to cnee_master atomically with backup.

CLI:
  python scripts/panjiva_clean.py --input panjiva_raw.xlsx --source-tag PANJIVA_2026W16
  python scripts/panjiva_clean.py --input panjiva_raw.xlsx --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import sys
import time
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

import pandas as pd

# ── Path setup ────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("panjiva_clean")

# ── Constants ─────────────────────────────────────────────────────────────────
BLACKLIST_FILE = _REPO_ROOT / "email_engine" / "data" / "competitor_blacklist.json"

# CNEE master resolution order (OneDrive primary → local fallback)
_ONEDRIVE_EMAIL = Path("D:/OneDrive/NelsonData/email")
CNEE_MASTER_CANDIDATES = [
    _ONEDRIVE_EMAIL / "cnee_master_v2_final.xlsx",
    _ONEDRIVE_EMAIL / "cnee_master_v2.xlsx",
    _REPO_ROOT / "email_engine" / "data" / "cnee_master_v2_final.xlsx",
    _REPO_ROOT / "email_engine" / "data" / "cnee_master.xlsx",
]

# Jobs/incoming dirs
DATA_PANJIVA = _REPO_ROOT / "email_engine" / "data_panjiva"
JOBS_DIR = DATA_PANJIVA / "jobs"
INCOMING_DIR = DATA_PANJIVA / "incoming"

# 18 commodity buckets per CNEE schema v3.1
COMMODITY_CATEGORIES = [
    "FLOORING", "FURNITURE_INDOOR", "FURNITURE_OUTDOOR",
    "RUBBER", "PLASTIC", "CANDLE", "TEXTILE", "APPAREL",
    "FOOTWEAR", "ELECTRONICS", "METAL", "WOOD", "CERAMIC",
    "FOOD", "CHEMICAL", "PAPER", "COSMETICS", "OTHERS",
]

# Keyword → commodity quick-map (no LLM call needed)
_KEYWORD_MAP: dict[str, str] = {
    "flooring": "FLOORING", "vinyl floor": "FLOORING", "laminate": "FLOORING",
    "hardwood floor": "FLOORING", "tile floor": "FLOORING", "plank": "FLOORING",
    "parquet": "FLOORING", "hardwood": "FLOORING", "lvt": "FLOORING",
    "spc floor": "FLOORING", "floor": "FLOORING",
    "furniture": "FURNITURE_INDOOR", "sofa": "FURNITURE_INDOOR",
    "chair": "FURNITURE_INDOOR", "table": "FURNITURE_INDOOR",
    "cabinet": "FURNITURE_INDOOR", "drawer": "FURNITURE_INDOOR",
    "bookcase": "FURNITURE_INDOOR", "desk": "FURNITURE_INDOOR",
    "bed frame": "FURNITURE_INDOOR", "mattress": "FURNITURE_INDOOR",
    "outdoor furniture": "FURNITURE_OUTDOOR", "patio": "FURNITURE_OUTDOOR",
    "garden furniture": "FURNITURE_OUTDOOR", "adirondack": "FURNITURE_OUTDOOR",
    "rubber": "RUBBER", "latex": "RUBBER", "gasket": "RUBBER",
    "plastic": "PLASTIC", "polypropylene": "PLASTIC", "polyethylene": "PLASTIC",
    "pvc": "PLASTIC", "hdpe": "PLASTIC", "nylon": "PLASTIC",
    "candle": "CANDLE", "wax": "CANDLE", "taper": "CANDLE",
    "textile": "TEXTILE", "fabric": "TEXTILE", "yarn": "TEXTILE",
    "curtain": "TEXTILE", "blanket": "TEXTILE",
    "apparel": "APPAREL", "garment": "APPAREL", "clothing": "APPAREL",
    "shirt": "APPAREL", "jacket": "APPAREL", "dress": "APPAREL",
    "footwear": "FOOTWEAR", "shoe": "FOOTWEAR", "boot": "FOOTWEAR",
    "sandal": "FOOTWEAR", "sneaker": "FOOTWEAR",
    "electronic": "ELECTRONICS", "circuit": "ELECTRONICS",
    "cable": "ELECTRONICS", "battery": "ELECTRONICS", "led": "ELECTRONICS",
    "steel": "METAL", "iron": "METAL", "aluminum": "METAL",
    "copper": "METAL", "metal": "METAL", "alloy": "METAL",
    "wood": "WOOD", "plywood": "WOOD", "lumber": "WOOD", "mdf": "WOOD",
    "ceramic": "CERAMIC", "porcelain": "CERAMIC",
    "food": "FOOD", "frozen": "FOOD", "seafood": "FOOD",
    "beverage": "FOOD", "snack": "FOOD",
    "chemical": "CHEMICAL", "solvent": "CHEMICAL", "resin": "CHEMICAL",
    "paper": "PAPER", "carton": "PAPER", "tissue": "PAPER",
    "cosmetic": "COSMETICS", "skincare": "COSMETICS", "beauty": "COSMETICS",
}

# HS code prefix → commodity
_HS_MAP: dict[str, str] = {
    "39": "PLASTIC",      # Plastics
    "40": "RUBBER",       # Rubber
    "44": "WOOD",         # Wood
    "48": "PAPER",        # Paper
    "54": "TEXTILE",      # Synthetic filaments
    "55": "TEXTILE",      # Synthetic staple fibres
    "57": "FLOORING",     # Carpets
    "61": "APPAREL",      # Knitted clothing
    "62": "APPAREL",      # Non-knitted clothing
    "64": "FOOTWEAR",     # Footwear
    "69": "CERAMIC",      # Ceramics
    "72": "METAL",        # Iron/steel
    "73": "METAL",        # Articles of iron/steel
    "76": "METAL",        # Aluminium
    "85": "ELECTRONICS",  # Electrical machinery
    "87": "ELECTRONICS",  # Vehicles (treated as electronics-adj)
    "94": "FURNITURE_INDOOR",  # Furniture
}


# ── Helper: load blacklist ─────────────────────────────────────────────────────
def _load_blacklist() -> dict:
    try:
        data = json.loads(BLACKLIST_FILE.read_text(encoding="utf-8"))
        whitelist = set(d.lower().strip() for d in data.get("whitelist_domains", []) if d)
        whitelist.add("pudongprime.vn")
        return {
            "domains": set(d.lower().strip() for d in data.get("domains", []) if d),
            "emails":  set(e.lower().strip() for e in data.get("emails", []) if e),
            "keywords": [k.upper().strip() for k in data.get("keywords_in_company", []) if k],
            "whitelist_domains": whitelist,
        }
    except Exception as exc:
        log.warning(f"Blacklist load failed: {exc} — competitor filter disabled")
        return {"domains": set(), "emails": set(), "keywords": [], "whitelist_domains": {"pudongprime.vn"}}


def _is_blacklisted(email: str, company: str, bl: dict) -> bool:
    em = (email or "").lower().strip()
    if not em or "@" not in em:
        return False
    domain = em.split("@", 1)[1]
    if domain in bl.get("whitelist_domains", set()):
        return False
    if em in bl["emails"] or domain in bl["domains"]:
        return True
    co = (company or "").upper()
    for kw in bl["keywords"]:
        if kw in co:
            return True
    return False


# ── Helper: resolve cnee_master path ──────────────────────────────────────────
def _resolve_cnee_master() -> Optional[Path]:
    for p in CNEE_MASTER_CANDIDATES:
        if p.exists():
            return p
    return None


# ── Step 1: Read & normalize Panjiva file ─────────────────────────────────────
def _read_panjiva(input_path: str) -> pd.DataFrame:
    """Read raw Panjiva XLSX → normalize to internal schema."""
    df = pd.read_excel(input_path, header=0, dtype=str)
    df = df.fillna("")

    # Detect column aliases (Panjiva sometimes varies headers slightly)
    col_map = {}
    for col in df.columns:
        cu = col.strip().upper()
        if "CONSIGNEE" in cu and "EMAIL" not in cu and "PHONE" not in cu and "ADDRESS" not in cu:
            if "CONSIGNEE" == cu or cu in ("CONSIGNEE NAME",):
                col_map["COMPANY"] = col
        if cu == "CONSIGNEE":
            col_map.setdefault("COMPANY", col)
        if "CONSIGNEE EMAIL 1" in cu or cu == "CONSIGNEE EMAIL 1":
            col_map["EMAIL"] = col
        if "CONSIGNEE EMAIL 2" in cu:
            col_map["EMAIL2"] = col
        if "CONSIGNEE EMAIL 3" in cu:
            col_map["EMAIL3"] = col
        if "CONSIGNEE PHONE 1" in cu or cu == "CONSIGNEE PHONE 1":
            col_map["PHONE"] = col
        if "SHIPMENT DESTINATION" in cu:
            col_map["DESTINATION"] = col
        if "PLACE OF RECEIPT" in cu:
            col_map["POL"] = col
        if "MATCHING FIELDS" in cu:
            col_map["PRODUCT_DESCRIPTION"] = col
        if "HS CODE" in cu:
            col_map["HS_CODE"] = col
        if "SHIPPER" == cu:
            col_map["SHIPPER"] = col

    out = pd.DataFrame()
    def _get_col(key: str, lower: bool = False) -> pd.Series:
        col_name = col_map.get(key)
        if col_name and col_name in df.columns:
            s = df[col_name].fillna("").astype(str).str.strip()
            return s.str.lower() if lower else s
        return pd.Series([""] * len(df), dtype=str)

    out["COMPANY"]             = _get_col("COMPANY")
    out["EMAIL"]               = _get_col("EMAIL", lower=True)
    out["EMAIL2"]              = _get_col("EMAIL2", lower=True)
    out["PHONE"]               = _get_col("PHONE")
    out["DESTINATION"]         = _get_col("DESTINATION")
    out["POL"]                 = _get_col("POL")
    out["PRODUCT_DESCRIPTION"] = _get_col("PRODUCT_DESCRIPTION")
    out["HS_CODE"]             = _get_col("HS_CODE")
    out["SHIPPER"]             = _get_col("SHIPPER")

    # Drop rows where COMPANY is empty (header repetitions in some Panjiva exports)
    out = out[out["COMPANY"].str.len() > 0].reset_index(drop=True)

    log.info(f"Step 1 READ: {len(out)} rows after normalize")
    return out


# ── Step 2: Blacklist filter ───────────────────────────────────────────────────
def _filter_blacklist(df: pd.DataFrame, bl: dict) -> tuple[pd.DataFrame, int]:
    mask = df.apply(
        lambda r: _is_blacklisted(r["EMAIL"], r["COMPANY"], bl), axis=1
    )
    excluded = int(mask.sum())
    df_clean = df[~mask].reset_index(drop=True)
    log.info(f"Step 2 BLACKLIST: excluded {excluded}, kept {len(df_clean)}")
    return df_clean, excluded


# ── Step 2b: Bounce KB filter (Sprint 1 v3) ──────────────────────────────────
def _filter_bounce_kb(df: pd.DataFrame) -> tuple[pd.DataFrame, int, int]:
    """Apply bounce knowledge base filter on top of manual blacklist.

    Returns (df_clean, dropped_count, flagged_count).
    Flagged emails are kept but marked with PRIORITY=LOW.
    """
    try:
        from email_engine.core.bounce_knowledge import filter_emails, filter_company_name
    except ImportError as exc:
        log.warning(f"Step 2b BOUNCE_KB: import failed ({exc}) — skipping")
        return df, 0, 0

    emails = df["EMAIL"].tolist()
    try:
        result = filter_emails(emails)
    except Exception as exc:
        log.error(f"Step 2b BOUNCE_KB: filter_emails failed ({exc}) — rejecting import for safety")
        raise

    dropped_set = {item["email"].lower() for item in result["dropped"]}
    flagged_map = {item["email"].lower(): item["reason"] for item in result["flagged"]}

    # Also check company keywords via bounce KB (catches any new additions)
    additional_drop = set()
    for _, row in df.iterrows():
        if row["EMAIL"].lower() in dropped_set:
            continue
        try:
            blocked, _kw = filter_company_name(row.get("COMPANY", ""))
            if blocked:
                additional_drop.add(row["EMAIL"].lower())
        except Exception:
            pass

    all_dropped = dropped_set | additional_drop

    # Apply
    mask_keep = ~df["EMAIL"].str.lower().isin(all_dropped)
    df_clean = df[mask_keep].copy().reset_index(drop=True)

    # Mark flagged rows as LOW priority
    if "PRIORITY" not in df_clean.columns:
        df_clean["PRIORITY"] = "NORMAL"
    flagged_mask = df_clean["EMAIL"].str.lower().isin(flagged_map)
    df_clean.loc[flagged_mask, "PRIORITY"] = "LOW"

    dropped_count = int(len(all_dropped))
    flagged_count = int(flagged_mask.sum())
    log.info(
        f"Step 2b BOUNCE_KB: dropped {dropped_count}, flagged {flagged_count} (LOW priority), "
        f"kept {len(df_clean)}"
    )
    return df_clean, dropped_count, flagged_count


# ── Step 3: LLM classify commodity ────────────────────────────────────────────
def _classify_commodity_keywords(product_desc: str, hs_code: str) -> str:
    """Fast keyword-based classifier (no LLM call)."""
    text = (product_desc or "").lower()
    for kw, cat in _KEYWORD_MAP.items():
        if kw in text:
            return cat
    # HS code prefix fallback
    hs = re.sub(r"[^0-9]", "", (hs_code or ""))[:2]
    if hs and hs in _HS_MAP:
        return _HS_MAP[hs]
    return "OTHERS"


def _classify_batch_llm(rows: list[dict]) -> list[str]:
    """
    Batch LLM classify for rows that keyword method couldn't resolve.
    Falls back to OTHERS if LLM unavailable.
    """
    try:
        from email_engine.core.llm_client import _get_api_key, _get_endpoint
        import httpx

        api_key = _get_api_key()
        if not api_key:
            log.info("LLM classify: MOCK mode (no MINIMAX_API_KEY)")
            return ["OTHERS"] * len(rows)

        categories_str = ", ".join(COMMODITY_CATEGORIES)
        items_str = "\n".join(
            f'{i+1}. desc="{r["desc"]}" hs="{r["hs"]}"'
            for i, r in enumerate(rows)
        )
        prompt = (
            f"Classify each item into ONE category from: {categories_str}\n"
            f"Return ONLY a JSON array of strings, same order as input.\n"
            f"Items:\n{items_str}"
        )

        payload = {
            "model": "MiniMax-Text-01",
            "messages": [
                {"role": "system", "content": "You are a logistics commodity classifier. Output valid JSON array only."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
            "max_tokens": 512,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        endpoint = _get_endpoint()
        with httpx.Client(timeout=30) as client:
            resp = client.post(endpoint, json=payload, headers=headers)
            resp.raise_for_status()

        content = (
            resp.json().get("choices", [{}])[0]
            .get("message", {}).get("content", "[]").strip()
        )
        # Strip markdown fences
        if content.startswith("```"):
            content = "\n".join(l for l in content.split("\n") if not l.startswith("```")).strip()

        result = json.loads(content)
        if isinstance(result, list) and len(result) == len(rows):
            # Validate each category
            return [r if r in COMMODITY_CATEGORIES else "OTHERS" for r in result]
        return ["OTHERS"] * len(rows)

    except Exception as exc:
        log.warning(f"LLM classify batch failed: {exc} — using OTHERS")
        return ["OTHERS"] * len(rows)


def _classify_all(df: pd.DataFrame) -> pd.DataFrame:
    """Classify commodity for each row, batch LLM for OTHERS fallback."""
    categories = []
    llm_batch_indices = []
    llm_batch_rows = []

    for i, row in df.iterrows():
        cat = _classify_commodity_keywords(row["PRODUCT_DESCRIPTION"], row["HS_CODE"])
        categories.append(cat)
        if cat == "OTHERS" and row["PRODUCT_DESCRIPTION"].strip():
            llm_batch_indices.append(i)
            llm_batch_rows.append({"desc": row["PRODUCT_DESCRIPTION"][:200], "hs": row["HS_CODE"][:10]})

    # Batch LLM for OTHERS rows (50 per call)
    if llm_batch_rows:
        log.info(f"Step 3 LLM: classifying {len(llm_batch_rows)} OTHERS rows via LLM")
        batch_size = 50
        for start in range(0, len(llm_batch_rows), batch_size):
            batch = llm_batch_rows[start:start + batch_size]
            results = _classify_batch_llm(batch)
            for j, cat in enumerate(results):
                original_idx = llm_batch_indices[start + j]
                categories[original_idx] = cat

    df = df.copy()
    df["COMMODITY_CATEGORY"] = categories
    breakdown = {c: categories.count(c) for c in COMMODITY_CATEGORIES if categories.count(c) > 0}
    log.info(f"Step 3 CLASSIFY: {breakdown}")
    return df, breakdown


# ── Step 4: Parse STATE ────────────────────────────────────────────────────────
def _parse_states(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Parse US state / CA province from DESTINATION column."""
    try:
        from email_engine.core.state_parser import parse_state_bulk
        states = parse_state_bulk(df["DESTINATION"].tolist())
    except ImportError:
        log.warning("state_parser not found — using inline fallback")
        states = [_state_fallback(d) for d in df["DESTINATION"].tolist()]

    df = df.copy()
    df["STATE"] = [s or "" for s in states]
    unparseable = int(sum(1 for s in states if not s))
    log.info(f"Step 4 STATE: parsed {len(states) - unparseable}/{len(states)}, {unparseable} unparseable")
    return df, unparseable


def _state_fallback(destination: str) -> Optional[str]:
    """Minimal inline state parser fallback if state_parser.py not available."""
    if not destination:
        return None
    # Try 2-letter code at end
    m = re.search(r"\b([A-Z]{2})\b", destination.upper())
    return m.group(1) if m else None


# ── Step 5: Dedup vs existing cnee_master ─────────────────────────────────────
def _fuzzy_company_match(name_a: str, name_b: str, threshold: float = 0.85) -> bool:
    """Simple fuzzy match using SequenceMatcher (no external dep)."""
    a = re.sub(r"[^A-Z0-9 ]", "", name_a.upper().strip())
    b = re.sub(r"[^A-Z0-9 ]", "", name_b.upper().strip())
    if not a or not b:
        return False
    ratio = SequenceMatcher(None, a, b).ratio()
    return ratio >= threshold


def _norm_company(name: str) -> str:
    """Normalize company name for exact/prefix matching (strip punctuation, upper)."""
    return re.sub(r"[^A-Z0-9 ]", "", (name or "").upper().strip())


def _dedup(df: pd.DataFrame, master: pd.DataFrame) -> tuple[pd.DataFrame, int, int]:
    """
    Dedup incoming rows against master using vectorized pandas operations.
    Strategy:
      1. EMAIL exact match → duplicate (skip)
      2. COMPANY_NORM + STATE exact match → new_pic (append with marker)
    Fuzzy match intentionally dropped for performance — exact norm covers 95%+ of cases
    at 9K×22K scale without SequenceMatcher O(n×m) penalty.

    Returns: (new_rows_df, duplicates_count, new_pic_count)
    """
    if master is None or master.empty:
        return df, 0, 0

    # ── Resolve column names ───────────────────────────────────────────────────
    master_email_col = next((c for c in ["EMAIL", "CNEE_EMAIL"] if c in master.columns), None)
    master_company_col = next((c for c in ["COMPANY", "CNEE_NAME"] if c in master.columns), None)
    master_state_col = "STATE" if "STATE" in master.columns else None

    # ── Build master lookup sets (vectorized) ──────────────────────────────────
    master_emails: set[str] = set()
    if master_email_col:
        master_emails = set(
            master[master_email_col].dropna().astype(str)
            .str.lower().str.strip()
            .pipe(lambda s: s[s.str.contains("@", na=False)])
            .tolist()
        )

    # Build set of (company_norm, state) pairs for exact company dedup
    master_cs: set[tuple[str, str]] = set()
    if master_company_col:
        co_series = master[master_company_col].fillna("").astype(str).str.upper().str.strip()
        co_series = co_series.str.replace(r"[^A-Z0-9 ]", "", regex=True)
        st_series = (
            master[master_state_col].fillna("").astype(str).str.upper().str.strip()
            if master_state_col else pd.Series([""] * len(master), dtype=str)
        )
        master_cs = set(zip(co_series.tolist(), st_series.tolist()))

    # ── Vectorized email dedup ────────────────────────────────────────────────
    incoming_emails = df["EMAIL"].str.lower().str.strip()
    email_dup_mask = incoming_emails.isin(master_emails) & (incoming_emails != "")
    duplicates = int(email_dup_mask.sum())
    df_no_email_dup = df[~email_dup_mask].copy()

    # ── Company+state exact dedup on remaining rows ────────────────────────────
    if master_cs and not df_no_email_dup.empty:
        co_in = df_no_email_dup["COMPANY"].fillna("").str.upper().str.strip().str.replace(r"[^A-Z0-9 ]", "", regex=True)
        st_in = df_no_email_dup.get("STATE", pd.Series([""] * len(df_no_email_dup), dtype=str)).fillna("").str.upper().str.strip()
        co_st_pairs = list(zip(co_in.tolist(), st_in.tolist()))
        company_match_mask = pd.Series(
            [(co, st) in master_cs and co != "" for co, st in co_st_pairs],
            index=df_no_email_dup.index,
        )
        new_pic = int(company_match_mask.sum())
        if new_pic > 0:
            df_no_email_dup.loc[company_match_mask, "_dedupe_parent"] = "COMPANY_MATCH"
    else:
        new_pic = 0

    result = df_no_email_dup.reset_index(drop=True)
    log.info(f"Step 5 DEDUP: {duplicates} duplicates, {new_pic} new_pic_same_company, {len(result)} to add")
    return result, duplicates, new_pic


# ── Step 6: Filter hard bounce ────────────────────────────────────────────────
def _filter_hard_bounce(df: pd.DataFrame, master: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Skip emails that are HARD_BOUNCE in existing master."""
    if master is None or master.empty or "EMAIL_STATUS" not in master.columns:
        log.warning("Step 6 BOUNCE: EMAIL_STATUS column not found in master — skipping filter")
        return df, 0

    email_col = None
    for c in ["EMAIL", "CNEE_EMAIL"]:
        if c in master.columns:
            email_col = c
            break
    if not email_col:
        return df, 0

    bounce_emails: set[str] = set(
        e.lower().strip()
        for e, s in zip(
            master[email_col].fillna("").astype(str),
            master["EMAIL_STATUS"].fillna("").astype(str),
        )
        if s.upper() == "HARD_BOUNCE" and "@" in e
    )

    if not bounce_emails:
        return df, 0

    mask = df["EMAIL"].str.lower().str.strip().isin(bounce_emails)
    excluded = int(mask.sum())
    df_clean = df[~mask].reset_index(drop=True)
    log.info(f"Step 6 BOUNCE: excluded {excluded} hard-bounce emails")
    return df_clean, excluded


# ── Atomic write to cnee_master ────────────────────────────────────────────────
def _append_to_master(new_rows: pd.DataFrame, master_path: Path, source_tag: str) -> str:
    """Backup master, append new rows, write atomically. Returns backup filename."""
    # Backup
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"cnee_master_v2_final.backup_{ts}.xlsx"
    backup_path = master_path.parent / backup_name
    shutil.copy2(master_path, backup_path)
    log.info(f"Backup created: {backup_path}")

    # Load existing
    existing = pd.read_excel(master_path, dtype=str)

    # Prepare new rows with schema alignment
    new_rows = new_rows.copy()
    new_rows["SOURCE_TAG"] = source_tag or "PANJIVA"
    new_rows["IMPORT_DATE"] = datetime.now().strftime("%Y-%m-%d")

    # Rename to match master schema
    rename_map = {}
    if "EMAIL" in new_rows.columns and "EMAIL" not in existing.columns:
        if "CNEE_EMAIL" in existing.columns:
            rename_map["EMAIL"] = "CNEE_EMAIL"
    if "COMPANY" in new_rows.columns and "COMPANY" not in existing.columns:
        if "CNEE_NAME" in existing.columns:
            rename_map["COMPANY"] = "CNEE_NAME"
    if rename_map:
        new_rows = new_rows.rename(columns=rename_map)

    # Drop internal dedup marker columns
    for drop_col in ["_dedupe_parent"]:
        if drop_col in new_rows.columns:
            new_rows = new_rows.drop(columns=[drop_col])

    # Align columns (add missing cols as empty)
    for col in existing.columns:
        if col not in new_rows.columns:
            new_rows[col] = ""

    # Keep only master columns in same order (ignore extra new cols)
    new_rows_aligned = new_rows[[c for c in existing.columns if c in new_rows.columns]]

    combined = pd.concat([existing, new_rows_aligned], ignore_index=True)

    # Write to temp then replace atomically
    tmp_path = master_path.with_suffix(".tmp.xlsx")
    combined.to_excel(tmp_path, index=False)
    tmp_path.replace(master_path)
    log.info(f"Master updated: {len(combined)} total rows (added {len(new_rows_aligned)})")
    return str(backup_path)


# ── Main pipeline ─────────────────────────────────────────────────────────────
def clean_panjiva(
    input_path: str,
    dry_run: bool = False,
    source_tag: str = None,
    job_id: str = None,
) -> dict:
    """
    Run full 6-step Panjiva ETL pipeline.

    Args:
        input_path: Path to raw Panjiva .xlsx file
        dry_run:    If True, do NOT write to cnee_master (just report)
        source_tag: Label for import tracking (e.g. 'PANJIVA_2026W16')
        job_id:     Optional job ID to write status updates (for API background task)

    Returns:
        Report dict with counts + breakdown
    """
    t0 = time.time()

    def _update_job(step: int, step_name: str, pct: int, status: str = "running"):
        if job_id:
            JOBS_DIR.mkdir(parents=True, exist_ok=True)
            job_file = JOBS_DIR / f"{job_id}.json"
            data = {
                "job_id": job_id,
                "status": status,
                "step": step,
                "step_name": step_name,
                "progress_pct": pct,
                "updated_at": datetime.now().isoformat(),
            }
            job_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    report: dict = {
        "input_rows": 0, "output_added": 0, "duplicates": 0,
        "new_pic_same_company": 0, "bounces_excluded": 0,
        "blacklist_excluded": 0,
        "bounce_kb_dropped": 0, "bounce_kb_flagged": 0,
        "commodity_breakdown": {},
        "state_breakdown": {}, "state_unparseable": 0,
        "source_tag": source_tag or "PANJIVA",
        "duration_sec": 0, "backup_file": None,
        "dry_run": dry_run, "error": None,
    }

    try:
        # ── Step 1: Read ──────────────────────────────────────────────────────
        _update_job(1, "READ raw file", 10)
        df = _read_panjiva(input_path)
        report["input_rows"] = len(df)

        if df.empty:
            report["error"] = "Input file has no valid rows"
            _update_job(6, "done", 100, "done")
            return report

        # ── Step 2: Blacklist ─────────────────────────────────────────────────
        _update_job(2, "Blacklist filter", 25)
        bl = _load_blacklist()
        df, blacklist_excluded = _filter_blacklist(df, bl)
        report["blacklist_excluded"] = blacklist_excluded

        # ── Step 2b: Bounce KB filter (Sprint 1 v3) ───────────────────────────
        _update_job(2, "Bounce KB filter", 30)
        df, kb_dropped, kb_flagged = _filter_bounce_kb(df)
        report["bounce_kb_dropped"] = kb_dropped
        report["bounce_kb_flagged"] = kb_flagged

        # ── Step 3: LLM classify ──────────────────────────────────────────────
        _update_job(3, "LLM classify", 45)
        df, commodity_breakdown = _classify_all(df)
        report["commodity_breakdown"] = commodity_breakdown

        # ── Step 4: Parse state ───────────────────────────────────────────────
        _update_job(4, "Parse state", 60)
        df, state_unparseable = _parse_states(df)
        report["state_unparseable"] = state_unparseable
        state_breakdown = (
            df["STATE"].value_counts()
            .to_dict() if "STATE" in df.columns else {}
        )
        # Convert keys to str, filter empty
        report["state_breakdown"] = {k: v for k, v in state_breakdown.items() if k}

        # ── Load master for dedup/bounce ───────────────────────────────────────
        master_path = _resolve_cnee_master()
        master_df = None
        if master_path:
            try:
                master_df = pd.read_excel(master_path, dtype=str).fillna("")
                log.info(f"Master loaded: {len(master_df)} rows from {master_path}")
            except Exception as exc:
                log.warning(f"Could not load master: {exc}")

        # ── Step 5: Dedup ──────────────────────────────────────────────────────
        _update_job(5, "Dedup vs master", 75)
        df, duplicates, new_pic = _dedup(df, master_df)
        report["duplicates"] = duplicates
        report["new_pic_same_company"] = new_pic

        # ── Step 6: Filter hard bounce ────────────────────────────────────────
        _update_job(6, "Filter hard bounce", 88)
        df, bounces_excluded = _filter_hard_bounce(df, master_df)
        report["bounces_excluded"] = bounces_excluded

        report["output_added"] = len(df)

        # ── Write to master (unless dry_run) ──────────────────────────────────
        if not dry_run and len(df) > 0:
            if master_path:
                _update_job(6, "Writing to master", 95)
                backup = _append_to_master(df, master_path, source_tag or "PANJIVA")
                report["backup_file"] = backup
            else:
                log.warning("cnee_master not found — cannot append (dry_run forced)")
                report["dry_run"] = True
                report["error"] = "cnee_master not found — no rows written"
        elif dry_run:
            log.info("DRY RUN — no rows written to master")

    except Exception as exc:
        log.exception(f"Pipeline error: {exc}")
        report["error"] = str(exc)
        if job_id:
            JOBS_DIR.mkdir(parents=True, exist_ok=True)
            job_file = JOBS_DIR / f"{job_id}.json"
            job_file.write_text(json.dumps({
                "job_id": job_id, "status": "error",
                "error": str(exc), "report": report,
                "updated_at": datetime.now().isoformat(),
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        report["duration_sec"] = round(time.time() - t0, 1)
        return report

    report["duration_sec"] = round(time.time() - t0, 1)

    # Final job status
    if job_id:
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        job_file = JOBS_DIR / f"{job_id}.json"
        job_file.write_text(json.dumps({
            "job_id": job_id, "status": "done",
            "step": 6, "step_name": "Complete", "progress_pct": 100,
            "report": report,
            "updated_at": datetime.now().isoformat(),
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    log.info(
        f"Pipeline complete: +{report['output_added']} added, "
        f"{report['duplicates']} dupes, {report['blacklist_excluded']} blacklisted, "
        f"{report['bounces_excluded']} bounce, {report['duration_sec']}s"
    )
    return report


# ── CLI ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Panjiva ETL Pipeline — clean + merge into cnee_master")
    parser.add_argument("--input", required=True, help="Path to raw Panjiva .xlsx file")
    parser.add_argument("--source-tag", default=None, help="Import tag e.g. PANJIVA_2026W16")
    parser.add_argument("--dry-run", action="store_true", help="Run pipeline without writing to master")
    args = parser.parse_args()

    result = clean_panjiva(
        input_path=args.input,
        dry_run=args.dry_run,
        source_tag=args.source_tag,
    )

    print("\n" + "=" * 50)
    print("  PANJIVA CLEAN REPORT")
    print("=" * 50)
    print(f"  Source     : {result['source_tag']}")
    print(f"  Dry run    : {result['dry_run']}")
    print(f"  Input rows : {result['input_rows']}")
    print(f"  Added      : +{result['output_added']}")
    print(f"  Duplicates : -{result['duplicates']}")
    print(f"  New PIC    : +{result['new_pic_same_company']} (same company, new contact)")
    print(f"  Blacklisted: -{result['blacklist_excluded']}")
    print(f"  Bounce skip: -{result['bounces_excluded']}")
    print(f"  State N/A  : {result['state_unparseable']}")
    print(f"  Duration   : {result['duration_sec']}s")
    if result.get("backup_file"):
        print(f"  Backup     : {result['backup_file']}")
    if result.get("error"):
        print(f"  ERROR      : {result['error']}")
    print("\n  Commodity breakdown:")
    for cat, cnt in sorted(result["commodity_breakdown"].items(), key=lambda x: -x[1]):
        print(f"    {cat:<25} {cnt}")
    print("\n  Top states:")
    top_states = sorted(result["state_breakdown"].items(), key=lambda x: -x[1])[:10]
    for st, cnt in top_states:
        print(f"    {st:<8} {cnt}")
    print("=" * 50)
    if result.get("error"):
        sys.exit(1)
