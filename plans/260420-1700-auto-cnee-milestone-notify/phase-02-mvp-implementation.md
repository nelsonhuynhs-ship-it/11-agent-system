# Phase 02 — MVP Implementation (Single File)

**Effort:** 2h
**Priority:** CRITICAL (core feature)
**Status:** pending
**Depends on:** Phase 01

## Key Changes vs v1

- **1 file** (~200 LOC) thay vì 3 module + hook module (red-team C1)
- **Plain dict** pass (no dataclass/Enum) (red-team C1, C5)
- **Inline Telegram list** (no buffer pattern) (red-team C2)
- **Separate Task Scheduler entry** for ETA (no schedule_override) (red-team C3)
- **Security baked in** (red-team A1-A5)
- **JSON sidecar state** (no xlsm write from scanner) (red-team B2)

## Deliverables

### File 1: `email_engine/core/cnee_milestone.py` (~200 LOC)

```python
"""
cnee_milestone.py — Auto CNEE notification (ATD + ETA-7)

MVP v2 (post red-team). Single-file design.

Exported:
    on_atd_detected(mail_item, stages, identifiers, sender_smtp) -> bool
    run_eta_reminder() -> int   # CLI entry for Task Scheduler
    flush_telegram_summary()    # called at end of scanner run

Security controls:
    - Authentication-Results header check (SPF/DKIM/DMARC)
    - Explicit OPS sender allowlist (not domain-wide)
    - Placeholder sanitization (strip + length cap + regex whitelist)
    - Rate limiting (MAX_DRAFTS_PER_RUN, DAY)
    - Kill switch file
    - Bulk-Bkg detection (reject >3 Bkg in one mail)
    - Date sanity (ATD within ReceivedTime ± 30d)
    - ActiveInspector check (don't steal Nelson's Outlook)
"""
from __future__ import annotations
import json, re, os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

# ── Config ─────────────────────────────────────────────────────────
OPS_ALLOWLIST = {
    # Fill actual OPS Pudong senders after Phase 01 audit
    # "ops@pudongprime.vn",
    # "pricing@pudongprime.vn",
}
BLACKLIST_REGEX = re.compile(
    r"VESSEL\s+CHANGE|RVS\s+ETD|REVISED\s+ETD|CHANGE\s+VESSEL|NEW\s+ETD",
    re.I,
)
MAX_DRAFTS_PER_RUN = 5
MAX_DRAFTS_PER_DAY = 20
KILL_SWITCH = Path(__file__).parent.parent / "data" / "AUTO_NOTIFY_DISABLED"
STATE_FILE = Path(__file__).parent.parent / "data" / "milestone_state.jsonl"
DAILY_COUNTER = Path(__file__).parent.parent / "data" / "milestone_daily.json"

# Placeholder sanitization rules
FIELD_LIMITS = {
    "bkg": (20, r"^[A-Z0-9]{5,20}$"),
    "hbl": (20, r"^[A-Z0-9]{5,20}$"),
    "vessel": (40, None),
    "carrier": (20, r"^[A-Z\s]+$"),
    "customer": (80, None),
    "pol": (20, None),
    "pod": (30, None),
}

# Date patterns (supports /, -, .)
DATE_PATTERNS = [
    r"ATD\s*[:=]?\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})",
    r"vessel\s+departed\s+on\s+(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})",
    r"loaded\s+on\s+board\s+(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})",
]

# Telegram aggregation (module-local list, reset per scan)
_telegram_lines: list[str] = []


# ── Security gate ──────────────────────────────────────────────────
def _check_kill_switch() -> bool:
    if KILL_SWITCH.exists():
        _log("⚠ KILL SWITCH active, aborting")
        return False
    return True

def _daily_count() -> int:
    today = date.today().isoformat()
    if DAILY_COUNTER.exists():
        data = json.loads(DAILY_COUNTER.read_text())
        if data.get("date") == today:
            return data.get("count", 0)
    return 0

def _increment_daily() -> int:
    today = date.today().isoformat()
    count = _daily_count() + 1
    DAILY_COUNTER.write_text(json.dumps({"date": today, "count": count}))
    return count

def _check_auth_results(mail_item) -> bool:
    """Parse Authentication-Results header via PropertyAccessor."""
    try:
        PR_HEADERS = "http://schemas.microsoft.com/mapi/proptag/0x007D001F"
        headers = mail_item.PropertyAccessor.GetProperty(PR_HEADERS)
        auth = re.search(r"Authentication-Results:(.*?)(?:\r?\n\S|\Z)",
                         headers, re.S | re.I)
        if not auth:
            return False
        auth_text = auth.group(1).lower()
        return all(tag + "=pass" in auth_text for tag in ["spf", "dkim", "dmarc"])
    except Exception:
        return False


# ── Sanitization ───────────────────────────────────────────────────
def _sanitize(field: str, value: str) -> str | None:
    """Return sanitized value or None if invalid."""
    if not value:
        return None
    # Strip control chars
    cleaned = re.sub(r"[\r\n\t\x00-\x1f]", " ", str(value)).strip()
    # Length cap
    limit, pattern = FIELD_LIMITS.get(field, (100, None))
    if len(cleaned) > limit:
        return None
    # Regex whitelist
    if pattern and not re.match(pattern, cleaned):
        return None
    return cleaned


# ── Date extraction with cross-check ───────────────────────────────
def extract_atd_date(text: str, received_time: datetime) -> date | None:
    """Extract ATD date, validate within ReceivedTime ± 30 days."""
    candidates = []
    for pat in DATE_PATTERNS:
        for m in re.finditer(pat, text, re.I):
            d = _parse_date_flex(m.group(1))
            if d:
                candidates.append(d)
    if not candidates:
        return None
    # Pick first valid (within receive window)
    lo = received_time.date() - timedelta(days=30)
    hi = received_time.date() + timedelta(days=1)
    for d in candidates:
        if lo <= d <= hi:
            return d
    return None

def _parse_date_flex(s: str) -> date | None:
    """Parse dd/mm/yyyy, dd-mm-yyyy, dd.mm.yyyy. Assume dd first (Vietnam)."""
    parts = re.split(r"[/.\-]", s)
    if len(parts) != 3:
        return None
    try:
        d, m, y = [int(p) for p in parts]
        if y < 100:
            y += 2000
        if d > 31 or m > 12:
            return None
        return date(y, m, d)
    except ValueError:
        return None


# ── Main hook (called from shipment_brain) ──────────────────────────
def on_atd_detected(mail_item, stages, identifiers, sender_smtp) -> bool:
    if not _check_kill_switch():
        return False

    # 1. Sender allowlist
    if sender_smtp.lower() not in {e.lower() for e in OPS_ALLOWLIST}:
        return False

    # 2. Auth-Results
    if not _check_auth_results(mail_item):
        _log(f"Rejected: auth fail from {sender_smtp}")
        return False

    # 3. Rate limit
    if _daily_count() >= MAX_DRAFTS_PER_DAY:
        _queue_telegram(f"⚠ Daily cap ({MAX_DRAFTS_PER_DAY}) reached, skip more")
        return False

    # 4. Gather text
    subject = mail_item.Subject or ""
    body = mail_item.Body or ""  # full body, not preview
    text = f"{subject}\n{body}"

    # 5. Blacklist
    if BLACKLIST_REGEX.search(text):
        return False

    # 6. Bulk detect (>3 Bkg = bulk sheet)
    bkg_list = identifiers.get("BKG", [])
    if len(bkg_list) > 3:
        _queue_telegram(f"⚠ Bulk mail detected ({len(bkg_list)} Bkg), skip")
        return False

    # 7. Extract ATD date
    atd = extract_atd_date(text, mail_item.ReceivedTime)
    if not atd:
        _queue_telegram(f"⚠ ATD detected but no parseable date: {subject[:60]}")
        return False

    # 8. Process each Bkg
    made_drafts = 0
    for bkg in bkg_list:
        if made_drafts >= MAX_DRAFTS_PER_RUN:
            break
        if _process_bkg(bkg, atd, text, mail_item):
            made_drafts += 1
            _increment_daily()

    return made_drafts > 0


# ── Per-Bkg processing ─────────────────────────────────────────────
def _process_bkg(bkg: str, atd: date, source_text: str, source_mail) -> bool:
    # Match Active Jobs (recency: ETD > today - 60d)
    job = _find_active_job(bkg, max_age_days=60)
    if not job:
        return False

    # Dedup via sidecar
    if _already_notified(bkg, "ATD"):
        return False

    # CRM opt-in check
    if not _crm_auto_notify(job.get("CUSTOMER", "")):
        return False

    # Email lookup
    cnee_emails = _lookup_cnee_emails(job)
    if not cnee_emails:
        _queue_telegram(f"⚠ Missing CNEE email: {job.get('CUSTOMER')} / {bkg}")
        return False

    # Build + sanitize placeholders
    ctx = _build_context(job, atd)
    for k in FIELD_LIMITS:
        sanitized = _sanitize(k, ctx.get(k, ""))
        if sanitized is None and ctx.get(k):
            _queue_telegram(f"⚠ Sanitize fail for {k}: {bkg}")
            return False
        ctx[k] = sanitized or "N/A"

    # Compose draft (check ActiveInspector)
    if not _create_outlook_draft_polite(cnee_emails, "ATD", ctx):
        return False

    # Log to sidecar (NOT xlsm)
    _write_state(bkg, "ATD", atd.isoformat(), source_mail.EntryID)
    _queue_telegram(f"✅ Draft: {ctx['customer']} / {bkg}")
    return True


# ── ETA-7 reminder (CLI entry for Task Scheduler) ──────────────────
def run_eta_reminder() -> int:
    if not _check_kill_switch():
        return 0
    today = date.today()
    window_lo, window_hi = today + timedelta(days=1), today + timedelta(days=8)
    count = 0
    for job in _load_active_jobs():
        eta = _parse_job_date(job.get("ETA_DATE"))
        if not eta or not (window_lo <= eta <= window_hi):
            continue
        if _already_notified(job["BKG"], "ETA7"):
            continue
        if not _crm_auto_notify(job.get("CUSTOMER", "")):
            continue
        cnee = _lookup_cnee_emails(job)
        if not cnee:
            continue
        ctx = _build_context(job, None)
        if _create_outlook_draft_polite(cnee, "ETA7", ctx):
            _write_state(job["BKG"], "ETA7", today.isoformat(), None)
            _queue_telegram(f"⏰ ETA-7 draft: {ctx['customer']} / {job['BKG']}")
            count += 1
            if count >= MAX_DRAFTS_PER_RUN:
                break
    flush_telegram_summary()
    return count


# ── Outlook polite draft ───────────────────────────────────────────
def _create_outlook_draft_polite(to_list: list[str], template_type: str, ctx: dict) -> bool:
    import win32com.client, pythoncom
    pythoncom.CoInitialize()
    try:
        ol = win32com.client.Dispatch("Outlook.Application")
        inspector = ol.ActiveInspector()
        if inspector is not None:
            _queue_telegram(f"ℹ Outlook busy, deferring {ctx.get('bkg')}")
            return False

        template_path = Path(__file__).parent.parent / "templates" / f"milestone_{template_type.lower()}.txt"
        tmpl = template_path.read_text(encoding="utf-8")
        filled = tmpl.format_map(_SafeDict(ctx))

        subject_line, _, body = filled.partition("\n\n")
        subject = subject_line.removeprefix("Subject:").strip()
        # Prefix for visibility
        subject = f"[AUTO] {subject}"

        mail = ol.CreateItem(0)
        mail.To = "; ".join(to_list)
        mail.Subject = subject
        mail.Body = body
        mail.Save()
        return True
    except Exception as e:
        _log(f"Draft creation failed: {e}")
        return False


# ── Helpers ─────────────────────────────────────────────────────────
class _SafeDict(dict):
    def __missing__(self, key):
        return "N/A"

def _queue_telegram(line: str): _telegram_lines.append(line)

def flush_telegram_summary():
    global _telegram_lines
    if _telegram_lines:
        msg = "📬 CNEE Milestone Summary\n\n" + "\n".join(_telegram_lines)
        _send_telegram(msg[:4000])
    _telegram_lines = []

# ... _log, _find_active_job, _crm_auto_notify, _lookup_cnee_emails,
#     _build_context, _already_notified, _write_state, _load_active_jobs,
#     _parse_job_date, _send_telegram ...


# ── CLI entry ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "eta-reminder":
        print(f"ETA-7 drafts created: {run_eta_reminder()}")
```

