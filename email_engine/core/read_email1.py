"""
read_email1.py — Email Signal Scanner & Data Cleaner
=====================================================
Quét Inbox Outlook, phân loại 5 loại tín hiệu email, ghi vào
email_knowledge.csv và write-back xoá email hỏng khỏi data.xlsx.

Signal types
------------
hard_bounce    → user unknown / no such recipient / address not found
soft_bounce    → mailbox full / quota / deferred (giữ lại, tạm thời)
policy_reject  → blocked / DMARC / SPF
auto_reply     → out of office / automatic reply
human_reply    → customer phản hồi thật sự

DRY_RUN (default: True)
    True  → chỉ log, KHÔNG sửa data.xlsx (an toàn để test)
    False → write-back thật, backup tự động trước khi xoá
"""

from __future__ import annotations

import re
import shutil
import csv
import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import win32com.client

# =========================================================
# CONFIG — chỉ thay đổi ở đây, không đụng code bên dưới
# =========================================================
DRY_RUN              = False   # LIVE MODE — write-back to data.xlsx enabled
AUTO_CLEAN_HARD_BOUNCE = True  # xoá hard_bounce trong data.xlsx (chỉ có tác dụng khi DRY_RUN=False)
INBOX_SCAN_LIMIT     = 500     # số email quét trong Inbox

# =========================================================
# PATHS
# =========================================================
BASE_DIR       = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent
LOG_DIR        = PROJECT_ROOT / "logs"
BACKUP_DIR     = PROJECT_ROOT / "backup"
DATA_FILE      = PROJECT_ROOT / "data.xlsx"
EMAIL_LOG_FILE = PROJECT_ROOT / "logs"  / "email_log.csv"
KNOWLEDGE_FILE = PROJECT_ROOT / "logs"  / "email_knowledge.csv"

LOG_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)

