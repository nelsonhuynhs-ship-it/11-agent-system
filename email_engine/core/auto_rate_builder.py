# -*- coding: utf-8 -*-
"""
auto_rate_builder.py — Auto-Generate HTML Rate Table from Parquet
=================================================================
Queries Parquet for latest rates per customer route (DESTINATION),
applies minimum $20 markup, and generates Outlook-compatible HTML table
matching the NELSON WEEK format.

Called by send_email.py --auto-rate or run_all.py option 13.

Usage:
    from auto_rate_builder import build_rate_table_for_customer
    html = build_rate_table_for_customer(pol="HPH", destinations="USCHI,USLAX")
"""
import io
import sys
import logging
import os
from pathlib import Path
from datetime import datetime

import pandas as pd

if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

log = logging.getLogger("auto_rate_builder")

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).parent           # email_engine/core
PROJECT_ROOT    = BASE_DIR.parent                 # email_engine/

try:
    from shared.paths import PARQUET_FILE, PORT_MAP as PORT_MAP_FILE
except ImportError:
    # Fallback for environments without shared.paths (should not happen in normal use)
    ENGINE_TEST   = PROJECT_ROOT.parent
    PARQUET_FILE  = ENGINE_TEST / "Pricing_Engine" / "data" / "Cleaned_Master_History.parquet"
    PORT_MAP_FILE = PROJECT_ROOT / "data" / "Port_Code_Mapping_Final.xlsx"

MARKUP_MIN      = 20   # minimum markup per container per route


# ── Port Code Mapping ────────────────────────────────────────────────────────
_port_map_cache = None

def _load_port_map() -> dict:
    """Load port code → city name mapping. Returns {PORT_CODE: CITY_NAME}."""
    global _port_map_cache
    if _port_map_cache is not None:
        return _port_map_cache

    if not PORT_MAP_FILE.exists():
        log.warning("Port_Code_Mapping_Final.xlsx not found: %s", PORT_MAP_FILE)
        return {}

    df = pd.read_excel(PORT_MAP_FILE)
    df.columns = df.columns.str.strip()
    mapping = {}
    for _, row in df.iterrows():
        code = str(row.get("PortCode", "")).strip().upper()
        name = str(row.get("PortName", "")).strip()
        if code and name and "/" not in code:
            mapping[code] = name

    _port_map_cache = mapping
    log.info("[AutoRate] Port map loaded: %d entries", len(mapping))
    return mapping


# ── Parquet Loader (DuckDB — fast, filtered) ────────────────────────────────
_parquet_cache = None
_parquet_time  = None

def _load_parquet() -> pd.DataFrame:
    """Load valid rates from Parquet via DuckDB (28x faster, filtered by Exp >= today)."""
    global _parquet_cache, _parquet_time
    if _parquet_cache is not None:
        return _parquet_cache

    if not PARQUET_FILE.exists():
        log.error("[AutoRate] Parquet not found: %s", PARQUET_FILE)
        return pd.DataFrame()

    try:
        import duckdb
        t0 = datetime.now()
        query = f"""
            SELECT *
            FROM read_parquet('{str(PARQUET_FILE).replace(chr(92), "/")}')
            WHERE UPPER(Charge_Name) LIKE '%TOTAL%'
              AND Exp >= CURRENT_DATE + INTERVAL '2 days'
            ORDER BY Exp DESC
        """
        df = duckdb.sql(query).df()
        elapsed = (datetime.now() - t0).total_seconds()
        log.info("[AutoRate] DuckDB loaded: %d valid rows in %.1fs (filtered Exp >= today, TOTAL only)", len(df), elapsed)
    except Exception as e:
        log.warning("[AutoRate] DuckDB failed (%s), falling back to Pandas...", e)
        df = pd.read_parquet(PARQUET_FILE)
        # Apply same filters with Pandas
        df = df[df["Charge_Name"].astype(str).str.upper().str.contains("TOTAL", na=False)]
        try:
            df["Exp"] = pd.to_datetime(df["Exp"], errors="coerce")
            df = df[df["Exp"] >= pd.Timestamp.now() + pd.Timedelta(days=2)]
        except Exception:
            pass
        log.info("[AutoRate] Pandas fallback loaded: %d rows", len(df))

    _parquet_cache = df
    _parquet_time  = datetime.now()
    return df


