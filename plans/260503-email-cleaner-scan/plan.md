---
title: "Email Intelligence — Scan, Classify, Route, Delete"
status: completed
priority: P1
effort: "6h"
created: 2026-05-03
completed: 2026-05-03
---

# Plan: Email Intelligence — Scan, Classify, Route, Delete

## Context

**Hệ thống hiện có:**
- `reply_detector.py` — scan Outlook Inbox, match replies vs CNEE list
- `handlers.py` — `handle_bounce()`, `handle_real_reply()`, `handle_auto_reply()`, `_move_to_deleted()` (move NDR → Deleted Items)
- `process_reply.py` — intent classifier (booking/negotiating/price_inquiry/objection/gratitude), scan Inbox + TEAM SUNNY folder, assign tiers, export to intel.db
- Dashboard V7 `viewCleaner` — sẵn UI stats + results table nhưng `revalidateEmails()` mock

**3 vấn đề cần giải quyết:**
1. **Delete bad emails** — bounce/error trong INBOX + row trong Excel
2. **Reply routing intelligence** — khi reply đề cập "gửi cho A/B phòng logistic" hoặc "cc thêm người phụ trách khác"
3. **Dashboard review UI** — Nelson duyệt routing suggestions trước khi apply

---

## Phase 1 — Bounce + Error Email Cleanup (INBOX + Excel)
**Status:** ✅ DONE (2026-05-03) | **Effort:** 2h

### 1A. Scan INBOX for bounce/error emails
Dùng `handlers.py:_move_to_deleted()` đã có, nhưng thêm endpoint để Nelson trigger thủ công:

```
GET /api/cleaner/scan-inbox
→ Scan INBOX (Outlook COM) cho NDR/bounce emails
→ Move to Deleted Items
→ Trả về: { moved: N, bounce_emails: [...] }
```

Tìm bounce emails trong INBOX bằng subject/body pattern:
- Subject chứa: "undelivered", "delivery failed", "returned", "bounce", "NDR"
- Body chứa: DSN format (Final-Recipient, Diagnostic-Code)

### 1B. Scan Excel master cho bad emails
```
GET /api/cleaner/scan-master
→ Đọc contact_unified_v7.xlsx CNEE sheet
→ Apply classifiers:
```

| Code | Pattern |
|------|---------|
| `PREFIX_CORRUPT` | local part bắt đầu `me.`, `te.`, `em.` |
| `DISPOSABLE_DOMAIN` | domain: `mailinator.com`, `tempmail.com`, vv. |
| `DOMAIN_TYPO` | `gmal.com`, `gmial.com`, `yahooo.com` |
| `SYNTAX_INVALID` | không có `@`, ký tự lạ |
| `DUPLICATE` | email trùng trong master file |

### 1C. Delete bad rows from Excel
```
POST /api/cleaner/delete-rows
Body: { emails: ["a@b.com", ...] }
→ Backup: copy sheet → data/cleaner_backup_YYYYMMDD.xlsx
→ Xóa rows khỏi CNEE sheet
→ Response: { deleted: N, remaining: M }
```

**Safety:** Backup trước. Không xóa email đang cooldown (LAST_SENT_EMAIL < 14 ngày).

---

## Phase 2 — Reply Routing Intelligence (CC + Forward Detection)
**Status:** ✅ DONE (2026-05-03) | **Effort:** 2.5h

### 2A. Parse reply body cho routing signals

Cập nhật `handlers.py:handle_real_reply()` hoặc thêm vào `llm_extract_reply.py`:

**Signal 1: CC Suggestion** — khách reply nhắc nên CC thêm người khác
```python
# Pattern examples trong reply body:
# "pls cc our logistics person: john@company.com"
# "adding my colleague Mary on this"
# "Cc: shipping@company.com"
# "my shipping manager should be in the loop"

CC_PATTERNS = [
    r"cc[:\s]+([^\s]+@[^\s]+)",          # cc: john@x.com
    r"cc[:\s]+([A-Z][a-z]+ [A-Z][a-z]+)", # cc: John Smith
    r"should be in the loop[:\s]+([^\s]+@[^\s]+)",
    r"add.+on this[:\s]+([^\s]+@[^\s]+)",
    r"my colleague[:\s]+([^\s]+@[^\s]+)",
    r"copy.*([^\s]+@[^\s]+)",
]
```

