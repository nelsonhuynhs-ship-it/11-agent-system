# -*- coding: utf-8 -*-
"""
scripts/lib/audit_logger.py — Row-level change CSV writer for migration audits.
================================================================================
Records every NEW/UPDATE/SKIP action per email row with before/after diffs.

Usage:
    logger = AuditLogger(Path("backups/migration_audit_20260422_1800.csv"))
    logger.log("NEW",    email="a@b.com", company="Acme", changed_cols=[])
    logger.log("UPDATE", email="c@d.com", company="Corp", changed_cols=["POL","STATE"])
    logger.log("SKIP",   email="e@f.com", reason="PRIORITY_LOCK")
    logger.close()   # flush + close
    stats = logger.summary()   # {"NEW": 500, "UPDATE": 80, "SKIP": 200}
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from pathlib import Path
from typing import Optional


# CSV column order
_FIELDNAMES = [
    "run_ts",
    "action",       # NEW | UPDATE | SKIP
    "sheet",        # CNEE | SHIPPER
    "email",
    "company",
    "changed_cols", # pipe-separated list or empty
    "reason",       # human-readable reason for SKIP / UPDATE
]


class AuditLogger:
    """Write row-level migration audit entries to a CSV file.

    Thread-safety: single-threaded use only (no locking).
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._counts: dict[str, int] = {"NEW": 0, "UPDATE": 0, "SKIP": 0}
        self._run_ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(path, "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._fh, fieldnames=_FIELDNAMES)
        self._writer.writeheader()

    # ── Public API ────────────────────────────────────────────────────────────

    def log(
        self,
        action: str,
        email: str,
        company: str = "",
        sheet: str = "CNEE",
        changed_cols: Optional[list[str]] = None,
        reason: str = "",
    ) -> None:
        """Write one audit row.

        Args:
            action:       "NEW", "UPDATE", or "SKIP"
            email:        primary email address
            company:      company name
            sheet:        "CNEE" or "SHIPPER"
            changed_cols: list of column names that changed (UPDATE only)
            reason:       human-readable reason (SKIP reason or UPDATE trigger)
        """
        action_upper = action.upper()
        self._counts[action_upper] = self._counts.get(action_upper, 0) + 1
        self._writer.writerow({
            "run_ts":       self._run_ts,
            "action":       action_upper,
            "sheet":        sheet,
            "email":        (email or "").lower().strip(),
            "company":      company or "",
            "changed_cols": "|".join(changed_cols) if changed_cols else "",
            "reason":       reason,
        })

    def log_bulk(self, rows: list[dict]) -> None:
        """Write multiple audit rows from a list of dicts matching _FIELDNAMES."""
        for row in rows:
            self.log(
                action=row.get("action", "SKIP"),
                email=row.get("email", ""),
                company=row.get("company", ""),
                sheet=row.get("sheet", "CNEE"),
                changed_cols=row.get("changed_cols"),
                reason=row.get("reason", ""),
            )

    def summary(self) -> dict[str, int]:
        """Return action counts dict (safe to call before close)."""
        return dict(self._counts)

    def close(self) -> None:
        """Flush and close the underlying file handle."""
        if not self._fh.closed:
            self._fh.flush()
            self._fh.close()

    def __enter__(self) -> "AuditLogger":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ── Dry-run in-memory variant ─────────────────────────────────────────────

    @staticmethod
    def dry_run_logger() -> "AuditLogger":
        """Return an AuditLogger that writes to /dev/null (dry-run mode).

        Still tracks counts in memory; nothing is written to disk.
        """
        logger = object.__new__(AuditLogger)
        logger._counts = {"NEW": 0, "UPDATE": 0, "SKIP": 0}
        logger._run_ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        logger.path = Path("/dev/null")
        buf = io.StringIO()
        logger._fh = buf  # type: ignore[assignment]
        logger._writer = csv.DictWriter(buf, fieldnames=_FIELDNAMES)
        return logger
