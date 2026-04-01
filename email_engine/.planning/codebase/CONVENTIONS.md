# CONVENTIONS — Code Style & Patterns

## Python Style
- **Python 3.12** with `from __future__ import annotations`
- **Type hints** used in newer modules (`email_parser.py`, `data_collector.py`, `pst_importer.py`)
- **Older modules** (`read_email1.py`, `send_email.py`) lack type hints
- **No linter config** found (no `.flake8`, `pyproject.toml`, `ruff.toml`)

## Naming Conventions
- **Files:** `snake_case.py`
- **Classes:** `PascalCase` (`EmailClassifier`, `DataCollector`)
- **Functions:** `snake_case` (`save_msg_local`, `instant_reject`)
- **Constants:** `UPPER_SNAKE_CASE` (`PROJECT_ROOT`, `DB_PATH`, `BLACKLIST_DOMAINS`)
- **Private methods:** `_prefix` (`_insert_event`, `_upsert_shipment`, `_move_to_processed`)

## Logging Pattern
Every module follows the same pattern:
```python
import logging
import logging.handlers

log = logging.getLogger(__name__)

_fmt = logging.Formatter("[%(asctime)s] %(levelname)-8s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
_console = logging.StreamHandler(sys.stdout)
_console.setFormatter(_fmt)
_file_handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
_file_handler.setFormatter(_fmt)
logging.basicConfig(level=logging.INFO, handlers=[_console, _file_handler])
```

## Path Resolution Pattern
All modules use the same root-relative pattern:
```python
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH      = PROJECT_ROOT / 'logs' / 'shipments.db'
```

## Error Handling Pattern
- **Try/except with continue** — errors in individual email processing don't crash the pipeline
- **Move to `_unmatched/`** — failed files moved to quarantine folder
- Errors logged but not raised (fail-safe design)

## Database Access Pattern
- Direct `sqlite3.connect()` — no ORM, no connection pool
- `INSERT OR IGNORE` for idempotent inserts
- Manual upsert via `SELECT` → `INSERT/UPDATE`
- `conn.commit()` after batch operations

## Configuration Pattern
- JSON/YAML files in `data/` loaded with `json.load()` / `yaml.safe_load()`
- No environment variable config (except `ANTHROPIC_API_KEY` in pst_importer)
- Hardcoded paths relative to `PROJECT_ROOT`

## Module Pattern
Each script is both importable and directly executable:
```python
def main():
    ...

if __name__ == '__main__':
    main()
```

## Docstrings
- Module-level docstrings with `=====` separator style
- Function docstrings present in newer modules, sparse in older ones
- No docstring standard enforced