### File 2: `email_engine/templates/milestone_atd.txt`

```
Subject: Shipment Update — Vessel Departed | Bkg {bkg}

Dear {customer},

We're pleased to confirm your shipment has loaded on board:

  Booking:   {bkg}
  HBL:       {hbl}
  Vessel:    {vessel} ({carrier})
  Routing:   {pol} → {pod}
  ETD:       {etd}
  ETA:       {eta}

We will notify you again 7 days before arrival.

Best regards,
Nelson Huynh
Pudong Prime
```

### File 3: `email_engine/templates/milestone_eta7.txt`

(Similar pattern, ETA-7 wording)

### File 4: `tests/test_cnee_milestone.py` (~60 LOC)

```python
import pytest
from datetime import date, datetime
from email_engine.core.cnee_milestone import (
    extract_atd_date, _sanitize, _parse_date_flex,
)

# Date parsing — 5 formats
@pytest.mark.parametrize("s,expected", [
    ("26/04/2026", date(2026, 4, 26)),
    ("26-04-2026", date(2026, 4, 26)),
    ("26.04.2026", date(2026, 4, 26)),  # dot format (red-team D1)
    ("26/04/26",   date(2026, 4, 26)),
    ("99/99/9999", None),               # invalid
])
def test_parse_date_flex(s, expected):
    assert _parse_date_flex(s) == expected

# ATD sanity window (red-team B4)
def test_atd_outside_window_rejected():
    received = datetime(2026, 4, 20, 10, 0)
    text = "ATD: 01/01/2020"  # 6+ years before receive
    assert extract_atd_date(text, received) is None

# Sanitize injection (red-team A3)
@pytest.mark.parametrize("field,value,expected", [
    ("vessel", "MSC OSCAR", "MSC OSCAR"),
    ("vessel", "MSC\nWire payment to 1234", None),  # reject newline
    ("hbl", "PYTO26010027", "PYTO26010027"),
    ("hbl", "'; DROP TABLE;", None),  # reject invalid chars
    ("bkg", "x" * 50, None),  # reject over length
])
def test_sanitize(field, value, expected):
    assert _sanitize(field, value) == expected

# Blacklist pattern (verifies VESSEL CHANGE skip)
def test_blacklist_regex():
    from email_engine.core.cnee_milestone import BLACKLIST_REGEX
    assert BLACKLIST_REGEX.search("RE: VESSEL CHANGE NOTICE")
    assert BLACKLIST_REGEX.search("rvs etd //")
    assert not BLACKLIST_REGEX.search("ATD// normal mail")
```

