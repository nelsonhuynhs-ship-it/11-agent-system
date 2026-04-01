# -*- coding: utf-8 -*-
"""
data_access.py — Centralized Data Access Layer (Repository Pattern)
====================================================================
Single point of access for ALL data in the Nelson Freight platform.
Currently backed by: Parquet (rates), JSON (quotes, shipments, customers),
and SQLite (KPI). Will migrate to PostgreSQL progressively.

RULE: No other module should read/write data files directly.
      All data access goes through this module.

Usage:
    from data_access import dal
    rates = dal.get_rates(pol="HPH", place="Denver")
    quote = dal.create_quote(payload)
    shipments = dal.get_shipments()
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# PATHS (configurable via env vars)
# ──────────────────────────────────────────────────────────────────────────────
BASE_DIR     = Path(os.environ.get("NELSON_BASE_DIR",
                    str(Path(__file__).parent.parent)))  # Engine_test/
PRICING_DIR  = BASE_DIR / "Pricing_Engine"
BOT_DIR      = BASE_DIR / "TelegramBot"
EMAIL_DIR    = Path(os.environ.get("EMAIL_ENGINE_DIR",
                    str(Path(__file__).parent.parent.parent.parent / "email_engine")))
if not EMAIL_DIR.exists():
    EMAIL_DIR = Path(r"D:\NELSON\email_engine")

PARQUET_FILE   = PRICING_DIR / "data" / "Cleaned_Master_History.parquet"
CARRIER_RULES  = PRICING_DIR / "data" / "carrier_rules.json"
CARRIER_TIPS   = BOT_DIR / "carrier_tips.json"
SQLITE_DB      = BOT_DIR / "data" / "freight_bot.db"

QUOTES_FILE    = Path(__file__).parent / "data" / "quotes.json"
SHIPMENT_STATE = EMAIL_DIR / "shipment_state.json"
CUSTOMER_RULES = EMAIL_DIR / "customer_rules.json"
TEAM_RULES     = EMAIL_DIR / "rules.json"
DATASET_DIR    = EMAIL_DIR / "datasets"

# Ensure data dir exists
(Path(__file__).parent / "data").mkdir(exist_ok=True)


# ==============================================================================
# DATA ACCESS LAYER CLASS
# ==============================================================================

class DataAccessLayer:
    """
    Centralized data access — Repository Pattern.

    Phase 1: JSON/Parquet backend (current)
    Phase 2+: PostgreSQL backend (swap methods, keep interface)
    """

    def __init__(self):
        # Parquet caches
        self._df_cache: pd.DataFrame | None = None
        self._df_loaded: datetime | None = None
        self._df_full_cache: pd.DataFrame | None = None
        self._df_full_loaded: datetime | None = None
        self._cache_ttl = int(os.environ.get("NELSON_CACHE_TTL", "600"))

    @property
    def rates_loaded_at(self) -> datetime | None:
        """When rates cache was last loaded."""
        return self._df_loaded

    def invalidate_cache(self):
        """Clear all data caches. Call after Parquet update."""
        self._df_cache = None
        self._df_loaded = None
        self._df_full_cache = None
        self._df_full_loaded = None
        log.info("DAL cache invalidated")

    # ──────────────────────────────────────────────────────────────────────
    # INTERNAL: File I/O helpers
    # ──────────────────────────────────────────────────────────────────────

    def _load_json(self, path: Path) -> dict | list:
        """Load JSON file, return empty dict if missing."""
        if not path.exists():
            return {}
        try:
            with path.open(encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error("Failed to load %s: %s", path.name, e)
            return {}

    def _save_json(self, path: Path, data) -> None:
        """Atomic JSON write (write to .tmp then rename)."""
        tmp = path.with_suffix(".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            tmp.replace(path)
        except Exception as e:
            log.error("Failed to save %s: %s", path.name, e)
            if tmp.exists():
                tmp.unlink()
            raise

    # ──────────────────────────────────────────────────────────────────────
    # RATES (Parquet)
    # ──────────────────────────────────────────────────────────────────────

    def load_rates(self, full: bool = False) -> pd.DataFrame | None:
        """
        Load pricing rates from Parquet with caching.

        Args:
            full: If True, load ALL charge types.
                  If False (default), load only 'Total Ocean Freight' active rates.
        """
        if full:
            return self._load_parquet_full()
        return self._load_parquet_filtered()

    # Columns needed for filtered (Total Ocean Freight) queries
    _RATE_COLUMNS = [
        'POL', 'POD', 'Place', 'Carrier', 'Container_Type',
        'Amount', 'Eff', 'Exp', 'Rate_Type', 'Note',
        'Charge_Name', 'Contract', 'Commodity',
    ]

    def _load_parquet_filtered(self) -> pd.DataFrame | None:
        """Load active Total or Base Ocean Freight rates only — memory-optimized."""
        now = datetime.now()
        if (self._df_cache is not None and self._df_loaded and
                (now - self._df_loaded).seconds < self._cache_ttl):
            return self._df_cache

        if not PARQUET_FILE.exists():
            return None

        today = pd.Timestamp(date.today())
        try:
            # Arrow pushdown: only read rows where Exp >= today from disk
            df = pd.read_parquet(
                PARQUET_FILE,
                columns=self._RATE_COLUMNS,
                filters=[
                    ('Exp', '>=', today),
                    ('Charge_Name', 'in', ['Total Ocean Freight', 'Base Ocean Freight']),
                ],
            )
        except Exception:
            # Fallback if pushdown fails (old Parquet format)
            log.warning("Arrow pushdown failed — falling back to full load")
            df = pd.read_parquet(PARQUET_FILE, columns=self._RATE_COLUMNS)
            df['Exp'] = pd.to_datetime(df['Exp'], errors='coerce')
            df = df[df['Charge_Name'].isin(['Total Ocean Freight', 'Base Ocean Freight']) &
                    (df['Exp'] >= today)]

        df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')
        df = df[df['Amount'] > 900].copy()

        self._df_cache = df
        self._df_loaded = now
        log.info("Parquet loaded (filtered): %s active rates", f"{len(df):,}")
        return df

    def _load_parquet_full(self) -> pd.DataFrame | None:
        """Load all charge types (for breakdown views) — memory-optimized."""
        now = datetime.now()
        if (self._df_full_cache is not None and self._df_full_loaded and
                (now - self._df_full_loaded).seconds < self._cache_ttl):
            return self._df_full_cache

        if not PARQUET_FILE.exists():
            return None

        today = pd.Timestamp(date.today())
        try:
            # Arrow pushdown: only read non-expired rates
            df = pd.read_parquet(
                PARQUET_FILE,
                filters=[('Exp', '>=', today)],
            )
        except Exception:
            log.warning("Arrow pushdown failed (full) — falling back")
            df = pd.read_parquet(PARQUET_FILE)
            df['Exp'] = pd.to_datetime(df['Exp'], errors='coerce')
            df = df[df['Exp'] >= today]

        df['Eff'] = pd.to_datetime(df['Eff'], errors='coerce')
        df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')
        df = df[df['Amount'] > 0].copy()

        self._df_full_cache = df
        self._df_full_loaded = now
        log.info("Parquet loaded (full): %s rates", f"{len(df):,}")
        return df

    @property
    def rates_loaded_at(self) -> datetime | None:
        return self._df_loaded

    def invalidate_rates_cache(self):
        """Force reload on next access."""
        self._df_cache = None
        self._df_loaded = None
        self._df_full_cache = None
        self._df_full_loaded = None

    # ──────────────────────────────────────────────────────────────────────
    # CARRIER RULES
    # ──────────────────────────────────────────────────────────────────────

    def get_carrier_rules(self) -> dict:
        """Load carrier rules (freetime, DEM/DET, etc.)."""
        return self._load_json(CARRIER_RULES)

    def get_carrier_tips(self) -> dict:
        """Load carrier advisory tips."""
        return self._load_json(CARRIER_TIPS)

    # ──────────────────────────────────────────────────────────────────────
    # QUOTES (JSON → will be PostgreSQL)
    # ──────────────────────────────────────────────────────────────────────

    def load_quotes_data(self) -> dict:
        """Load raw quotes data structure."""
        if not QUOTES_FILE.exists():
            return {"quotes": {}, "counter": 0}
        try:
            data = self._load_json(QUOTES_FILE)
            if "quotes" not in data:
                data["quotes"] = {}
            if "counter" not in data:
                data["counter"] = len(data["quotes"])
            return data
        except Exception:
            return {"quotes": {}, "counter": 0}

    def save_quotes_data(self, data: dict) -> None:
        """Save quotes data structure."""
        self._save_json(QUOTES_FILE, data)

    def list_quotes(self, status: Optional[str] = None) -> list:
        """List quotes, optionally filtered by status."""
        data = self.load_quotes_data()
        quotes = list(data["quotes"].values())
        if status:
            quotes = [q for q in quotes
                      if q.get("status", "").upper() == status.upper()]
        quotes.sort(key=lambda q: q.get("created_at", ""), reverse=True)
        return quotes

    def get_quote(self, quote_id: str) -> Optional[dict]:
        """Get a single quote by ID."""
        data = self.load_quotes_data()
        return data["quotes"].get(quote_id)

    # ──────────────────────────────────────────────────────────────────────
    # SHIPMENTS (JSON → will be PostgreSQL)
    # ──────────────────────────────────────────────────────────────────────

    def load_shipment_state(self) -> dict:
        """Load full shipment state."""
        return self._load_json(SHIPMENT_STATE)

    def save_shipment_state(self, data: dict) -> None:
        """Save shipment state."""
        data["last_updated"] = datetime.now().isoformat()
        self._save_json(SHIPMENT_STATE, data)

    def get_shipments(self) -> list:
        """Get all shipments as a list of dicts."""
        state = self.load_shipment_state()
        shipments = state.get("shipments", {})
        items = []
        for sid, rec in shipments.items():
            risks = rec.get("risks", [])
            latest_risk = risks[-1]["level"] if risks else None
            items.append({
                "id":            sid,
                "customer":      rec.get("customer", ""),
                "type":          rec.get("type", ""),
                "stage":         rec.get("stage", ""),
                "routing":       rec.get("routing", ""),
                "carrier":       rec.get("carrier", ""),
                "container":     rec.get("container", ""),
                "quantity":      rec.get("quantity", 1),
                "etd":           rec.get("etd", ""),
                "eta":           rec.get("eta", ""),
                "ata":           rec.get("ata", ""),
                "selling_rate":  rec.get("selling_rate", 0),
                "buying_rate":   rec.get("buying_rate", 0),
                "profit":        rec.get("profit", 0),
                "profit_margin": rec.get("profit_margin", ""),
                "delay_count":   rec.get("delay_count", 0),
                "risk_level":    latest_risk,
                "risk_count":    len(risks),
                "created_at":    rec.get("created_at", ""),
                "updated_at":    rec.get("updated_at", ""),
                "last_subject":  rec.get("last_subject", ""),
                "last_sender":   rec.get("last_sender", ""),
                "stage_history": rec.get("stage_history", []),
                "source":        rec.get("source", ""),
                "email_summary": rec.get("email_summary", ""),
                "email_alerts":  rec.get("email_alerts", []),
            })
        items.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return items

    def get_shipment(self, shipment_id: str) -> Optional[dict]:
        """Get a single shipment by ID."""
        state = self.load_shipment_state()
        return state.get("shipments", {}).get(shipment_id)

    # ──────────────────────────────────────────────────────────────────────
    # CUSTOMERS
    # ──────────────────────────────────────────────────────────────────────

    def get_customers_raw(self) -> dict:
        """Load raw customer rules."""
        return self._load_json(CUSTOMER_RULES)

    def get_customers(self) -> list:
        """Get enriched customer list with shipment stats."""
        data = self.get_customers_raw()
        customers_raw = data.get("customers", {})
        state = self.load_shipment_state()
        shipments = state.get("shipments", {})

        customers = []
        for name, info in customers_raw.items():
            cust_ships = [s for s in shipments.values()
                          if s.get("customer", "").upper() == name.upper()]
            active = [s for s in cust_ships
                      if s.get("stage") != "PAYMENT_CONFIRMED"]
            risks = sum(len(s.get("risks", [])) for s in cust_ships)

            customers.append({
                "name":             name,
                "type":             info.get("type", ""),
                "priority":         info.get("priority", ""),
                "sla_hours":        info.get("sla_hours", 4),
                "routes":           info.get("routes", []),
                "carrier_affinity": info.get("carrier_affinity", []),
                "notes":            info.get("notes", ""),
                "total_shipments":  len(cust_ships),
                "active_shipments": len(active),
                "risk_events":      risks,
                "health":           "active" if active else (
                    "watch" if cust_ships else "new"),
            })
        return customers

    # ──────────────────────────────────────────────────────────────────────
    # TEAM
    # ──────────────────────────────────────────────────────────────────────

    def get_team(self) -> list:
        """Get team members from rules.json."""
        rules = self._load_json(TEAM_RULES)
        members_raw = rules.get("members", {})
        members = []
        for email, data in members_raw.items():
            members.append({
                "email":       email,
                "name":        data.get("name", ""),
                "role":        data.get("role", ""),
                "folder":      data.get("folder", ""),
                "reports_to":  data.get("reports_to", ""),
                "required_cc": data.get("required_cc", []),
                "skip":        data.get("skip_routing", False),
            })
        return members

    # ──────────────────────────────────────────────────────────────────────
    # KPI (SQLite → will be PostgreSQL)
    # ──────────────────────────────────────────────────────────────────────

    def get_kpi(self) -> dict:
        """Get KPI summary from shipment state."""
        state = self.load_shipment_state()
        shipments = state.get("shipments", {})
        total = len(shipments)
        active = sum(1 for s in shipments.values()
                     if s.get("stage") != "PAYMENT_CONFIRMED")
        risks = sum(1 for s in shipments.values() if s.get("risks"))
        paid = sum(1 for s in shipments.values()
                   if s.get("stage") == "PAYMENT_CONFIRMED")
        return {
            "total_shipments": total,
            "active_shipments": active,
            "at_risk": risks,
            "paid": paid,
            "last_updated": state.get("last_updated", ""),
        }

    # ──────────────────────────────────────────────────────────────────────
    # DATASETS (Parquet)
    # ──────────────────────────────────────────────────────────────────────

    def get_dataset_status(self) -> dict:
        """Return row counts for accumulated datasets."""
        status = {}
        for name in ["email_dataset", "shipment_history"]:
            path = DATASET_DIR / f"{name}.parquet"
            if path.exists():
                try:
                    status[name] = len(pd.read_parquet(path))
                except Exception:
                    status[name] = -1
            else:
                status[name] = 0
        return status

    def get_email_dataset(self, days: int = 30,
                          customer: Optional[str] = None) -> list:
        """Query email dataset records."""
        path = DATASET_DIR / "email_dataset.parquet"
        if not path.exists():
            return []
        df = pd.read_parquet(path)
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
        df = df[df['date'] >= cutoff]
        if customer:
            df = df[df['customer'].str.upper() == customer.upper()]
        return df.to_dict('records')[-100:]

    # ──────────────────────────────────────────────────────────────────────
    # SYSTEM STATUS
    # ──────────────────────────────────────────────────────────────────────

    def get_system_status(self) -> dict:
        """System health check for /api/status."""
        df = self.load_rates()
        return {
            "api": "online",
            "timestamp": datetime.now().isoformat(),
            "parquet": {
                "loaded": df is not None,
                "rates": len(df) if df is not None else 0,
            },
            "shipment_state": SHIPMENT_STATE.exists(),
            "customer_rules": CUSTOMER_RULES.exists(),
            "team_rules": TEAM_RULES.exists(),
            "datasets": {
                "email": (DATASET_DIR / "email_dataset.parquet").exists(),
                "shipment_history": (DATASET_DIR / "shipment_history.parquet").exists(),
            },
        }


# ──────────────────────────────────────────────────────────────────────────────
# SINGLETON INSTANCE — with PostgreSQL auto-detection
# ──────────────────────────────────────────────────────────────────────────────

def _create_dal() -> DataAccessLayer:
    """
    Factory: create the right DAL based on environment.

    If DATABASE_URL is set → hybrid mode:
      - Quotes, Shipments, Events → PostgreSQL (dal_postgres.py)
      - Rates → Parquet (always, performance)
      - Config files → JSON (always, read-only)

    If DATABASE_URL is not set → pure file mode (current).
    """
    file_dal = DataAccessLayer()

    database_url = os.environ.get("DATABASE_URL", "")
    if database_url:
        try:
            from database.dal_postgres import pg_dal
            log.info("DATABASE_URL detected — PostgreSQL mode for quotes/shipments")

            # Monkey-patch: replace quote/shipment methods with PG versions
            file_dal.load_quotes_data    = pg_dal.load_quotes_data
            file_dal.save_quotes_data    = pg_dal.save_quotes_data
            file_dal.get_quote           = pg_dal.get_quote
            file_dal.list_quotes         = pg_dal.list_quotes
            file_dal.load_shipment_state = pg_dal.load_shipment_state
            file_dal.save_shipment_state = pg_dal.save_shipment_state
            file_dal._pg_dal             = pg_dal

            log.info("PostgreSQL DAL mounted (quotes, shipments → PG; rates → Parquet)")
        except ImportError as e:
            log.warning("PostgreSQL driver not installed (%s) — falling back to JSON", e)
        except Exception as e:
            log.error("PostgreSQL setup failed: %s — falling back to JSON", e)
    else:
        log.info("No DATABASE_URL — using JSON file backend")

    return file_dal


dal = _create_dal()
