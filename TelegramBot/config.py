# -*- coding: utf-8 -*-
"""
Nelson Freight Bot — Configuration
Reads secrets from .env file, paths are relative to __file__.
"""
import os
from dotenv import load_dotenv

# Load .env from TelegramBot/ folder
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# ── Telegram ──────────────────────────────────────
BOT_TOKEN     = os.environ.get("BOT_TOKEN", "")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))
ADMIN_NAME    = os.environ.get("ADMIN_NAME", "Nelson")

# ── AI ────────────────────────────────────────────
GEMINI_API_KEY  = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL    = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
FALLBACK_MODEL  = os.environ.get("FALLBACK_MODEL", "gemini-3.1-flash-lite-preview")

# ── Rate limits (free tier) ───────────────────────
MAX_RPM = int(os.environ.get("MAX_RPM", "5"))
MAX_RPD = int(os.environ.get("MAX_RPD", "20"))

# ── Paths (via shared.paths — OneDrive data, local runtime) ──
import sys
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
from shared import paths as sp

BASE_DIR           = str(sp.CODE_DIR)
PRICING_ENGINE_DIR = str(sp.PRICING_CODE)
ERP_DIR            = str(sp.CODE_DIR / "ERP")
MASTER_FILE        = str(sp.PRICING_DATA / "MasterFullPricing.xlsx")
ERP_FILE           = str(sp.ERP_DATA / "ERP_Master.xlsm")
DB_FILE            = str(sp.BOT_DATA / "freight_bot.db")
LOG_DIR            = str(sp.BOT_LOG_DIR)

# ── Ensure dirs exist ─────────────────────────────
os.makedirs(str(sp.BOT_DATA), exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