# PropertyAccessor tag để lấy SMTP thật từ Exchange (tránh lỗi X500)
PR_SMTP_ADDRESS = "http://schemas.microsoft.com/mapi/proptag/0x39FE001E"

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    level   = logging.INFO,
    format  = "[%(asctime)s] %(levelname)-8s %(message)s",
    datefmt = "%H:%M:%S",
    handlers= [logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# =========================================================
# KEYWORD LISTS
# =========================================================
HARD_BOUNCE_KEYWORDS = [
    "user unknown",
    "no such user",
    "no such recipient",
    "address not found",
    "address rejected",
    "mailbox unavailable",
    "does not exist",
    "invalid recipient",
    "invalid address",
    "account does not exist",
    "550",  # SMTP 550 = permanent failure
    "551",
    "553",
    "554",
]

SOFT_BOUNCE_KEYWORDS = [
    "mailbox full",
    "quota exceeded",
    "over quota",
    "temporarily unavailable",
    "try again later",
    "deferred",
    "452",  # SMTP 452 = insufficient storage
]

POLICY_KEYWORDS = [
    "blocked",
    "rejected by policy",
    "policy violation",
    "dmarc",
    "spf",
    "dkim",
    "blacklisted",
    "550-5.7",
    "mx block",
]

SPAM_KEYWORDS = [
    "spam",
    "blacklist",
    "reputation",
    "junk",
]

# Subject-level bounce detection (mailer-daemon emails)
BOUNCE_SUBJECT_KEYWORDS = [
    "undeliverable",
    "delivery status notification",
    "delivery failure",
    "returned mail",
    "mail delivery failed",
    "failure notice",
    "non-delivery report",
    "non-delivery receipt",
]

AUTO_REPLY_SUBJECT_KEYWORDS = [
    "out of office",
    "automatic reply",
    "auto reply",
    "auto-reply",
    "autoreply",
]

AUTO_REPLY_BODY_KEYWORDS = [
    "out of office",
    "automatic reply",
    "auto reply",
    "away from the office",
    "currently away",
    "limited access to email",
    "will return",
    "on leave",
    "on vacation",
    "on annual leave",
]

SYSTEM_SENDERS = [
    "mailer-daemon",
    "postmaster",
    "no-reply",
    "noreply",
    "donotreply",
    "do-not-reply",
    "maildelivery",
    "mail-delivery",
]

# Infra domains — không phải customer email thật
INFRA_DOMAINS = [
    "prod.outlook.com",
    "mail.protection.outlook.com",
    "apcprd",
    "eurprd",
    "namprd",
    "pphosted.com",
    "mimecast",
    "barracuda",
]

# =========================================================
# REGEX
# =========================================================
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
SMTP_CODE_REGEX = re.compile(r"\b(5\d{2}|4\d{2})\b")

# =========================================================
# UTIL
# =========================================================
def extract_emails(text: str) -> list[str]:
    if not isinstance(text, str):
        return []
    return list(set(EMAIL_REGEX.findall(text.lower())))

def extract_domain(email: str) -> str:
    return email.split("@")[1].lower() if "@" in email else ""

def is_system_sender(sender: str) -> bool:
    return any(k in sender.lower() for k in SYSTEM_SENDERS)

def is_infra_email(email: str) -> bool:
    domain = extract_domain(email)
    return any(d in domain for d in INFRA_DOMAINS)

# =========================================================
# OOO BODY PARSER — Extract contact / title from auto-reply
# =========================================================

# Inline patterns: "please contact John Smith at ..." / "reach out to Mary"
_CONTACT_NAME_PATTERNS = [
    re.compile(r"(?:please\s+)?contact\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})", re.I),
    re.compile(r"(?:please\s+)?reach\s+(?:out\s+to\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})", re.I),
    re.compile(r"speak\s+(?:with|to)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})", re.I),
    re.compile(r"(?:my\s+)?colleague[,\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})", re.I),
    re.compile(r"(?:forwarded?\s+to|handled?\s+by|covered?\s+by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})", re.I),
    re.compile(r"(?:alternate|alternative)\s+contact[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})", re.I),
    re.compile(r"(?:kindly\s+)?(?:contact|email)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s+(?:at|on|via)", re.I),
    re.compile(r"name\s*[:\-]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})", re.I),
]

# Job title keywords — most specific first to avoid false positives from "manager" in body text
_TITLE_KEYWORDS = [
    "chief executive officer", "chief operating officer", "chief financial officer",
    "chief logistics officer", "chief supply chain officer",
    "vp of logistics", "vp of operations", "vp of sales", "vp, logistics",
    "vice president",
    "general manager", "country manager", "branch manager", "regional manager",
    "sales manager", "logistics manager", "import manager", "export manager",
    "purchasing manager", "procurement manager", "traffic manager",
    "operations manager", "supply chain manager", "account manager",
    "marketing manager", "business development manager",
    "logistics coordinator", "import coordinator", "export coordinator",
    "freight forwarder", "customs broker", "trade specialist",
    "purchasing agent", "procurement specialist",
    "sales representative", "sales executive", "business development executive",
    "import specialist", "export specialist", "supply chain specialist",
    "ceo", "coo", "cfo", "cto", "cpo",
    "director of logistics", "director of operations", "director of sales",
    "director of supply chain", "director of purchasing",
    "manager", "director", "coordinator", "specialist",
    "supervisor", "analyst", "officer", "assistant",
]

# Explicit label patterns: "Position: Sales Manager" / "Title: ..."
_TITLE_LABEL_RE = re.compile(
    r"(?:title|position|role|designation|job\s*title)\s*[:\-]\s*([^\n]{4,80})",
    re.I,
)

# A "name-like" line: 2–4 words, each starting with a capital, no digits, not too long
_NAME_LINE_RE = re.compile(
    r"^([A-Z][a-zA-Z'-]{1,20}(?:\s+[A-Z][a-zA-Z'-]{1,20}){1,3})$"
)

# Generic words that appear in OOO bodies but are NOT names
_NAME_BLACKLIST = {
    "out", "office", "away", "currently", "return", "urgent",
    "assistance", "contact", "please", "team", "sales", "logistics",
    "company", "regards", "sincerely", "thank", "best", "kind",
    "hello", "dear", "hi", "from", "sent", "with", "will",
    "have", "apologies", "inconvenience",
    "below", "person", "someone", "anyone", "above", "following",
    "note", "message", "email", "mail", "reply",
}


def _is_name_line(line: str) -> bool:
    """Return True if the line looks like a person's name (2–4 proper words)."""
    stripped = line.strip()
    m = _NAME_LINE_RE.match(stripped)
    if not m:
        return False
    words = stripped.split()
    # All words must be proper-cased and not in blacklist
    for w in words:
        if w.lower().rstrip(".,") in _NAME_BLACKLIST:
            return False
    return True


def _is_title_line(line: str) -> str:
    """Return the title string if the line contains a job title keyword, else ''."""
    line_l = line.lower().strip()
    for kw in _TITLE_KEYWORDS:
        if kw in line_l:
            candidate = line.strip().lstrip(",-|: ").rstrip(".,;")
            if 4 <= len(candidate) <= 100:
                return candidate
    return ""


def extract_ooo_contact(body: str, original_email: str) -> dict:
    """
    Parse the full body of an OOO / auto-reply email to extract:
      - replacement_email : alternative contact email
      - contact_name      : name of the person to contact instead
      - job_title         : their job title / designation

    Strategy (two-pass):
    --------------------
    Pass 1 — Anchor-around-email:
        For every email address found in the body (that is not original / infra),
        inspect the ±5 lines around it to find a name line and a title line.
        This handles typical multi-line OOO blocks:
            John Smith          <- name line
            Sales Manager       <- title line
            john@company.com    <- email line (anchor)

    Pass 2 — Inline sentence patterns:
        "please contact Mary Lee at mary@company.com"
        "reach out to Tom Chen, Import Manager"
        "Name: John Smith" / "Title: Logistics Manager"
    """
    result = {"replacement_email": "", "contact_name": "", "job_title": ""}
    if not isinstance(body, str) or not body.strip():
        return result

    orig_domain = extract_domain(original_email)

    # Split into non-empty lines for contextual scanning
    lines = body.splitlines()
    lines_lower = [l.lower() for l in lines]

    # --- Collect all emails from body ---
    all_emails_in_body = extract_emails(body)

    # Candidate replacement emails: not original, not infra
    candidates = [
        e for e in all_emails_in_body
        if e != original_email and not is_infra_email(e)
    ]
    same_domain = [e for e in candidates if extract_domain(e) == orig_domain]

    # =========================================================
    # PASS 1: Anchor-around-email (handles multi-line blocks)
    # =========================================================
    # For each candidate email, find its line index and inspect ±5 lines
    best_match = None  # {"email", "name", "title", "score"}

    for email in (same_domain or candidates):
        # Find which line this email appears on
        email_line_idx = next(
            (i for i, l in enumerate(lines_lower) if email in l),
            None
        )
        if email_line_idx is None:
            continue

        window_start = max(0, email_line_idx - 6)
        window_end   = min(len(lines), email_line_idx + 4)
        window_lines = lines[window_start:window_end]

        found_name  = ""
        found_title = ""

        for wl in window_lines:
            wl_stripped = wl.strip()
            if not wl_stripped or email in wl_stripped.lower():
                continue  # skip the email line itself

            # Try name detection first
            if not found_name and _is_name_line(wl_stripped):
                found_name = wl_stripped

            # Try title detection
            if not found_title:
                t = _is_title_line(wl_stripped)
                if t:
                    found_title = t

        score = bool(found_name) + bool(found_title)
        if best_match is None or score > best_match["score"]:
            best_match = {
                "email": email,
                "name":  found_name,
                "title": found_title,
                "score": score,
            }

    if best_match:
        result["replacement_email"] = best_match["email"]
        result["contact_name"]      = best_match["name"]
        result["job_title"]         = best_match["title"]

    # =========================================================
    # PASS 2: Inline sentence patterns (fallback / supplement)
    # =========================================================

    # Override or fill missing fields from sentence-level patterns
    if not result["replacement_email"] and candidates:
        result["replacement_email"] = candidates[0]

    if not result["contact_name"]:
        for pattern in _CONTACT_NAME_PATTERNS:
            m = pattern.search(body)
            if m:
                name = m.group(1).strip()
                if len(name) >= 4 and not any(
                    w in name.lower() for w in _NAME_BLACKLIST
                ):
                    result["contact_name"] = name
                    break

    if not result["job_title"]:
        # Try explicit label: "Title: Sales Manager"
        m_label = _TITLE_LABEL_RE.search(body)
        if m_label:
            result["job_title"] = m_label.group(1).strip()[:80]
        else:
            # Scan full body line by line
            for line in lines:
                t = _is_title_line(line)
                if t:
                    result["job_title"] = t[:80]
                    break

    return result

def get_sender_smtp(msg) -> str:
    """
    Trích xuất SMTP address thật từ MailItem.
    Dùng PropertyAccessor để bypass lỗi X500 của Exchange Server.
    """
    # Thử PropertyAccessor trên Sender object trước (Exchange internal)
    try:
        pa   = msg.Sender.PropertyAccessor
        smtp = pa.GetProperty(PR_SMTP_ADDRESS)
        if smtp and "@" in smtp:
            return smtp.strip().lower()
    except Exception:
        pass

    # Fallback: SenderEmailAddress (external / SMTP accounts)
    try:
        addr = msg.SenderEmailAddress
        if addr and "@" in addr and not addr.startswith("/O="):
            return addr.strip().lower()
    except Exception:
        pass

    # Fallback cuối: GetExchangeUser (legacy)
    try:
        if msg.SenderEmailType == "EX":
            return msg.Sender.GetExchangeUser().PrimarySmtpAddress.lower()
    except Exception:
        pass

    return ""

# =========================================================
# LOAD HELPERS
# =========================================================
def load_sent_emails() -> set[str]:
    """Trả về set email đã gửi từ email_log.csv."""
    if not EMAIL_LOG_FILE.exists():
        log.warning("email_log.csv not found — no sent email reference.")
        return set()
    df = pd.read_csv(EMAIL_LOG_FILE)
    df.columns = df.columns.str.lower()
    return set(df["email"].astype(str).str.lower())

def load_email_company_map() -> dict[str, str]:
    """Map email → company name từ data.xlsx."""
    if not DATA_FILE.exists():
        return {}
    df = pd.read_excel(DATA_FILE)
    df.columns = df.columns.str.upper().str.replace(" ", "_")
    mapping: dict[str, str] = {}
    for _, r in df.iterrows():
        for e_col, n_col in [("CNEE_EMAIL", "CNEE_NAME"), ("SHIPPER_EMAIL", "SHIPPER_NAME")]:
            email = r.get(e_col)
            if isinstance(email, str) and "@" in email:
                mapping[email.strip().lower()] = str(r.get(n_col, ""))
    return mapping

def load_knowledge() -> pd.DataFrame:
    cols = ["EMAIL", "DOMAIN", "COMPANY", "STATUS",
            "REPLACEMENT_EMAIL", "ROLE_HINT", "REMARK", "COUNT", "LAST_SEEN"]
    if not KNOWLEDGE_FILE.exists():
        pd.DataFrame(columns=cols).to_csv(KNOWLEDGE_FILE, index=False, encoding="utf-8-sig")
    df = pd.read_csv(KNOWLEDGE_FILE, encoding="utf-8-sig")
    df.columns = df.columns.astype(str).str.upper()
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    df["EMAIL"] = df["EMAIL"].astype(str).str.lower()
    df["COUNT"] = pd.to_numeric(df["COUNT"], errors="coerce").fillna(1)
    return df[cols]

def update_knowledge(
    df: pd.DataFrame,
    email: str,
    status: str,
    company: str = "",
    replacement: str = "",
    role: str = "",
    remark: str = "",
) -> pd.DataFrame:
    now   = datetime.now().date()
    email = email.lower()
    domain = extract_domain(email)

    if email in df["EMAIL"].values:
        mask = df["EMAIL"] == email
        df.loc[mask, "STATUS"]    = status
        df.loc[mask, "LAST_SEEN"] = now
        df.loc[mask, "COUNT"]    += 1
        if replacement:
            df.loc[mask, "REPLACEMENT_EMAIL"] = replacement
        if role:
            df.loc[mask, "ROLE_HINT"] = role
        if remark:
            df.loc[mask, "REMARK"] = remark
    else:
        df.loc[len(df)] = [email, domain, company, status,
                           replacement, role, remark, 1, now]
    return df

# =========================================================
# EMAIL CLASSIFIER
# =========================================================
def classify_message(sender: str, subject: str, body: str, sent_emails: set) -> tuple[str | None, list[str]]:
    """
    Phân loại một MailItem thành 1 trong 5 loại tín hiệu.

    Returns
    -------
    (signal_type, related_emails)
        signal_type  : 'hard_bounce' | 'soft_bounce' | 'policy_reject' |
                       'spam_block'  | 'auto_reply'  | 'human_reply' | None
        related_emails : list email liên quan tìm được trong body/subject
    """
    text          = (subject + " " + body).lower()
    related       = [e for e in extract_emails(text) if e in sent_emails and not is_infra_email(e)]
    is_sys_sender = is_system_sender(sender)

    # ---------- 1. HUMAN REPLY (highest priority) ----------
    # If sender is a known contact who replied directly, that wins over any
    # bounce keyword match found in old email threads in the body.
    subject_is_auto   = any(k in subject.lower() for k in AUTO_REPLY_SUBJECT_KEYWORDS)
    subject_is_bounce = any(k in subject.lower() for k in BOUNCE_SUBJECT_KEYWORDS)

    if sender in sent_emails and not is_sys_sender and not subject_is_auto and not subject_is_bounce:
        return "human_reply", [sender]

    # ---------- 2. AUTO REPLY ----------
    body_is_auto = any(k in body.lower() for k in AUTO_REPLY_BODY_KEYWORDS)

    if subject_is_auto or body_is_auto:
        return "auto_reply", related

    # ---------- 3. BOUNCE (system sender or SMTP 5xx/4xx codes) ----------
    has_smtp_code = bool(SMTP_CODE_REGEX.search(text))

    if is_sys_sender or has_smtp_code or subject_is_bounce:
        if any(k in text for k in HARD_BOUNCE_KEYWORDS):
            return "hard_bounce", related
        if any(k in text for k in SOFT_BOUNCE_KEYWORDS):
            return "soft_bounce", related
        if any(k in text for k in POLICY_KEYWORDS):
            return "policy_reject", related
        if any(k in text for k in SPAM_KEYWORDS):
            return "spam_block", related
        # Bounce subject but no specific keyword matched -> treat as hard_bounce
        if subject_is_bounce or is_sys_sender:
            return "hard_bounce", related

    return None, []

# =========================================================
# WRITE-BACK TO data.xlsx
# =========================================================
def write_back_to_data(bad_emails: set[str]) -> int:
    """
    Xoá các email trong bad_emails khỏi CNEE_EMAIL / SHIPPER_EMAIL trong data.xlsx.

    Returns
    -------
    int  Số ô email bị xoá.
    """
    if not bad_emails or not DATA_FILE.exists():
        return 0

    # Backup trước khi xoá
    backup_path = BACKUP_DIR / f"data_before_bounce_clean_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    shutil.copy(DATA_FILE, backup_path)
    log.info("Backup saved → %s", backup_path.name)

    df = pd.read_excel(DATA_FILE)
    df.columns = df.columns.str.upper().str.replace(" ", "_")

    cleared = 0
    for col in ["CNEE_EMAIL", "SHIPPER_EMAIL"]:
        if col not in df.columns:
            continue
        mask = df[col].astype(str).str.lower().str.strip().isin(bad_emails)
        cleared += mask.sum()
        df.loc[mask, col] = ""

    # Cập nhật STATUS column nếu có
    if "STATUS" in df.columns:
        for col in ["CNEE_EMAIL", "SHIPPER_EMAIL"]:
            if col not in df.columns:
                continue
            bounce_mask = df[col] == ""
            df.loc[bounce_mask, "STATUS"] = "BAD_EMAIL"

    df.to_excel(DATA_FILE, index=False)
    return cleared

# =========================================================
# MAIN
# =========================================================
def main() -> None:
    log.info("=" * 65)
    log.info("EMAIL SIGNAL SCANNER%s", "  [DRY RUN — data.xlsx WILL NOT change]" if DRY_RUN else "  [LIVE MODE]")
    log.info("=" * 65)

    # 1. Load tham chiếu
    sent_emails   = load_sent_emails()
    email_company = load_email_company_map()
    df_kn         = load_knowledge()

    if not sent_emails:
        log.error("Không tìm thấy email đã gửi trong email_log.csv. Dừng.")
        return

    log.info("Sent email addresses loaded: %d", len(sent_emails))

    # 2. Kết nối Outlook
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        inbox   = outlook.GetNamespace("MAPI").GetDefaultFolder(6)
    except Exception as exc:
        log.error("Không kết nối được Outlook: %s", exc)
        return

    messages = inbox.Items
    messages.Sort("[ReceivedTime]", True)  # mới nhất trước

    # 3. Quét & phân loại
    stats: dict[str, list[str]] = {
        "hard_bounce":   [],
        "soft_bounce":   [],
        "policy_reject": [],
        "spam_block":    [],
        "auto_reply":    [],
        "human_reply":   [],
        "skipped":       [],
    }

    scanned    = 0
    hard_to_clean: set[str] = set()

    for msg in messages:
        if scanned >= INBOX_SCAN_LIMIT:
            break
        scanned += 1

        try:
            subject = (msg.Subject or "").strip()
            body    = (msg.Body    or "").strip()
            sender  = get_sender_smtp(msg)
        except Exception:
            stats["skipped"].append("(unreadable)")
            continue

        signal, related = classify_message(sender, subject, body, sent_emails)

        if signal is None:
            stats["skipped"].append(sender)
            continue

        # --- Xử lý từng loại ---
        if signal == "human_reply":
            df_kn = update_knowledge(
                df_kn, sender, "human_reply",
                company=email_company.get(sender, ""),
                remark="real customer reply",
            )
            stats["human_reply"].append(sender)
            log.info("HUMAN REPLY  | %s | %s", sender, subject[:50])

        elif signal == "auto_reply":
            # Determine the OOO email (the one who is away)
            original    = next((e for e in related), sender)

            # Parse body for replacement contact, name, title
            ooo_data    = extract_ooo_contact(body, original)
            replacement = ooo_data["replacement_email"]
            contact_name = ooo_data["contact_name"]
            job_title    = ooo_data["job_title"]

            # Build remark string
            remark_parts = ["OOO/auto-reply"]
            if contact_name:
                remark_parts.append(f"alt contact: {contact_name}")
            if job_title:
                remark_parts.append(f"title: {job_title}")
            if replacement:
                remark_parts.append(f"email: {replacement}")
            remark = " | ".join(remark_parts)

            df_kn = update_knowledge(
                df_kn, original, "auto_reply",
                company=email_company.get(original, ""),
                replacement=replacement,
                role=job_title,
                remark=remark,
            )
            stats["auto_reply"].append(original)
            log.info(
                "AUTO REPLY   | %-35s | alt: %-30s | name: %-20s | title: %s",
                original,
                replacement or "-",
                contact_name or "-",
                job_title or "-",
            )

        else:  # bounce varieties
            for email in related:
                if not email or is_infra_email(email):
                    continue
                df_kn = update_knowledge(
                    df_kn, email, signal,
                    company=email_company.get(email, ""),
                    remark=f"{signal} detected — subject: {subject[:60]}",
                )
                stats[signal].append(email)

                if signal == "hard_bounce" and AUTO_CLEAN_HARD_BOUNCE:
                    hard_to_clean.add(email)

                log.info("%-14s | %s | %s", signal.upper(), email, subject[:45])

    # 4. Write-back hard bounce → data.xlsx
    cleared = 0
    if hard_to_clean:
        if DRY_RUN:
            log.info("[DRY RUN] Will clear %d hard bounce emails from data.xlsx: %s",
                     len(hard_to_clean), ", ".join(sorted(hard_to_clean)))
        else:
            cleared = write_back_to_data(hard_to_clean)
            log.info("Cleared %d bad email cells from data.xlsx", cleared)

    # 5. Lưu knowledge
    df_kn.to_csv(KNOWLEDGE_FILE, index=False, encoding="utf-8-sig")
    log.info("email_knowledge.csv updated -> %s", KNOWLEDGE_FILE)

    # 6. Summary report
    log.info("")
    log.info("=" * 65)
    log.info("  SCAN RESULT  (%d emails scanned, limit %d)", scanned, INBOX_SCAN_LIMIT)
    log.info("=" * 65)
    log.info("  %-20s : %d unique addresses", "hard_bounce",   len(set(stats["hard_bounce"])))
    log.info("  %-20s : %d unique addresses", "soft_bounce",   len(set(stats["soft_bounce"])))
    log.info("  %-20s : %d unique addresses", "policy_reject", len(set(stats["policy_reject"])))
    log.info("  %-20s : %d unique addresses", "spam_block",    len(set(stats["spam_block"])))
    log.info("  %-20s : %d unique addresses", "auto_reply",    len(set(stats["auto_reply"])))
    log.info("  %-20s : %d unique addresses", "human_reply",   len(set(stats["human_reply"])))
    log.info("  %-20s : %d",                  "skipped/other", len(stats["skipped"]))
    log.info("-" * 65)
    if DRY_RUN:
        log.info("  [DRY RUN] data.xlsx was NOT modified.")
        log.info("  Set DRY_RUN = False to enable actual write-back.")
    else:
        log.info("  data.xlsx: cleared %d bad email cells.", cleared)
    log.info("=" * 65)


# =========================================================
if __name__ == "__main__":
    main()
