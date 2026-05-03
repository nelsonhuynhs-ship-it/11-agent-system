# bounce_handler.py Phase 6 — Rewrite → Outlook COM

**Applied: 5 fixes | Deferred: 0**

## Changes Applied

| # | Change | Status |
|---|--------|--------|
| 1 | NEW `parse_dsn_from_outlook_item(item)` — extracts body/Subject/ReceivedTime from Outlook MailItem, calls `_parse_multipart_dsn` or `_fallback_subject_parse`, populates `received_at` | ✅ |
| 2 | DELETE `parse_dsn_from_graph_msg(msg: dict)` — removed entirely | ✅ |
| 3 | UPDATE `handle_bounce(graph_msg: dict)` → `handle_bounce(item)` — parameter renamed, calls `parse_dsn_from_outlook_item`, log uses subject not msg id, removed `receivedDateTime` ref, docstring updated (no Graph/webhook/NDR refs) | ✅ |
| 4 | REWRITE `scan_bounces()` — now uses Outlook COM (`pythoncom.CoInitialize()` → `win32com.client.Dispatch("Outlook.Application")` → `ns.GetDefaultFolder(6)`), iterates inbox items, filters on `NDR_SUBJECTS` keywords | ✅ |
| 5 | UPDATE module docstring — removed Phase 3 header, Graph/webhook description, `handle_bounce(graph_message_dict)` usage line | ✅ |
| 6 | `update_cnee_master()` stub — kept as-is | ✅ (no-op) |

## Verification

```
python -c "from email_engine.core.bounce_handler import handle_bounce, scan_bounces; print('OK')"
→ OK

grep "graph_msg\|Graph\|webhook" email_engine/core/bounce_handler.py
→ (empty) ✅

grep "parse_dsn_from_graph_msg" email_engine/core/bounce_handler.py
→ (empty) ✅
```

## Helpers/Constants Preserved
- `_parse_multipart_dsn`, `_fallback_subject_parse`, `_classify`, `_extract_multipart_boundary`, `_split_multipart`, `_extract_dsn_fields`
- `EMAIL_RE`, `NDR_SUBJECTS`, `HARD_KEYWORDS`, `SOFT_KEYWORDS`
- `init_db()`, `_get_db()`, `_insert_bounce()`, `_add_to_suppression_list()`, `_get_soft_count()`
