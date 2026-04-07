# -*- coding: utf-8 -*-
"""
campaign-dashboard.py — Self-contained HTML dashboard for GoClaw campaign runs.

Reads campaign log CSV → generates rich HTML → opens in browser.

Usage (standalone):
    python campaign-dashboard.py --log path/to/log.csv --dry-run

Usage (imported):
    from campaign_dashboard import open_dashboard
    open_dashboard(log_path, is_dry_run=True, tiers="HOT", count=3)
"""
import webbrowser
import tempfile
import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd


# ── HTML Template ─────────────────────────────────────────────────────────────

_STATUS_BADGE = {
    "DRY_RUN":        ('<span class="badge dry">Would Send</span>', "row-dry"),
    "sent":           ('<span class="badge sent">Sent</span>',      "row-sent"),
    "SKIP_NO_RATES":  ('<span class="badge skip">No Rates</span>',  "row-skip"),
    "SKIP_BLOCKED":   ('<span class="badge skip">Cooldown</span>',  "row-skip"),
    "FAILED":         ('<span class="badge fail">Failed</span>',    "row-fail"),
}

_CSS = """
:root{--bg:#0f1117;--card:#1a1d27;--border:#2a2d3a;--accent:#4f8ef7;
  --green:#3ecf8e;--amber:#f59e0b;--red:#f87171;--muted:#6b7280;
  --text:#e5e7eb;font-family:'Inter',system-ui,sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);padding:24px;min-height:100vh}
h1{font-size:1.4rem;font-weight:700;margin-bottom:4px}
.subtitle{color:var(--muted);font-size:.85rem;margin-bottom:24px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:28px}
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px}
.card .label{font-size:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px}
.card .value{font-size:2rem;font-weight:700}
.card.green .value{color:var(--green)}
.card.amber .value{color:var(--amber)}
.card.red   .value{color:var(--red)}
.card.blue  .value{color:var(--accent)}
.section{background:var(--card);border:1px solid var(--border);border-radius:10px;overflow:hidden;margin-bottom:20px}
.section-head{padding:12px 16px;border-bottom:1px solid var(--border);font-size:.85rem;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
table{width:100%;border-collapse:collapse;font-size:.82rem}
th{padding:10px 12px;text-align:left;color:var(--muted);font-weight:500;border-bottom:1px solid var(--border)}
td{padding:9px 12px;border-bottom:1px solid #1e2130}
tr:last-child td{border-bottom:none}
tr.row-dry td:first-child{border-left:3px solid var(--accent)}
tr.row-sent td:first-child{border-left:3px solid var(--green)}
tr.row-skip td:first-child{border-left:3px solid var(--muted)}
tr.row-fail td:first-child{border-left:3px solid var(--red)}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.75rem;font-weight:600}
.badge.dry {background:#1e3a6e;color:#93c5fd}
.badge.sent{background:#064e3b;color:#6ee7b7}
.badge.skip{background:#1f2937;color:#9ca3af}
.badge.fail{background:#450a0a;color:#fca5a5}
.bar-wrap{display:flex;height:8px;border-radius:4px;overflow:hidden;margin:8px 0}
.bar-seg{transition:width .4s}
.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:.78rem;color:var(--muted);padding:12px 16px}
.legend span{display:flex;align-items:center;gap:5px}
.dot{width:8px;height:8px;border-radius:50%}
"""

def _bar_html(sent, skip, fail, total):
    """Horizontal segmented progress bar."""
    if total == 0:
        return "<div class='bar-wrap' style='background:#1e2130'></div>"
    s = round(sent / total * 100, 1)
    k = round(skip / total * 100, 1)
    f = round(fail / total * 100, 1)
    return (
        f"<div class='bar-wrap'>"
        f"<div class='bar-seg' style='width:{s}%;background:#3ecf8e'></div>"
        f"<div class='bar-seg' style='width:{k}%;background:#374151'></div>"
        f"<div class='bar-seg' style='width:{f}%;background:#f87171'></div>"
        f"</div>"
    )


