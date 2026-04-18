# Phase 01 — Nelson Customer Sort

**Effort:** 4-6 hours (1 buổi)
**Priority:** HIGH — prerequisite cho Phase 02
**Status:** pending

## Context Links

- Brainstorm report: `../260416-email-nelson-solo-platform/reports/brainstorm-customer-sort-20260418.md`
- Existing framework: `email_engine/core/outlook_scanner.py`
- Customer data: `D:/OneDrive/NelsonData/email/customer_rules.json`

## Overview

Thêm 1 job mới `run_nelson_customer_sort` vào `outlook_scanner.py`, match 8 khách hiện có trong `customer_rules.json`, move email từ Inbox root vào folder `DIRECT/{Name}` hoặc `FW/{Name}` đã tồn tại trong Outlook.

Email mentee đã được sort bởi `run_mentee_classification`. Email còn lại trong Inbox (khách Nelson) → pass 2 sort vào folder riêng.

## Key Insights từ scout

- `rules.json` cho mentee có `"skip_routing": true` cho Nelson → email Nelson-facing không được move = đúng cơ chế, giờ thêm pass 2
- `customer_rules.json` đã có 8 khách với `seen_senders`, `email_domains`, `hbl_prefixes`, `bkg_prefixes`, `detection_rules.keywords` — đủ material match
- Outlook folders `DIRECT/`, `FW/`, `CNEE/` đã có sẵn (Sếp confirm) — chỉ cần navigate + move

## Requirements

### Functional
- F1: Load `customer_rules.json` từ OneDrive path
- F2: Scan Inbox root only (skip items đã trong sub-folder = idempotent)
- F3: Match priority: sender exact → domain → hbl/bkg prefix → company keyword
- F4: Move email vào `{type_folder}/{customer_name}/` (DIRECT hoặc FW)
- F5: Skip nếu folder đích không tồn tại (log warning, không crash)
- F6: Dry-run support (`--job nelson_customer_sort --dry-run`)
- F7: Telegram summary: "Sorted N emails: X DIRECT, Y FW"

### Non-functional
- N1: Idempotent — re-run không double-move
- N2: Graceful failure — 1 email lỗi không làm crash batch
- N3: Max 200 emails/run (reuse scanner.yaml `max_items`)
- N4: Respect `processed_category = "Nelson-Scanned"` để dedup với inbox_scanner v3

## Architecture

```
Task Scheduler NelsonUnifiedScanner (existing, 30min)
    ↓
outlook_scanner.py main()
    ├── run_mentee_classification(config)   ← existing
    └── run_nelson_customer_sort(config)    ← NEW
         ├── load_customer_rules()          ← reads customer_rules.json
         ├── scan_inbox_root()              ← Outlook COM, skip sub-folders
         ├── match_customer(msg, rules)     ← priority cascade
         ├── move_to_folder(msg, target)    ← Outlook MoveTo()
         └── collect_telegram_summary()
```

## Related Code Files

### Modify
- `email_engine/core/outlook_scanner.py` — thêm job runner + map entry
- `email_engine/core/scan_config.json` — thêm job config block (nếu chưa có)

### Create
- `email_engine/core/nelson_customer_sort.py` — core logic (matcher + mover)

### Read (reference)
- `email_engine/core/main.py` — pattern Outlook COM navigation
- `email_engine/core/outlook_scanner.py` — job runner pattern
- `D:/OneDrive/NelsonData/email/customer_rules.json` — 8 khách

## Implementation Steps

### Step 1 — Scaffold `nelson_customer_sort.py`
```python
# email_engine/core/nelson_customer_sort.py
from pathlib import Path
import json
import re
import win32com.client

RULES_PATH = Path("D:/OneDrive/NelsonData/email/customer_rules.json")
TYPE_TO_FOLDER = {"DIRECT": "DIRECT", "FWD": "FW"}

def load_rules():
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))

def match_customer(msg, rules):
    """Return (customer_id, type) or (None, None)."""
    sender = (msg.SenderEmailAddress or "").lower()
    subject = msg.Subject or ""
    body = msg.Body or ""

    for cid, cust in rules["customers"].items():
        # 1. sender exact
        if sender in [s.lower() for s in cust.get("seen_senders", [])]:
            return cid, cust["type"]
        # 2. domain
        domain = sender.split("@")[-1] if "@" in sender else ""
        if domain in [d.lower() for d in cust.get("email_domains", [])]:
            return cid, cust["type"]
        # 3. prefix in subject/body
        text = f"{subject} {body[:500]}"
        for prefix in cust.get("hbl_prefixes", []) + cust.get("bkg_prefixes", []):
            if re.search(rf"\b{re.escape(prefix)}\d+\b", text, re.I):
                return cid, cust["type"]

    # 4. detection_rules.keywords fuzzy fallback
    for cat_rules in rules["detection_rules"].values():
        for kw in cat_rules.get("keywords", []):
            if kw.lower() in (subject + body[:500]).lower():
                # find matching customer
                for cid, cust in rules["customers"].items():
                    if kw.lower() in cid.lower() or kw.lower() in cust.get("notes", "").lower():
                        return cid, cust["type"]
    return None, None
```

