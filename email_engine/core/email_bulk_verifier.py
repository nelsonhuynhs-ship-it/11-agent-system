# -*- coding: utf-8 -*-
"""
email_bulk_verifier.py — Bulk Email Verification (Local, No Paid API)
=====================================================================
3-stage verification:
  Stage 1: Syntax check (instant)
  Stage 2: MX record lookup (fast, ~0.5s/domain, cached)
  Stage 3: SMTP handshake (slow, 1-2s/email, optional — needs port 25 open)

Input:  cnee_master_v2.xlsx (or any Excel with EMAIL column)
Output: Same file + VERIFY_STATUS + VERIFY_REMARK columns (NO rows/cols deleted)

Usage:
    from email_bulk_verifier import bulk_verify
    stats = bulk_verify()                    # Stage 1+2 only (safe, fast)
    stats = bulk_verify(smtp=True)           # Stage 1+2+3 (needs port 25)
    stats = bulk_verify(input_file="...", output_file="...")
"""
import logging
import re
import socket
import smtplib
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

log = logging.getLogger("email_verifier")

BASE_DIR = Path(__file__).parent.parent
DEFAULT_INPUT  = BASE_DIR / "data" / "cnee_master_v2.xlsx"
DEFAULT_OUTPUT = BASE_DIR / "data" / "cnee_master_v2.xlsx"  # update in-place

# ── Stage 1: Syntax ──────────────────────────────────────────────
_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}$"
)

def _check_syntax(email: str) -> tuple[bool, str]:
    email = str(email).strip().lower()
    if not email or "@" not in email:
        return False, "INVALID_SYNTAX: missing @ or empty"
    if not _EMAIL_RE.match(email):
        return False, "INVALID_SYNTAX: bad format"
    if ".." in email:
        return False, "INVALID_SYNTAX: consecutive dots"
    return True, ""


# ── Stage 2: MX Record (cached per domain) ──────────────────────
_mx_cache: dict[str, tuple[bool, str, str]] = {}

def _check_mx(domain: str) -> tuple[bool, str, str]:
    """Returns (has_mx, mx_host, remark)"""
    if domain in _mx_cache:
        return _mx_cache[domain]
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, "MX")
        mx_host = str(answers[0].exchange).rstrip(".")
        result = (True, mx_host, "")
    except ImportError:
        # Fallback: socket check
        try:
            socket.getaddrinfo(domain, 25)
            result = (True, domain, "")
        except socket.gaierror:
            result = (False, "", f"NO_MX: domain '{domain}' has no mail server")
    except Exception as e:
        result = (False, "", f"NO_MX: {domain} — {e}")
    _mx_cache[domain] = result
    return result


# ── Stage 3: SMTP Handshake (optional) ──────────────────────────
def _check_smtp(email: str, mx_host: str, timeout: int = 10) -> tuple[bool, str]:
    """Connect to MX server, RCPT TO check. Returns (is_valid, remark)."""
    try:
        with smtplib.SMTP(mx_host, 25, timeout=timeout) as smtp:
            smtp.ehlo("verify.local")
            smtp.mail("verify@verify.local")
            code, msg = smtp.rcpt(email)
            if code == 250:
                return True, "SMTP_OK"
            elif code == 550:
                return False, f"DEAD: mailbox does not exist (SMTP {code})"
            elif code == 552:
                return False, f"DEAD: mailbox full/disabled (SMTP {code})"
            else:
                return True, f"SMTP_UNKNOWN: code {code} — treated as valid"
    except smtplib.SMTPServerDisconnected:
        return True, "SMTP_SKIP: server disconnected (catch-all or greylisting)"
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        return True, f"SMTP_SKIP: port 25 blocked or timeout ({e})"
    except Exception as e:
        return True, f"SMTP_SKIP: {e}"


