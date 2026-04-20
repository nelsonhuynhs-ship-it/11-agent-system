# -*- coding: utf-8 -*-
"""
Pricing_Engine/normalization/text_normalize.py
================================================
Standalone normalization functions for Note and Commodity columns.

Extracted from:
    Pricing_Engine/scripts/create_master_dashboard.py
    - normalize_notes()       (line ~218)
    - normalize_text_data()   (line ~363)

Both create_master_dashboard.py and refresh-v14.py import from HERE.
Do NOT duplicate these functions in those files — DRY principle.

Public API:
    normalize_notes(df: pd.DataFrame) -> pd.DataFrame
    normalize_text_data(df: pd.DataFrame, port_map: dict = None) -> pd.DataFrame
    normalize_commodity_display(df: pd.DataFrame) -> pd.DataFrame
    normalize_container_types(df: pd.DataFrame) -> pd.DataFrame
    normalize_source(df: pd.DataFrame) -> pd.DataFrame

All functions are pure: they receive a DataFrame, return a modified copy.
They do NOT read files or import carrier_rules directly — caller passes context
if carrier-specific shortcuts are needed (carrier_rules module does that).
"""
from __future__ import annotations

import re
import pandas as pd
from typing import Optional


# ── Constants ──────────────────────────────────────────────────────────────
_TRANSIT_KEYWORDS = ["YANTIAN", "KAOHSIUNG", "HONG KONG", "SINGAPORE", "SHANGHAI"]
_CAI_MEP_KEYWORDS = ["CAI MEP"]
_DIRECT_KEYWORDS  = ["DIRECT", "HPH"]
_HAIPHONG_WORDS   = ["HAIPHONG", "HAI PHONG"]

_TONNAGE_RE = re.compile(r"(?:UP\s*TO|UPTO)\s*([\d]+(?:\.[\d]+)?)", re.IGNORECASE)


# ── Internal helpers ────────────────────────────────────────────────────────

def _tonnage_warn(note_upper: str) -> str:
    """Return OWS warning tag if tonnage limit < 22 tons is detected in note."""
    m = _TONNAGE_RE.search(note_upper)
    if m:
        try:
            tons = float(m.group(1))
            if tons < 22:
                return f" [!OWS<22T:{tons}t]"
        except ValueError:
            pass
    return ""


