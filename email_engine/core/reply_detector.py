"""
reply_detector.py — Scan Outlook Inbox for replies from CNEE contacts
======================================================================
Uses win32com.client directly (same pattern as web_server.py _do_send).
Gracefully returns empty if Outlook unavailable.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

_engine_dir = Path(__file__).parent.parent  # email_engine/
CNEE_V2   = _engine_dir / "data" / "cnee_master_v2.xlsx"
EMAIL_LOG = _engine_dir / "logs" / "email_log.csv"
REPLY_LOG = _engine_dir / "logs" / "reply_log.csv"


def _get_sent_subjects() -> set[str]:
    """Load subjects from email_log.csv for RE: matching."""
    if not EMAIL_LOG.exists():
        return set()
    try:
        df = pd.read_csv(EMAIL_LOG, usecols=["subject"])
        return set(df["subject"].dropna().str.strip().str.lower())
    except Exception:
        return set()


def _get_known_emails() -> set[str]:
    """Load email addresses from cnee_master_v2 for sender matching."""
    if not CNEE_V2.exists():
        return set()
    try:
        df = pd.read_excel(CNEE_V2, usecols=["EMAIL"])
        return set(df["EMAIL"].dropna().astype(str).str.lower().str.strip())
    except Exception:
        return set()


def scan_replies(hours_back: int = 24) -> list[dict]:
    """Scan Outlook Inbox for replies. Returns list of reply dicts."""
    try:
        import win32com.client
        outlook = win32com.client.Dispatch("Outlook.Application")
        ns = outlook.GetNamespace("MAPI")
        inbox = ns.GetDefaultFolder(6)  # olFolderInbox
    except Exception as e:
        return []  # Outlook not available — graceful

    sent_subjects = _get_sent_subjects()
    known_emails  = _get_known_emails()
    cutoff = datetime.now() - timedelta(hours=hours_back)

    replies = []
    try:
        messages = inbox.Items
        messages.Sort("[ReceivedTime]", True)  # newest first
        for msg in messages:
            try:
                received = msg.ReceivedTime
                # win32com returns a pywintypes.datetime — convert
                if hasattr(received, "replace"):
                    received_dt = datetime(
                        received.year, received.month, received.day,
                        received.hour, received.minute, received.second
                    )
                else:
                    continue
                if received_dt < cutoff:
                    break  # sorted desc, so all subsequent are older

                sender = str(msg.SenderEmailAddress or "").lower().strip()
                subject = str(msg.Subject or "").strip()
                subject_lower = subject.lower()

                # Match: RE: + known subject OR sender in cnee list
                is_reply = subject_lower.startswith("re:")
                subject_match = is_reply and any(
                    s in subject_lower for s in sent_subjects
                )
                sender_match = sender in known_emails

                if subject_match or sender_match:
                    body = str(msg.Body or "")[:500]
                    replies.append({
                        "email":       sender,
                        "subject":     subject,
                        "received_at": received_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "body_preview": body.strip(),
                    })
            except Exception:
                continue
    except Exception:
        pass

    return replies


def _log_reply(email: str, subject: str, campaign_id: str, received_at: str):
    exists = REPLY_LOG.exists()
    with open(REPLY_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["timestamp", "email", "subject", "campaign_id", "received_at"])
        w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    email, subject, campaign_id, received_at])


def process_replies(replies: list[dict]) -> int:
    """Update cnee_master_v2 for each reply. Returns count of new replies processed."""
    if not replies or not CNEE_V2.exists():
        return 0

    df = pd.read_excel(CNEE_V2)
    df.columns = df.columns.str.strip().str.upper()
    df["_EMAIL_LOWER"] = df["EMAIL"].astype(str).str.lower().str.strip()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    count = 0

    for reply in replies:
        sender = reply["email"].lower().strip()
        mask = df["_EMAIL_LOWER"] == sender
        if not mask.any():
            continue

        # Skip if already marked replied
        current_status = df.loc[mask, "SEQ_STATUS"].iloc[0] if "SEQ_STATUS" in df.columns else ""
        if str(current_status).upper() == "REPLIED":
            continue

        # Update master
        if "SEQ_STATUS" in df.columns:
            df.loc[mask, "SEQ_STATUS"] = "REPLIED"
        if "LAST_REPLY" in df.columns:
            df.loc[mask, "LAST_REPLY"] = now_str
        if "LEAD_SCORE" in df.columns:
            current_score = pd.to_numeric(df.loc[mask, "LEAD_SCORE"].iloc[0], errors="coerce") or 0
            df.loc[mask, "LEAD_SCORE"] = min(100, current_score + 30)

        # Get campaign_id for log
        campaign_id = str(df.loc[mask, "CAMPAIGN_ID"].iloc[0]) if "CAMPAIGN_ID" in df.columns else ""
        _log_reply(sender, reply["subject"], campaign_id, reply["received_at"])
        count += 1

    df.drop(columns=["_EMAIL_LOWER"], inplace=True)
    if count > 0:
        df.to_excel(CNEE_V2, index=False)

    return count


def get_hot_leads(days: int = 7) -> list[dict]:
    """Return contacts who replied within last N days, sorted by LEAD_SCORE desc."""
    if not CNEE_V2.exists():
        return []
    df = pd.read_excel(CNEE_V2)
    df.columns = df.columns.str.strip().str.upper()

    if "LAST_REPLY" not in df.columns:
        return []

    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
    df["LAST_REPLY_DT"] = pd.to_datetime(df["LAST_REPLY"], errors="coerce")
    hot = df[df["LAST_REPLY_DT"] >= cutoff].copy()

    if "LEAD_SCORE" in hot.columns:
        hot = hot.sort_values("LEAD_SCORE", ascending=False)

    results = []
    for _, row in hot.iterrows():
        results.append({
            "email":       str(row.get("EMAIL", "")),
            "company":     str(row.get("COMPANY", "")),
            "campaign_id": str(row.get("CAMPAIGN_ID", "")),
            "lead_score":  int(pd.to_numeric(row.get("LEAD_SCORE", 0), errors="coerce") or 0),
            "last_reply":  str(row.get("LAST_REPLY", "")),
        })
    return results
