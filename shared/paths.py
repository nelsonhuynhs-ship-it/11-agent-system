# -*- coding: utf-8 -*-
"""
shared/paths.py — Central path resolver for all Nelson Freight services.
=====================================================================
All modules import from here instead of using Path(__file__).parent chains.

Resolves from env vars with sensible fallbacks per machine:
  - PC Home:   NELSON_DATA_DIR → OneDrive/NelsonData
  - Laptop VP: NELSON_DATA_DIR → OneDrive/NelsonData
  - VPS:       NELSON_DATA_DIR → /opt/nelson/data

Usage:
    from shared.paths import PARQUET_FILE, CNEE_MASTER, MACHINE
    print(f"Running on {MACHINE.name}")
"""
import os
import socket
from dataclasses import dataclass
from pathlib import Path


# ── Machine Detection ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MachineInfo:
    """Identifies which machine the code is running on."""
    name: str        # "pc-home", "laptop-vp", "vps", "unknown"
    hostname: str
    is_local: bool   # True for PC Home / Laptop VP, False for VPS

def _detect_machine() -> MachineInfo:
    """Detect current machine from hostname or env var override."""
    # Allow explicit override via env var
    override = os.environ.get("NELSON_MACHINE", "").lower().strip()
    hostname = socket.gethostname().upper()

    if override:
        return MachineInfo(
            name=override,
            hostname=hostname,
            is_local=override != "vps",
        )

    # Auto-detect from hostname
    if "DESKTOP" in hostname or "ADMIN" in hostname:
        return MachineInfo(name="pc-home", hostname=hostname, is_local=True)
    elif "LAPTOP" in hostname:
        return MachineInfo(name="laptop-vp", hostname=hostname, is_local=True)
    else:
        # VPS or unknown linux server
        return MachineInfo(name="vps", hostname=hostname, is_local=False)


MACHINE = _detect_machine()


# ── Base Directories ──────────────────────────────────────────────────────────

def _resolve_data_dir() -> Path:
    """Resolve data directory from env var with OneDrive fallback."""
    env_val = os.environ.get("NELSON_DATA_DIR", "")
    if env_val and Path(env_val).exists():
        return Path(env_val)

    # Fallback: search common OneDrive locations (local machines)
    if MACHINE.is_local:
        # Check OneDrive env var (Windows sets this)
        onedrive_root = os.environ.get("OneDriveConsumer") or os.environ.get("OneDrive", "")
        if onedrive_root:
            candidate = Path(onedrive_root) / "NelsonData"
            if candidate.exists():
                return candidate

        # Common Windows paths
        home = Path.home()
        for candidate in [
            home / "OneDrive" / "NelsonData",
            Path("D:/OneDrive/NelsonData"),
            Path("C:/Users/Nelson/OneDrive/NelsonData"),
            Path("C:/Users/ADMIN/OneDrive/NelsonData"),
        ]:
            if candidate.exists():
                return candidate

    # VPS fallback
    vps_data = Path("/opt/nelson/data")
    if vps_data.exists():
        return vps_data

    # Last resort: old repo layout (backward compat during migration)
    repo_root = Path(__file__).parent.parent
    return repo_root


def _resolve_local_dir() -> Path:
    """Resolve local runtime directory (machine-specific, not synced)."""
    env_val = os.environ.get("NELSON_LOCAL_DIR", "")
    if env_val and Path(env_val).exists():
        return Path(env_val)

    if MACHINE.is_local:
        # Prefer D:\NelsonLocal, fallback to home dir
        for candidate in [Path("D:/NelsonLocal"), Path.home() / "NelsonLocal"]:
            if candidate.exists():
                return candidate

    vps_local = Path("/opt/nelson/local")
    if vps_local.exists():
        return vps_local

    # Fallback: repo root (old layout)
    return Path(__file__).parent.parent


def _resolve_code_dir() -> Path:
    """Resolve code/repo root directory."""
    env_val = os.environ.get("NELSON_CODE_DIR", "")
    if env_val and Path(env_val).exists():
        return Path(env_val)
    # Default: parent of shared/
    return Path(__file__).parent.parent


DATA_DIR = _resolve_data_dir()
LOCAL_DIR = _resolve_local_dir()
CODE_DIR = _resolve_code_dir()


# ── Pricing Data (OneDrive) ──────────────────────────────────────────────────

