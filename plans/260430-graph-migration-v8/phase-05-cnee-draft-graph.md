---
phase: 5
title: CNEE Milestone Draft Migration
effort_mm: 2h
depends: []
blocks: []
---

# Phase 5 — CNEE Milestone Draft

## Goal

Replace COM `Outlook.Application.CreateItem(0)` trong `core/cnee_milestone.py` bằng Graph `POST /me/messages` (create draft). Memory ghi đây là TODO #8 từ Sprint 1, chưa làm.

## Files Modify

- `email_engine/core/cnee_milestone.py` — line 603-652 (Draft creation block):
  - Bỏ `import win32com`
  - Replace `outlook.CreateItem(0)` + `.Save()` bằng Graph create draft
- `email_engine/core/cnee_milestone.py` — line 44 TODO weekly digest (nếu cùng pattern)

## New Logic (pseudo)

```python
def create_cnee_draft(cnee_email: str, subject: str, body_html: str, attachments=None) -> str:
    """Create draft trong Drafts folder qua Graph. Return draft message ID."""
    payload = {
        "subject": subject,
        "body": {
            "contentType": "html",
            "content": body_html
        },
        "toRecipients": [{"emailAddress": {"address": cnee_email}}],
        "isDraft": True
    }
    
    if attachments:
        payload["attachments"] = [
            {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": a["filename"],
                "contentBytes": base64.b64encode(a["data"]).decode()
            } for a in attachments
        ]
    
    resp = graph_client.post("/me/messages", json=payload)
    draft_id = resp["id"]
    log.info(f"CNEE draft created: {draft_id} for {cnee_email}")
    return draft_id
```

## Acceptance Criteria

- [ ] AC1: Create draft với subject + html body + 1 recipient → draft xuất hiện trong web Outlook Drafts folder
- [ ] AC2: Attachment work (PDF rate sheet)
- [ ] AC3: KHÔNG còn `import win32com` trong cnee_milestone.py
- [ ] AC4: Backward compat — function signature giữ nguyên (caller không break)

## Done When

- [ ] 4 AC pass
- [ ] Test 3 CNEE draft cycle
