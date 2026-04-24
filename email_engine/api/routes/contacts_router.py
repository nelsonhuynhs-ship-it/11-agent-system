# contacts_router.py — Contacts Tab API (Phase 4, Email Dashboard v6)
# 8 endpoints for CNEE/SHIPPER contact management via DuckDB on contact_unified_v6.xlsx
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import duckdb
import pandas as pd
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

log = logging.getLogger("contacts_router")

# ── Paths ─────────────────────────────────────────────────────────────────────
_ONEDRIVE = Path("D:/OneDrive/NelsonData/email")
# v7 primary; fall back to v6 only if v7 missing. Variable name kept for back-compat.
_V7 = _ONEDRIVE / "contact_unified_v7.xlsx"
_V6 = _ONEDRIVE / "contact_unified_v6.xlsx"
UNIFIED_V6 = _V7 if _V7.exists() else _V6
BACKUP_DIR  = _ONEDRIVE / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

_ENGINE_TEST = Path(__file__).parent.parent.parent.parent
_SCRIPTS     = _ENGINE_TEST / "scripts"

# 5 columns that must NEVER be overwritten by inline edit / import
_LOCKED_ALWAYS = {"EMAIL_STATUS", "SEND_COUNT_EMAIL", "SEND_COUNT_WA", "SEND_COUNT_LI",
                  "LAST_SENT_EMAIL", "LAST_SENT_WA", "LAST_SENT_LI",
                  "REPLY_STATUS"}
# TIER also locked when value is CUSTOMER or VIP
_TIER_LOCK_VALUES = {"CUSTOMER", "VIP"}

# ── DuckDB in-memory cache ────────────────────────────────────────────────────
_con: duckdb.DuckDBPyConnection | None = None
_loaded_at: datetime | None = None
_CACHE_TTL_SECONDS = 300  # 5 min cache


def _get_con() -> duckdb.DuckDBPyConnection:
    global _con, _loaded_at
    now = datetime.now()
    if _con is None or _loaded_at is None or (now - _loaded_at).total_seconds() > _CACHE_TTL_SECONDS:
        _reload_cache()
    return _con  # type: ignore[return-value]


def _reload_cache() -> None:
    global _con, _loaded_at
    if not UNIFIED_V6.exists():
        log.warning(f"contact_unified_v6.xlsx not found at {UNIFIED_V6}")
        _con = duckdb.connect()
        _con.execute("CREATE TABLE IF NOT EXISTS cnee AS SELECT 1 AS dummy WHERE FALSE")
        _con.execute("CREATE TABLE IF NOT EXISTS shipper AS SELECT 1 AS dummy WHERE FALSE")
        _loaded_at = datetime.now()
        return

    try:
        df_cnee    = pd.read_excel(UNIFIED_V6, sheet_name="CNEE")
        df_shipper = pd.read_excel(UNIFIED_V6, sheet_name="SHIPPER")
        df_cnee.columns    = df_cnee.columns.str.strip().str.upper()
        df_shipper.columns = df_shipper.columns.str.strip().str.upper()

        con = duckdb.connect()
        con.register("cnee_df",    df_cnee)
        con.register("shipper_df", df_shipper)
        con.execute("CREATE TABLE cnee    AS SELECT * FROM cnee_df")
        con.execute("CREATE TABLE shipper AS SELECT * FROM shipper_df")

        _con        = con
        _loaded_at  = datetime.now()
        log.info(f"DuckDB cache reloaded: CNEE={len(df_cnee)}, SHIPPER={len(df_shipper)}")
    except Exception as exc:
        log.error(f"Failed to load contact_unified_v6.xlsx: {exc}")
        raise RuntimeError(str(exc)) from exc


def _invalidate_cache() -> None:
    global _con, _loaded_at
    _con = None
    _loaded_at = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _table(sheet: str) -> str:
    return "shipper" if sheet.upper() == "SHIPPER" else "cnee"


def _row_to_dict(row: Any) -> dict:
    """Convert DuckDB Row/tuple + description to plain dict."""
    if hasattr(row, "_asdict"):
        return dict(row._asdict())
    return dict(row)


