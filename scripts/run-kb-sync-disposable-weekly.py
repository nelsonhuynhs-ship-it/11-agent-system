#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
run-kb-sync-disposable-weekly.py
---------------------------------
Weekly cron: refresh disposable domain list from GitHub.

Scheduled via Task Scheduler: Monday 06:30 (see register-kb-sync-weekly.ps1).

Usage:
    python scripts/run-kb-sync-disposable-weekly.py
"""

import sys
import logging
from pathlib import Path

# Add project root to path
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("kb-sync")


def main():
    log.info("Starting disposable domain sync...")
    try:
        from email_engine.core.bounce_knowledge import sync_disposable_domains
        count = sync_disposable_domains(timeout=60)
        if count > 0:
            log.info(f"Sync complete: {count} disposable domains updated in KB")
            sys.exit(0)
        else:
            log.error("Sync returned 0 domains — check network or source URL")
            sys.exit(1)
    except Exception as exc:
        log.error(f"Sync failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
