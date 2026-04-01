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

# ── Paths (relative — works on both Windows + Linux) ──
BASE_DIR           = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRICING_ENGINE_DIR = os.path.join(BASE_DIR, "Pricing_Engine")
ERP_DIR            = os.path.join(BASE_DIR, "ERP")
MASTER_FILE        = os.path.join(PRICING_ENGINE_DIR, "data", "MasterFullPricing.xlsx")
ERP_FILE           = os.path.join(ERP_DIR, "data", "ERP_Master.xlsm")
DB_FILE            = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "freight_bot.db")
LOG_DIR            = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

# ── Ensure dirs exist ─────────────────────────────
os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"), exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
