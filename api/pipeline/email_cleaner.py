"""
email_cleaner.py — Panjiva email prefix cleaner.
Strips country-code prefixes (em, us, id, me, te) and mailto: from raw emails.
"""
import re
from typing import Optional

import pandas as pd

# Panjiva prepends country/type codes before emails
_PREFIX_RE = re.compile(
    r"^(mailto:\s*|em[,\s]+|me[,\s]+|te[,\s]+|us[,\s]+|id[,\s]+|cn[,\s]+|th[,\s]+|vn[,\s]+|ph[,\s]+|in[,\s]+|jp[,\s]+|kr[,\s]+|tw[,\s]+|hk[,\s]+|sg[,\s]+|my[,\s]+|au[,\s]+|de[,\s]+|fr[,\s]+|gb[,\s]+|ca[,\s]+)",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_DIGIT_START_RE = re.compile(r"^\d")


def clean_panjiva_email(raw: str) -> Optional[str]:
    """Clean a single Panjiva email value. Returns None if invalid."""
    if not raw or not isinstance(raw, str):
        return None

    raw = raw.strip()
    if not raw:
        return None

    # Skip digit-prefixed entries (phone numbers in email field)
    if _DIGIT_START_RE.match(raw):
        return None

    # Strip known prefixes (may need multiple passes)
    cleaned = _PREFIX_RE.sub("", raw).strip()
    # Remove any remaining leading commas/spaces
    cleaned = cleaned.lstrip(", ").strip()

    if not cleaned:
        return None

    # Validate email format
    if _EMAIL_RE.match(cleaned):
        return cleaned.lower()

    return None


def clean_email_column(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Clean an email column in-place, adding {col}_CLEANED and {col}_ORIGINAL."""
    df = df.copy()
    df[f"{col}_ORIGINAL"] = df[col]
    df[col] = df[col].apply(clean_panjiva_email)
    cleaned_count = df[col].notna().sum()
    original_count = df[f"{col}_ORIGINAL"].notna().sum()
    fixed = original_count - (original_count - cleaned_count)
    print(f"  {col}: {original_count} → {cleaned_count} valid ({original_count - cleaned_count} removed/invalid)")
    return df