def _count_rows(sheet: str) -> int:
    try:
        con = _get_con()
        tbl = _table(sheet)
        return con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    except Exception:
        return 0


def _save_to_xlsx(sheet: str, df: pd.DataFrame) -> None:
    """Write one sheet back to UNIFIED_V6 without touching the other sheet."""
    other_sheet = "SHIPPER" if sheet.upper() == "CNEE" else "CNEE"
    try:
        df_other = pd.read_excel(UNIFIED_V6, sheet_name=other_sheet)
    except Exception:
        df_other = pd.DataFrame()

    with pd.ExcelWriter(UNIFIED_V6, engine="openpyxl") as writer:
        if sheet.upper() == "CNEE":
            df.to_excel(writer, sheet_name="CNEE", index=False)
            df_other.to_excel(writer, sheet_name="SHIPPER", index=False)
        else:
            df_other.to_excel(writer, sheet_name="CNEE", index=False)
            df.to_excel(writer, sheet_name="SHIPPER", index=False)


def _make_backup() -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    dest = BACKUP_DIR / f"contact_unified_v6.backup_{ts}.xlsx"
    shutil.copy2(UNIFIED_V6, dest)
    log.info(f"Backup created: {dest.name}")
    return dest.name


# ── Models ────────────────────────────────────────────────────────────────────

class ContactPatch(BaseModel):
    sheet: str = "CNEE"
    fields: dict[str, Any]  # column → new value


class ContactCreate(BaseModel):
    sheet: str = "CNEE"
    email: str
    company: str = ""
    pic: str = ""
    state: str = ""
    timezone: str = ""
    tier: str = "COLD"
    commodity: str = ""
    extra: dict[str, Any] = {}


# ── Router ────────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/v6/contacts", tags=["contacts-v6"])


# 1. GET /api/contacts — paginated list with filters
@router.get("")
def list_contacts(
    sheet: str = Query("CNEE"),
    tier: Optional[str] = Query(None),
    commodity: Optional[str] = Query(None),
    tz: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    has_whatsapp: Optional[bool] = Query(None),
    q: Optional[str] = Query(None, description="Fuzzy search email/company"),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
):
    try:
        con   = _get_con()
        tbl   = _table(sheet)
        where = ["1=1"]
        params: list[Any] = []

        if tier:
            where.append("UPPER(TIER) = UPPER(?)")
            params.append(tier)
        if commodity:
            where.append("UPPER(COMMODITY_CATEGORY) LIKE UPPER(?)")
            params.append(f"%{commodity}%")
        if tz:
            where.append("UPPER(TIMEZONE) = UPPER(?)")
            params.append(tz)
        if state:
            where.append("UPPER(STATE) = UPPER(?)")
            params.append(state)
        if has_whatsapp is not None:
            if has_whatsapp:
                where.append("WHATSAPP IS NOT NULL AND WHATSAPP != ''")
            else:
                where.append("(WHATSAPP IS NULL OR WHATSAPP = '')")
        if q:
            where.append("(LOWER(EMAIL) LIKE LOWER(?) OR LOWER(COMPANY) LIKE LOWER(?))")
            params.extend([f"%{q}%", f"%{q}%"])

        where_sql = " AND ".join(where)
        offset    = (page - 1) * limit

        # Safe column check — not all schemas guaranteed to have every column
        # DuckDB PRAGMA table_info returns (cid, name, type, notnull, dflt, pk) — use r[1] for name
        cols_available = {r[1].upper() for r in con.execute(f"PRAGMA table_info({tbl})").fetchall()}

        def col(c: str) -> str:
            return c if c in cols_available else f"NULL AS {c}"

        sel_cols = ", ".join([
            col("EMAIL"), col("COMPANY"), col("PIC"), col("STATE"),
            col("TIMEZONE"), col("TIER"), col("EMAIL_STATUS"),
            col("SEND_COUNT_EMAIL"), col("LAST_SENT_EMAIL"),
            col("WHATSAPP"), col("COMMODITY_CATEGORY"), col("REPLY_STATUS"),
        ])

        total_q = f"SELECT COUNT(*) FROM {tbl} WHERE {where_sql}"
        total   = con.execute(total_q, params).fetchone()[0]

        rows_q = (
            f"SELECT {sel_cols} FROM {tbl} "
            f"WHERE {where_sql} "
            f"ORDER BY COMPANY NULLS LAST "
            f"LIMIT {limit} OFFSET {offset}"
        )
        rows = con.execute(rows_q, params).fetchall()
        desc = con.description

        contacts = [dict(zip([d[0] for d in desc], row)) for row in rows]

        # Stats for sidebar
        tier_counts_raw = con.execute(
            f"SELECT TIER, COUNT(*) AS n FROM {tbl} WHERE {where_sql} GROUP BY TIER",
            params,
        ).fetchall()
        tier_counts = {r[0]: r[1] for r in tier_counts_raw}

        typo_count = 0
        if "TYPO_FLAG" in cols_available:
            typo_count = con.execute(
                f"SELECT COUNT(*) FROM {tbl} WHERE TYPO_FLAG = TRUE"
            ).fetchone()[0]

        return {
            "sheet": sheet.upper(),
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit,
            "contacts": contacts,
            "stats": {"tier_breakdown": tier_counts, "typo_suspects": typo_count},
        }
    except Exception as exc:
        log.error(f"list_contacts error: {exc}")
        raise HTTPException(500, str(exc))


