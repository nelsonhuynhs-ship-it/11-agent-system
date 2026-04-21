# Phase 02 — Composer Module + Templates

**Effort:** 1.5h
**Priority:** HIGH
**Status:** pending
**Depends on:** Phase 01

## Overview

Build `cnee_milestone_composer.py` — core engine to compose EN draft email + create Outlook Draft. Standalone module, testable in isolation.

## Files Created

| File | Purpose |
|------|---------|
| `email_engine/core/cnee_milestone_composer.py` | NEW — main composer |
| `email_engine/templates/milestone_atd.txt` | NEW — ATD template EN |
| `email_engine/templates/milestone_eta7.txt` | NEW — ETA-7 template EN |

## API Contract

```python
# cnee_milestone_composer.py

from dataclasses import dataclass
from enum import Enum

class MilestoneType(Enum):
    ATD = "ATD"
    ETA_7 = "ETA-7"

@dataclass
class MilestoneContext:
    bkg: str
    customer: str
    hbl: str
    vessel: str
    carrier: str
    pol: str
    pod: str
    etd: str
    eta: str
    milestone_date: str  # ATD date or ETA date

def compose_draft(
    milestone: MilestoneType,
    ctx: MilestoneContext,
    cnee_email: str,
    dry_run: bool = False,
) -> dict:
    """
    Returns:
        {
            "success": bool,
            "draft_id": str | None,  # Outlook EntryID
            "subject": str,
            "body": str,
            "error": str | None,
        }
    """
```

## Template Format

### milestone_atd.txt
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

### milestone_eta7.txt
```
Subject: Arriving in 7 Days — Please Prepare | Bkg {bkg}

Dear {customer},

Your shipment is expected to arrive at {pod} in 7 days:

  Booking:   {bkg}
  HBL:       {hbl}
  Vessel:    {vessel}
  ETA:       {eta}

Please prepare for pickup. Let me know if you need any documents.

Best regards,
Nelson Huynh
Pudong Prime
```

## Email Lookup Logic

```python
def lookup_cnee_email(customer: str, bkg: str) -> str | None:
    # 1. Try CRM sheet
    crm = load_crm()
    entry = crm.get(customer.upper())
    if entry and entry.get("EMAIL"):
        return entry["EMAIL"]

    # 2. Fallback Active Jobs EMAIL col
    job = find_job_by_bkg(bkg)
    if job and job.get("EMAIL"):
        return job["EMAIL"]

    # 3. None found
    return None
```

## Outlook Draft Creation

```python
import win32com.client

def create_outlook_draft(to: str, subject: str, body: str) -> str:
    ol = win32com.client.Dispatch("Outlook.Application")
    mail = ol.CreateItem(0)  # olMailItem
    mail.To = to
    mail.Subject = subject
    mail.Body = body
    # NOT .Send() — keep as Draft
    mail.Save()
    return mail.EntryID
```

## Implementation Steps

1. Create `email_engine/templates/` dir + 2 template files
2. Write `cnee_milestone_composer.py`:
   - Load templates
   - Placeholder substitution (str.format_map with safe defaults)
   - CRM + Active Jobs reader functions
   - Outlook COM draft creator
3. Unit test: compose ATD + ETA-7 with mock data → verify draft appears in Outlook Drafts
4. Run test với 1 job thật trong Active Jobs (NOTIFY chưa bật toàn local test)

## Todo List

- [ ] Create templates folder + 2 EN templates
- [ ] Write composer module
- [ ] CRM email lookup function
- [ ] Active Jobs fallback lookup
- [ ] Outlook COM Draft creation
- [ ] Unit test with mock data
- [ ] Manual test với 1 job thật

## Success Criteria

- [ ] Compose ATD draft → appears trong Outlook Drafts với đúng To/Subject/Body
- [ ] Placeholder điền chính xác từ Active Jobs data
- [ ] Email lookup fallback hoạt động
- [ ] Dry-run mode trả về body EN mà không tạo draft thực

## Risks

| Risk | Mitigation |
|------|-----------|
| Outlook không chạy khi script gọi | Try-except + log, retry 1 lần |
| Template field thiếu placeholder | Use `format_map(defaultdict(lambda: "N/A"))` |
| CRM sheet lock (Excel mở) | Read via openpyxl (không lock) hoặc Excel COM read-only |
| Placeholder injection (XSS-like) | Plain text body, không HTML |

## Next Phase

Phase 03 — Hook composer vào shipment_brain khi detect ATD.