**Signal 2: Forward/Routing Suggestion** — khách bảo gửi cho người khác
```python
# Pattern examples:
# "pls send to our freight forwarder: ff@company.com"
# "contact our logistics dept at logistics@company.com"
# "send to attention: john@company.com"
# "for booking pls email: booking@company.com"
# "our shipping in charge is mary@company.com"

FORWARD_PATTERNS = [
    r"send to[:\s]+([^\s]+@[^\s]+)",
    r"contact[:\s].*at[:\s]+([^\s]+@[^\s]+)",
    r"attention[:\s]+([^\s]+@[^\s]+)",
    r"forward.*to[:\s]+([^\s]+@[^\s]+)",
    r"email.*at[:\s]+([^\s]+@[^\s]+)",
    r"(?:logistics|purchasing|ops|booking).*@",  # department catch-all
]
```

### 2B. Store routing signals
Thêm vào `intel.db email_events` hoặc `customer_rules.json`:

```json
{
  "cc_suggestions": [
    { "email": "john@company.com", "context": "logistics person", "source_email": "original@cnee.com", "timestamp": "2026-05-03" }
  ],
  "forward_suggestions": [
    { "email": "booking@company.com", "context": "booking dept", "source_email": "original@cnee.com", "timestamp": "2026-05-03" }
  ]
}
```

### 2C. API endpoints
```
GET /api/routing/suggestions
→ Trả về list CC + forward suggestions chưa review

POST /api/routing/approve
Body: { source_email: "a@b.com", suggested_email: "c@d.com", type: "cc|forward" }
→ Cập nhật contact profile trong Excel (thêm CC contact)
→ Đánh dấu đã approve

POST /api/routing/reject
Body: { source_email, suggested_email, reason: "..." }
→ Bỏ suggestion, không apply
```

---

## Phase 3 — Dashboard UI: Cleaner Tab + Routing Review
**Status:** ✅ DONE (2026-05-03) | **Effort:** 1.5h

### 3A. Cleaner Tab (mở rộng từ viewCleaner có sẵn)
```javascript
// Gọi GET /api/cleaner/scan-inbox + /api/cleaner/scan-master
// Hiển thị:
//   - Tabs: [Bad Emails] [Routing Suggestions]
//   - Bad Emails: email, issue, suggested fix, checkbox → Delete
//   - Routing Suggestions: from, suggests CC/forward to, context, [Approve] [Reject]
```

### 3B. New tab: Routing Review
```
<!-- Thêm vào sidebar nav -->
<div class="nav-item" data-view="viewRouting">
  <div class="nav-icon">🧭</div>
  <div class="nav-label">Routing</div>
</div>

<!-- View mới trong dashboard -->
<section class="view" id="viewRouting">
  <h2>Routing Intelligence</h2>
  <p>Contacts suggested CC or forwarding changes based on reply analysis</p>
  <table>
    <thead><tr><th>From</th><th>Type</th><th>Suggested Contact</th><th>Context</th><th>Actions</th></tr></thead>
    <tbody id="routingBody"></tbody>
  </table>
</section>
```

---

## Related Files
- `email_engine/core/handlers.py` — thêm CC/forward parsing, mở rộng `handle_real_reply()`
- `email_engine/core/llm_extract_reply.py` — thêm `extract_routing_signals()`
- `email_engine/web_server.py` — thêm routes: `/api/cleaner/*`, `/api/routing/*`
- `email_engine/data/customer_rules.json` — lưu CC + forward suggestions
- `plans/visuals/email-dashboard.html` — thêm viewRouting + mở rộng viewCleaner

## Success Criteria
- [ ] Scan INBOX → move ≥1 NDR to Deleted Items
- [ ] Scan master → classify PREFIX_CORRUPT, DISPOSABLE, TYPO, DUPLICATE
- [ ] Delete rows → backup trước, verify row count giảm
- [ ] Reply parsing → detect CC patterns và forward patterns
- [ ] Routing suggestions → lưu vào customer_rules.json
- [ ] Dashboard → approve/reject routing suggestions

## Risk
- CC email regex có thể parse sai → flag là "pending review", không auto-apply
- Excel writeback corruption → backup + verify row count sau mỗi lần xóa
- Forward suggestion cần Nelson confirm trước khi tạo contact mới