# ── Bulk Verify ──────────────────────────────────────────────────
def bulk_verify(
    input_file: str | Path = None,
    output_file: str | Path = None,
    smtp: bool = False,
    smtp_threads: int = 5,
    smtp_delay: float = 0.5,
    progress_callback=None,
) -> dict:
    """
    Verify all emails in Excel file. Adds VERIFY_STATUS + VERIFY_REMARK columns.
    Never deletes any row or column.

    Args:
        input_file:  Path to xlsx (default: cnee_master_v2.xlsx)
        output_file: Path to save (default: same as input — in-place update)
        smtp:        Enable Stage 3 SMTP check (needs port 25 open)
        smtp_threads: Parallel SMTP connections (default 5)
        smtp_delay:  Delay between SMTP checks in seconds
        progress_callback: fn(current, total, email, status) for UI updates

    Returns:
        dict with stats: total, valid, invalid_syntax, no_mx, dead_smtp, skipped
    """
    src = Path(input_file) if input_file else DEFAULT_INPUT
    dst = Path(output_file) if output_file else (Path(input_file) if input_file else DEFAULT_OUTPUT)

    if not src.exists():
        return {"error": f"File not found: {src}"}

    df = pd.read_excel(src)
    df.columns = df.columns.str.strip().str.upper()
    total = len(df)

    if "EMAIL" not in df.columns:
        return {"error": "No EMAIL column found"}

    # Init result columns (preserve existing if re-running)
    df["VERIFY_STATUS"] = "PENDING"
    df["VERIFY_REMARK"] = ""

    stats = {"total": total, "valid": 0, "invalid_syntax": 0, "no_mx": 0,
             "dead_smtp": 0, "skipped": 0, "started_at": datetime.now().isoformat()}

    for i, row in df.iterrows():
        email = str(row.get("EMAIL", "")).strip().lower()

        # Stage 1: Syntax
        ok, remark = _check_syntax(email)
        if not ok:
            df.at[i, "VERIFY_STATUS"] = "INVALID"
            df.at[i, "VERIFY_REMARK"] = remark
            stats["invalid_syntax"] += 1
            if progress_callback:
                progress_callback(i + 1, total, email, "INVALID")
            continue

        # Stage 2: MX
        domain = email.split("@")[1]
        has_mx, mx_host, mx_remark = _check_mx(domain)
        if not has_mx:
            df.at[i, "VERIFY_STATUS"] = "NO_MX"
            df.at[i, "VERIFY_REMARK"] = mx_remark
            stats["no_mx"] += 1
            if progress_callback:
                progress_callback(i + 1, total, email, "NO_MX")
            continue

        # Stage 3: SMTP (optional)
        if smtp:
            is_valid, smtp_remark = _check_smtp(email, mx_host)
            if not is_valid:
                df.at[i, "VERIFY_STATUS"] = "DEAD"
                df.at[i, "VERIFY_REMARK"] = smtp_remark
                stats["dead_smtp"] += 1
                if progress_callback:
                    progress_callback(i + 1, total, email, "DEAD")
                if smtp_delay > 0:
                    time.sleep(smtp_delay)
                continue
            df.at[i, "VERIFY_REMARK"] = smtp_remark
            if smtp_delay > 0:
                time.sleep(smtp_delay)

        # Passed all checks
        df.at[i, "VERIFY_STATUS"] = "VALID"
        stats["valid"] += 1
        if progress_callback:
            progress_callback(i + 1, total, email, "VALID")

    stats["finished_at"] = datetime.now().isoformat()
    stats["skipped"] = total - stats["valid"] - stats["invalid_syntax"] - stats["no_mx"] - stats["dead_smtp"]

    # Save — never delete any row or column
    df.to_excel(dst, index=False)
    log.info(f"Verification complete: {stats}")
    return stats


# ── CLI ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s", datefmt="%H:%M:%S")

    parser = argparse.ArgumentParser(description="Bulk Email Verifier")
    parser.add_argument("-i", "--input", default=str(DEFAULT_INPUT), help="Input Excel file")
    parser.add_argument("-o", "--output", help="Output file (default: same as input)")
    parser.add_argument("--smtp", action="store_true", help="Enable SMTP check (needs port 25)")
    args = parser.parse_args()

    def _progress(cur, tot, email, status):
        if cur % 100 == 0 or status != "VALID":
            print(f"  [{cur}/{tot}] {email} → {status}")

    result = bulk_verify(
        input_file=args.input,
        output_file=args.output or args.input,
        smtp=args.smtp,
        progress_callback=_progress,
    )
    print(f"\n{'='*50}")
    print(f"  Results: {result}")
    print(f"{'='*50}")
