# -*- coding: utf-8 -*-
"""
parquet_auditor.py — Cross-check Parquet data against source Excel files
========================================================================
Compares rates in Parquet with original Excel (FAK/SCFI/FIX) to verify:
- Price accuracy (amounts match)
- Contract/Group_Code (SCFI)
- Validity dates (Eff/Exp)
- Rate type classification
- Carrier assignment

Usage:
    python parquet_auditor.py                              # audit all
    python parquet_auditor.py --source path/to/file.xlsx   # audit vs specific file
    python parquet_auditor.py --html                       # generate HTML report
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

# Fix encoding (guard for pythonw.exe where stdout=None)
if sys.platform == 'win32':
    import io
    if sys.stdout and hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    elif sys.stdout is None:
        import os
        sys.stdout = open(os.devnull, 'w', encoding='utf-8')

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
PARQUET_FILE = DATA_DIR / "Cleaned_Master_History.parquet"
PROCESSED_DIR = DATA_DIR / "processed"
INCOMING_DIR = DATA_DIR / "incoming"

# Container normalization (both directions)
CONTAINER_NORMALIZE = {
    "20'": "20GP", "40'": "40GP", "40'HC": "40HQ",
    "20GP": "20GP", "40GP": "40GP", "40HQ": "40HQ",
    "45'HQ": "45'HQ", "40NOR": "40NOR",
    "20RF": "20RF", "40RF": "40RF",
}


def load_parquet() -> pd.DataFrame:
    """Load the Parquet file."""
    if not PARQUET_FILE.exists():
        print(f"[!] Parquet not found: {PARQUET_FILE}")
        return pd.DataFrame()
    df = pd.read_parquet(PARQUET_FILE)
    df['Eff'] = pd.to_datetime(df['Eff'], errors='coerce')
    df['Exp'] = pd.to_datetime(df['Exp'], errors='coerce')
    df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')
    return df


def audit_parquet_overview(df: pd.DataFrame) -> dict:
    """Generate high-level overview of Parquet data."""
    overview = {
        "total_rows": len(df),
        "carriers": sorted(df['Carrier'].dropna().unique().tolist()),
        "carrier_count": df['Carrier'].nunique(),
        "charge_types": sorted(df['Charge_Name'].dropna().unique().tolist()),
        "container_types": sorted(df['Container_Type'].dropna().unique().tolist()),
        "pols": sorted(df['POL'].dropna().unique().tolist()),
        "date_range": {
            "eff_min": str(df['Eff'].min())[:10] if pd.notna(df['Eff'].min()) else None,
            "eff_max": str(df['Eff'].max())[:10] if pd.notna(df['Eff'].max()) else None,
            "exp_min": str(df['Exp'].min())[:10] if pd.notna(df['Exp'].min()) else None,
            "exp_max": str(df['Exp'].max())[:10] if pd.notna(df['Exp'].max()) else None,
        },
    }

    # Breakdown by rate type
    if 'Rate_Type' in df.columns:
        overview["rate_types"] = df['Rate_Type'].value_counts().to_dict()

    # Breakdown by source file (top 10)
    if 'Source_File' in df.columns:
        overview["top_source_files"] = (
            df['Source_File'].value_counts().head(10).to_dict()
        )

    # New columns check
    overview["has_contract"] = 'Contract' in df.columns and df['Contract'].notna().any()
    overview["has_group_code"] = 'Group_Code' in df.columns and df['Group_Code'].notna().any()

    return overview


def audit_vs_excel(df: pd.DataFrame, excel_path: str) -> dict:
    """
    Cross-check Parquet data against a source Excel file.
    Returns detailed comparison report.
    """
    excel_path = Path(excel_path)
    if not excel_path.exists():
        return {"error": f"File not found: {excel_path}"}

    fname = excel_path.name
    fname_up = fname.upper()

    # Determine file type
    if "SCFI" in fname_up:
        return _audit_scfi(df, excel_path)
    elif "FIX" in fname_up or "FIXED" in fname_up:
        return _audit_fix(df, excel_path)
    else:
        return _audit_fak(df, excel_path)


def _audit_fak(df: pd.DataFrame, excel_path: Path) -> dict:
    """Audit FAK file vs Parquet."""
    report = {
        "file": excel_path.name,
        "type": "FAK",
        "checks": [],
        "mismatches": [],
        "summary": {},
    }

    # Read FAK file (single sheet, header row 0+1)
    try:
        raw = pd.read_excel(excel_path, header=None)
    except Exception as e:
        report["error"] = str(e)
        return report

    # Filter Parquet to this source file
    pq_match = df[df['Source_File'].str.contains(excel_path.stem, case=False, na=False)]
    report["parquet_rows_matched"] = len(pq_match)

    if len(pq_match) == 0:
        # Try matching by similar name pattern
        pq_match = df[df['Source_File'].str.contains(
            excel_path.stem[:20], case=False, na=False
        )]
        report["parquet_rows_matched_fuzzy"] = len(pq_match)

    # Sample checks: pick 5 random routes and verify amounts
    if len(pq_match) > 0:
        # Get unique route combinations
        routes = pq_match.groupby(['Carrier', 'Place', 'Container_Type', 'Charge_Name']).agg({
            'Amount': ['min', 'max', 'mean', 'count'],
            'Eff': 'min',
            'Exp': 'max'
        }).reset_index()
        routes.columns = ['Carrier', 'Place', 'Container_Type', 'Charge_Name',
                          'Min_Amount', 'Max_Amount', 'Mean_Amount', 'Count',
                          'Eff_Start', 'Exp_End']

        # Summary stats
        report["summary"] = {
            "unique_carriers": sorted(pq_match['Carrier'].unique().tolist()),
            "unique_places": len(pq_match['Place'].unique()),
            "unique_charges": sorted(pq_match['Charge_Name'].unique().tolist()),
            "container_types": sorted(pq_match['Container_Type'].unique().tolist()),
            "total_records": len(pq_match),
            "amount_range": f"${pq_match['Amount'].min():.0f} — ${pq_match['Amount'].max():.0f}",
        }

        # Take samples for spot checks
        samples = pq_match.sample(min(10, len(pq_match)))
        spot_checks = []
        for _, row in samples.iterrows():
            spot_checks.append({
                "carrier": str(row.get('Carrier', '')),
                "place": str(row.get('Place', ''))[:40],
                "container": str(row.get('Container_Type', '')),
                "charge": str(row.get('Charge_Name', '')),
                "amount": float(row.get('Amount', 0)),
                "eff": str(row.get('Eff', ''))[:10],
                "exp": str(row.get('Exp', ''))[:10],
                "note": str(row.get('Note', '')),
            })
        report["spot_checks"] = spot_checks

    report["checks"].append({"check": "parquet_has_data", "pass": len(pq_match) > 0})
    return report


def _audit_scfi(df: pd.DataFrame, excel_path: Path) -> dict:
    """Audit SCFI file vs Parquet — verify prices, Contract, and Group_Code."""
    report = {
        "file": excel_path.name,
        "type": "SCFI",
        "checks": [],
        "mismatches": [],
        "summary": {},
    }

    try:
        xls = pd.ExcelFile(excel_path)
        if 'RATE TABLE' not in xls.sheet_names:
            report["error"] = "No 'RATE TABLE' sheet found"
            return report

        raw = xls.parse('RATE TABLE', header=None)
        if len(raw) < 3:
            report["error"] = "Too few rows in RATE TABLE"
            return report

        # Parse SCFI source data
        # Row 0 = charge group (parent header), Row 1 = container sub-header
        header_parent = raw.iloc[0].fillna(method='ffill')
        header_container = raw.iloc[1]
        data = raw.iloc[2:].reset_index(drop=True)

        # Extract destinations and core data from SCFI
        source_rates = []
        for row_idx, row in data.iterrows():
            dest = str(row.iloc[0] if pd.notna(row.iloc[0]) else '').strip()
            if not dest or dest == 'nan':
                continue

            contract = str(row.iloc[3] if pd.notna(row.iloc[3]) else '').strip()
            mrcode = str(row.iloc[4] if pd.notna(row.iloc[4]) else '').strip()

            # Validity dates
            eff = row.iloc[5] if pd.notna(row.iloc[5]) else None
            exp = row.iloc[6] if pd.notna(row.iloc[6]) else None

            # Rate columns start from index 7 typically
            for col_idx in range(7, min(len(row), raw.shape[1])):
                amount = row.iloc[col_idx]
                if pd.isna(amount):
                    continue
                try:
                    amount = float(amount)
                except (ValueError, TypeError):
                    continue

                charge = str(header_parent.iloc[col_idx]).strip()
                container = str(header_container.iloc[col_idx]).strip()

                source_rates.append({
                    'Destination': dest,
                    'Contract': contract,
                    'Group_Code': mrcode,
                    'Charge': charge,
                    'Container': CONTAINER_NORMALIZE.get(container, container),
                    'Amount': amount,
                    'Eff': eff,
                    'Exp': exp,
                })

        # Filter Parquet for HPL/SCFI
        pq_scfi = df[
            (df['Carrier'].str.upper() == 'HPL') &
            (df['Rate_Type'] == 'SCFI') &
            (df['Source_File'].str.contains('SCFI', case=False, na=False))
        ]

        report["source_rates_count"] = len(source_rates)
        report["parquet_scfi_count"] = len(pq_scfi)

        # Cross-check: for each source rate, find it in Parquet
        matches = 0
        mismatches = []
        for src in source_rates[:30]:  # Check first 30
            dest_key = src['Destination'].upper()
            # Find in Parquet by destination + charge + container
            pq_rows = pq_scfi[
                (pq_scfi['Place'].str.upper().str.contains(dest_key[:20], na=False)) &
                (pq_scfi['Container_Type'] == src['Container'])
            ]

            if len(pq_rows) > 0:
                # Check if any amount matches
                amounts = pq_rows['Amount'].values
                if any(abs(a - src['Amount']) < 1 for a in amounts):
                    matches += 1
                else:
                    mismatches.append({
                        "destination": src['Destination'][:40],
                        "charge": src['Charge'],
                        "container": src['Container'],
                        "source_amount": src['Amount'],
                        "parquet_amounts": [round(a, 2) for a in amounts[:5]],
                        "status": "AMOUNT_MISMATCH",
                    })
            else:
                mismatches.append({
                    "destination": src['Destination'][:40],
                    "charge": src['Charge'],
                    "container": src['Container'],
                    "source_amount": src['Amount'],
                    "status": "NOT_FOUND_IN_PARQUET",
                })

        report["summary"] = {
            "source_rates": len(source_rates),
            "checked": min(30, len(source_rates)),
            "matches": matches,
            "mismatches": len(mismatches),
            "accuracy": f"{matches / min(30, len(source_rates)) * 100:.1f}%" if source_rates else "N/A",
        }

        # Contract check
        if 'Contract' in pq_scfi.columns:
            has_contract = pq_scfi['Contract'].notna() & (pq_scfi['Contract'] != '') & (pq_scfi['Contract'] != 'nan')
            report["contract_check"] = {
                "rows_with_contract": int(has_contract.sum()),
                "total_scfi_rows": len(pq_scfi),
                "sample_contracts": pq_scfi.loc[has_contract, 'Contract'].unique()[:5].tolist(),
            }

        if 'Group_Code' in pq_scfi.columns:
            has_gc = pq_scfi['Group_Code'].notna() & (pq_scfi['Group_Code'] != '') & (pq_scfi['Group_Code'] != 'nan')
            report["group_code_check"] = {
                "rows_with_group_code": int(has_gc.sum()),
                "sample_codes": pq_scfi.loc[has_gc, 'Group_Code'].unique()[:5].tolist(),
            }

        report["mismatches"] = mismatches[:10]  # Top 10 mismatches

        report["checks"].append({"check": "scfi_data_found", "pass": len(pq_scfi) > 0})
        report["checks"].append({"check": "amount_accuracy", "pass": len(mismatches) == 0, "details": f"{matches}/{min(30, len(source_rates))}"})
        report["checks"].append({"check": "has_contract_column", "pass": 'Contract' in pq_scfi.columns})
        report["checks"].append({"check": "has_group_code_column", "pass": 'Group_Code' in pq_scfi.columns})

    except Exception as e:
        report["error"] = str(e)
        import traceback
        traceback.print_exc()

    return report


def _audit_fix(df: pd.DataFrame, excel_path: Path) -> dict:
    """Audit Fixed Rate file vs Parquet — check COC + SOC HPL sheets."""
    report = {
        "file": excel_path.name,
        "type": "FIX",
        "checks": [],
        "mismatches": [],
        "sheets_found": [],
        "summary": {},
    }

    try:
        xls = pd.ExcelFile(excel_path)
        report["sheets_found"] = xls.sheet_names

        # Check COC sheet
        if 'COC' in xls.sheet_names:
            coc = xls.parse('COC', header=0)
            coc_routes = len(coc.dropna(subset=[coc.columns[0]]))

            # Find matching data in Parquet
            pq_fix = df[df['Rate_Type'] == 'FIX']
            pq_coc = pq_fix[~pq_fix['Note'].str.contains('SOC', case=False, na=False)]

            report["coc_check"] = {
                "source_routes": coc_routes,
                "parquet_rows": len(pq_coc),
                "carriers": pq_coc['Carrier'].unique().tolist() if len(pq_coc) > 0 else [],
            }

            # Spot check: compare a few COC rates
            if len(coc) > 0 and len(pq_coc) > 0:
                spot = []
                for _, row in coc.head(5).iterrows():
                    pod = str(row.get('POD', ''))
                    carrier = str(row.get('Carrier', ''))
                    if pod and carrier:
                        pq_match = pq_coc[
                            (pq_coc['POD'].str.contains(pod[:10], case=False, na=False)) &
                            (pq_coc['Carrier'].str.contains(carrier[:3], case=False, na=False))
                        ]
                        spot.append({
                            "pod": pod[:30],
                            "carrier": carrier,
                            "source_20gp": float(row.get('Base Ocean Freight', 0) if pd.notna(row.get('Base Ocean Freight', None)) else 0),
                            "parquet_match_count": len(pq_match),
                        })
                report["coc_spot_checks"] = spot

        # Check SOC HPL sheet
        if 'SOC HPL' in xls.sheet_names:
            soc = xls.parse('SOC HPL', header=None)
            soc_data = soc.iloc[2:]  # Skip 2 header rows
            soc_routes = len(soc_data.dropna(subset=[0]))

            pq_soc = df[
                (df['Rate_Type'] == 'FIX') &
                (df['Note'].str.contains('SOC', case=False, na=False)) &
                (df['Carrier'].str.upper() == 'HPL')
            ]

            report["soc_hpl_check"] = {
                "source_routes": soc_routes,
                "parquet_rows": len(pq_soc),
                "has_puc_applied": any(
                    pq_soc['Charge_Name'].str.contains('Total', case=False, na=False)
                ) if len(pq_soc) > 0 else False,
            }

            # Check Contract column for SOC
            if 'Contract' in pq_soc.columns and len(pq_soc) > 0:
                has_sc = pq_soc['Contract'].notna() & (pq_soc['Contract'] != '') & (pq_soc['Contract'] != 'nan')
                report["soc_contract_check"] = {
                    "rows_with_contract": int(has_sc.sum()),
                    "sample": pq_soc.loc[has_sc, 'Contract'].unique()[:5].tolist(),
                }

        report["checks"].append({"check": "coc_sheet", "pass": 'COC' in xls.sheet_names})
        report["checks"].append({"check": "soc_hpl_sheet", "pass": 'SOC HPL' in xls.sheet_names})

    except Exception as e:
        report["error"] = str(e)

    return report


def generate_html_report(overview: dict, audits: list[dict]) -> str:
    """Generate a visual HTML report for Parquet audit."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    checks_html = ""
    for audit in audits:
        file_name = audit.get("file", "Unknown")
        file_type = audit.get("type", "?")
        checks = audit.get("checks", [])
        summary = audit.get("summary", {})
        mismatches = audit.get("mismatches", [])

        # Status badges
        all_pass = all(c.get("pass", False) for c in checks)
        status_badge = '✅ PASS' if all_pass else '⚠️ ISSUES'
        status_color = '#2ecc71' if all_pass else '#e74c3c'

        checks_rows = ""
        for c in checks:
            icon = "✅" if c.get("pass") else "❌"
            detail = c.get("details", "")
            checks_rows += f"<tr><td>{icon}</td><td>{c['check']}</td><td>{detail}</td></tr>"

        mismatch_rows = ""
        for m in mismatches[:5]:
            mismatch_rows += f"""<tr>
                <td>{m.get('destination', m.get('pod', ''))}</td>
                <td>{m.get('charge', '')}</td>
                <td>{m.get('container', '')}</td>
                <td>${m.get('source_amount', 0):,.0f}</td>
                <td>{m.get('parquet_amounts', m.get('status', ''))}</td>
                <td>{m.get('status', '')}</td>
            </tr>"""

        summary_html = ""
        for k, v in summary.items():
            summary_html += f"<tr><td><strong>{k}</strong></td><td>{v}</td></tr>"

        # Contract/Group_Code checks (SCFI)
        contract_html = ""
        if "contract_check" in audit:
            cc = audit["contract_check"]
            contract_html += f"""
            <h4>📋 Contract (SC) Check</h4>
            <p>Rows with Contract: <strong>{cc.get('rows_with_contract', 0)}</strong> / {cc.get('total_scfi_rows', 0)}</p>
            <p>Sample: {', '.join(str(s) for s in cc.get('sample_contracts', []))}</p>
            """
        if "group_code_check" in audit:
            gc = audit["group_code_check"]
            contract_html += f"""
            <h4>🏷️ Group Code (mr code) Check</h4>
            <p>Rows with Group Code: <strong>{gc.get('rows_with_group_code', 0)}</strong></p>
            <p>Sample: {', '.join(str(s) for s in gc.get('sample_codes', []))}</p>
            """

        # SOC HPL check (FIX)
        soc_html = ""
        if "soc_hpl_check" in audit:
            sc = audit["soc_hpl_check"]
            soc_html += f"""
            <h4>📦 SOC HPL Check</h4>
            <p>Source routes: {sc.get('source_routes', 0)} | Parquet rows: <strong>{sc.get('parquet_rows', 0)}</strong></p>
            <p>PUC Applied: {'✅ Yes' if sc.get('has_puc_applied') else '❌ No'}</p>
            """
        if "soc_contract_check" in audit:
            scc = audit["soc_contract_check"]
            soc_html += f"""
            <p>SOC Contract (SC): <strong>{scc.get('rows_with_contract',0)}</strong> rows</p>
            <p>Sample: {', '.join(str(s) for s in scc.get('sample', []))}</p>
            """

        checks_html += f"""
        <div class="audit-card">
            <div class="card-header" style="border-left: 4px solid {status_color};">
                <span class="badge" style="background:{status_color}">{file_type}</span>
                <h3>{file_name}</h3>
                <span class="status">{status_badge}</span>
            </div>
            <div class="card-body">
                <h4>📊 Summary</h4>
                <table class="summary-table"><tbody>{summary_html}</tbody></table>

                <h4>✅ Checks</h4>
                <table class="checks-table">
                <thead><tr><th></th><th>Check</th><th>Details</th></tr></thead>
                <tbody>{checks_rows}</tbody>
                </table>

                {contract_html}
                {soc_html}

                {"<h4>⚠️ Mismatches (top 5)</h4><table class='mismatch-table'><thead><tr><th>Destination</th><th>Charge</th><th>Container</th><th>Source $</th><th>Parquet $</th><th>Status</th></tr></thead><tbody>" + mismatch_rows + "</tbody></table>" if mismatch_rows else ""}
            </div>
        </div>
        """

    # Overview stats
    ov = overview
    rate_types_html = ""
    for rt, cnt in ov.get("rate_types", {}).items():
        rate_types_html += f"<tr><td>{rt}</td><td>{cnt:,}</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Parquet Audit Report — Nelson Freight</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0f1419; color: #e1e8ed; padding: 24px; }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        h1 {{ color: #1da1f2; margin-bottom: 8px; font-size: 28px; }}
        h2 {{ color: #8899a6; font-size: 18px; margin-bottom: 24px; font-weight: 400; }}
        h3 {{ color: #fff; margin: 0; font-size: 16px; }}
        h4 {{ color: #1da1f2; margin: 16px 0 8px; font-size: 14px; }}

        .overview {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 32px; }}
        .stat-card {{ background: #192734; border-radius: 12px; padding: 20px; text-align: center; }}
        .stat-card .value {{ font-size: 32px; font-weight: 700; color: #1da1f2; }}
        .stat-card .label {{ color: #8899a6; font-size: 13px; margin-top: 4px; }}

        .audit-card {{ background: #192734; border-radius: 12px; margin-bottom: 20px; overflow: hidden; }}
        .card-header {{ padding: 16px 20px; display: flex; align-items: center; gap: 12px; background: #22303c; }}
        .card-body {{ padding: 20px; }}
        .badge {{ padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 700; color: #fff; }}
        .status {{ margin-left: auto; font-size: 14px; }}

        table {{ width: 100%; border-collapse: collapse; margin: 8px 0; }}
        th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #22303c; font-size: 13px; }}
        th {{ color: #8899a6; font-weight: 600; }}
        tr:hover {{ background: #22303c; }}

        .summary-table td:first-child {{ width: 200px; color: #8899a6; }}
        .mismatch-table {{ font-size: 12px; }}
        .mismatch-table td {{ color: #e74c3c; }}

        .footer {{ text-align: center; color: #657786; font-size: 12px; margin-top: 32px; }}
    </style>
</head>
<body>
<div class="container">
    <h1>🔍 Parquet Audit Report</h1>
    <h2>Nelson Freight Pricing System — {timestamp}</h2>

    <div class="overview">
        <div class="stat-card">
            <div class="value">{ov.get('total_rows', 0):,}</div>
            <div class="label">Total Rows</div>
        </div>
        <div class="stat-card">
            <div class="value">{ov.get('carrier_count', 0)}</div>
            <div class="label">Carriers</div>
        </div>
        <div class="stat-card">
            <div class="value">{len(ov.get('charge_types', []))}</div>
            <div class="label">Charge Types</div>
        </div>
        <div class="stat-card">
            <div class="value">{'✅' if ov.get('has_contract') else '❌'}</div>
            <div class="label">Contract Column</div>
        </div>
        <div class="stat-card">
            <div class="value">{'✅' if ov.get('has_group_code') else '❌'}</div>
            <div class="label">Group Code Column</div>
        </div>
    </div>

    <div class="audit-card">
        <div class="card-header" style="border-left: 4px solid #1da1f2;">
            <h3>📈 Rate Type Breakdown</h3>
        </div>
        <div class="card-body">
            <table><thead><tr><th>Rate Type</th><th>Count</th></tr></thead>
            <tbody>{rate_types_html}</tbody></table>
        </div>
    </div>

    {checks_html}

    <div class="footer">
        Generated by parquet_auditor.py — Nelson Freight Rate Import System
    </div>
</div>
</body>
</html>"""

    return html


def run_full_audit(source_files: list[str] = None, output_html: bool = True) -> dict:
    """
    Run full audit: overview + cross-check against source files.

    Args:
        source_files: list of Excel files to verify against. If None, auto-detect.
        output_html: generate HTML report

    Returns:
        Full audit report
    """
    print("=" * 60)
    print("PARQUET AUDIT — Nelson Freight Pricing")
    print("=" * 60)

    # Load Parquet
    df = load_parquet()
    if df.empty:
        return {"error": "No Parquet data"}

    # Overview
    overview = audit_parquet_overview(df)
    print(f"\n📊 Overview: {overview['total_rows']:,} rows | "
          f"{overview['carrier_count']} carriers | "
          f"Contract: {'✅' if overview['has_contract'] else '❌'} | "
          f"Group_Code: {'✅' if overview['has_group_code'] else '❌'}")

    # Find source files to audit against
    if source_files is None:
        source_files = []
        # Check processed/ and incoming/ and data/
        for d in [PROCESSED_DIR, INCOMING_DIR, DATA_DIR]:
            for f in d.glob("*.xlsx"):
                fname_up = f.name.upper()
                if any(k in fname_up for k in ['SCFI', 'FIX', 'FIXED', 'RATE SHEET', 'US CANADA', 'UPDATE RATE']):
                    source_files.append(str(f))

    # Run audits per file
    audits = []
    for fpath in source_files[:10]:  # Max 10 files
        print(f"\n🔍 Auditing: {Path(fpath).name}")
        result = audit_vs_excel(df, fpath)
        audits.append(result)

        # Print summary
        summary = result.get("summary", {})
        for k, v in summary.items():
            print(f"    {k}: {v}")

        mismatches = result.get("mismatches", [])
        if mismatches:
            print(f"    ⚠️  {len(mismatches)} mismatches found")
        else:
            print(f"    ✅ All checks passed")

    # Generate HTML
    if output_html:
        html = generate_html_report(overview, audits)
        report_path = DATA_DIR / f"audit_report_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
        with report_path.open("w", encoding="utf-8") as f:
            f.write(html)
        print(f"\n📄 HTML Report: {report_path}")

    full_report = {
        "overview": overview,
        "audits": audits,
        "files_checked": len(audits),
        "timestamp": datetime.now().isoformat(),
    }

    return full_report


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Parquet Audit Tool")
    parser.add_argument("--source", nargs="*", help="Excel file(s) to check against")
    parser.add_argument("--html", action="store_true", default=True, help="Generate HTML report")
    parser.add_argument("--no-html", action="store_true", help="Skip HTML report")

    args = parser.parse_args()

    result = run_full_audit(
        source_files=args.source,
        output_html=not args.no_html
    )

    # Print JSON result
    print("\n" + json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