def _normalize_note(note: str, carrier: str = "") -> str:
    """Normalize a single Note value for a given carrier.

    Priority order:
      1. ZIM service codes (Z7S / ZXB / ZEX / generic ZIM OWS)
      2. EMC-specific (PCTF/STF/PCS/SUEZ)
      3. COSCO vessel names
      4. MSC service names (shortened with [ref])
      5. CMA service names
      6. SOC variants (TRANSIT / Cai Mep / DIRECT / plain SOC)
      7. Non-SOC routing (TRANSIT / Cai Mep / DIRECT)
      8. Unrecognized -> kept as-is (trimmed)
    """
    if not note or str(note).strip() in ("", "nan"):
        return ""
    n = str(note).strip()
    nu = n.upper()
    cu = str(carrier).upper()

    # ── 1. ZIM SERVICE BLOCK ──────────────────────────────────────────────
    if "ZIM" in nu or "Z7S" in nu or "ZXB" in nu or "ZEX" in nu:
        if "OWS" in nu:
            if "SUBJECT TO OWS" in nu or "SUBJECT TO  OWS" in nu:
                ows_tag = " OWS EXTRA"
            else:
                ows_tag = " OWS INCL"
            warn = _tonnage_warn(nu)
        else:
            ows_tag = ""
            warn = ""
        if "Z7S" in nu:
            return f"Z7S{ows_tag}{warn}"
        if "ZXB" in nu:
            return f"ZXB{ows_tag}{warn}"
        if "ZEX" in nu:
            return "ZEX"
        # Generic ZIM with OWS
        if ows_tag:
            return f"ZIM{ows_tag}{warn}"
        return n

    # ── 1b. OWS CATCH-ALL (no ZIM keyword) ───────────────────────────────
    if "OWS" in nu:
        if "SUBJECT TO OWS" in nu or "SUBJECT TO  OWS" in nu:
            return f"ZIM OWS EXTRA{_tonnage_warn(nu)}"
        return f"ZIM OWS INCL{_tonnage_warn(nu)}"

    # ── 2. EMC-SPECIFIC ───────────────────────────────────────────────────
    if "EMC" in cu:
        has_cmep = "VIA CMEP" in nu or "CMEP" in nu
        if "PCTF" in nu or "PANAMA CANAL TRANSIT" in nu:
            if "STF" in nu or "SUEZ TRANSIT" in nu:
                return "via CMEP PCTF/STF" if has_cmep else "PCTF/STF SURCHG"
            return "via CMEP PCTF" if has_cmep else "PCTF SURCHG"
        if "PCS" in nu or "SUEZ" in nu:
            return "via CMEP PCS/SUEZ" if has_cmep else "PCS/SUEZ"
        if has_cmep:
            return "via CMEP"

    # ── 3. COSCO-SPECIFIC ─────────────────────────────────────────────────
    if "COSCO" in cu:
        if "CMA CGM NILE" in nu or "POINTE-NOIRE" in nu or "POINTE NOIRE" in nu:
            return "NILE/P-NOIRE"
        if "OPNW" in nu:
            return "via OPNW"

    # ── 4. MSC-SPECIFIC ───────────────────────────────────────────────────
    if "MSC" in cu:
        if "AMERICA" in nu and "EMPIRE" in nu:
            return "AMR/EMP/AMB/EMR/ELE/SAN/LION [ref:SvcGroup1]"
        if "LIBERTY" in nu and ("NOT" in nu or "OTHER" in nu):
            return "non-Liberty"
        if "SENTOSA" in nu and "PEARL" in nu:
            return "Sentosa/Pearl"
        if "LONE STAR" in nu or "PELICAN" in nu:
            return "LONE STAR/PELICAN"
        if "CHINOOK" in nu:
            return "on Chinook" if "ON CHINOOK" in nu else "Chinook"

    # ── 5. CMA-SPECIFIC ───────────────────────────────────────────────────
    if "CMA" in cu:
        if "SERVICE" in nu and ":" in n:
            svc_name = n.split(":", 1)[1].strip()
            svc_short = svc_name.split(" ")[:2]
            return " ".join(svc_short)

    # ── 6–7. SOC / ROUTING BLOCK ─────────────────────────────────────────
    has_soc = "SOC" in nu

    if any(kw in nu for kw in _TRANSIT_KEYWORDS):
        return "SOC TRANSIT" if has_soc else "TRANSIT"
    if any(kw in nu for kw in _CAI_MEP_KEYWORDS):
        return "SOC Cai Mep (EC3)" if has_soc else "Cai Mep (EC3)"
    if any(kw in nu for kw in _DIRECT_KEYWORDS) or any(kw in nu for kw in _HAIPHONG_WORDS):
        return "SOC DIRECT" if has_soc else "DIRECT"

    # ── 8. Unrecognized -> keep trimmed ───────────────────────────────────
    return n


# ── Public functions ────────────────────────────────────────────────────────

