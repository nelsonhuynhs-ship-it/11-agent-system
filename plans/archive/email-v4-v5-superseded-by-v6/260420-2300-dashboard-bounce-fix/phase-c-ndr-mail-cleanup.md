# Phase C — NDR Mail Cleanup

**Effort:** 0.5h
**Priority:** MEDIUM (UX — Inbox clean)
**Status:** pending
**Depends on:** none (independent of A+B)

## Overview

Sau khi `handle_bounce()` ghi log + update master thành công → **move NDR mail vào Deleted Items**. Outlook tự purge theo Office 365 retention (30 ngày default).

## Files Modified

### `email_engine/scanner/handlers.py` — `handle_bounce()` add move step

```python
_OUTLOOK_DELETED_ID = 3  # olFolderDeletedItems

def _move_to_deleted(item) -> bool:
    """Move Outlook MailItem to Deleted Items folder. Returns True on success."""
    try:
        import win32com.client
        outlook = win32com.client.Dispatch("Outlook.Application")
        ns = outlook.GetNamespace("MAPI")
        deleted_folder = ns.GetDefaultFolder(_OUTLOOK_DELETED_ID)
        item.Move(deleted_folder)
        return True
    except Exception as exc:
        log.warning(f"Could not move NDR to Deleted: {exc}")
        return False


def handle_bounce(item: Any, bounced_email: str) -> None:
    """Bounce / DSN handler — logs event, updates master, then moves to Deleted Items."""
    body = _safe_attr(item, "Body")
    subject = _safe_attr(item, "Subject")

    target = (bounced_email or extract_bounced_email(body) or "").lower().strip()
    if not target:
        log.warning("handle_bounce: could not extract recipient; subject=%r", subject[:120])
        return

    severity = classify_bounce_severity(body)

    _log_event(
        "BOUNCE",
        email=target,
        severity=severity,
        subject=subject,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    decision = _evaluate_event("BOUNCE", email=target, severity=severity) or {}
    _update_master(
        target,
        {
            "EMAIL_STATUS": "HARD_BOUNCE" if severity == "HARD" else "SOFT_BOUNCE",
            "LAST_BOUNCE_AT": datetime.now(timezone.utc).isoformat(),
            "LAST_BOUNCE_SEVERITY": severity,
            **({"TIER": decision["tier"]} if decision.get("tier") else {}),
        },
    )
    
    # 🆕 Move to Deleted Items (Inbox cleanup)
    if _move_to_deleted(item):
        log.info(f"BOUNCE logged + moved to Deleted: {target} ({severity})")
    else:
        log.info(f"BOUNCE logged (move failed, remains in Inbox): {target}")
```

## Optional: also move UNSUBSCRIBE + AUTO_REPLY to Deleted?

**Decision: NO for now.**
- AUTO_REPLY can contain useful info (OOO dates, alternate contact)
- UNSUBSCRIBE needs manual review sometimes (legitimate vs test)
- Only BOUNCE is pure noise — auto-move OK

Can add later if Nelson requests.

## Implementation Steps

1. Add `_move_to_deleted()` helper function to `handlers.py`
2. Add call inside `handle_bounce()` AFTER `_update_master` succeeded
3. Test: run scanner on folder with 1 NDR mail → verify it moved to Deleted Items
4. Run full `run_scan(force=True, hours=720)` → check Inbox NDR count → should drop to 0

## Success Criteria

- [ ] After scan, 0 NDR mails remain in Inbox (within 30d window scanned)
- [ ] Deleted Items has +6 NDR mails
- [ ] If move fails (rare — Outlook locked), log warning but event still logged
- [ ] Nelson can Ctrl+Z in Deleted Items to restore if needed

## Risks

| Risk | Mitigation |
|------|-----------|
| Move during Outlook busy | Try-except, continue. Item still tagged Nelson-Scanned. |
| Accidental move of non-bounce | Only `handle_bounce` calls it — label must == BOUNCE |
| User wants audit trail | Deleted Items retention 30d — enough window to investigate |

## Post-Phase

- [ ] Update `docs/SYSTEM_STANDARDS.md` with NDR cleanup behavior
- [ ] Document Outlook Deleted Items retention setting trong memory

## Testing Script

```python
# scripts/_verify_ndr_cleanup.py
import win32com.client
outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
inbox = outlook.GetDefaultFolder(6)
deleted = outlook.GetDefaultFolder(3)

def count_ndr(folder):
    n = 0
    for msg in folder.Items:
        try:
            if msg.Class != 43: continue
            subj = (msg.Subject or '').lower()
            if any(kw in subj for kw in ['undeliverable', 'delivery status', 'delivery failure']):
                n += 1
        except Exception: continue
    return n

print(f"Inbox NDR: {count_ndr(inbox)}")
print(f"Deleted NDR: {count_ndr(deleted)}")
```

Expected after run_scan(force=True, hours=720):
- Inbox NDR: 0 (hoặc giảm từ 6 → 0)
- Deleted NDR: +6
