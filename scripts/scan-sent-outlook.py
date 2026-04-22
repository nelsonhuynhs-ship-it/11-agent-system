"""scan-sent-outlook.py — Scan Outlook Sent Items for spam/over-send detection.

Usage:
    python scripts/scan-sent-outlook.py [--days 14] [--threshold 3]
                                         [--update-master] [--block-threshold 5]

Output:
    - Console: Top 30 worst recipients + summary
    - CSV:  D:/OneDrive/NelsonData/email/backups/sent_audit_YYYYMMDD_HHMM.csv
    - JSON: D:/OneDrive/NelsonData/email/backups/sent_audit_latest.json
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sent-scan")

# ── Paths ─────────────────────────────────────────────────────────
_ONEDRIVE_EMAIL = Path("D:/OneDrive/NelsonData/email")
_BACKUP_DIR     = _ONEDRIVE_EMAIL / "backups"
_MASTER_V6      = _ONEDRIVE_EMAIL / "contact_unified_v6.xlsx"     # v6 primary
_MASTER_V2      = _ONEDRIVE_EMAIL / "cnee_master_v2_final.xlsx"   # v5 fallback
_ENGINE_TEST    = Path(__file__).parent.parent
_EXCLUDED_FILE  = _ENGINE_TEST / "email_engine" / "data" / "excluded_emails.json"

# Resolve master target — prefer v6
_MASTER_TARGET = _MASTER_V6 if _MASTER_V6.exists() else _MASTER_V2

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


# ── Outlook helpers ───────────────────────────────────────────────

def _get_outlook():
    """Return Outlook Application COM object, starting Outlook if needed."""
    try:
        import win32com.client
        return win32com.client.Dispatch("Outlook.Application")
    except Exception as exc:
        log.error(f"Cannot connect to Outlook COM: {exc}")
        sys.exit(1)


def _get_sent_folder(outlook):
    """Return Sent Items MAPIFolder, trying multiple locale names + fallback index."""
    ns = outlook.GetNamespace("MAPI")
    # Try by well-known folder constant first (locale-independent)
    try:
        return ns.GetDefaultFolder(5)  # olFolderSentMail = 5
    except Exception:
        pass
    # Fallback: search by name
    for name in ("Sent Items", "Mục đã gửi", "Sent", "Enviados"):
        try:
            return ns.Folders.Item(1).Folders[name]
        except Exception:
            pass
    log.error("Cannot find Sent Items folder — tried default + locale names")
    sys.exit(1)


def _extract_emails(to_field: str) -> list[str]:
    """Extract individual email addresses from To field.

    Handles:
    - 'Name <email@domain.com>; Name2 <email2@domain.com>'
    - 'email@domain.com, email2@domain.com'
    - Distribution lists (skipped — resolved to display name only)
    """
    if not to_field:
        return []
    return _EMAIL_RE.findall(to_field)


# ── Core scan logic ───────────────────────────────────────────────

def scan_sent(days: int = 14) -> dict[str, dict]:
    """Scan Sent Items last `days` days → {email: {count, first_sent, last_sent, subjects}}."""
    log.info(f"Starting Outlook Sent Items scan — last {days} days")
    outlook = _get_outlook()
    folder  = _get_sent_folder(outlook)

    cutoff   = datetime.now() - timedelta(days=days)
    agg: dict[str, dict] = defaultdict(lambda: {
        "count": 0,
        "first_sent": None,
        "last_sent": None,
        "subjects": [],
    })

    total_items = folder.Items.Count
    log.info(f"Sent folder has {total_items} total items — filtering last {days}d")

    scanned = 0
    for item in folder.Items:
        try:
            sent_on = item.SentOn
            # pywintypes.datetime may be timezone-aware — always normalise to
            # naive local datetime so comparison with cutoff (naive) works.
            sent_dt = datetime(
                sent_on.year, sent_on.month, sent_on.day,
                sent_on.hour, sent_on.minute, sent_on.second,
            )
            if sent_dt < cutoff:
                continue

            to_str = getattr(item, "To", "") or ""
            subj   = getattr(item, "Subject", "") or ""
            emails = _extract_emails(to_str)

            for em in emails:
                em_lc = em.lower().strip()
                rec   = agg[em_lc]
                rec["count"] += 1
                if rec["first_sent"] is None or sent_dt < rec["first_sent"]:
                    rec["first_sent"] = sent_dt
                if rec["last_sent"] is None or sent_dt > rec["last_sent"]:
                    rec["last_sent"] = sent_dt
                if subj and subj not in rec["subjects"]:
                    rec["subjects"].append(subj)

            scanned += 1
        except Exception as exc:
            log.debug(f"Skipped item: {exc}")
            continue

    log.info(f"Scanned {scanned} sent emails → {len(agg)} unique recipients")
    return dict(agg)


# ── Serialisation helpers ─────────────────────────────────────────

def _fmt_dt(dt) -> str:
    if dt is None:
        return ""
    try:
        return datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(dt)


def _to_rows(agg: dict, threshold: int = 1) -> list[dict]:
    rows = []
    for em, rec in agg.items():
        if rec["count"] < threshold:
            continue
        domain = em.split("@", 1)[1] if "@" in em else ""
        rows.append({
            "email":         em,
            "count":         rec["count"],
            "first_sent":    _fmt_dt(rec["first_sent"]),
            "last_sent":     _fmt_dt(rec["last_sent"]),
            "domain":        domain,
            "subjects_sample": " | ".join(rec["subjects"][:3]),
        })
    rows.sort(key=lambda r: r["count"], reverse=True)
    return rows


# ── Output writers ────────────────────────────────────────────────

def write_csv(rows: list[dict], backup_dir: Path) -> Path:
    import csv
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts      = datetime.now().strftime("%Y%m%d_%H%M")
    out     = backup_dir / f"sent_audit_{ts}.csv"
    fields  = ["email", "count", "first_sent", "last_sent", "domain", "subjects_sample"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    log.info(f"CSV written: {out}")
    return out


def write_json_summary(rows: list[dict], backup_dir: Path, days: int, threshold: int) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    out = backup_dir / "sent_audit_latest.json"
    summary = {
        "generated_at":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "days_scanned":    days,
        "threshold":       threshold,
        "total_recipients": len(rows),
        "top30":           rows[:30],
    }
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"JSON summary: {out}")
    return out


# ── --update-master ───────────────────────────────────────────────

def update_master(rows: list[dict]) -> int:
    """Update SEND_COUNT + LAST_SENT_DATE in contact_unified_v6.xlsx (v6 primary).

    Falls back to cnee_master_v2_final.xlsx if v6 not present.
    Uses xlsx_write_lock to prevent concurrent write corruption.
    """
    # Re-resolve at call time (v6 may have appeared since startup)
    master_path = _MASTER_V6 if _MASTER_V6.exists() else _MASTER_V2
    if not master_path.exists():
        log.warning(f"Master not found at {master_path} — skipping update")
        return 0

    try:
        import shutil
        import pandas as pd
        from pathlib import Path as _Path

        sys.path.insert(0, str(_ENGINE_TEST))
        from email_engine.core.xlsx_lock import xlsx_write_lock

        # Determine sheet to read/write (v6 has CNEE sheet, v5 has no sheet)
        is_v6 = master_path.name == "contact_unified_v6.xlsx"
        sheet_name = "CNEE" if is_v6 else None

        with xlsx_write_lock(master_path):
            if sheet_name:
                try:
                    df = pd.read_excel(master_path, sheet_name=sheet_name)
                except Exception:
                    df = pd.read_excel(master_path)
            else:
                df = pd.read_excel(master_path)

            df.columns = df.columns.str.strip().str.upper()
            email_col = "EMAIL" if "EMAIL" in df.columns else "CNEE_EMAIL"
            if email_col not in df.columns:
                log.warning("No EMAIL/CNEE_EMAIL column in master — skipping update")
                return 0

            lookup = {r["email"]: r for r in rows}
            updated = 0
            for idx, row in df.iterrows():
                em = str(row.get(email_col, "")).lower().strip()
                if em in lookup:
                    rec = lookup[em]
                    if "SEND_COUNT" in df.columns:
                        df.at[idx, "SEND_COUNT"] = rec["count"]
                    if "LAST_SENT_DATE" in df.columns:
                        df.at[idx, "LAST_SENT_DATE"] = rec["last_sent"]
                    updated += 1

            # Backup before save
            ts  = datetime.now().strftime("%Y%m%d_%H%M")
            bak_name = f"{master_path.stem}.backup_{ts}.xlsx"
            bak = master_path.parent / bak_name
            shutil.copy2(master_path, bak)

            if is_v6:
                # Preserve SHIPPER sheet when writing back
                try:
                    df_shipper = pd.read_excel(master_path, sheet_name="SHIPPER")
                except Exception:
                    df_shipper = pd.DataFrame()
                tmp = master_path.with_suffix(".tmp.xlsx")
                with pd.ExcelWriter(tmp, engine="openpyxl") as writer:
                    df.to_excel(writer, sheet_name="CNEE", index=False)
                    if not df_shipper.empty:
                        df_shipper.to_excel(writer, sheet_name="SHIPPER", index=False)
                tmp.replace(master_path)
            else:
                df.to_excel(master_path, index=False)

        log.info(f"Master updated: {updated} rows  (backup: {bak.name})  target={master_path.name}")
        return updated
    except Exception as exc:
        log.error(f"update_master failed: {exc}")
        return 0


# ── --block-threshold (auto-add to excluded_emails.json) ─────────

def auto_block(rows: list[dict], threshold: int) -> list[str]:
    """Add emails with count >= threshold to excluded_emails.json."""
    to_block = [r for r in rows if r["count"] >= threshold]
    if not to_block:
        log.info("No emails meet block threshold — nothing added")
        return []

    try:
        if _EXCLUDED_FILE.exists():
            data = json.loads(_EXCLUDED_FILE.read_text(encoding="utf-8"))
        else:
            data = {"excluded": {}}
        data.setdefault("excluded", {})

        blocked = []
        for rec in to_block:
            em = rec["email"]
            if em not in data["excluded"]:
                data["excluded"][em] = {
                    "reason":    f"auto-blocked: sent {rec['count']}x in scan",
                    "count":     rec["count"],
                    "last_sent": rec["last_sent"],
                    "added_at":  datetime.now().strftime("%Y-%m-%d"),
                    "added_by":  "scan-sent-outlook",
                }
                blocked.append(em)

        _EXCLUDED_FILE.parent.mkdir(parents=True, exist_ok=True)
        _EXCLUDED_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log.info(f"Auto-blocked {len(blocked)} emails → {_EXCLUDED_FILE}")
        return blocked
    except Exception as exc:
        log.error(f"auto_block failed: {exc}")
        return []


# ── Console report ────────────────────────────────────────────────

def print_report(rows: list[dict], top: int = 30, threshold: int = 3):
    print("\n" + "=" * 60)
    print(f"  SENT ITEMS SCAN — Top {top} over-sent recipients")
    print("=" * 60)
    flagged = [r for r in rows if r["count"] >= threshold]
    print(f"  Total unique recipients:  {len(rows)}")
    print(f"  Flagged (>= {threshold}x):          {len(flagged)}")
    print()
    header = f"{'#':>3}  {'COUNT':>5}  {'EMAIL':<35}  {'LAST SENT':<17}"
    print(header)
    print("-" * len(header))
    for i, r in enumerate(rows[:top], 1):
        flag = " *** SPAM" if r["count"] >= 5 else (" !" if r["count"] >= 3 else "")
        print(f"{i:>3}  {r['count']:>5}  {r['email']:<35}  {r['last_sent']:<17}{flag}")
    print()


# ── Entry point ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scan Outlook Sent Items")
    parser.add_argument("--days",            type=int, default=14, help="Days to look back (default 14)")
    parser.add_argument("--threshold",       type=int, default=3,  help="Min send count to flag (default 3)")
    parser.add_argument("--update-master",   action="store_true",  help="Update SEND_COUNT in contact_unified_v6.xlsx (v5 fallback)")
    parser.add_argument("--block-threshold", type=int, default=0,  help="Auto-add to excluded_emails.json if sent >= N (0=disabled)")
    args = parser.parse_args()

    agg  = scan_sent(days=args.days)
    rows = _to_rows(agg, threshold=1)

    csv_path  = write_csv(rows, _BACKUP_DIR)
    json_path = write_json_summary(rows, _BACKUP_DIR, days=args.days, threshold=args.threshold)

    print_report(rows, top=30, threshold=args.threshold)

    if args.update_master:
        n = update_master(rows)
        print(f"  Master updated: {n} rows")

    if args.block_threshold > 0:
        blocked = auto_block(rows, threshold=args.block_threshold)
        if blocked:
            print(f"\n  AUTO-BLOCKED ({args.block_threshold}+ sends):")
            for em in blocked:
                print(f"    - {em}")

    print(f"\n  CSV:  {csv_path}")
    print(f"  JSON: {json_path}")
    print()
    return rows


if __name__ == "__main__":
    main()