### File 5: Hook wire-in `email_engine/core/shipment_brain.py`

After the per-email stage loop (verify actual location first!), add:

```python
# At END of the email processing loop, after all stages detected:
if any(s in {"ATD", "LOADED"} for s in stages):
    try:
        from email_engine.core.cnee_milestone import on_atd_detected
        on_atd_detected(mail, stages, ids, sender_smtp)
    except Exception as e:
        log.error("milestone hook failed: %s", e)

# At END of scan_and_update(), after all emails processed:
try:
    from email_engine.core.cnee_milestone import flush_telegram_summary
    flush_telegram_summary()
except Exception:
    pass
```

### File 6: Windows Task Scheduler

New task: `NelsonCNEEMilestoneETA7`
- Trigger: Daily 08:00
- Action: `C:/Users/Nelson/anaconda3/python -m email_engine.core.cnee_milestone eta-reminder`
- Condition: Run whether user logged in or not

### File 7: VBA Sync Button on ERP ribbon

Add to existing Pricing ribbon tab:

```vbnet
Public Sub Btn_SyncMilestones_OnAction(control As IRibbonControl)
    ' Read milestone_state.jsonl → update Active Jobs cols ATD/NOTIFIED_*
    ' Clear sidecar after successful write
    ' Called manually or auto via Workbook_Open
End Sub
```

