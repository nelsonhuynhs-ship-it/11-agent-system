# bounce_handler.py — Scan Outlook NDR, classify bounces, update cnee_master_v2.xlsx
import re
import logging
from pathlib import Path
import pandas as pd

log = logging.getLogger("bounce_handler")
DATA_DIR = Path(__file__).parent.parent / "data"
MASTER_V2 = DATA_DIR / "cnee_master_v2.xlsx"

HARD_KEYWORDS = [
    "does not exist", "unknown user", "invalid address",
    "no such user", "rejected", "user unknown", "address rejected",
    "not found", "invalid recipient",
]
SOFT_KEYWORDS = [
    "mailbox full", "temporarily", "try again later",
    "quota exceeded", "over quota", "service unavailable",
    "too many connections",
]

NDR_SUBJECTS = ["undeliverable", "delivery status notification", "mail delivery failed",
                "returned mail", "failure notice", "delivery failure"]

EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}")


def classify_bounce(email: str, body: str) -> str:
    body_lower = body.lower()
    for kw in HARD_KEYWORDS:
        if kw in body_lower:
            return "HARD"
    for kw in SOFT_KEYWORDS:
        if kw in body_lower:
            return "SOFT"
    # Default: treat unknown NDR as HARD to be safe
    return "HARD"


def _extract_email_from_ndr(subject: str, body: str) -> str | None:
    """Try to extract original recipient from NDR body."""
    # Pattern 1: "Your message to X@Y.Z could not be delivered"
    m = re.search(r"(?:to|for|recipient)[:\s]+([^\s<>]+@[^\s<>]+)", body, re.I)
    if m:
        return m.group(1).strip().lower()
    # Pattern 2: "Final-Recipient: rfc822; user@domain"
    m = re.search(r"Final-Recipient[:\s]+rfc822;\s*([^\s]+)", body, re.I)
    if m:
        return m.group(1).strip().lower()
    # Pattern 3: any email in body that isn't from our domain
    candidates = EMAIL_RE.findall(body)
    for c in candidates:
        if not any(skip in c for skip in ["mailer-daemon", "postmaster", "noreply"]):
            return c.strip().lower()
    return None


def scan_bounces() -> list[dict]:
    """Connect to Outlook Inbox, find NDR messages, return list of {email, bounce_type}."""
    try:
        import win32com.client
    except ImportError:
        log.error("win32com not available — cannot scan Outlook")
        return []

    bounces = []
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        ns = outlook.GetNamespace("MAPI")
        inbox = ns.GetDefaultFolder(6)  # 6 = olFolderInbox
        messages = inbox.Items
        messages.Sort("[ReceivedTime]", True)

        for msg in messages:
            try:
                subj = str(msg.Subject or "").lower()
                if not any(kw in subj for kw in NDR_SUBJECTS):
                    continue
                body = str(msg.Body or "")
                email = _extract_email_from_ndr(subj, body)
                if not email:
                    continue
                bounce_type = classify_bounce(email, body)
                bounces.append({"email": email, "bounce_type": bounce_type})
                log.info(f"NDR found: {email} → {bounce_type}")
            except Exception as e:
                log.debug(f"Skip message: {e}")
    except Exception as e:
        log.error(f"Outlook scan failed: {e}")

    log.info(f"scan_bounces: found {len(bounces)} NDRs")
    return bounces


def update_cnee_master(bounces: list[dict]) -> dict:
    """Update cnee_master_v2.xlsx with bounce info. Returns stats dict."""
    if not MASTER_V2.exists():
        log.error(f"cnee_master_v2.xlsx not found — run data_migrator first")
        return {"error": "cnee_master_v2.xlsx not found"}

    df = pd.read_excel(MASTER_V2)
    df.columns = df.columns.str.strip().str.upper()

    # Ensure columns exist
    for col, default in [("BOUNCE_COUNT", 0), ("EMAIL_STATUS", "VALID")]:
        if col not in df.columns:
            df[col] = default

    stats = {"updated": 0, "hard": 0, "soft": 0}
    email_col = df["EMAIL"].astype(str).str.lower().str.strip()

    for b in bounces:
        email = b["email"].lower().strip()
        mask = email_col == email
        if not mask.any():
            continue

        df.loc[mask, "BOUNCE_COUNT"] = df.loc[mask, "BOUNCE_COUNT"].fillna(0).astype(int) + 1

        if b["bounce_type"] == "HARD":
            df.loc[mask, "EMAIL_STATUS"] = "HARD_BOUNCE"
            stats["hard"] += 1
        else:
            count = int(df.loc[mask, "BOUNCE_COUNT"].iloc[0])
            if count >= 3:
                df.loc[mask, "EMAIL_STATUS"] = "SOFT_SUPPRESSED"
            else:
                df.loc[mask, "EMAIL_STATUS"] = "SOFT_BOUNCE"
            stats["soft"] += 1

        stats["updated"] += 1

    df.to_excel(MASTER_V2, index=False)
    log.info(f"update_cnee_master: {stats}")
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bounces = scan_bounces()
    if bounces:
        result = update_cnee_master(bounces)
        print(f"Updated: {result}")
    else:
        print("No bounces found")
