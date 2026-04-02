# -*- coding: utf-8 -*-
"""
config.py — Centralized Configuration
=========================================
All environment variables and settings in one place.
Modules should import from here instead of using os.environ.get() directly.

Usage:
    from config import cfg
    url = cfg.DATABASE_URL
    key = cfg.API_KEY
"""
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Ensure repo root is in sys.path for shared imports
_repo_root = str(Path(__file__).parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from shared import paths as sp


@dataclass
class Config:
    """Application configuration from environment variables."""

    # ── Paths (delegated to shared.paths) ─────────────────────────────────
    BASE_DIR: Path = field(default_factory=lambda: sp.CODE_DIR)

    @property
    def API_DIR(self) -> Path:
        return sp.API_DIR

    @property
    def PRICING_DIR(self) -> Path:
        return sp.PRICING_CODE

    @property
    def BOT_DIR(self) -> Path:
        return sp.BOT_CODE

    @property
    def EMAIL_DIR(self) -> Path:
        return sp.EMAIL_CODE

    @property
    def PARQUET_FILE(self) -> Path:
        return sp.PARQUET_FILE

    # ── Database ──────────────────────────────────────────────────────────
    DATABASE_URL: str = field(default_factory=lambda: os.environ.get("DATABASE_URL", ""))
    DEFAULT_TENANT_ID: str = "00000000-0000-0000-0000-000000000001"

    @property
    def is_postgres(self) -> bool:
        return bool(self.DATABASE_URL)

    # ── Auth ──────────────────────────────────────────────────────────────
    API_KEY: str = field(default_factory=lambda: os.environ.get("NELSON_API_KEY", ""))
    ERP_API_KEY: str = field(default_factory=lambda: os.environ.get("ERP_API_KEY", ""))
    SUPABASE_URL: str = field(default_factory=lambda: os.environ.get("SUPABASE_URL", ""))
    SUPABASE_KEY: str = field(default_factory=lambda: os.environ.get("SUPABASE_KEY", ""))

    @property
    def auth_mode(self) -> str:
        if self.SUPABASE_URL:
            return "supabase"
        elif self.API_KEY:
            return "api_key"
        return "open"

    # ── Workers ───────────────────────────────────────────────────────────
    EMAIL_WORKER_ENABLED: bool = field(default_factory=lambda:
        os.environ.get("EMAIL_WORKER_ENABLED", "true").lower() == "true")
    EMAIL_SCAN_INTERVAL: int = field(default_factory=lambda:
        int(os.environ.get("EMAIL_SCAN_INTERVAL", "15")))
    EVALUATOR_ENABLED: bool = field(default_factory=lambda:
        os.environ.get("EVALUATOR_ENABLED", "true").lower() == "true")

    # ── Notifications ─────────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = field(default_factory=lambda:
        os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    TELEGRAM_ALERT_CHAT_ID: str = field(default_factory=lambda:
        os.environ.get("TELEGRAM_ALERT_CHAT_ID", ""))

    # ── Rate Limiting ─────────────────────────────────────────────────────
    RATE_LIMIT_ENABLED: bool = field(default_factory=lambda:
        os.environ.get("RATE_LIMIT_ENABLED", "true").lower() == "true")
    RATE_LIMIT_DEFAULT: int = field(default_factory=lambda:
        int(os.environ.get("RATE_LIMIT_DEFAULT", "60")))  # requests per minute
    RATE_LIMIT_HEAVY: int = field(default_factory=lambda:
        int(os.environ.get("RATE_LIMIT_HEAVY", "10")))    # for /dashboard, /intelligence

    # ── Performance ───────────────────────────────────────────────────────
    CACHE_TTL: int = field(default_factory=lambda:
        int(os.environ.get("NELSON_CACHE_TTL", "600")))    # seconds
    EVENT_LOG_SIZE: int = field(default_factory=lambda:
        int(os.environ.get("EVENT_LOG_SIZE", "1000")))

    # ── CORS ──────────────────────────────────────────────────────────────
    CORS_ORIGINS: list = field(default_factory=lambda: [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3003",
        "http://14.225.207.145:3003",
        "https://nelsonfreight.pro.vn",
        "https://*.nelsonfreight.pro.vn",
    ])

    def summary(self) -> dict:
        """Return non-sensitive config summary."""
        return {
            "auth_mode": self.auth_mode,
            "database": "postgresql" if self.is_postgres else "json_files",
            "email_worker": self.EMAIL_WORKER_ENABLED,
            "scan_interval_min": self.EMAIL_SCAN_INTERVAL,
            "evaluator": self.EVALUATOR_ENABLED,
            "telegram": bool(self.TELEGRAM_BOT_TOKEN),
            "rate_limit": f"{self.RATE_LIMIT_DEFAULT}/min" if self.RATE_LIMIT_ENABLED else "disabled",
            "cache_ttl": f"{self.CACHE_TTL}s",
        }


# Singleton
cfg = Config()