### Step 2 — Mover function
```python
def move_to_folder(msg, type_type: str, customer_name: str, root_folder, dry_run: bool):
    folder_path = f"{TYPE_TO_FOLDER[type_type]}/{customer_name}"
    target = navigate_folder(root_folder, folder_path)
    if target is None:
        log.warning(f"Folder not found: {folder_path}")
        return False
    if dry_run:
        log.info(f"[DRY] Would move '{msg.Subject[:60]}' -> {folder_path}")
        return True
    msg.Move(target)
    return True
```

### Step 3 — Main loop
```python
def run(dry_run: bool = False) -> dict:
    rules = load_rules()
    outlook = win32com.client.Dispatch("Outlook.Application")
    ns = outlook.GetNamespace("MAPI")
    inbox = ns.GetDefaultFolder(6)
    root = inbox.Parent  # mailbox root contains DIRECT/, FW/, CNEE/

    moved = {"DIRECT": 0, "FW": 0, "SKIPPED": 0}
    for msg in list(inbox.Items)[:200]:
        if msg.Class != 43:  # olMail
            continue
        cid, ctype = match_customer(msg, rules)
        if cid is None:
            continue
        if move_to_folder(msg, ctype, cid, root, dry_run):
            moved[TYPE_TO_FOLDER[ctype]] += 1
    return moved
```

### Step 4 — Wire vào outlook_scanner.py
```python
# outlook_scanner.py — add to _JOB_RUNNERS
def run_nelson_customer_sort(config, dry_run=False):
    from nelson_customer_sort import run
    return run(dry_run=dry_run)

_JOB_RUNNERS["nelson_customer_sort"] = run_nelson_customer_sort
```

### Step 5 — Register config block
```json
// scan_config.json
{
  "nelson_customer_sort": {
    "description": "Move khách Nelson emails to DIRECT/FW folders",
    "timeout_seconds": 120,
    "telegram_on_summary": true
  }
}
```

### Step 6 — Test dry-run
```bash
python email_engine/core/outlook_scanner.py --job nelson_customer_sort --dry-run
```
Expect log: `[DRY] Would move 'FW: Booking SIRI1234' -> FW/SIRI` etc.

### Step 7 — Enable live + verify 1 cycle
Remove `--dry-run`, run once, open Outlook → check folders `DIRECT/Nafood/`, `FW/PANDA/` etc có email mới.

## Todo List

- [ ] Create `email_engine/core/nelson_customer_sort.py` với 4 functions (load_rules, match_customer, move_to_folder, run)
- [ ] Add helper `navigate_folder(root, path)` — đệ quy tìm folder theo path
- [ ] Wire `run_nelson_customer_sort` vô `outlook_scanner.py` `_JOB_RUNNERS`
- [ ] Add config block to `scan_config.json`
- [ ] Test dry-run, verify log output matches expected
- [ ] Run live 1 cycle, manually verify 3-5 folders có email đúng
- [ ] Add to Task Scheduler NelsonUnifiedScanner job list (nếu chưa auto-pickup từ scanner_config)
- [ ] Update memory: `project-email-dashboard-v5-research.md` với section Customer Sort shipped

## Success Criteria

- ✅ Dry-run log hiển thị ≥80% email test được match đúng khách + folder đích
- ✅ Live run 1 cycle: ≥5 email thực được move vào 3+ folders khác nhau
- ✅ Zero crash khi gặp email edge case (no sender, empty body, attachment-only)
- ✅ Telegram summary arrives sau khi task chạy xong
- ✅ False positive ≤1% sau 1 tuần observation

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Folder name case mismatch ("Direct" vs "DIRECT") | MED | HIGH | Case-insensitive folder lookup |
| Outlook COM timeout với 200 email | LOW | MED | Batch size 100, retry logic |
| False positive move (email ngân hàng match "nafood" keyword) | MED | MED | Keyword match phải kèm sender domain check |
| customer_rules.json corrupt / missing | LOW | HIGH | Fallback: skip job gracefully, log error, Telegram alert |
| Email đang trong Drafts bị move | LOW | HIGH | Filter `msg.Sent == True` only |

## Security Considerations

- No new credentials
- No new network calls
- Respects existing Outlook ACL
- Dry-run mandatory trước live

## Next Steps

Phase 01 ship → Phase 02 Shipment Extractor có thể scan sub-folder DIRECT/FW thay vì Inbox root → data cleaner + customer_id đã sẵn.

**Status:** ready to code tomorrow morning
