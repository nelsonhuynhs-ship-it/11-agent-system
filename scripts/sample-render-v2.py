#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sample-render-v2.py — Generate sample rate table v2 HTML for visual verification.
Run from repo root: python scripts/sample-render-v2.py

Saves output to: plans/visuals/sample-render-v2-actual.html
Open that file in browser and compare with plans/visuals/rate-table-v2-preview.html.
"""
import sys
import os
from pathlib import Path

# Add email_engine/templates and email_engine/core to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "email_engine" / "templates"))
sys.path.insert(0, str(REPO_ROOT / "email_engine" / "core"))
sys.path.insert(0, str(REPO_ROOT / "email_engine"))
sys.path.insert(0, str(REPO_ROOT))

from rate_table_renderer import render_dual_rate_table

# Sample rate data — mimics shape from auto_rate_builder.build_rate_table_for_customer
import pandas as pd
from datetime import datetime, timedelta

TODAY = datetime.now().date()
EXP1 = pd.Timestamp(TODAY + timedelta(days=9))   # ~3 May
EXP2 = pd.Timestamp(TODAY + timedelta(days=21))  # ~15 May
EXP3 = pd.Timestamp(TODAY + timedelta(days=6))   # SCFI shorter

def _r(pod, carrier, r20, r40, rate_type="FAK", routing_label="", eff=None, exp=None):
    return {
        "pod_code": pod, "carrier": carrier, "rate_20": r20, "rate_40": r40,
        "rate_type": rate_type, "routing_label": routing_label,
        "eff": eff, "exp": exp or EXP2,
    }

HPH_RATES = [
    # USLAX
    _r("USLAX", "ONE",  1681, 2175, "FIX", exp=EXP2),
    _r("USLAX", "CMA",  1774, 2199, "FIX", exp=EXP2),
    _r("USLAX", "HPL",  1860, 2320, "FAK", exp=EXP2),
    # USSAV
    _r("USSAV", "HPL",  2988, 3016, "SCFI", exp=EXP3),
    _r("USSAV", "ONE",  3142, 3312, "FIX", exp=EXP2),
    _r("USSAV", "CMA",  3200, 3450, "FIX", exp=EXP2),
    # USNYC
    _r("USNYC", "HPL",  3016, 3016, "SCFI", exp=EXP3),
    _r("USNYC", "CMA",  3280, 3420, "FIX", exp=EXP2),
    _r("USNYC", "YML",  3350, 3550, "FIX", exp=EXP2),
    # USHOU
    _r("USHOU", "CMA",  2980, 3620, "FIX", exp=EXP2),
    _r("USHOU", "ONE",  3050, 3700, "FIX", exp=EXP2),
    _r("USHOU", "HPL",  3180, 3820, "FAK", exp=EXP2),
    # USMIA
    _r("USMIA", "HPL",  3050, 3450, "SCFI", exp=EXP3),
    _r("USMIA", "CMA",  3280, 3680, "FIX", exp=EXP2),
    _r("USMIA", "ZIM",  3400, 3820, "FAK", exp=EXP2),
    # USTIW
    _r("USTIW", "YML",  1570, 2580, "FIX", exp=EXP2),
    _r("USTIW", "ONE",  1681, 2175, "FIX", exp=EXP2),
    _r("USTIW", "CMA",  1820, 2250, "FIX", exp=EXP2),
    # USATL — RIPI via SAV
    _r("USATL", "HPL",  3580, 4120, "SCFI", routing_label="via SAV", exp=EXP3),
    _r("USATL", "ONE",  3780, 4350, "FIX",  routing_label="via NOR", exp=EXP2),
    _r("USATL", "CMA",  3850, 4420, "FIX",  routing_label="via SAV", exp=EXP2),
    # USCHI — IPI
    _r("USCHI", "ONE",  3450, 4020, "FIX", exp=EXP2),
    _r("USCHI", "HPL",  3520, 4080, "SCFI", exp=EXP3),
    _r("USCHI", "CMA",  3620, 4180, "FIX", exp=EXP2),
    # USDAL — IPI
    _r("USDAL", "CMA",  3280, 3850, "FIX", exp=EXP2),
    _r("USDAL", "ONE",  3380, 3980, "FIX", exp=EXP2),
    _r("USDAL", "HPL",  3480, 4050, "FAK", exp=EXP2),
    # USDEN — IPI
    _r("USDEN", "ONE",  3850, 4420, "FIX", exp=EXP2),
    _r("USDEN", "HPL",  3920, 4520, "FAK", exp=EXP2),
    _r("USDEN", "CMA",  3980, 4580, "FIX", exp=EXP2),
]

HCM_RATES = [
    _r("USLAX", "ONE",  1581, 2075, "FIX", exp=EXP2),
    _r("USLAX", "CMA",  1674, 2099, "FIX", exp=EXP2),
    _r("USLAX", "WHL",  1760, 2220, "FAK", exp=EXP2),
    _r("USSAV", "HPL",  2888, 2916, "SCFI", exp=EXP3),
    _r("USSAV", "ONE",  3042, 3212, "FIX", exp=EXP2),
    _r("USSAV", "CMA",  3100, 3350, "FIX", exp=EXP2),
    _r("USNYC", "HPL",  2417, 3016, "SCFI", exp=EXP3),
    _r("USNYC", "ONE",  2593, 3112, "FIX", exp=EXP2),
    _r("USNYC", "CMA",  2680, 3320, "FIX", exp=EXP2),
    _r("USHOU", "CMA",  2780, 3420, "FIX", exp=EXP2),
    _r("USHOU", "ONE",  2850, 3500, "FIX", exp=EXP2),
    _r("USHOU", "HPL",  2980, 3620, "FAK", exp=EXP2),
    _r("USMIA", "HPL",  2950, 3350, "SCFI", exp=EXP3),
    _r("USMIA", "CMA",  3180, 3580, "FIX", exp=EXP2),
    _r("USMIA", "ZIM",  3300, 3720, "FAK", exp=EXP2),
    _r("USTIW", "YML",  1470, 2480, "FIX", exp=EXP2),
    _r("USTIW", "ONE",  1581, 2075, "FIX", exp=EXP2),
    _r("USTIW", "CMA",  1720, 2150, "FIX", exp=EXP2),
    _r("USATL", "HPL",  3480, 4020, "SCFI", routing_label="via SAV", exp=EXP3),
    _r("USATL", "ONE",  3680, 4250, "FIX",  routing_label="via NOR", exp=EXP2),
    _r("USATL", "CMA",  3750, 4320, "FIX",  routing_label="via SAV", exp=EXP2),
    _r("USCHI", "ONE",  3350, 3920, "FIX", exp=EXP2),
    _r("USCHI", "HPL",  3420, 3980, "SCFI", exp=EXP3),
    _r("USCHI", "CMA",  3520, 4080, "FIX", exp=EXP2),
    _r("USDAL", "CMA",  3180, 3750, "FIX", exp=EXP2),
    _r("USDAL", "ONE",  3280, 3880, "FIX", exp=EXP2),
    _r("USDAL", "HPL",  3380, 3950, "FAK", exp=EXP2),
    _r("USDEN", "ONE",  3750, 4320, "FIX", exp=EXP2),
    _r("USDEN", "HPL",  3820, 4420, "FAK", exp=EXP2),
    _r("USDEN", "CMA",  3880, 4480, "FIX", exp=EXP2),
]

POD_LIST = [
    {"code": "USLAX", "city": "Los Angeles", "type": "main"},
    {"code": "USSAV", "city": "Savannah",    "type": "main"},
    {"code": "USNYC", "city": "New York",    "type": "main"},
    {"code": "USHOU", "city": "Houston",     "type": "main"},
    {"code": "USMIA", "city": "Miami",       "type": "main"},
    {"code": "USTIW", "city": "Tacoma",      "type": "main"},
    {"code": "USATL", "city": "Atlanta",     "type": "inland", "gateway": "RIPI"},
    {"code": "USCHI", "city": "Chicago",     "type": "inland", "gateway": "IPI"},
    {"code": "USDAL", "city": "Dallas",      "type": "inland", "gateway": "IPI"},
    {"code": "USDEN", "city": "Denver",      "type": "inland", "gateway": "IPI"},
]

from datetime import date
week = date.today().isocalendar()[1]

html_fragment = render_dual_rate_table(
    hph_rates=HPH_RATES,
    hcm_rates=HCM_RATES,
    pod_list=POD_LIST,
    week=week,
)

# Wrap in standalone HTML page for browser preview
FULL_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sample Render v2 — Rate Table Actual</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Arial, sans-serif; margin: 24px; background: #f5f7fa; }}
  h1 {{ color: #0a4d3c; font-size: 18px; margin-bottom: 4px; }}
  .note {{ background: #fff9e6; border-left: 3px solid #f0b429; padding: 8px 12px; margin: 12px 0; font-size: 13px; }}
</style>
</head>
<body>
<h1>Rate Table v2 — Actual Render Output</h1>
<div class="note">This is the Python renderer output. Compare with rate-table-v2-preview.html</div>
{html_fragment}
</body>
</html>"""

OUT = REPO_ROOT / "plans" / "visuals" / "sample-render-v2-actual.html"
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(FULL_HTML, encoding="utf-8")

size = OUT.stat().st_size
print(f"Saved: {OUT}")
print(f"Size:  {size:,} bytes ({size/1024:.1f} KB)")
if size > 51_200:
    print("WARNING: size > 50KB — optimize CSS or reduce content")
else:
    print("OK: size within 50KB limit")
