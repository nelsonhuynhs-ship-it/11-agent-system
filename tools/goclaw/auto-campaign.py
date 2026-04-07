# -*- coding: utf-8 -*-
"""
auto-campaign.py — GoClaw Email Campaign Orchestrator.

Runs on Laptop VP where Outlook COM is available.
Queries rate tables locally from Parquet (no VPS), sends via local Outlook COM.

Flow:
  1. Pre-check: Outlook running? Parquet fresh?
  2. Load cnee_master_v2.xlsx → filter eligible leads
  3. For each lead: query rate preview from API → send via Outlook COM
  4. Log results → generate report → publish HTML → send Telegram link

Usage:
    python auto-campaign.py --dry-run --tier HOT,WARM_A --count 10
    python auto-campaign.py --tier HOT,WARM_A --count 30
    python auto-campaign.py --report-only
    python auto-campaign.py --auto-tier --count 100 --batches 5
    python auto-campaign.py --preview 3
"""
import argparse
import csv
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# ── Setup ────────────────────────────────────────────────────────────────────

# Resolve repo root: tools/goclaw/auto-campaign.py → Engine_test/
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

try:
    import pandas as pd
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas", "openpyxl", "-q"])
    import pandas as pd

from shared.paths import EMAIL_DATA, EMAIL_LOG, PARQUET_FILE, COMPANY_PDF

# Local email builder + dashboard (same directory — no VPS dependency)
sys.path.insert(0, str(REPO_ROOT / "tools" / "goclaw"))
from local_email_builder import build_email_for_lead          # noqa: E402
from campaign_dashboard import open_dashboard as _open_dashboard  # noqa: E402

# ── Constants ────────────────────────────────────────────────────────────────
CNEE_V2 = EMAIL_DATA / "cnee_master_v2.xlsx"
DEFAULT_DESTINATIONS = "USLAX,USLGB,USNYC,USSAV,USEWR"
DEFAULT_MARKUP = 20.0
DEFAULT_COOLDOWN_DAYS = 14
BATCH_SIZE = 100
BATCH_PAUSE_SEC = 120
JITTER_MIN_SEC = 2
JITTER_MAX_SEC = 5
MAX_TOTAL = 500
MAX_BATCHES = 5
ELIGIBLE_ACTIONS = {"SEND_NOW", "FOLLOW_UP", "PERSONALIZED"}
PLANS_DIR = Path(r"D:/GoClaw-plans")
PUBLISH_BAT = Path(r"C:/Users/Nelson/5398948978/publish-plan.bat")
TELEGRAM_BAT = Path(r"C:/Users/Nelson/5398948978/send-telegram.bat")
CAMPAIGN_LOG = EMAIL_DATA / "campaign_runs"


# ── Pre-checks ───────────────────────────────────────────────────────────────

def check_outlook() -> tuple[bool, str]:
    """Check if Outlook is running (classic OUTLOOK.EXE or new olk.exe). Returns (ok, message)."""
    try:
        result = subprocess.run(
            ["tasklist"], capture_output=True, text=True, timeout=10,
        )
        stdout_upper = result.stdout.upper()
        if "OUTLOOK.EXE" in stdout_upper:
            return True, "Outlook (classic) is running"
        if "OLK.EXE" in stdout_upper:
            return True, "Outlook (New) is running"
        return False, "Outlook is NOT running — mo Outlook truoc khi chay campaign"
    except Exception as e:
        return False, f"Cannot check Outlook: {e}"


def check_parquet_freshness() -> tuple[bool, str, int]:
    """Check Parquet freshness from local file mtime (no VPS call)."""
    if PARQUET_FILE.exists():
        days_old = (datetime.now() - datetime.fromtimestamp(PARQUET_FILE.stat().st_mtime)).days
        if days_old <= 3:
            return True, f"Parquet fresh ({days_old}d old)", days_old
        return False, f"Parquet {days_old}d old — sync OneDrive trước khi chạy", days_old
    return False, f"Parquet not found: {PARQUET_FILE}", 999


def send_telegram_alert(message: str):
    """Send alert to Nelson via Telegram."""
    try:
        subprocess.run(
            [str(TELEGRAM_BAT), "--message", message],
            timeout=30, capture_output=True,
        )
    except Exception as e:
        print(f"[WARN] Telegram send failed: {e}")


# ── Lead Selection ───────────────────────────────────────────────────────────