def normalize_notes(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize Note column in-place.

    Applies carrier-aware note normalization using _normalize_note().
    Requires 'Note' and 'Carrier' columns (or just 'Note').

    Args:
        df: DataFrame with at least 'Note' column

    Returns:
        DataFrame with 'Note' column normalized
    """
    if "Note" not in df.columns:
        return df

    carrier_col = df["Carrier"].astype(str) if "Carrier" in df.columns else pd.Series([""] * len(df))
    df = df.copy()
    df["Note"] = df.apply(
        lambda r: _normalize_note(r.get("Note", ""), r.get("Carrier", "")),
        axis=1
    )
    return df


def normalize_text_data(df: pd.DataFrame, port_map: Optional[dict] = None) -> pd.DataFrame:
    """Normalize Commodity and port code columns.

    Applies universal + carrier-specific commodity shortcuts.
    Optionally maps port codes via port_map dict.

    Args:
        df: DataFrame with 'Commodity' and 'Carrier' columns
        port_map: Optional dict mapping raw port names -> codes

    Returns:
        DataFrame with normalized Commodity, POL, POD
    """
    if "Commodity" not in df.columns:
        df = df.copy()
        df["Commodity"] = ""

    df = df.copy()
    comm = df["Commodity"].astype(str)
    carrier = df["Carrier"].astype(str).str.upper() if "Carrier" in df.columns else pd.Series([""] * len(df))

    # ── UNIVERSAL: FAK INCLUDING/EXCLUDING GARMENT ────────────────────────
    mask_fak_incl = (
        comm.str.contains("FAK", case=False, na=False) &
        comm.str.contains("INCLUDING|INCL", case=False, na=False) &
        comm.str.contains("GARMENT", case=False, na=False)
    )
    df.loc[mask_fak_incl, "Commodity"] = "FAK INCL GARMENT"

    mask_fak_excl = (
        comm.str.contains("FAK", case=False, na=False) &
        comm.str.contains("EXCLUDING|EXCL", case=False, na=False) &
        comm.str.contains("GARMENT", case=False, na=False)
    )
    df.loc[mask_fak_excl, "Commodity"] = "FAK EXCL GARMENT"

    # Refresh after universal rules
    comm = df["Commodity"].astype(str)

    # ── COSCO ─────────────────────────────────────────────────────────────
    mask_cosco = carrier.str.contains("COSCO", na=False)
    df.loc[
        mask_cosco &
        comm.str.contains("GARMENT|TEXTILE|CONSOL", case=False, na=False) &
        ~comm.str.contains("FAK", case=False, na=False),
        "Commodity"
    ] = "GARMENT"

    # ── ONE ───────────────────────────────────────────────────────────────
    mask_one = carrier.str.contains("ONE", na=False)
    df.loc[mask_one & comm.str.contains("REEFER", case=False, na=False), "Commodity"] = "REEFER FAK"
    df.loc[
        mask_one & comm.str.contains(r"FAK[:\s]*TP[EF]\d", case=False, na=False, regex=True),
        "Commodity"
    ] = "FAK: TPE1"
    df.loc[mask_one & comm.str.contains("GDSM", case=False, na=False), "Commodity"] = "SHORT TERM GDSM"
    df.loc[mask_one & comm.str.upper().str.strip().str.startswith("GARMENT"), "Commodity"] = "GARMENT"

    # ONE SOC Group
    comm = df["Commodity"].astype(str)
    mask_soc_group = comm.str.contains("Group SOC", case=False, na=False)
    if mask_soc_group.any():
        df.loc[mask_one & mask_soc_group, "Commodity"] = df.loc[
            mask_one & mask_soc_group, "Commodity"
        ].apply(
            lambda x: re.split(r"Group SOC\b", str(x), maxsplit=1, flags=re.IGNORECASE)[0].strip() + " Group SOC"
            if re.search(r"group soc", str(x), re.IGNORECASE) else x
        )

    df.loc[mask_one & comm.str.contains("FURNITURE", case=False, na=False), "Commodity"] = "FURNITURE"
    df.loc[
        mask_one & comm.str.contains(r"^\d{4}\.\d{2}\.\d{4}", na=False, regex=True),
        "Commodity"
    ] = "HS CODE"

    # ── YML ───────────────────────────────────────────────────────────────
    mask_yml = carrier.str.contains("YML", na=False)
    comm = df["Commodity"].astype(str)
    df.loc[
        mask_yml &
        comm.str.contains("GROUP A", case=False, na=False) &
        comm.str.contains("FAK", case=False, na=False),
        "Commodity"
    ] = "GROUP A : FAK"
    df.loc[
        mask_yml &
        comm.str.contains("FAK", case=False, na=False) &
        comm.str.contains("NON-HAZ|EXCLUDING", case=False, na=False) &
        ~comm.str.contains("GROUP", case=False, na=False),
        "Commodity"
    ] = "FAK"
    df.loc[
        mask_yml &
        comm.str.contains("SHIPS|BOATS|VEHICLES|CARS", case=False, na=False) &
        ~comm.str.contains("FAK", case=False, na=False),
        "Commodity"
    ] = "VEHICLES/CARS"

    # ── CMA ───────────────────────────────────────────────────────────────
    mask_cma = carrier.str.contains("CMA", na=False)
    comm = df["Commodity"].astype(str)
    df.loc[mask_cma & comm.str.contains("PANAMA", case=False, na=False), "Commodity"] = "PANAMA SURCHG"
    df.loc[mask_cma & comm.str.contains("DIRECT SERVICE", case=False, na=False), "Commodity"] = "DIRECT SVC"

    # ── EMC ───────────────────────────────────────────────────────────────
    mask_emc = carrier.str.contains("EMC", na=False)
    comm = df["Commodity"].astype(str)
    df.loc[
        mask_emc & comm.str.contains("RATE 1.*GENERAL CARGO", case=False, na=False),
        "Commodity"
    ] = "RATE 1"

    # ── ZIM ───────────────────────────────────────────────────────────────
    mask_zim = carrier.str.contains("ZIM", na=False)
    comm = df["Commodity"].astype(str)
    df.loc[
        mask_zim &
        comm.str.contains("SUBJECT TO OWS|OWS.*20|20.*OWS|include OWS|OWS include", case=False, na=False),
        "Commodity"
    ] = "OWS 20GP"
    df.loc[
        mask_zim & comm.str.contains(r"^\d{4}\.\d{2}\.\d{4}", na=False, regex=True),
        "Commodity"
    ] = "HS CODE"
    df.loc[
        mask_zim &
        comm.str.contains("INCLUDE.*FREETIME|FREETIME.*COMBINE|DET.*include", case=False, na=False),
        "Commodity"
    ] = "FAK"
    df.loc[mask_zim & comm.str.contains("HAWAII", case=False, na=False), "Commodity"] = "FAK HAWAII"

    # ── MSC ───────────────────────────────────────────────────────────────
    mask_msc = carrier.str.contains("MSC", na=False)
    comm = df["Commodity"].astype(str)
    df.loc[
        mask_msc &
        comm.str.contains("America:|Elephant:|sentosa:|Pearl:", case=False, na=False),
        "Commodity"
    ] = "FAK"

    # ── WHL ───────────────────────────────────────────────────────────────
    mask_whl = carrier.str.contains("WHL", na=False)
    comm = df["Commodity"].astype(str)
    df.loc[
        mask_whl & comm.str.contains("FOODSTUFF|FROZEN|SEAFOOD", case=False, na=False),
        "Commodity"
    ] = "FROZEN FOOD"

    # ── CATCH-ALL ─────────────────────────────────────────────────────────
    comm = df["Commodity"].astype(str)
    df.loc[
        comm.str.contains("APPLY.*FILE.*COMMODITY|apply.*commodity.*booking", case=False, na=False),
        "Commodity"
    ] = "FAK"

    # Truncate commodity > 25 chars (keep first 3 words max)
    comm = df["Commodity"].astype(str)
    long_mask = comm.str.len() > 25
    if long_mask.any():
        df.loc[long_mask, "Commodity"] = comm[long_mask].apply(
            lambda x: " ".join(str(x).split()[:3])[:25].strip()
        )

    # ── Port mapping ──────────────────────────────────────────────────────
    if port_map:
        if "POL" in df.columns:
            df["POL"] = df["POL"].astype(str).str.upper().str.strip().map(port_map).fillna(df["POL"])
        if "POD" in df.columns:
            df["POD"] = df["POD"].astype(str).str.upper().str.strip().map(port_map).fillna(df["POD"])

    # Rename Source_File -> Source if present
    if "Source_File" in df.columns:
        df = df.rename(columns={"Source_File": "Source"})

    return df


def normalize_commodity_display(df_in: pd.DataFrame) -> pd.DataFrame:
    """Shorten verbose Commodity strings for ERP display layer.

    Pure display normalization — does NOT affect dedup or joins.
    Apply AFTER pivot (refresh-v14.py pattern).

    Rules (in order):
      1. Trim whitespace and trailing newlines
      2. If contains 'REEFER' -> 'REEFER'
      3. If has parenthesis detail ' (' -> keep text before it
      4. Else keep as-is

    Args:
        df_in: DataFrame with 'Commodity' column

    Returns:
        Copy with shortened Commodity values
    """
    if "Commodity" not in df_in.columns:
        return df_in
    df_in = df_in.copy()

    def _shorten(raw) -> str:
        if raw is None:
            return raw
        try:
            s = str(raw).strip().strip("\r\n").strip()
        except Exception:
            return raw
        if not s:
            return s
        upper = s.upper()
        if "REEFER" in upper:
            return "REEFER"
        paren_idx = s.find(" (")
        if paren_idx > 0:
            return s[:paren_idx].strip()
        return s

    df_in["Commodity"] = df_in["Commodity"].map(_shorten)
    return df_in


def normalize_container_types(df_in: pd.DataFrame) -> pd.DataFrame:
    """Collapse container type variants before pivot.

    Fixes: '45\\'HQ' (with literal quote) -> '45HQ' to prevent pivot column collision.
    Must run BEFORE pivot_table on Container_Type.

    Args:
        df_in: DataFrame with 'Container_Type' column

    Returns:
        Copy with normalized Container_Type values
    """
    if "Container_Type" not in df_in.columns:
        return df_in
    df_in = df_in.copy()
    df_in["Container_Type"] = df_in["Container_Type"].replace({"45'HQ": "45HQ"})
    return df_in


# ── Source shortcuts (Rate_Type display names) ───────────────────────────────

# Exact-match map: Source column value → display label
_SOURCE_SHORTCUTS: dict[str, str] = {
    "FIX": "Special Rate",
    "FAK": "FAK",
    "SCFI": "SCFI",
}

# Note column substrings → display label (applied before existing note normalize)
_NOTE_SHORTCUTS_SOURCE: dict[str, str] = {
    "FIXED RATE": "Special Rate",
    "Fixed Rate": "Special Rate",
    "FIX RATE": "Special Rate",
}


def normalize_source(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize Source column display names (Rate_Type after pivot rename).

    Applies _SOURCE_SHORTCUTS to col 'Source' (exact match, idempotent):
      - 'FIX' -> 'Special Rate'
      - 'FAK' -> 'FAK'  (no-op, kept for completeness)
      - 'SCFI' -> 'SCFI' (no-op)

    Also applies _NOTE_SHORTCUTS_SOURCE to col 'Note': replaces verbose
    FIX-related substrings ('FIXED RATE', 'FIX RATE') with 'Special Rate'.
    Runs BEFORE the existing note-normalization pipeline so later rules see
    the canonical label.

    Safe to call multiple times (idempotent): 'Special Rate' is not in any
    source shortcut value that maps to something else.

    Args:
        df: DataFrame after pivot rename Rate_Type -> Source.
            Expected cols: 'Source' (required), 'Note' (optional).

    Returns:
        Copy with normalized Source (and optionally Note) values.
    """
    df = df.copy()

    # ── Source column ─────────────────────────────────────────────────────
    if "Source" in df.columns:
        df["Source"] = df["Source"].map(
            lambda v: _SOURCE_SHORTCUTS.get(str(v).strip(), v) if v is not None else v
        )
    elif "Rate_Type" in df.columns:
        # Fallback: caller didn't rename yet — normalize Rate_Type in place
        df["Rate_Type"] = df["Rate_Type"].map(
            lambda v: _SOURCE_SHORTCUTS.get(str(v).strip(), v) if v is not None else v
        )

    # ── Note column: replace verbose FIX strings ──────────────────────────
    if "Note" in df.columns:
        def _apply_source_note(note_val) -> str:
            if note_val is None or str(note_val).strip() in ("", "nan"):
                return note_val  # type: ignore[return-value]
            s = str(note_val)
            for old, new in _NOTE_SHORTCUTS_SOURCE.items():
                # Case-sensitive replacement (keys are title/upper cased)
                if old in s:
                    s = s.replace(old, new)
            return s

        df["Note"] = df["Note"].map(_apply_source_note)

    return df