# ── Query Rates ──────────────────────────────────────────────────────────────

def _query_best_rates(pol: str, place: str, df: pd.DataFrame, top_n: int = 2) -> pd.DataFrame:
    """
    Query Parquet for best rates to a specific place.
    Returns top_n carriers sorted by price for 40HQ.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    # Data already filtered by DuckDB: TOTAL charges + Exp >= today
    # Just filter by POL + Place/POD
    pol_upper = pol.upper()
    pol_mask = df["POL"].astype(str).str.upper().str.contains(pol_upper, na=False)

    place_upper = place.upper()
    place_mask = (
        df["Place"].astype(str).str.upper().str.contains(place_upper, na=False)
        | df["POD"].astype(str).str.upper().str.contains(place_upper, na=False)
    )

    filtered = df[pol_mask & place_mask].copy()
    if filtered.empty:
        return pd.DataFrame()

    # Container column = 'Container_Type'
    ct_col = "Container_Type"
    results_40 = filtered[filtered[ct_col].astype(str).str.upper().isin(["40HQ", "40HC", "40HG"])]
    results_20 = filtered[filtered[ct_col].astype(str).str.upper().isin(["20GP", "20DC", "20"])]

    if results_40.empty and results_20.empty:
        return pd.DataFrame()

    # ── Helper: find a column value by trying multiple possible names ──────────
    def _get_col(row: pd.Series, *candidates, default=""):
        """Try multiple column name candidates; return first match found."""
        for name in candidates:
            if name in row.index and not pd.isnull(row[name]):
                return row[name]
        return default

    def _parse_date(val):
        """
        Parse a date value into a pd.Timestamp or NaT.
        Returns pd.NaT if invalid/empty.
        """
        if val is None or val == "" or (isinstance(val, float) and pd.isna(val)):
            return pd.NaT
        try:
            ts = pd.to_datetime(val, errors="coerce")
            return ts  # may be NaT
        except Exception:
            return pd.NaT

    # Get best rates by carrier for 40HQ (include Eff/Exp dates)
    # Strategy: pick the LATEST Exp first, then cheapest among latest
    best_40 = {}
    if not results_40.empty:
        for carrier, grp in results_40.groupby("Carrier"):
            grp = grp.copy()
            grp["_exp_ts"] = pd.to_datetime(grp["Exp"], errors="coerce")
            max_exp = grp["_exp_ts"].max()
            # Keep only rates with the latest expiry (within 1 day tolerance)
            latest = grp[grp["_exp_ts"] >= max_exp - pd.Timedelta(days=1)]
            if latest.empty:
                latest = grp
            best_row = latest.loc[latest["Amount"].idxmin()]
            # Exp: try multiple column name variants
            exp_val = _get_col(best_row,
                "Exp", "exp", "Expiry", "ExpDate", "Exp_Date",
                "ExpiryDate", "Valid_To", "ValidTo", "valid_to",
            )
            # Eff: try multiple column name variants
            eff_val = _get_col(best_row,
                "Eff", "eff", "Effective", "EffDate", "Eff_Date",
                "ValidFrom", "Valid_From", "valid_from", "EffectiveDate",
            )
            best_40[str(carrier)] = {
                "rate_40": float(best_row["Amount"]),
                "exp":     _parse_date(exp_val),   # pd.Timestamp or NaT
                "eff":     _parse_date(eff_val),   # pd.Timestamp or NaT
                "note":    str(_get_col(best_row, "Note", "note", "Remark")),
            }

    # Get best rates by carrier for 20GP (same logic: latest Exp first)
    best_20 = {}
    if not results_20.empty:
        for carrier, grp in results_20.groupby("Carrier"):
            grp = grp.copy()
            grp["_exp_ts"] = pd.to_datetime(grp["Exp"], errors="coerce")
            max_exp = grp["_exp_ts"].max()
            latest = grp[grp["_exp_ts"] >= max_exp - pd.Timedelta(days=1)]
            if latest.empty:
                latest = grp
            best_row = latest.loc[latest["Amount"].idxmin()]
            best_20[str(carrier)] = float(best_row["Amount"])

    # Combined: sort by 40HQ rate ascending, take top_n
    rows = []
    for carrier, data40 in sorted(best_40.items(), key=lambda x: x[1]["rate_40"]):
        rate_20 = best_20.get(carrier, None)
        rows.append({
            "carrier":  carrier,
            "rate_20":  rate_20,
            "rate_40":  data40["rate_40"],
            "exp":      data40["exp"],   # pd.Timestamp or NaT
            "eff":      data40["eff"],   # pd.Timestamp or NaT
            "note":     data40["note"],
        })

    return pd.DataFrame(rows[:top_n])


# ── HTML Rate Table Builder ──────────────────────────────────────────────────

_TABLE_CSS = """<style type="text/css">
.tg {border-collapse:collapse;border-spacing:0;margin:0 auto;}
.tg td{border-color:#ddd;border-style:solid;border-width:1px;font-family:'Segoe UI',Arial,sans-serif;font-size:13px;
  overflow:hidden;padding:8px 12px;word-break:normal;text-align:center;vertical-align:middle;}