def auto_select_tiers(cooldown_days: int) -> tuple[list[str], dict[str, int]]:
    """Auto-evaluate tiers based on eligible lead counts. Returns (tier_list, tier_counts)."""
    df = pd.read_excel(CNEE_V2)

    # Base filter: has email + action eligible + not PARK/COOL
    mask = df["EMAIL"].notna() & df["EMAIL"].str.contains("@", na=False)
    mask &= df["ACTION"].isin(ELIGIBLE_ACTIONS)
    mask &= ~df["TIER"].isin(["PARK", "COOL"])

    # Cooldown filter
    cutoff = datetime.now() - timedelta(days=cooldown_days)
    sent_mask = df["LAST_SENT_DATE"].notna()
    recent_mask = sent_mask & (pd.to_datetime(df["LAST_SENT_DATE"], errors="coerce") > cutoff)
    mask &= ~recent_mask

    eligible = df[mask]
    tier_counts = eligible["TIER"].value_counts().to_dict()

    # Priority order: VIP → HOT → WARM_A → WARM_B
    priority = ["VIP", "HOT", "WARM_A", "WARM_B"]
    selected = [t for t in priority if tier_counts.get(t, 0) > 0]

    print(f"[AUTO-TIER] Eligible leads per tier:")
    for t in priority:
        cnt = tier_counts.get(t, 0)
        marker = "✓" if t in selected else "✗"
        print(f"  {marker} {t}: {cnt}")

    return selected, tier_counts


def load_eligible_leads(
    tiers: list[str],
    cooldown_days: int,
    count: int,
) -> pd.DataFrame:
    """Load cnee_master_v2 and filter eligible leads."""
    df = pd.read_excel(CNEE_V2)

    # Filter: has email + action eligible
    mask = df["EMAIL"].notna() & df["EMAIL"].str.contains("@", na=False)
    mask &= df["ACTION"].isin(ELIGIBLE_ACTIONS)

    # Filter: tier
    if tiers:
        mask &= df["TIER"].isin(tiers)

    # Filter: cooldown (not sent in last N days)
    cutoff = datetime.now() - timedelta(days=cooldown_days)
    sent_mask = df["LAST_SENT_DATE"].notna()
    recent_mask = sent_mask & (pd.to_datetime(df["LAST_SENT_DATE"], errors="coerce") > cutoff)
    mask &= ~recent_mask

    # Filter: skip PARK tier always
    mask &= df["TIER"] != "PARK"

    eligible = df[mask].copy()

    # Dedupe by email
    eligible["_email_lower"] = eligible["EMAIL"].str.lower().str.strip()
    eligible = eligible.drop_duplicates(subset="_email_lower")

    # Sort by priority score desc, then tier rank
    tier_rank = {"VIP": 0, "HOT": 1, "WARM_A": 2, "WARM_B": 3, "COOL": 4}
    eligible["_tier_rank"] = eligible["TIER"].map(tier_rank).fillna(5)
    eligible = eligible.sort_values(
        ["_tier_rank", "PRIORITY_SCORE"],
        ascending=[True, False],
    )

    return eligible.head(count).drop(columns=["_email_lower", "_tier_rank"])


# ── Rate Query + Send ────────────────────────────────────────────────────────

def get_rate_preview(lead: dict, markup: float) -> dict | None:
    """Build rate preview locally from Parquet. No VPS dependency."""
    try:
        return build_email_for_lead(lead, markup)
    except Exception as e:
        return {"error": str(e)}


def send_via_outlook(
    to_email: str,
    subject: str,
    html_body: str,
    company: str = "",
) -> tuple[bool, str]:
    """Send email via local Outlook COM. Returns (success, message)."""
    try:
        import win32com.client
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)
        mail.To = to_email
        mail.Subject = subject
        mail.HTMLBody = html_body

        # Attach company profile PDF if exists
        if COMPANY_PDF.exists():
            mail.Attachments.Add(str(COMPANY_PDF))

        mail.Send()
        return True, "sent"
    except Exception as e:
        return False, str(e)


