"""
smart_send_window.py — Timezone-aware send time planner
========================================================
Phase 2B — Smart Send Window

Calculates the optimal UTC send time for a contact based on their TIMEZONE.

Target window: Tue/Wed/Thu 9h–11h local time.

Avoid:
  - Monday before 10h local (post-weekend inbox overload)
  - Friday after 15h local (people heading out)
  - Saturday / Sunday (B2B not reading)
  - US federal holidays (via us_holidays module)

URGENT bypass: contact['URGENT'] == True → return now immediately.

Usage:
    from email_engine.core.smart_send_window import plan_send_time
    from datetime import datetime, timezone

    utc_send = plan_send_time(contact_row, now_utc=datetime.now(timezone.utc))
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from email_engine.core.us_holidays import is_us_holiday

log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
_DEFAULT_TZ = "America/New_York"    # fallback if TIMEZONE missing / invalid
_WINDOW_OPEN_H  = 9                 # 09:00 local
_WINDOW_CLOSE_H = 11                # 11:00 local (send by 10:59)
_MON_MIN_H      = 10                # Monday: not before 10:00
_FRI_MAX_H      = 15                # Friday: not after 15:00
_MAX_ADVANCE_DAYS = 14              # safety cap — never queue >14 days out

# Weekday constants (datetime.weekday())
_MON, _TUE, _WED, _THU, _FRI, _SAT, _SUN = 0, 1, 2, 3, 4, 5, 6

# Preferred send days: Tue/Wed/Thu first, then Mon/Fri as fallback
_PREFERRED_DAYS = {_TUE, _WED, _THU}
_ALLOWED_DAYS   = {_MON, _TUE, _WED, _THU, _FRI}


def _get_tz(tz_str: str):
    """Return a ZoneInfo object, falling back to EST on unknown TZ string."""
    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            return ZoneInfo(tz_str)
        except (ZoneInfoNotFoundError, KeyError):
            log.warning("smart_send_window: unknown TZ %r — fallback to %s", tz_str, _DEFAULT_TZ)
            return ZoneInfo(_DEFAULT_TZ)
    except ImportError:
        # Python < 3.9 fallback via pytz
        try:
            import pytz
            try:
                return pytz.timezone(tz_str)
            except Exception:
                log.warning("smart_send_window: unknown TZ %r — fallback to %s", tz_str, _DEFAULT_TZ)
                return pytz.timezone(_DEFAULT_TZ)
        except ImportError:
            log.error("Neither zoneinfo nor pytz available. pip install pytz")
            return timezone.utc


def _is_in_window(local_dt: datetime) -> bool:
    """Return True if local_dt is inside an acceptable send window."""
    wd = local_dt.weekday()
    h  = local_dt.hour

    if wd in (_SAT, _SUN):
        return False
    if wd == _MON and h < _MON_MIN_H:
        return False
    if wd == _FRI and h >= _FRI_MAX_H:
        return False
    if h < _WINDOW_OPEN_H or h >= _WINDOW_CLOSE_H:
        return False
    if is_us_holiday(local_dt.date()):
        return False
    return True


def _next_window_start(local_dt: datetime) -> datetime:
    """Advance local_dt to the start of the next valid send window (9h local).

    Never modifies timezone — always returns tz-aware datetime in same tz.
    """
    candidate = local_dt.replace(hour=_WINDOW_OPEN_H, minute=0, second=0, microsecond=0)

    # If we've already passed today's window start, move to tomorrow
    if local_dt >= candidate.replace(hour=_WINDOW_CLOSE_H):
        candidate += timedelta(days=1)
        candidate = candidate.replace(hour=_WINDOW_OPEN_H, minute=0, second=0, microsecond=0)

    for _ in range(_MAX_ADVANCE_DAYS):
        wd = candidate.weekday()

        # Skip weekend
        if wd in (_SAT, _SUN):
            candidate += timedelta(days=1)
            candidate = candidate.replace(hour=_WINDOW_OPEN_H, minute=0, second=0, microsecond=0)
            continue

        # Monday: push to 10h if needed
        if wd == _MON and candidate.hour < _MON_MIN_H:
            candidate = candidate.replace(hour=_MON_MIN_H)

        # Friday: skip if past 15h
        if wd == _FRI and candidate.hour >= _FRI_MAX_H:
            candidate += timedelta(days=1)
            candidate = candidate.replace(hour=_WINDOW_OPEN_H, minute=0, second=0, microsecond=0)
            continue

        # US holiday: skip entire day
        if is_us_holiday(candidate.date()):
            candidate += timedelta(days=1)
            candidate = candidate.replace(hour=_WINDOW_OPEN_H, minute=0, second=0, microsecond=0)
            continue

        # Valid slot found
        return candidate

    # Safety fallback — should never reach here in normal operations
    log.warning("smart_send_window: exceeded %d day advance limit", _MAX_ADVANCE_DAYS)
    return local_dt


def plan_send_time(
    contact_row: dict[str, Any],
    now_utc: Optional[datetime] = None,
) -> datetime:
    """Calculate optimal UTC send time for a contact.

    Args:
        contact_row: Dict with at least 'TIMEZONE' key (e.g. "America/Los_Angeles").
                     Optional 'URGENT' key: if truthy, returns now immediately.
        now_utc:     Current UTC datetime (injectable for testing). Defaults to
                     datetime.now(timezone.utc).

    Returns:
        datetime in UTC — the scheduled send time.
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    # Ensure UTC-aware
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    # URGENT bypass
    if contact_row.get("URGENT"):
        log.debug("smart_send_window: URGENT flag — sending now")
        return now_utc

    tz_str = str(contact_row.get("TIMEZONE") or "").strip() or _DEFAULT_TZ
    tz = _get_tz(tz_str)

    try:
        local_now = now_utc.astimezone(tz)
    except Exception as exc:
        log.warning("smart_send_window: astimezone failed for %r: %s — using UTC", tz_str, exc)
        local_now = now_utc

    # If currently inside window, send now
    if _is_in_window(local_now):
        log.debug("smart_send_window: already in window (tz=%s) → send now", tz_str)
        return now_utc

    # Else find next window start
    next_local = _next_window_start(local_now)

    try:
        next_utc = next_local.astimezone(timezone.utc)
    except Exception as exc:
        log.warning("smart_send_window: back-conversion to UTC failed: %s — sending now", exc)
        return now_utc

    log.debug(
        "smart_send_window: tz=%s local_now=%s → next_window=%s (UTC: %s)",
        tz_str,
        local_now.strftime("%a %Y-%m-%d %H:%M"),
        next_local.strftime("%a %Y-%m-%d %H:%M"),
        next_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    return next_utc