def generate_dashboard_html(log_path: Path, is_dry_run: bool, tiers: str = "", count: int = 0) -> str:
    """Generate self-contained HTML dashboard from campaign log CSV."""
    df = pd.read_csv(log_path) if log_path.exists() else pd.DataFrame()

    total = len(df)
    sent  = int((df["status"] == ("DRY_RUN" if is_dry_run else "sent")).sum()) if total else 0
    skip  = int(df["status"].str.startswith("SKIP").sum()) if total else 0
    fail  = int((df["status"] == "FAILED").sum()) if total else 0
    remaining = max(0, count - total)

    mode_label = "DRY-RUN PREVIEW" if is_dry_run else "LIVE CAMPAIGN"
    ts = datetime.now().strftime("%d %b %Y  %H:%M")

    # ── Summary cards
    sent_label  = "Would Send" if is_dry_run else "Sent"
    sent_color  = "blue" if is_dry_run else "green"
    cards = f"""
<div class="cards">
  <div class="card {sent_color}"><div class="label">{sent_label}</div><div class="value">{sent}</div></div>
  <div class="card"><div class="label">Skipped</div><div class="value" style="color:var(--muted)">{skip}</div></div>
  <div class="card red"><div class="label">Failed</div><div class="value">{fail}</div></div>
  <div class="card"><div class="label">Total Processed</div><div class="value">{total}</div></div>
  <div class="card amber"><div class="label">Remaining</div><div class="value">{remaining}</div></div>
</div>"""

    # ── Progress bar
    bar = _bar_html(sent, skip, fail, total) if total else ""
    legend = f"""
<div class="legend">
  <span><div class="dot" style="background:#3ecf8e"></div>{sent_label}: {sent}</span>
  <span><div class="dot" style="background:#374151"></div>Skipped: {skip}</span>
  <span><div class="dot" style="background:#f87171"></div>Failed: {fail}</span>
</div>"""

    # ── Campaign breakdown
    campaign_rows = ""
    if total > 0 and "campaign_id" in df.columns:
        for camp, grp in df.groupby("campaign_id"):
            c_sent = int((grp["status"].isin(["DRY_RUN", "sent"])).sum())
            c_skip = int(grp["status"].str.startswith("SKIP").sum())
            c_bar  = _bar_html(c_sent, c_skip, 0, len(grp))
            campaign_rows += f"<tr><td>{camp}</td><td>{len(grp)}</td><td>{c_sent}</td><td>{c_bar}</td></tr>"

    campaign_section = f"""
<div class="section">
  <div class="section-head">By Campaign</div>
  <table><thead><tr><th>Campaign</th><th>Total</th><th>{sent_label}</th><th>Progress</th></tr></thead>
  <tbody>{campaign_rows or '<tr><td colspan=4 style="color:var(--muted);text-align:center">No data</td></tr>'}</tbody>
  </table>
</div>""" if total > 0 else ""

    # ── Lead rows
    lead_rows = ""
    if total > 0:
        for i, row in df.iterrows():
            badge, row_cls = _STATUS_BADGE.get(row.get("status", ""), ('<span class="badge skip">?</span>', ""))
            company  = str(row.get("company", ""))[:35]
            campaign = str(row.get("campaign_id", ""))
            tier     = str(row.get("tier", ""))
            rates    = str(row.get("rates_found", row.get("row_count", "—")))
            ts_cell  = str(row.get("timestamp", ""))[:16] if "timestamp" in df.columns else "—"
            lead_rows += (
                f'<tr class="{row_cls}">'
                f'<td>{i+1}</td><td style="color:#93c5fd">{row.get("email","")}</td>'
                f'<td>{company}</td><td>{campaign}</td><td>{tier}</td>'
                f'<td>{badge}</td><td style="text-align:center">{rates}</td><td style="color:var(--muted)">{ts_cell}</td>'
                f'</tr>'
            )

    leads_section = f"""
<div class="section">
  <div class="section-head">Lead Results ({total})</div>
  <table>
    <thead><tr><th>#</th><th>Email</th><th>Company</th><th>Campaign</th><th>Tier</th><th>Status</th><th>Rates</th><th>Time</th></tr></thead>
    <tbody>{lead_rows or '<tr><td colspan=8 style="color:var(--muted);text-align:center;padding:20px">No leads processed</td></tr>'}</tbody>
  </table>
</div>"""

    return f"""<!DOCTYPE html><html lang="en">
<head><meta charset="utf-8"><title>GoClaw {mode_label}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{_CSS}</style></head>
<body>
<h1>GoClaw — {mode_label}</h1>
<div class="subtitle">{ts} &nbsp;·&nbsp; Tiers: {tiers or 'all'} &nbsp;·&nbsp; Target: {count}</div>
{cards}
<div class="section">
  <div class="section-head">Progress</div>
  {bar}{legend}
</div>
{campaign_section}
{leads_section}
</body></html>"""


def open_dashboard(log_path: Path, is_dry_run: bool = True, tiers: str = "", count: int = 0):
    """Generate dashboard HTML and open in browser. Returns file path."""
    html = generate_dashboard_html(log_path, is_dry_run, tiers, count)
    tmp = Path(tempfile.gettempdir()) / "goclaw-campaign-dashboard.html"
    tmp.write_text(html, encoding="utf-8")
    webbrowser.open(tmp.as_uri())
    print(f"[DASHBOARD] Opened: {tmp}")
    return tmp


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--log",     required=True, help="Campaign log CSV path")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tiers",   default="")
    ap.add_argument("--count",   type=int, default=0)
    args = ap.parse_args()
    open_dashboard(Path(args.log), args.dry_run, args.tiers, args.count)