def log_send(
    log_path: Path,
    lead: dict,
    status: str,
    preview: dict | None,
    error: str = "",
):
    """Append send result to campaign log CSV."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = log_path.exists()
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "timestamp", "email", "company", "campaign_id", "tier",
                "status", "rates_found", "days_used", "error",
            ])
        writer.writerow([
            datetime.now().isoformat(timespec="seconds"),
            lead.get("EMAIL", ""),
            lead.get("COMPANY", ""),
            lead.get("CAMPAIGN_ID", ""),
            lead.get("TIER", ""),
            status,
            preview.get("row_count", 0) if preview else 0,
            preview.get("days_used", 0) if preview else 0,
            error,
        ])


# ── Report Generation ────────────────────────────────────────────────────────

def preview_emails(leads: pd.DataFrame, count: int, markup: float):
    """Render N sample emails, save HTML, open in browser for review."""
    import tempfile
    import webbrowser

    samples = leads.head(count)
    html_parts = [
        "<html><head><meta charset='utf-8'>",
        "<style>body{font-family:Arial;max-width:900px;margin:auto;padding:20px}",
        ".email-card{border:2px solid #333;margin:20px 0;padding:20px;border-radius:8px}",
        ".meta{background:#f0f0f0;padding:10px;margin-bottom:15px;border-radius:4px}",
        ".meta b{color:#333} .tier-badge{display:inline-block;padding:2px 8px;border-radius:4px;",
        "color:white;font-size:12px;margin-left:8px}",
        ".tier-VIP{background:#e74c3c} .tier-HOT{background:#e67e22}",
        ".tier-WARM_A{background:#f1c40f;color:#333} .tier-WARM_B{background:#3498db}",
        "</style></head><body>",
        f"<h1>Email Preview — {count} samples</h1>",
        f"<p>Markup: ${markup} | Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>",
        "<hr>",
    ]

    for i, (_, lead) in enumerate(samples.iterrows()):
        email = str(lead["EMAIL"]).strip()
        company = str(lead.get("COMPANY", "")).strip()
        tier = str(lead.get("TIER", "")).strip()
        campaign = str(lead.get("CAMPAIGN_ID", "")).strip()

        print(f"[PREVIEW {i+1}/{count}] Querying rates for {email}...")
        preview = get_rate_preview(lead, markup)

        if not preview or "error" in preview:
            err = preview.get("error", "no response") if preview else "no response"
            html_parts.append(
                f"<div class='email-card'>"
                f"<div class='meta'><b>#{i+1}</b> {email} ({company})"
                f"<span class='tier-badge tier-{tier}'>{tier}</span>"
                f" — Campaign: {campaign}</div>"
                f"<p style='color:red'>API Error: {err}</p></div>"
            )
            continue

        row_count = preview.get("row_count", 0)
        subject = preview.get("subject", "N/A")
        body_html = preview.get("html", "<p>No HTML body</p>")
        days_used = preview.get("days_used", 0)

        html_parts.append(
            f"<div class='email-card'>"
            f"<div class='meta'>"
            f"<b>#{i+1}</b> To: {email} ({company})"
            f"<span class='tier-badge tier-{tier}'>{tier}</span>"
            f" — Campaign: {campaign}<br>"
            f"<b>Subject:</b> {subject}<br>"
            f"<b>Rates:</b> {row_count} rows ({days_used}d data)"
            f"</div>"
            f"<div class='email-body'>{body_html}</div>"
            f"</div>"
        )

    html_parts.append("</body></html>")

    # Save and open
    preview_path = Path(tempfile.gettempdir()) / "goclaw-email-preview.html"
    preview_path.write_text("\n".join(html_parts), encoding="utf-8")
    webbrowser.open(str(preview_path))
    print(f"\n[PREVIEW] Opened in browser: {preview_path}")
    return preview_path


def generate_report(log_path: Path, args) -> str:
    """Generate markdown report from campaign log. Returns markdown string."""
    if not log_path.exists():
        return "# Campaign Report\n\nNo data — log file not found."

    df = pd.read_csv(log_path)
    total = len(df)
    sent = (df["status"] == "sent").sum()
    dry_run = (df["status"] == "DRY_RUN").sum()
    skipped = (df["status"] == "SKIP_NO_RATES").sum()
    blocked = (df["status"] == "SKIP_BLOCKED").sum()
    failed = (df["status"] == "FAILED").sum()

    mode = "🔍 DRY-RUN" if args.dry_run else "📧 LIVE SEND"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        f"# {mode} Campaign Report",
        f"**Date:** {ts} | **Tiers:** {args.tier} | **Count:** {args.count}",
        "",
        "## Summary",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total processed | {total} |",
    ]
    if args.dry_run:
        lines.append(f"| Would send | {dry_run} |")
    else:
        lines.append(f"| Sent | {sent} |")
    lines.extend([
        f"| Skipped (no rates) | {skipped} |",
        f"| Skipped (blocked) | {blocked} |",
        f"| Failed | {failed} |",
    ])

    # By campaign breakdown
    if total > 0:
        campaign_counts = df.groupby("campaign_id")["status"].value_counts().unstack(fill_value=0)
        lines.extend(["", "## By Campaign", ""])
        lines.append(f"| Campaign | Count | Status |")
        lines.append(f"|----------|-------|--------|")
        for campaign, row in campaign_counts.iterrows():
            dominant = row.idxmax()
            lines.append(f"| {campaign} | {row.sum()} | {dominant} |")

    # By tier breakdown
    if total > 0:
        tier_counts = df["tier"].value_counts()
        lines.extend(["", "## By Tier", ""])
        for tier, cnt in tier_counts.items():
            lines.append(f"- **{tier}**: {cnt}")

    # Errors
    errors = df[df["error"].notna() & (df["error"] != "")]
    if len(errors) > 0:
        lines.extend(["", "## Errors", ""])
        for _, row in errors.head(5).iterrows():
            lines.append(f"- {row['email']}: {row['error'][:100]}")

    return "\n".join(lines)


def publish_report(markdown: str, title: str) -> str | None:
    """Write markdown to file, publish as HTML, return URL."""
    report_path = PLANS_DIR / "_current-campaign-report.md"
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    report_path.write_text(markdown, encoding="utf-8")

    try:
        result = subprocess.run(
            [str(PUBLISH_BAT), "--title", title, "--input", str(report_path)],
            capture_output=True, text=True, timeout=30,
        )
        for line in result.stdout.splitlines():
            if line.startswith("PUBLISHED:"):
                return line.split("PUBLISHED:", 1)[1].strip()
    except Exception as e:
        print(f"[WARN] Publish failed: {e}")
    return None


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="GoClaw Email Campaign Orchestrator")
    parser.add_argument("--tier", default="HOT,WARM_A", help="Comma-separated tiers (default: HOT,WARM_A)")
    parser.add_argument("--auto-tier", action="store_true", help="Auto-evaluate tiers based on eligible counts")
    parser.add_argument("--count", type=int, default=100, help="Max leads per batch (default: 100, max: 500)")
    parser.add_argument("--batches", type=int, default=1, help="Number of batches (default: 1, max: 5)")
    parser.add_argument("--markup", type=float, default=DEFAULT_MARKUP, help="Rate markup USD (default: 20)")
    parser.add_argument("--cooldown", type=int, default=DEFAULT_COOLDOWN_DAYS, help="Cooldown days (default: 14)")
    parser.add_argument("--dry-run", action="store_true", help="Preview mode — do not send")
    parser.add_argument("--preview", type=int, default=0, metavar="N", help="Render N sample emails in browser for review")
    parser.add_argument("--report-only", action="store_true", help="Only generate report from last run")
    parser.add_argument("--skip-outlook-check", action="store_true", help="Skip Outlook pre-check (for testing)")
    parser.add_argument("--yes", action="store_true", help="Bỏ qua confirmation gate (dùng cho GoClaw cron sau khi đã confirm qua Telegram)")
    args = parser.parse_args()

    # Cap count and batches
    args.count = min(args.count, MAX_TOTAL)
    args.batches = min(args.batches, MAX_BATCHES)
    total_target = args.count * args.batches

    # Resolve tiers: auto-tier or manual
    if args.auto_tier:
        tiers, tier_counts = auto_select_tiers(args.cooldown)
        if not tiers:
            print("[AUTO-TIER] No eligible leads in any tier. Done.")
            send_telegram_alert("📭 Auto-campaign: 0 eligible leads across all tiers.")
            return 0
        args.tier = ",".join(tiers)
    else:
        tiers = [t.strip().upper() for t in args.tier.split(",") if t.strip()]

    # Log file for this run
    run_ts = datetime.now().strftime("%y%m%d-%H%M")
    CAMPAIGN_LOG.mkdir(parents=True, exist_ok=True)
    log_path = CAMPAIGN_LOG / f"run-{run_ts}.csv"

    # ── Report-only mode ─────────────────────────────────────────────────
    if args.report_only:
        # Find latest log
        logs = sorted(CAMPAIGN_LOG.glob("run-*.csv"), reverse=True)
        if not logs:
            print("No campaign logs found.")
            return 1
        report_md = generate_report(logs[0], args)
        url = publish_report(report_md, "Campaign Report")
        if url:
            send_telegram_alert(f"📊 Campaign Report: {url}")
            print(f"REPORT: {url}")
        else:
            print(report_md)
        return 0

    # ── Step 0: Pre-checks ───────────────────────────────────────────────

    print("=" * 60)
    print(f"  GoClaw Auto-Campaign — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    mode_str = "DRY-RUN" if args.dry_run else ("PREVIEW" if args.preview > 0 else "LIVE SEND")
    print(f"  Mode: {mode_str} | Auto-tier: {'ON' if args.auto_tier else 'OFF'}")
    print(f"  Tiers: {tiers} | Count: {args.count}×{args.batches} = {total_target} | Markup: ${args.markup}")
    print("=" * 60)

    # 0a. Outlook check
    if not args.skip_outlook_check and not args.dry_run:
        ok, msg = check_outlook()
        print(f"[CHECK] Outlook: {msg}")
        if not ok:
            alert = "⚠ Outlook tắt! Bật Outlook rồi gõ: chạy campaign"
            send_telegram_alert(alert)
            print(f"[STOP] {alert}")
            return 2

    # 0b. Parquet freshness
    fresh, msg, days = check_parquet_freshness()
    print(f"[CHECK] Parquet: {msg}")
    if not fresh:
        send_telegram_alert(f"⚠ {msg}")
        # Continue anyway — old rates still valid, just warn

    # ── Step 1: Load eligible leads ──────────────────────────────────────

    if not CNEE_V2.exists():
        print(f"[ERROR] cnee_master_v2.xlsx not found at {CNEE_V2}")
        send_telegram_alert(f"❌ Campaign failed: cnee_master_v2.xlsx not found")
        return 3

    leads = load_eligible_leads(tiers, args.cooldown, total_target)
    print(f"[LEADS] {len(leads)} eligible leads found (from {tiers})")
    print(f"[PLAN] {args.batches} batch(es) × {args.count} = {total_target} target")

    if len(leads) == 0:
        msg = f"📭 0 eligible leads for tiers {tiers} (cooldown {args.cooldown}d). Không có email nào cần gửi hôm nay."
        send_telegram_alert(msg)
        print(f"[DONE] {msg}")
        return 0

    # ── Step 1.5: Preview mode ──────────────────────────────────────────

    if args.preview > 0:
        preview_path = preview_emails(leads, args.preview, args.markup)
        answer = input("\n[PREVIEW] Proceed with campaign? (y/n): ").strip().lower()
        if answer != "y":
            print("[ABORT] Campaign cancelled by user after preview.")
            return 0
        print("[OK] Proceeding with campaign...\n")
        args.yes = True  # preview already confirmed — skip Step 1.6 gate

    # ── Step 1.6: Live send confirmation gate (BẮTBUỘC) ─────────────────

    if not args.dry_run and not args.yes:
        print()
        print("─" * 60)
        print(f"  ⚠  LIVE SEND — sắp gửi {len(leads)} emails THẬT")
        print(f"  Tiers: {tiers} | Batches: {args.batches} × {args.count}")
        print()
        # Show sample of first 3 leads
        for i, (_, lead) in enumerate(leads.head(3).iterrows()):
            print(f"  [{i+1}] {lead.get('EMAIL','')} — {str(lead.get('COMPANY',''))[:40]}")
        if len(leads) > 3:
            print(f"  ... và {len(leads)-3} leads khác")
        print("─" * 60)
        answer = input("\n  Gõ 'yes' để gửi, Enter để hủy: ").strip().lower()
        if answer != "yes":
            print("[ABORT] Cancelled. Dùng --dry-run để test trước.")
            return 0
        print("[OK] Confirmed. Starting live send...\n")

    # ── Step 2-4: Process leads in batches ───────────────────────────────

    sent_count = 0
    skip_count = 0
    fail_count = 0
    consecutive_fails = 0
    stopped = False

    for batch_num in range(args.batches):
        batch_start = batch_num * args.count
        batch_end = min(batch_start + args.count, len(leads))
        batch_leads = leads.iloc[batch_start:batch_end]

        if len(batch_leads) == 0:
            print(f"\n[BATCH {batch_num+1}] No more leads. Done.")
            break

        print(f"\n{'─'*60}")
        print(f"  BATCH {batch_num+1}/{args.batches} — {len(batch_leads)} leads (#{batch_start+1}-{batch_end})")
        print(f"{'─'*60}")

        for i, (_, lead) in enumerate(batch_leads.iterrows()):
            global_idx = batch_start + i
            email = str(lead["EMAIL"]).strip()
            company = str(lead.get("COMPANY", "")).strip()
            tier = str(lead.get("TIER", "")).strip()
            campaign = str(lead.get("CAMPAIGN_ID", "")).strip()

            print(f"\n[{global_idx+1}/{len(leads)}] {email} ({company}) [{tier}/{campaign}]")

            # Query rate preview
            preview = get_rate_preview(lead, args.markup)
            if not preview or "error" in preview:
                err = preview.get("error", "unknown") if preview else "no response"
                print(f"  ✗ API error: {err}")
                log_send(log_path, lead, "SKIP_API_ERROR", preview, err)
                skip_count += 1
                continue

            row_count = preview.get("row_count", 0)
            is_blocked = preview.get("is_blocked", False)
            days_used = preview.get("days_used", 0)

            if row_count == 0:
                print(f"  ✗ No rates found")
                log_send(log_path, lead, "SKIP_NO_RATES", preview)
                skip_count += 1
                continue

            if is_blocked:
                print(f"  ✗ Rates blocked (expired carriers)")
                log_send(log_path, lead, "SKIP_BLOCKED", preview)
                skip_count += 1
                continue

            print(f"  ✓ {row_count} rates ({days_used}d data)")

            # Dry-run: log but don't send
            if args.dry_run:
                print(f"  → DRY-RUN (would send)")
                log_send(log_path, lead, "DRY_RUN", preview)
                sent_count += 1
                consecutive_fails = 0
                continue

            # Real send via Outlook COM
            subject = preview.get("subject", f"Ocean Freight Rates // NELSON")
            html = preview.get("html", "")
            ok, msg = send_via_outlook(email, subject, html, company)

            if ok:
                print(f"  → SENT ✓")
                log_send(log_path, lead, "sent", preview)
                sent_count += 1
                consecutive_fails = 0
            else:
                print(f"  → FAILED: {msg}")
                log_send(log_path, lead, "FAILED", preview, msg)
                fail_count += 1
                consecutive_fails += 1

                # Circuit breaker: 3 consecutive failures → stop all
                if consecutive_fails >= 3:
                    alert = f"🔴 Circuit breaker: {consecutive_fails} consecutive failures. Campaign paused."
                    send_telegram_alert(alert)
                    print(f"[STOP] {alert}")
                    stopped = True
                    break

            # Jitter between sends
            delay = random.uniform(JITTER_MIN_SEC, JITTER_MAX_SEC)
            time.sleep(delay)

        if stopped:
            break

        # Pause between batches (except last)
        if batch_num + 1 < args.batches and batch_end < len(leads):
            print(f"\n[BATCH PAUSE] {BATCH_PAUSE_SEC}s before next batch...")
            time.sleep(BATCH_PAUSE_SEC)

    # ── Step 5-7: Report ─────────────────────────────────────────────────

    print(f"\n{'='*60}")
    mode_label = "DRY-RUN" if args.dry_run else "LIVE"
    print(f"  {mode_label} COMPLETE: {sent_count} sent, {skip_count} skipped, {fail_count} failed")
    print(f"{'='*60}")

    # ── Dashboard: open in browser automatically
    try:
        _open_dashboard(
            log_path,
            is_dry_run=args.dry_run,
            tiers=args.tier,
            count=total_target,
        )
    except Exception as _dash_err:
        print(f"[WARN] Dashboard open failed: {_dash_err}")

    # ── Report & Telegram (best-effort, non-blocking)
    report_md = generate_report(log_path, args)
    title = f"{'DryRun' if args.dry_run else 'Campaign'} {datetime.now().strftime('%d/%m')}"
    url = publish_report(report_md, title)
    emoji = "🔍" if args.dry_run else "✅"
    summary = (
        f"{emoji} Campaign {'dry-run' if args.dry_run else 'done'}: "
        f"{sent_count}/{len(leads)} sent, {skip_count} skipped"
    )
    if url:
        summary += f" | {url}"
    send_telegram_alert(summary)

    return 0


if __name__ == "__main__":
    sys.exit(main())
