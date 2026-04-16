"""
backfill_intel_from_inbox.py — Stub: import REPLY/BOUNCE events from Outlook
============================================================================
TODO (Phase 04 — dev-scanner):
    Once dev-scanner upgrades email_engine/core/process_reply.py v3.0 to emit
    structured reply records (sentiment + intent already extracted), this
    script will:
      1. Connect via win32com.client to Outlook Inbox + 'Junk Email' folder
      2. Iterate messages received in the last N days (default 60)
      3. For each message:
           - Match SenderEmailAddress against cnee_master_v2 EMAIL column
           - Detect bounce via Sender == "MAILER-DAEMON" / DSN headers
           - Run reply_analyzer to classify sentiment + intent
           - Build event via intel.build_reply_event / build_bounce_event
      4. memory.log_events_bulk(events)
      5. Trigger tier_engine.evaluate_event for each, persist tier changes,
         queue writeback updates

For now this is a stub so Phase 02 has a placeholder script. Run with --check
to verify intel.db is initialized — actual backfill will land in Phase 04.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT))

from email_engine.intel import memory  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--days", type=int, default=60,
                   help="(future) lookback window in days")
    p.add_argument("--check", action="store_true",
                   help="just verify intel.db initialized")
    args = p.parse_args()

    memory.init_db()
    if args.check:
        print("intel.db ok. Inbox backfill is a Phase 04 stub.")
        return 0

    print(
        "[stub] inbox backfill not implemented yet — depends on dev-scanner "
        "upgrading process_reply.py v3.0 to emit structured reply events. "
        f"Window: last {args.days}d."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