# 2. GET /api/contacts/:email — detail
@router.get("/{email:path}")
def get_contact(email: str, sheet: str = Query("CNEE")):
    try:
        con = _get_con()
        tbl = _table(sheet)
        row = con.execute(
            f"SELECT * FROM {tbl} WHERE LOWER(EMAIL) = LOWER(?)", [email]
        ).fetchone()
        if row is None:
            raise HTTPException(404, f"{email} not found in {sheet}")
        desc = con.description
        return dict(zip([d[0] for d in desc], row))
    except HTTPException:
        raise
    except Exception as exc:
        log.error(f"get_contact error: {exc}")
        raise HTTPException(500, str(exc))


# 3. PATCH /api/contacts/:email — inline edit with 5-col LOCK
@router.patch("/{email:path}")
def patch_contact(email: str, payload: ContactPatch):
    try:
        if not UNIFIED_V6.exists():
            raise HTTPException(503, "contact_unified_v6.xlsx not found")

        sheet = payload.sheet.upper()
        fields = dict(payload.fields)

        # Enforce 5-col LOCK — strip always-locked cols
        for locked in _LOCKED_ALWAYS:
            fields.pop(locked, None)

        # TIER lock if current value is CUSTOMER/VIP
        df = pd.read_excel(UNIFIED_V6, sheet_name=sheet)
        df.columns = df.columns.str.strip().str.upper()
        email_col = "EMAIL"
        if email_col not in df.columns:
            raise HTTPException(400, "EMAIL column not found in sheet")

        mask = df[email_col].astype(str).str.lower() == email.lower()
        if not mask.any():
            raise HTTPException(404, f"{email} not found in {sheet}")

        cur_tier = str(df.loc[mask, "TIER"].iloc[0]).upper() if "TIER" in df.columns else ""
        if cur_tier in _TIER_LOCK_VALUES:
            fields.pop("TIER", None)

        # Apply edits
        _make_backup()
        for col_name, val in fields.items():
            if col_name.upper() in df.columns:
                df.loc[mask, col_name.upper()] = val

        _save_to_xlsx(sheet, df)
        _invalidate_cache()
        log.info(f"PATCH {email} ({sheet}): {list(fields.keys())}")
        return {"ok": True, "updated": list(fields.keys())}
    except HTTPException:
        raise
    except Exception as exc:
        log.error(f"patch_contact error: {exc}")
        raise HTTPException(500, str(exc))


