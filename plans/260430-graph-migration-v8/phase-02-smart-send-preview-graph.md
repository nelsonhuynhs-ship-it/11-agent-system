---
phase: 2
title: Smart Send Preview qua Graph Draft + Web Outlook URL
effort_mm: 4h
depends: []
blocks: []
---

# Phase 2 — Smart Send Preview Migration

## Goal

Thay Outlook desktop COM dispatch (đang chết) bằng Graph draft API + web Outlook URL iframe. Khi Sếp click "Smart Send" toggle ON → preview email VIP đầu tiên hiển thị trong dashboard tab → confirm → send.

## Current Broken Flow

```
[Click Smart Send]
   ↓
smartSendFlow() JS @ email-dashboard.html:473
   ↓
COM dispatch → Outlook.Application.CreateItem()  ← CHẾT 04/27
   ↓
[Email VIP đầu tiên mở trong Outlook desktop]  ← KHÔNG XẢY RA
   ↓
[Sếp review + Confirm Send All]  ← STUCK
```

## New Flow (Graph)

```
[Click Smart Send toggle ON + Send button]
   ↓
POST /api/smart-send/preview   ← NEW endpoint
   ↓
Server: build email VIP đầu tiên (subject, html, signature, logo)
   ↓
Graph: POST /me/messages (create draft, isDraft=true)
   ↓
Return: {draft_id, web_outlook_url, total_to_send}
   ↓
Frontend: hiển thị iframe https://outlook.office.com/mail/drafts/{id}
   OR render preview HTML local trong tab
   ↓
[Sếp review + Confirm Send All button]
   ↓
POST /api/smart-send/confirm {draft_id, send_all_contacts: [...]}
   ↓
Server: 
  1. POST /me/messages/{draft_id}/send  (gửi VIP đầu)
  2. Loop bulk send remaining contacts qua _send_email_html()
   ↓
Return: {campaign_id, total, sent}
```

## Files Create / Modify

### CREATE
- `email_engine/api/routes/smart_send_router.py` — 2 endpoint mới (preview, confirm)

### MODIFY
- `email_engine/web_server.py` — mount smart_send_router
- `plans/visuals/email-dashboard.html` — JS `smartSendFlow()` rewrite:
  - Bỏ COM logic
  - Call `/api/smart-send/preview` → render iframe hoặc HTML preview pane
  - "Confirm Send All" button → call `/api/smart-send/confirm`

### KEEP
- `senders/graph_sender.py` — đã work (Sprint 1)
- Backend bulk send logic `_do_send_built_emails()` — KEEP

## Acceptance Criteria

- [ ] AC1: Click Smart Send → preview tab hiện trong dashboard ≤ 3s
- [ ] AC2: Preview hiển thị đúng email VIP đầu tiên (subject + body + signature + logo correct)
- [ ] AC3: Có 2 nút: "Confirm Send All" + "Cancel"
- [ ] AC4: Cancel → DELETE draft, return dashboard
- [ ] AC5: Confirm → email VIP đầu được send + N email batch đi theo, log đầy đủ
- [ ] AC6: KHÔNG còn COM dispatch trong smart send path
- [ ] AC7: 0 ImportError nếu Outlook desktop tắt máy

## Decision Point: iframe vs HTML local

**Option A — iframe web Outlook**: `<iframe src="https://outlook.office.com/mail/drafts/{id}">` — UI giống Outlook 100%, nhưng cần Sếp đã sign-in web Outlook trong browser session.

**Option B — Local HTML render**: render draft `body.content` (HTML từ Graph) trong tab dashboard. Đơn giản hơn, không phụ thuộc browser session.

→ **Em recommend B** (KISS) — Sếp đã ở dashboard rồi, không cần switch context.

## Done When

- [ ] All 7 AC pass
- [ ] Sếp test 5 lần liên tiếp Smart Send work
- [ ] No regression: bulk send 700 vẫn ổn