.tg th{border-color:#ddd;border-style:solid;border-width:1px;font-family:'Segoe UI',Arial,sans-serif;font-size:13px;
  font-weight:bold;overflow:hidden;padding:8px 12px;word-break:normal;}
.tg .hdr{background-color:#CFC;color:#1a4d49;text-align:center;vertical-align:top;font-weight:bold;}
.tg .val{text-align:center;vertical-align:middle;}
.tg .exp-warn{color:#c0392b;font-weight:bold;}
.tg .exp-ok{color:#27ae60;}
</style>"""


def _plain_to_html(text: str) -> str:
    """
    Convert plain-text with \\n / \\t bullet points to clean HTML.
    Handles lines starting with • or \\t• as <li> items.
    """
    import html as _html
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out = []
    in_list = False
    for line in lines:
        stripped = line.strip()
        is_bullet = stripped.startswith("•") or stripped.startswith("-")
        if is_bullet:
            if not in_list:
                out.append("<ul style='margin:4px 0 4px 18px;padding:0;'>")
                in_list = True
            item = stripped.lstrip("•-").strip()
            out.append(f"  <li>{_html.escape(item)}</li>")
        else:
            if in_list:
                out.append("</ul>")
                in_list = False
            if stripped:
                out.append(f"<p style='margin:4px 0;'>{_html.escape(stripped)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def _build_html_table(rows: list[dict]) -> str:
    """
    Build Outlook-compatible HTML rate table from rate rows.

    Each row: {pol, pod_code, place_name, carrier, rate_20, rate_40,
               eff_str (optional), exp_str (optional), exp (raw, for colour)}

    Validity shown as ONE combined column: "Valid Eff/Exp"
    Format: "01-31Mar" or "01Mar–10Apr" depending on month boundary.
    Expired rows highlighted red, expiring-today orange.
    """
    if not rows:
        return "<p><em>No rates available for this route.</em></p>"

    today = datetime.now().date()

    def _validity_cell(eff_ts, exp_ts) -> tuple[str, str]:
        """
        Returns (display_text, css_class) for the combined validity cell.

        eff_ts, exp_ts: pd.Timestamp or pd.NaT

        Format examples:
          same month  → "1-14Apr"
          cross-month → "28Mar-10Apr"
          exp only    → "-10Apr"
          neither     → "—"
        """
        eff_ok = eff_ts is not None and not pd.isnull(eff_ts)
        exp_ok = exp_ts is not None and not pd.isnull(exp_ts)

        # CSS colour based on expiry date
        css = "val"
        if exp_ok:
            if exp_ts.date() < today:
                css = "val exp-warn"   # red — already expired
            elif exp_ts.date() == today:
                css = "val exp-warn"   # red — expires today
            else:
                css = "val exp-ok"     # green — still valid

        # Build display text (use str(ts.day) — cross-platform, no leading zero)
        def _fmt(ts):
            """Return day+month string like '1Apr' or '28Mar' (no leading zero, Windows-safe)."""
            return f"{ts.day}{ts.strftime('%b')}"

        if eff_ok and exp_ok:
            # Same month → "1-14Apr"
            if eff_ts.month == exp_ts.month and eff_ts.year == exp_ts.year:
                text = f"{eff_ts.day}-{_fmt(exp_ts)}"
            else:
                # Cross-month → "28Mar-10Apr"
                text = f"{_fmt(eff_ts)}-{_fmt(exp_ts)}"
        elif exp_ok:
            text = f"-{_fmt(exp_ts)}"
        elif eff_ok:
            text = f"{_fmt(eff_ts)}-"
        else:
            text = "—"

        return text, css

    lines = [_TABLE_CSS]
    lines.append('<table class="tg"><thead>')
    lines.append("  <tr>")
    for col in ["POL", "POD", "Place Of Delivery", "Carrier", "20GP", "40HQ", "Valid Eff/Exp"]:
        lines.append(f'    <th class="hdr">{col}</th>')
    lines.append("  </tr>")
    lines.append("</thead><tbody>")

    for r in rows:
        rate_20_str = f"USD {int(r['rate_20']):,}" if r.get("rate_20") else "—"
        rate_40_str = f"USD {int(r['rate_40']):,}" if r.get("rate_40") else "—"

        valid_text, valid_css = _validity_cell(
            r.get("eff"),   # pd.Timestamp or NaT
            r.get("exp"),   # pd.Timestamp or NaT
        )

        lines.append("  <tr>")
        lines.append(f'    <td class="val">{r["pol"]}</td>')
        lines.append(f'    <td class="val">{r["pod_code"]}</td>')
        lines.append(f'    <td class="val">{r["place_name"]}</td>')
        lines.append(f'    <td class="val"><strong>{r["carrier"]}</strong></td>')
        lines.append(f'    <td class="val">{rate_20_str}</td>')
        lines.append(f'    <td class="val">{rate_40_str}</td>')
        lines.append(f'    <td class="{valid_css}">{valid_text}</td>')
        lines.append("  </tr>")

    lines.append("</tbody></table>")
    return "\n".join(lines)


# ── Expiry Checker ──────────────────────────────────────────────────────────

def check_expiry_warnings(all_rows: list[dict]) -> dict:
    """
    Inspect rate rows for expiry issues.

    Returns:
        {
          "expired":   [list of rows where exp <= today],
          "expiring":  [list of rows where exp == today],
          "ok":        bool — True if all rates are valid (exp > today or no exp),
          "block":     bool — True if ANY rate is already expired (exp < today)
                              send should be blocked in this case,
          "warn_msg":  str  — human-readable warning message
        }
    """
    today = datetime.now().date()
    expired  = []
    expiring = []

    for r in all_rows:
        raw_exp = r.get("exp")
        if not raw_exp:
            continue
        try:
            exp_date = pd.to_datetime(raw_exp).date()
            if exp_date < today:
                expired.append(r)
            elif exp_date == today:
                expiring.append(r)
        except Exception:
            pass

    block    = len(expired) > 0
    has_warn = len(expiring) > 0

    if block:
        warn = (f"⛔ {len(expired)} rate row(s) EXPIRED — send blocked. "
                f"Please refresh Parquet data before sending.")
    elif has_warn:
        warn = (f"⚠️  {len(expiring)} rate row(s) expire TODAY — "
                f"confirm with carrier before sending.")
    else:
        warn = ""

    return {
        "expired":  expired,
        "expiring": expiring,
        "ok":       not block and not has_warn,
        "block":    block,
        "warn_msg": warn,
    }


# ── Multi-POL Query (HPH + HCM merge) ───────────────────────────────────────

def _query_best_rates_multi_pol(
    pol_list: list[str],
    place: str,
    df: pd.DataFrame,
    top_n: int = 2,
) -> pd.DataFrame:
    """
    Query best rates across multiple POLs (e.g. HPH + HCM).
    Merges results and returns top_n cheapest rows overall.
    Each result row includes a 'pol' column indicating source.
    """
    frames = []
    for pol in pol_list:
        best = _query_best_rates(pol.strip().upper(), place, df, top_n=top_n)
        if not best.empty:
            best = best.copy()
            best["pol"] = pol.strip().upper()
            frames.append(best)

    if not frames:
        return pd.DataFrame()

    merged = pd.concat(frames, ignore_index=True)
    # Sort by 40HQ rate ascending, deduplicate carrier+pol combos, take top_n
    if "rate_40" in merged.columns:
        merged = merged.sort_values("rate_40", ascending=True)
    return merged.head(top_n * len(pol_list))   # keep top results per pol combo


# ── Main Entry Points ────────────────────────────────────────────────────────

def build_rate_table_for_customer(
    pol: str = "HPH",
    destinations: str = "",
    markup: float = MARKUP_MIN,
    top_per_route: int = 2,
) -> dict:
    """
    Build an auto-generated HTML rate table for a customer.
    
    Args:
        pol:            Port of Loading (HPH or HCM)
        destinations:   Comma-separated port codes  (e.g. "USCHI,USLAX,USSAV")
        markup:         Minimum markup per container (default $20)
        top_per_route:  Number of carrier options per route (default 2)
    
    Returns:
        dict with:
          html          — Complete HTML rate table
          routes_found  — Number of routes with rates
          total_rates   — Total rate rows
          routes_detail — List of {port, place, carriers} for logging
    """
    port_map = _load_port_map()
    df       = _load_parquet()

    if df.empty:
        return {"html": "<p>No Parquet data available</p>", "routes_found": 0,
                "total_rates": 0, "routes_detail": []}

    # Parse destinations — filter out UNMAPPED, split on comma
    dest_codes = [
        d.strip().upper()
        for d in destinations.split(",")
        if d.strip() and d.strip().upper() != "UNMAPPED"
    ]

    if not dest_codes:
        return {"html": "<p>No valid destination ports</p>", "routes_found": 0,
                "total_rates": 0, "routes_detail": []}

    all_rows = []
    routes_detail = []

    for pod_code in dest_codes:
        # Map port code to city name for Parquet query
        city_name = port_map.get(pod_code, "")
        if not city_name:
            # Try fuzzy: remove "US" prefix and search
            short = pod_code.replace("US", "")
            for k, v in port_map.items():
                if short in k:
                    city_name = v
                    break

        if not city_name:
            log.debug("[AutoRate] No mapping for %s, skipping", pod_code)
            continue

        # Extract just the city part (before comma) for Parquet search
        search_term = city_name.split(",")[0].strip()

        # Query Parquet
        best = _query_best_rates(pol, search_term, df, top_n=top_per_route)

        if best.empty:
            continue

        detail_carriers = []
        for _, rate_row in best.iterrows():
            r20 = rate_row.get("rate_20")
            r40 = rate_row.get("rate_40")

            # Apply markup
            sell_20 = int(r20 + markup) if r20 and pd.notna(r20) else None
            sell_40 = int(r40 + markup) if r40 and pd.notna(r40) else None

            all_rows.append({
                "pol":        pol.upper(),
                "pod_code":   pod_code,
                "place_name": city_name,
                "carrier":    str(rate_row["carrier"]),
                "rate_20":    sell_20,
                "rate_40":    sell_40,
                "eff":        rate_row.get("eff"),
                "exp":        rate_row.get("exp"),
            })
            detail_carriers.append(str(rate_row["carrier"]))

        routes_detail.append({
            "port": pod_code,
            "place": city_name,
            "carriers": detail_carriers,
        })

    html = _build_html_table(all_rows)

    return {
        "html":          html,
        "routes_found":  len(routes_detail),
        "total_rates":   len(all_rows),
        "routes_detail": routes_detail,
    }


def build_bulk_preview(
    data_file: str | Path = None,
    cmd_filter: str | list = None,
    markup: float = MARKUP_MIN,
) -> list[dict]:
    """
    Preview auto-rate tables for all customers in a CMD group.
    
    Returns list of {email, company, pol, destinations, html, routes_found}.
    """
    if data_file is None:
        data_file = PROJECT_ROOT / "data.xlsx"

    df = pd.read_excel(data_file)
    df.columns = df.columns.str.strip().str.upper()

    # Filter by CMD
    if cmd_filter:
        if isinstance(cmd_filter, str):
            cmd_filter = [cmd_filter.upper()]
        else:
            cmd_filter = [c.upper() for c in cmd_filter]
        df = df[df["CMD_NAME"].isin(cmd_filter)]

    # Filter only rows with DESTINATION
    df = df[df["DESTINATION"].notna()]

    results = []
    seen = set()  # dedup by email

    for _, row in df.iterrows():
        email = str(row.get("CNEE_EMAIL", "")).strip()
        if not email or "@" not in email or email in seen:
            continue
        seen.add(email)

        pol         = str(row.get("POL", "HPH")).strip() or "HPH"
        destinations = str(row.get("DESTINATION", "")).strip()
        company      = str(row.get("CNEE_NAME", "")).strip()

        result = build_rate_table_for_customer(
            pol=pol, destinations=destinations, markup=markup
        )
        result["email"]        = email
        result["company"]      = company
        result["pol"]          = pol
        result["destinations"] = destinations
        results.append(result)

    log.info("[AutoRate] Bulk preview: %d customers, %d with rates",
             len(results), sum(1 for r in results if r["routes_found"] > 0))
    return results


# ── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)-5s | %(message)s",
                        datefmt="%H:%M:%S")

    import argparse
    parser = argparse.ArgumentParser(description="Auto Rate Table Builder")
    parser.add_argument("--pol", default="HPH", help="Port of Loading")
    parser.add_argument("--dest", default="USCHI,USLAX,USSAV",
                        help="Comma-separated destination codes")
    parser.add_argument("--markup", type=float, default=20,
                        help="Markup per container (default $20)")
    parser.add_argument("--cmd", help="Preview bulk for CMD group")
    args = parser.parse_args()

    if args.cmd:
        results = build_bulk_preview(cmd_filter=args.cmd, markup=args.markup)
        for r in results[:5]:
            print(f"\n{'='*50}")
            print(f"  {r['company']} ({r['email']})")
            print(f"  Routes found: {r['routes_found']}")
            if r["routes_detail"]:
                for rd in r["routes_detail"]:
                    print(f"    {rd['port']} ({rd['place']}) → {rd['carriers']}")
    else:
        result = build_rate_table_for_customer(
            pol=args.pol, destinations=args.dest, markup=args.markup
        )
        print(f"\nRoutes: {result['routes_found']} | Rates: {result['total_rates']}")
        for rd in result["routes_detail"]:
            print(f"  {rd['port']} ({rd['place']}) → {rd['carriers']}")
        print(f"\n{result['html']}")
