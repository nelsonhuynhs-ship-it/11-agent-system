# CONCERNS — Technical Debt & Issues

## High Priority

### No `requirements.txt`
Dependencies installed globally with no version pinning. A `pip freeze` or `requirements.txt` would prevent breakage from upgrades.

### Outlook COM Fragility
- All Outlook interaction via COM (`win32com.client`) — no retry logic, no connection pooling
- COM errors silently swallowed in many places
- `ReceivedTime` timezone handling inconsistent (`.replace(tzinfo=None)` scattered)
- PST import relies on Outlook being open and responsive

### SQLite Concurrency
- Multiple scripts may write to `shipments.db` simultaneously (main.py + data_collector.py on scheduler)
- No WAL mode enabled, no write locking
- Could cause `database is locked` errors under concurrent access

### Encoding Issues
- 7 `.msg` files failed with `gb2312` codec errors during pipeline test
- `extract-msg` library has known encoding issues with Asian-language emails
- No fallback encoding strategy implemented

## Medium Priority

### Hardcoded Business Logic
- HBL/BKG regex patterns hardcoded in `email_parser.py` — should be in `shipment_patterns.yaml`
- Blacklist domains/subjects/senders hardcoded in `pst_importer.py`
- Member names hardcoded in multiple files (`BLUE`, `JENNIE`, `OTIS`, etc.)

### Duplicate Code
- Path resolution pattern (`PROJECT_ROOT = Path(__file__).parent.parent`) repeated in every module
- Logging setup boilerplate duplicated across all modules
- Email parsing logic partially duplicated between `email_parser.py` and `read_email1.py`

### No Data Validation
- No schema validation on `rules.json` or `rules.yaml`
- No input sanitization on email subjects/bodies before DB insert
- SQL injection theoretically possible via malformed email subjects (mitigated by parameterized queries)

### Legacy Code in `core/`
- `email_engine.py` (7KB) — older email sender, partially superseded by `send_email.py`
- `read_email1.py` vs `email_parser.py` — overlapping classification logic
- `ops_briefing.py` vs `nelson_briefing.py` — two briefing generators

## Low Priority

### No Git Repository
- No `.git/` directory found
- `_backup/` used instead of version control
- No branch management, no commit history

### Large Binary Files
- `backup.pst` (7.5GB) in project root
- `data.xlsx` (338KB) in project root
- Should be excluded from version control if git is adopted

### TODO Items
- `core/main.py` line 410: `# TODO: Implement attachment extraction when needed`

## Security Concerns
- `ANTHROPIC_API_KEY` read from `.env` file or environment — no encryption
- Outlook COM has full access to mailbox — no sandboxing
- No audit log for who/when accessed the system
- PST file stored unencrypted on disk