# 4. POST /api/contacts — manual add
@router.post("")
def create_contact(payload: ContactCreate):
    try:
        if not UNIFIED_V6.exists():
            raise HTTPException(503, "contact_unified_v6.xlsx not found")

        sheet = payload.sheet.upper()
        df = pd.read_excel(UNIFIED_V6, sheet_name=sheet)
        df.columns = df.columns.str.strip().str.upper()

        if "EMAIL" in df.columns:
            exists = df["EMAIL"].astype(str).str.lower().eq(payload.email.lower()).any()
            if exists:
                raise HTTPException(409, f"{payload.email} already exists")

        new_row: dict[str, Any] = {
            "EMAIL": payload.email,
            "COMPANY": payload.company,
            "PIC": payload.pic,
            "STATE": payload.state,
            "TIMEZONE": payload.timezone,
            "TIER": payload.tier,
            "COMMODITY_CATEGORY": payload.commodity,
            "EMAIL_STATUS": "ACTIVE",
            **payload.extra,
        }
        _make_backup()
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        _save_to_xlsx(sheet, df)
        _invalidate_cache()
        log.info(f"Created contact {payload.email} ({sheet})")
        return {"ok": True, "email": payload.email}
    except HTTPException:
        raise
    except Exception as exc:
        log.error(f"create_contact error: {exc}")
        raise HTTPException(500, str(exc))


# 5. DELETE /api/contacts/:email — soft delete (EMAIL_STATUS = DEAD)
@router.delete("/{email:path}")
def delete_contact(email: str, sheet: str = Query("CNEE")):
    try:
        if not UNIFIED_V6.exists():
            raise HTTPException(503, "contact_unified_v6.xlsx not found")

        sheet_upper = sheet.upper()
        df = pd.read_excel(UNIFIED_V6, sheet_name=sheet_upper)
        df.columns = df.columns.str.strip().str.upper()

        if "EMAIL" not in df.columns:
            raise HTTPException(400, "EMAIL column not found")

        mask = df["EMAIL"].astype(str).str.lower() == email.lower()
        if not mask.any():
            raise HTTPException(404, f"{email} not found in {sheet_upper}")

        _make_backup()
        df.loc[mask, "EMAIL_STATUS"] = "DEAD"
        _save_to_xlsx(sheet_upper, df)
        _invalidate_cache()
        log.info(f"Soft-deleted {email} ({sheet_upper}) → EMAIL_STATUS=DEAD")
        return {"ok": True, "email": email, "status": "DEAD"}
    except HTTPException:
        raise
    except Exception as exc:
        log.error(f"delete_contact error: {exc}")
        raise HTTPException(500, str(exc))


