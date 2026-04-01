# TESTING — Test Structure & Practices

## Current State
- **No test framework** configured (no pytest, unittest, or tox)
- **No CI/CD pipeline** (no `.github/workflows/`, no Jenkins, no GitLab CI)
- **1 integration test:** `test_pipeline.py` — end-to-end test using real `.msg` files

## `test_pipeline.py` Coverage
- Finds `.msg` files in `outlook/`
- Copies to processing folders
- Runs `DataCollector.init_db()` + `DataCollector.scan_msg_files()`
- Queries SQLite for stats (email_events, shipments, sales_replies, alerts, customers)
- Generates `nelson_briefing.xlsx`
- Prints summary report

## Testing Gaps
- **No unit tests** for `EmailClassifier`, `DataCollector`, individual parse functions
- **No mocking** — tests hit real Outlook COM and real `.msg` files
- **No edge case tests** — encoding issues (gb2312), missing fields, corrupt .msg
- **No regression tests** — no way to verify routing logic after changes
- **No test data fixtures** — relies on production .msg files in `outlook/`

## Verification Approach
- Manual verification via Excel output files
- Log file inspection (`logs/*.log`)
- SQLite queries for data validation
- `SOP.md` describes manual morning verification routine
