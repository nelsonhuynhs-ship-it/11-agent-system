# Phase 03 — ATD Hook into shipment_brain

**Effort:** 1.5h
**Priority:** HIGH
**Status:** pending
**Depends on:** Phase 02

## Overview

Extend `shipment_brain.py` to trigger composer when ATD detected. Add filter logic + dedup. NOT modify existing lifecycle detection — only ADD hook at end.

## Files Modified

| File | Change |
|------|--------|
| `email_engine/core/shipment_brain.py` | Add hook function + call at end of scan loop |
| `email_engine/core/cnee_milestone_composer.py` | Called from hook |

## Integration Point

In `shipment_brain.py` scan loop, after existing stage detection:

```python
# EXISTING CODE (line ~480-520):
stages = detect_stages(text)
# ... update shipment_state.json ...

# 🆕 NEW HOOK (append at end of process_email):
if "ATD" in stages or "LOADED" in stages:
    from email_engine.core.cnee_milestone_hook import on_atd_detected
    on_atd_detected(
        email_item=item,
        identifiers=ids,
        sender_domain=sender_domain,
        detected_text=text,
    )
```

## Hook Module

`email_engine/core/cnee_milestone_hook.py`:

```python
ALLOWED_DOMAINS = {"pudongprime.vn"}
NELSON_EMAILS = {"nelson@pudongprime.vn"}  # skip self-send
BLACKLIST_PATTERNS = [
    r"VESSEL\s+CHANGE",
    r"RVS\s+ETD",
    r"REVISED\s+ETD",
    r"CHANGE\s+VESSEL",
    r"NEW\s+ETD",
]

def on_atd_detected(email_item, identifiers, sender_domain, detected_text):
    # 1. Filter sender domain
    if sender_domain not in ALLOWED_DOMAINS:
        return
    sender = get_sender_smtp(email_item)
    if sender in NELSON_EMAILS:
        return  # skip self-send

    # 2. Blacklist check
    for pat in BLACKLIST_PATTERNS:
        if re.search(pat, detected_text, re.I):
            log.info("Skipped: blacklisted pattern matched")
            return

    # 3. Extract ATD date from body
    atd_date = extract_atd_date(detected_text)
    if not atd_date:
        log.warning("ATD detected but no date parsed, skip")
        return

    # 4. Match Bkg with Active Jobs
    for bkg in identifiers.get("BKG", []):
        job = find_active_job(bkg)
        if not job:
            continue  # silent skip

        # 5. Check CRM.AUTO_NOTIFY
        customer = job["CUSTOMER"]
        if not crm_auto_notify_enabled(customer):
            continue

        # 6. Dedup check
        last_notified = job.get("LAST_NOTIFIED", "")
        if "ATD" in last_notified:
            continue

        # 7. Get CNEE email
        cnee_email = lookup_cnee_email(customer, bkg)
        if not cnee_email:
            telegram_alert(f"⚠ Missing CNEE email for {customer} / {bkg}")
            continue

        # 8. Compose draft
        ctx = build_milestone_context(job, atd_date)
        result = compose_draft(MilestoneType.ATD, ctx, cnee_email)

        if result["success"]:
            # 9. Update Active Jobs
            update_active_job(bkg, {
                "ATD": atd_date,
                "LAST_NOTIFIED": f"ATD {atd_date}",
            })
            telegram_alert(f"✅ Draft ATD ready: {customer} / {bkg}")
        else:
            telegram_alert(f"❌ Draft failed: {result['error']}")
```

## ATD Date Extraction

```python
_DATE_PATTERNS = [
    r"ATD\s*[:=]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
    r"vessel\s+departed\s+on\s+(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
    r"loaded\s+on\s+board\s+(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
    r"\bATD\b.{0,20}(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
]

def extract_atd_date(text: str) -> str | None:
    for pat in _DATE_PATTERNS:
        m = re.search(pat, text, re.I)
        if m:
            return normalize_date(m.group(1))  # → YYYY-MM-DD
    return None
```

## Implementation Steps

1. Create `cnee_milestone_hook.py` with full logic
2. Add helper: `get_sender_smtp(email_item)` (already exists in shipment_brain — reuse)
3. Add helper: `find_active_job(bkg)` — read Active Jobs by Bkg
4. Add helper: `crm_auto_notify_enabled(customer)` — read CRM
5. Add helper: `update_active_job(bkg, updates)` — write back to xlsm
6. Modify `shipment_brain.py` — add hook call at end of `process_email`
7. Test: forward 1 mail OPS có ATD → run scanner → verify draft appears

## Todo List

- [ ] Write `cnee_milestone_hook.py`
- [ ] Implement sender filter + blacklist
- [ ] Implement ATD date extraction (regex + normalize)
- [ ] Implement Active Jobs reader/writer
- [ ] Implement CRM auto_notify checker
- [ ] Modify shipment_brain.py — add hook call
- [ ] Test with forwarded OPS mail
- [ ] Verify dedup (run scanner 2 lần → không tạo 2 draft)

## Success Criteria

- [ ] Mail OPS ATD → tạo draft EN trong Outlook
- [ ] Mail OPS "VESSEL CHANGE" → skip (log reason)
- [ ] Cùng mail run 2 lần → chỉ 1 draft (dedup hoạt động)
- [ ] Customer không có CRM.AUTO_NOTIFY → skip
- [ ] CNEE email rỗng → Telegram alert

## Risks

| Risk | Mitigation |
|------|-----------|
| shipment_brain side-effect breaking | Hook chạy ở CUỐI loop, try-except wrap toàn bộ |
| Date format edge case (26/04 vs 04/26) | Assume dd/mm (Vietnam convention), log Telegram nếu year ambiguous |
| xlsm write lock khi Nelson đang mở | Queue write, retry, hoặc write to `.pending.jsonl` rồi flush sau |
| Multi-Bkg trong 1 mail | Loop all Bkg, process từng cái riêng |

## Next Phase

Phase 04 — ETA-7 daily reminder (new scanner job).