# 6. POST /api/contacts/refresh-master — trigger migration + diff preview
@router.post("/refresh-master")
def refresh_master(dry_run: bool = True):
    try:
        migrate_script = _SCRIPTS / "migrate-to-unified-v6.py"
        if not migrate_script.exists():
            raise HTTPException(503, f"migrate-to-unified-v6.py not found at {migrate_script}")

        cmd = [sys.executable, str(migrate_script), "--dry-run" if dry_run else "--apply"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            log.error(f"migrate script error: {result.stderr}")
            raise HTTPException(500, result.stderr[:500])

        # Parse diff preview from stdout (expected JSON output from script)
        try:
            diff = json.loads(result.stdout)
        except json.JSONDecodeError:
            diff = {"raw_output": result.stdout[:2000]}

        if not dry_run:
            _invalidate_cache()

        return {
            "dry_run": dry_run,
            "diff": diff,
            "applied": not dry_run,
        }
    except HTTPException:
        raise
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Migration script timed out (>120s)")
    except Exception as exc:
        log.error(f"refresh_master error: {exc}")
        raise HTTPException(500, str(exc))


# 7. POST /api/contacts/import-panjiva — drag-drop raw file + merge
@router.post("/import-panjiva")
async def import_panjiva(file: UploadFile = File(...)):
    try:
        panjiva_script = _SCRIPTS / "panjiva_clean_v2.py"
        if not panjiva_script.exists():
            # Try legacy name
            panjiva_script = _SCRIPTS / "panjiva_clean.py"
        if not panjiva_script.exists():
            raise HTTPException(503, "panjiva_clean_v2.py not found")

        # Save upload to temp file
        suffix = Path(file.filename or "upload.xlsx").suffix or ".xlsx"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            # 2026-04-24 HIGH-2: bound upload to 50MB — Panjiva exports ~5-20MB.
            if len(content) > 50 * 1024 * 1024:
                tmp.close()
                Path(tmp.name).unlink(missing_ok=True)
                raise HTTPException(413, "File too large (max 50MB)")
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            cmd = [sys.executable, str(panjiva_script), "--input", str(tmp_path), "--merge"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        finally:
            tmp_path.unlink(missing_ok=True)

        if result.returncode != 0:
            raise HTTPException(500, result.stderr[:500])

        try:
            summary = json.loads(result.stdout)
        except json.JSONDecodeError:
            summary = {"raw_output": result.stdout[:2000]}

        _invalidate_cache()
        return {"ok": True, "filename": file.filename, "summary": summary}
    except HTTPException:
        raise
    except Exception as exc:
        log.error(f"import_panjiva error: {exc}")
        raise HTTPException(500, str(exc))


# 8. POST /api/contacts/rollback — restore last backup
@router.post("/rollback")
def rollback_backup(backup_name: Optional[str] = None):
    try:
        backups = sorted(BACKUP_DIR.glob("contact_unified_v6.backup_*.xlsx"), reverse=True)
        if not backups:
            raise HTTPException(404, "No backups found")

        if backup_name:
            target = BACKUP_DIR / backup_name
            if not target.exists():
                raise HTTPException(404, f"Backup {backup_name} not found")
        else:
            target = backups[0]  # most recent

        _make_backup()  # backup current before overwriting
        shutil.copy2(target, UNIFIED_V6)
        _invalidate_cache()
        log.info(f"Rolled back to {target.name}")
        return {
            "ok": True,
            "restored": target.name,
            "available_backups": [b.name for b in backups[:10]],
        }
    except HTTPException:
        raise
    except Exception as exc:
        log.error(f"rollback error: {exc}")
        raise HTTPException(500, str(exc))


# Utility: list available backups
@router.get("/backups")
def list_backups():
    backups = sorted(BACKUP_DIR.glob("contact_unified_v6.backup_*.xlsx"), reverse=True)
    return {
        "count": len(backups),
        "backups": [{"name": b.name, "size_kb": round(b.stat().st_size / 1024, 1)} for b in backups[:20]],
    }


# Utility: force cache reload
@router.post("/cache-reload")
def cache_reload():
    try:
        _reload_cache()
        return {"ok": True, "loaded_at": _loaded_at.isoformat() if _loaded_at else None}
    except Exception as exc:
        raise HTTPException(500, str(exc))


# 9. GET /api/contacts/typo-suspects — return typo suspect list from CSV
@router.get("/typo-suspects")
def get_typo_suspects(limit: int = Query(500, ge=1, le=5000)):
    """Return typo suspects from backups/typo_suspects_*.csv (most recent file)."""
    try:
        # Search for most recent typo_suspects CSV
        candidates = sorted(BACKUP_DIR.glob("typo_suspects_*.csv"), reverse=True)
        if not candidates:
            # Try adjacent paths
            alt = _ONEDRIVE / "typo_suspects_20260422.csv"
            if alt.exists():
                candidates = [alt]

        if not candidates:
            return {"suspects": [], "source": "no file found", "count": 0}

        csv_path = candidates[0]
        suspects: list[dict] = []
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            import csv as _csv
            reader = _csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= limit:
                    break
                # Normalize common column names
                suspects.append({
                    "email":       row.get("email") or row.get("EMAIL") or "",
                    "company":     row.get("company") or row.get("COMPANY") or "",
                    "fix":         row.get("fix") or row.get("suggested_fix") or row.get("FIX") or "",
                    "confidence":  float(row.get("confidence") or row.get("CONFIDENCE") or 0),
                    "typo_type":   row.get("typo_type") or row.get("TYPO_TYPE") or "",
                })

        return {
            "suspects": suspects,
            "count": len(suspects),
            "source": csv_path.name,
        }
    except Exception as exc:
        log.error(f"get_typo_suspects error: {exc}")
        raise HTTPException(500, str(exc))
