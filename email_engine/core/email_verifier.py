# email_verifier.py — Syntax + MX verification for bulk contact lists
import re
import logging
from pathlib import Path

log = logging.getLogger("email_verifier")

# TLD whitelist — replaces the too-permissive {2,} that passed .co/.cm/.og typos.
# Only allow TLDs known to appear in legitimate B2B freight prospect emails.
# If a real business TLD is missing, add it here — do NOT revert to {2,}.
_VALID_TLDS = (
    r"com|net|org|vn|io|edu|gov|asia"
    r"|co\.uk|co\.vn|co\.jp|co\.in|co\.kr"
    r"|jp|cn|kr|sg|th|my|id|ph|au|ca"
    r"|de|fr|nl|eu|mx|br|ar|it|es|pl|cz|ro"
    r"|us|biz|info|pro|mobi|name|coop|aero"
    r"|hk|tw|in|pk|bd|lk|np|ae|sa|eg|ng|za"
)

EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.(?:" + _VALID_TLDS + r")$",
    re.IGNORECASE,
)

try:
    import dns.resolver as _dns_resolver
    DNS_AVAILABLE = True
except ImportError:
    _dns_resolver = None
    DNS_AVAILABLE = False
    log.warning("dnspython not installed — MX verification disabled. pip install dnspython")

_mx_cache: dict[str, bool] = {}


def verify_syntax(email: str) -> bool:
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def verify_mx(domain: str) -> bool:
    if not DNS_AVAILABLE:
        return True  # Skip gracefully

    domain = domain.lower().strip()
    if domain in _mx_cache:
        return _mx_cache[domain]

    try:
        answers = _dns_resolver.resolve(domain, "MX", lifetime=5)
        result = len(answers) > 0
    except Exception:
        result = False

    _mx_cache[domain] = result
    return result


def bulk_verify(df) -> object:
    """
    Add EMAIL_STATUS='INVALID' for syntax failures, 'NO_MX' for domain failures.
    Preserves existing statuses for already-flagged emails.
    Returns modified DataFrame.
    """
    import pandas as pd

    if "EMAIL_STATUS" not in df.columns:
        df["EMAIL_STATUS"] = "VALID"

    invalid_syntax = 0
    no_mx = 0

    for idx, row in df.iterrows():
        # Skip already-suppressed rows
        current_status = str(row.get("EMAIL_STATUS", "VALID"))
        if current_status in ("HARD_BOUNCE", "SOFT_SUPPRESSED", "INVALID", "NO_MX"):
            continue

        email = str(row.get("EMAIL", "")).strip()

        if not verify_syntax(email):
            df.at[idx, "EMAIL_STATUS"] = "INVALID"
            invalid_syntax += 1
            continue

        domain = email.split("@")[-1]
        if not verify_mx(domain):
            df.at[idx, "EMAIL_STATUS"] = "NO_MX"
            no_mx += 1

    log.info(f"bulk_verify: invalid_syntax={invalid_syntax}, no_mx={no_mx}")
    return df, {"invalid_syntax": invalid_syntax, "no_mx": no_mx}


if __name__ == "__main__":
    import pandas as pd
    logging.basicConfig(level=logging.INFO)

    test_emails = [
        "valid@gmail.com", "bad-email", "user@nonexistent-domain-xyz123.com",
        "test@outlook.com", "", "no-at-sign.com"
    ]
    for e in test_emails:
        syntax_ok = verify_syntax(e)
        mx_ok = verify_mx(e.split("@")[-1]) if syntax_ok else False
        print(f"  {e!r:40s} syntax={syntax_ok} mx={mx_ok}")
