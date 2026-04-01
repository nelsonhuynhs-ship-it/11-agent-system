# -*- coding: utf-8 -*-
"""
event_bus.py — In-Process Event Bus with Persistence
=======================================================
Publish/subscribe system with optional file-based persistence.
Phase 1: In-process + JSON file log (current)
Phase 2+: Swap to Redis Streams for scalability.

Usage:
    from event_bus import bus, Event

    # Subscribe
    bus.subscribe("quote.created", my_handler)

    # Publish
    bus.publish(Event(type="quote.created", payload={"quote_id": "Q-001"}))
"""
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger("nelson.events")


@dataclass
class Event:
    """Immutable event record."""
    type: str                     # e.g. "quote.created", "shipment.stage_changed"
    payload: dict                 # event-specific data
    source: str = "api"           # "api", "bot", "erp", "email", "system"
    actor: str = "system"         # user_id or "system"
    timestamp: str = ""           # ISO format, auto-filled

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "payload": self.payload,
            "source": self.source,
            "actor": self.actor,
            "timestamp": self.timestamp,
        }


# Supported event types (for documentation)
EVENT_TYPES = {
    # Quote lifecycle
    "quote.created":         "New quote created",
    "quote.updated":         "Quote carriers/markup modified",
    "quote.status_changed":  "Quote status transition (DRAFT→SENT→ACCEPTED etc.)",
    "quote.converted":       "Quote converted to shipment",

    # Shipment lifecycle
    "shipment.created":      "New shipment created (from quote or email)",
    "shipment.stage_changed":"Shipment stage transition",
    "shipment.risk_detected":"Risk event detected",

    # Email pipeline
    "email.scanned":         "Outlook scan completed",
    "email.synced":          "Email→shipment sync completed",

    # Rate updates
    "rate.imported":         "New carrier rates imported",
    "rate.expired":          "Rate validity expired",

    # System
    "system.audit":          "Architecture audit completed",
    "system.health_check":   "Self-evaluation completed",

    # Alert
    "alert.triggered":       "Alert dispatched to notification service",
}


class EventBus:
    """
    In-process event bus with handler registration and file persistence.

    Scale path:
    - Phase 1: In-process + JSON file (this) — sufficient for single-server
    - Phase 2: Redis Streams (XADD/XREAD) — multi-worker
    - Phase 3: Celery + Redis — full async task queue
    """

    def __init__(self, persist_dir: Optional[Path] = None, max_log: int = 1000):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._event_log: list[Event] = []
        self._max_log_size = max_log
        self._persist_dir = persist_dir
        self._persist_file: Optional[Path] = None

        if persist_dir:
            persist_dir.mkdir(parents=True, exist_ok=True)
            self._persist_file = persist_dir / "events.jsonl"
            self._load_persisted_events()

    def _load_persisted_events(self):
        """Load events from JSONL file on startup."""
        if not self._persist_file or not self._persist_file.exists():
            return
        try:
            with self._persist_file.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        self._event_log.append(Event(**data))
            # Trim to max
            if len(self._event_log) > self._max_log_size:
                self._event_log = self._event_log[-self._max_log_size:]
            log.info("Loaded %d persisted events from %s",
                     len(self._event_log), self._persist_file.name)
        except Exception as e:
            log.warning("Failed to load persisted events: %s", e)

    def _persist_event(self, event: Event):
        """Append event to JSONL file."""
        if not self._persist_file:
            return
        try:
            with self._persist_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            log.warning("Failed to persist event: %s", e)

    def subscribe(self, event_type: str, handler: Callable):
        """Register handler for event type. Handler receives Event as arg."""
        self._handlers[event_type].append(handler)
        log.info("Subscribed %s to '%s'", handler.__name__, event_type)

    def unsubscribe(self, event_type: str, handler: Callable):
        """Remove handler."""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    def publish(self, event: Event):
        """Publish event to all subscribers. Synchronous for Phase 1."""
        # Store in memory log
        self._event_log.append(event)
        if len(self._event_log) > self._max_log_size:
            self._event_log = self._event_log[-self._max_log_size:]

        # Persist to file
        self._persist_event(event)

        log.info("EVENT [%s] source=%s payload_keys=%s",
                 event.type, event.source, list(event.payload.keys()))

        # Dispatch to handlers
        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                log.error("Handler %s failed for event %s: %s",
                          handler.__name__, event.type, e)

    def get_recent_events(self, event_type: Optional[str] = None,
                          limit: int = 50) -> list[dict]:
        """Get recent events from in-memory log."""
        events = self._event_log
        if event_type:
            events = [e for e in events if e.type == event_type]
        return [e.to_dict() for e in events[-limit:]]

    @property
    def stats(self) -> dict:
        """Event bus statistics."""
        type_counts = defaultdict(int)
        for e in self._event_log:
            type_counts[e.type] += 1
        return {
            "total_logged": len(self._event_log),
            "persisted": bool(self._persist_file),
            "handlers": {k: len(v) for k, v in self._handlers.items() if v},
            "event_counts": dict(type_counts),
        }

    def compact_log(self):
        """Compact persisted log file (rewrite with only recent events)."""
        if not self._persist_file:
            return
        try:
            events = self._event_log[-self._max_log_size:]
            with self._persist_file.open("w", encoding="utf-8") as f:
                for e in events:
                    f.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")
            log.info("Compacted event log to %d events", len(events))
        except Exception as e:
            log.warning("Failed to compact event log: %s", e)


# ──────────────────────────────────────────────────────────────────────────────
# SINGLETON INSTANCE — with file persistence
# ──────────────────────────────────────────────────────────────────────────────

_persist_dir = Path(__file__).parent / "data"
bus = EventBus(persist_dir=_persist_dir, max_log=1000)
