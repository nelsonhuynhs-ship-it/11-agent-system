"""
email_engine.intel — Intel Memory + Event Chain (Phase 02)
============================================================
SQLite append-only event log per CNEE + TIER auto-update engine
+ debounced writeback to OneDrive cnee_master_v2.xlsx.

Public surface (re-exported for convenience):
    from email_engine.intel import (
        init_db, log_event, get_timeline, get_cnee_summary,
        get_stale, count_events, recent_events,
        EVENT_TYPES, build_sent_event, build_reply_event,
        build_bounce_event, build_tier_event,
        evaluate_event, apply_promotion_rules, apply_demotion_rules,
        update_master, flush, start_background_flusher,
    )
"""
from __future__ import annotations

from .events import (
    EVENT_TYPES,
    build_sent_event,
    build_reply_event,
    build_bounce_event,
    build_tier_event,
    build_unsubscribe_event,
)
from .memory import (
    init_db,
    log_event,
    get_timeline,
    get_cnee_summary,
    get_stale,
    count_events,
    recent_events,
)
from .tier_engine import (
    evaluate_event,
    apply_promotion_rules,
    apply_demotion_rules,
)
from .writeback import (
    update_master,
    flush,
    start_background_flusher,
)

__all__ = [
    # events
    "EVENT_TYPES",
    "build_sent_event",
    "build_reply_event",
    "build_bounce_event",
    "build_tier_event",
    "build_unsubscribe_event",
    # memory
    "init_db",
    "log_event",
    "get_timeline",
    "get_cnee_summary",
    "get_stale",
    "count_events",
    "recent_events",
    # tier engine
    "evaluate_event",
    "apply_promotion_rules",
    "apply_demotion_rules",
    # writeback
    "update_master",
    "flush",
    "start_background_flusher",
]