## Todo

- [ ] Verify `shipment_brain.py` actual function signature + line numbers (read first!)
- [ ] Populate `OPS_ALLOWLIST` from audit report senders
- [ ] Write `cnee_milestone.py`
- [ ] Write 2 templates
- [ ] Write `test_cnee_milestone.py`
- [ ] Add hook call in `shipment_brain.py`
- [ ] Register Task Scheduler entry
- [ ] Add VBA Sync button
- [ ] Run `pytest tests/test_cnee_milestone.py` → all pass
- [ ] Manual test 1 job end-to-end

## Success Criteria

- [ ] All unit tests pass
- [ ] 1 real job ATD → draft appears with `[AUTO]` prefix, correct placeholder
- [ ] Kill switch file → scanner returns 0 immediately
- [ ] Spoofed auth header → reject logged
- [ ] Bulk mail (>3 Bkg) → reject, Telegram alert

## Risks

| Risk | Mitigation |
|------|-----------|
| OPS allowlist empty at first run | Start with 1 tested sender, grow from weekly digest |
| Auth-Results absent on internal mail | Fall back to stricter sender allowlist |
| JSON sidecar + VBA sync lag | Auto-flush on Workbook_Open event |

## Next Phase

Phase 03 — End-to-end verify + 1 week monitoring.
