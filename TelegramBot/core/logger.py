# -*- coding: utf-8 -*-
"""
Structured Logger for N.E.L.S.O.N v2.0
=======================================
All agents use this — no more bare print() calls.
Each agent gets console + JSON-lines file output.

Usage:
    from core.logger import NEXUS, ENGINE, LENS, SENTINEL, ORACLE

    NEXUS.info("Bot started")
    ENGINE.info("Parquet loaded: %d rows", 20276)
    LENS.info("Forecast complete")
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


class JsonFormatter(logging.Formatter):
    """Each log line = one JSON object. Easy to parse for RAG."""

    def format(self, record):
        return json.dumps({
            "ts": datetime.now().isoformat(),
            "agent": record.name,
            "level": record.levelname,
            "msg": record.getMessage(),
            "file": record.filename,
            "line": record.lineno,
        }, ensure_ascii=False)


def get_logger(agent_name: str) -> logging.Logger:
    """Create a structured logger with console + JSON file handlers."""
    logger = logging.getLogger(agent_name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # Console handler — clean format
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S"
    ))

    # File handler — JSON lines for RAG ingestion
    fh = logging.FileHandler(LOG_DIR / f"{agent_name}.log",
                             encoding="utf-8")
    fh.setFormatter(JsonFormatter())

    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger


# ── Pre-built loggers for each N.E.L.S.O.N agent ─────────────────────────
NEXUS = get_logger("NEXUS")       # Orchestrator / bot_v5.py
ENGINE = get_logger("ENGINE")     # Pricing / query_engine
LENS = get_logger("LENS")         # Analytics / intelligence
SENTINEL = get_logger("SENTINEL") # Monitor / heartbeat
ORACLE = get_logger("ORACLE")     # Memory / oracle.py
NOTIFY = get_logger("NOTIFY")     # Alerts / notifications