PRICING_DATA = DATA_DIR / "pricing"
PARQUET_FILE = PRICING_DATA / "Cleaned_Master_History.parquet"
CARRIER_RULES = PRICING_DATA / "carrier_rules.json"
RATE_TABLES_DIR = PRICING_DATA / "rate-tables"
MAPPING_DIR = PRICING_DATA / "mapping"
CARRIER_RATE_MAPPING = MAPPING_DIR / "CARRIER_RATE_MAPPING.json"


# ── Email Data (OneDrive) ────────────────────────────────────────────────────

EMAIL_DATA = DATA_DIR / "email"
CNEE_MASTER = EMAIL_DATA / "cnee_master.xlsx"
CONTACT_MASTER = EMAIL_DATA / "contact_master.xlsx"
SHIPPER_MASTER = EMAIL_DATA / "shipper_master.xlsx"
CUSTOMER_RULES = EMAIL_DATA / "customer_rules.json"
TEAM_RULES = EMAIL_DATA / "rules.json"
RULES_YAML = EMAIL_DATA / "rules.yaml"
CONFIG_XLSX = EMAIL_DATA / "config.xlsx"
PORT_MAP = EMAIL_DATA / "Port_Code_Mapping_Final.xlsx"
SHIPMENT_STATE = EMAIL_DATA / "shipment_state.json"
SHIPMENT_PATTERNS = EMAIL_DATA / "shipment_patterns.yaml"
CUSTOMER_FINAL = EMAIL_DATA / "customer_final.xlsx"
REPLACEMENT_LEADS = EMAIL_DATA / "replacement_leads.xlsx"
PANJIVA_DIR   = EMAIL_DATA / "panjiva"
DATA_LOC_DIR  = DATA_DIR / "Data Loc"


# ── Assets (OneDrive) ────────────────────────────────────────────────────────

ASSETS_DIR = DATA_DIR / "assets"
COMPANY_PDF = ASSETS_DIR / "PUDONG PRIME PROFILE.pdf"
LOGO_FILE = ASSETS_DIR / "logo.png"
EMAIL_TEMPLATE = ASSETS_DIR / "email_template.html"


# ── Bot Data (OneDrive) ──────────────────────────────────────────────────────

BOT_DATA = DATA_DIR / "bot"
CARRIER_TIPS = BOT_DATA / "carrier_tips.json"


# ── ERP Data (OneDrive) ──────────────────────────────────────────────────────

ERP_DATA = DATA_DIR / "erp"


# ── Local Runtime (machine-specific, NOT synced) ─────────────────────────────

LOG_DIR = LOCAL_DIR / "logs"
API_LOG_DIR = LOG_DIR / "api"
EMAIL_LOG_DIR = LOG_DIR / "email-engine"
BOT_LOG_DIR = LOG_DIR / "bot"

RUNTIME_DIR = LOCAL_DIR / "runtime"
QUOTES_FILE = RUNTIME_DIR / "quotes.json"
EVENTS_FILE = RUNTIME_DIR / "events.jsonl"
ACTIVE_ALERTS = RUNTIME_DIR / "active_alerts.json"
OUTLOOK_DATASET = RUNTIME_DIR / "outlook_dataset.json"
SYNC_STATE = RUNTIME_DIR / "sync_state.json"
EMAIL_LOG = EMAIL_LOG_DIR / "email_log.csv"
CACHE_DIR = LOCAL_DIR / "cache"


# ── Code Paths (repo) ────────────────────────────────────────────────────────

API_DIR = CODE_DIR / "api"
WEBAPP_DIR = CODE_DIR / "webapp"
PRICING_CODE = CODE_DIR / "Pricing_Engine"
EMAIL_CODE = CODE_DIR / "email_engine"
BOT_CODE = CODE_DIR / "TelegramBot"
INTELLIGENCE_DIR = CODE_DIR / "intelligence"
DB_DIR = CODE_DIR / "db"


# ── Backward Compatibility Fallbacks ─────────────────────────────────────────

def resolve_with_fallback(primary: Path, *fallbacks: Path) -> Path:
    """Return the first path that exists, or primary if none found."""
    if primary.exists():
        return primary
    for fb in fallbacks:
        if fb.exists():
            return fb
    return primary


# ── Session Info (for CLAUDE.md / session awareness) ─────────────────────────

def session_banner() -> str:
    """Return a human-readable session banner for machine identification."""
    data_status = "OK" if DATA_DIR.exists() and PARQUET_FILE.exists() else "MISSING"
    return (
        f"Machine: {MACHINE.name} ({MACHINE.hostname})\n"
        f"Data:    {DATA_DIR}  [{data_status}]\n"
        f"Local:   {LOCAL_DIR}\n"
        f"Code:    {CODE_DIR}"
    )
