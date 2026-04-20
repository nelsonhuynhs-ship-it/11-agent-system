"""
puc-audit.py — classify Total Ocean Freight behaviour per (Carrier × Rate_Type × SVC)

For each combo: compute avg(TOF) vs avg(BASIC + ISPS + ARB + HDL) vs avg(PSS/PUC)
residual = TOF - known_surcharges. Classify:
  - TOF_INCLUDES_PSS_PUC  : residual ≈ PSS/PUC amount (TOF already bundles PUC)
  - TOF_NET               : residual ≈ 0 (TOF = ocean + basic fees only — NEED add PSS/PUC for all-in)
  - UNCLEAR               : residual does not match either pattern (extra surcharges not accounted)

Output: plans/reports/puc-audit-result-YYYYMMDD.csv

Usage:
    python scripts/puc-audit.py
"""
from __future__ import annotations
import csv
from datetime import datetime
from pathlib import Path

import duckdb

PARQUET = r"D:/OneDrive/NelsonData/pricing/Cleaned_Master_History.parquet"
REPORTS_DIR = Path(__file__).parent.parent / "plans" / "reports"


def main() -> int:
    con = duckdb.connect()
    q = f"""
WITH base AS (
  SELECT Carrier, Rate_Type, POL, POD, Place, Container_Type, Note,
    MAX(CASE WHEN Charge_Name='Total Ocean Freight' THEN Amount END) as tof,
    MAX(CASE WHEN Charge_Name IN ('BASIC O/F','Base Ocean Freight') THEN Amount END) as basic,
    MAX(CASE WHEN Charge_Name='ISPS/LSF/CMC' THEN Amount END) as isps,
    MAX(CASE WHEN Charge_Name='ARB/OLF' THEN Amount END) as arb,
    MAX(CASE WHEN Charge_Name IN ('PSS/PUC','PSS') THEN Amount END) as pss_puc,
    MAX(CASE WHEN Charge_Name='HANDLING FEE FOR CARRIER' THEN Amount END) as hdl
  FROM read_parquet('{PARQUET}')
  WHERE Container_Type IN ('20GP','40HQ') AND Exp >= '2026-04-01'
  GROUP BY Carrier, Rate_Type, POL, POD, Place, Container_Type, Note
  HAVING tof IS NOT NULL AND basic IS NOT NULL
)
SELECT Carrier, Rate_Type,
  CASE WHEN LOWER(COALESCE(Note,'')) LIKE '%soc%' THEN 'SOC' ELSE 'COC' END as svc,
  COUNT(*) as n,
  ROUND(AVG(tof),0) as avg_tof,
  ROUND(AVG(basic + COALESCE(isps,0) + COALESCE(arb,0) + COALESCE(hdl,0)),0) as avg_known,
  ROUND(AVG(COALESCE(pss_puc,0)),0) as avg_pss_puc,
  ROUND(AVG(tof - basic - COALESCE(isps,0) - COALESCE(arb,0) - COALESCE(hdl,0)),0) as residual
FROM base GROUP BY Carrier, Rate_Type, svc HAVING n >= 3
ORDER BY Carrier, Rate_Type, svc
"""
    rows = con.execute(q).fetchall()
    REPORTS_DIR.mkdir(exist_ok=True, parents=True)
    out = REPORTS_DIR / f"puc-audit-result-{datetime.now().strftime('%Y%m%d')}.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Carrier", "Rate_Type", "SVC", "Sample_N",
                    "Avg_TOF", "Avg_Known_Sum", "Avg_PSS_PUC", "Residual",
                    "Classification"])
        for r in rows:
            carrier, rt, svc, n, tof, known, puc, resid = r
            if puc > 50 and abs(resid - puc) < 100:
                cls = "TOF_INCLUDES_PSS_PUC"
            elif abs(resid) < 50:
                cls = "TOF_NET"
            else:
                cls = f"UNCLEAR_residual_${int(resid)}"
            w.writerow([carrier, rt, svc, n, tof, known, puc, resid, cls])
            print(f"  {carrier:10s} {rt:5s} {svc:4s} n={n:>4d}  TOF=${tof:>5.0f}  "
                  f"known=${known:>5.0f}  PUC=${puc:>4.0f}  resid=${resid:>5.0f}  -> {cls}")
    print(f"\n[OK] Saved: {out}  rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
