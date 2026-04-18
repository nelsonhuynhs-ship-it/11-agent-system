# -*- coding: utf-8 -*-
"""
shipment_brief.py — FastAPI router for Shipment Brain retrieval endpoints.

Endpoints:
  POST /api/shipment/brief          — NL query → Telegram markdown brief
  GET  /api/shipment/{shipment_ref} — Direct lookup, full event list
  GET  /api/shipment/top-active     — Morning brief: top N active shipments

Integration contract:
  - Phase 02 provides email_engine.core.shipment_db  (get_conn, get_shipment, get_events)
  - Phase 02 provides email_engine.core.llm_client   (llm_call)
  Both are imported via try/except — 503 returned if unavailable.
"""
from __future__ import annotations

import json
import logging
import time
from functools import wraps
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

log = logging.getLogger("shipment_brief")

# ── Phase-02 DB import (graceful) ─────────────────────────────────────────────
try:
    from email_engine.core.shipment_db import (  # type: ignore
        get_conn,
        get_shipment,
        get_events,
    )
    _DB_AVAILABLE = True
except ImportError:
    try:
        from shipment_db import get_conn, get_shipment, get_events  # type: ignore
        _DB_AVAILABLE = True
    except ImportError:
        _DB_AVAILABLE = False
        get_conn = get_shipment = get_events = None  # type: ignore

# ── Phase-03 own modules ──────────────────────────────────────────────────────
try:
    from email_engine.core.query_parser import parse_query  # type: ignore
except ImportError:
    from query_parser import parse_query  # type: ignore

try:
    from email_engine.core.brief_synthesizer import synthesize  # type: ignore
except ImportError:
    from brief_synthesizer import synthesize  # type: ignore

# ── Vault base path ────────────────────────────────────────────────────────────
_VAULT_CANDIDATES = [
    Path("D:/OneDrive/NelsonData/vault"),
    Path(__file__).parent.parent / "vault",
]

def _vault_base() -> Optional[Path]:
    for p in _VAULT_CANDIDATES:
        if p.exists():
            return p
    return None

# ── Fuzzy suggestions (rapidfuzz optional) ────────────────────────────────────
try:
    from rapidfuzz import process as rf_process, fuzz as rf_fuzz  # type: ignore
    _FUZZY_AVAILABLE = True
except ImportError:
    _FUZZY_AVAILABLE = False


# ── Simple dict-based TTL cache (60s) ─────────────────────────────────────────
_QUERY_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 60  # seconds


def _cache_get(key: str) -> Optional[Any]:
    entry = _QUERY_CACHE.get(key)
    if entry and (time.time() - entry[0]) < _CACHE_TTL:
        return entry[1]
    _QUERY_CACHE.pop(key, None)
    return None


def _cache_set(key: str, value: Any) -> None:
    _QUERY_CACHE[key] = (time.time(), value)


# ── Router ────────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/shipment", tags=["shipment"])


# ── Request / Response models ─────────────────────────────────────────────────
class BriefRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Natural-language shipment query")


class BriefResponse(BaseModel):
    status: str  # "ok" | "multiple" | "not_found"
    brief: Optional[str] = None
    shipments: Optional[list] = None
    suggestions: Optional[list] = None


# ── Internal helpers ──────────────────────────────────────────────────────────
def _require_db() -> None:
    if not _DB_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "shipment_db module unavailable (Phase 02 not deployed)",
                "hint": "Deploy Phase 02 first, then restart web_server.py",
            },
        )


def _sql_lookup(ref: Optional[str], customer: Optional[str]) -> list[dict]:
    """Query DuckDB for matching shipments + their events.

    Returns list of dicts:
      {"shipment": {row}, "events": [{row}, ...]}
    """
    conn = get_conn()
    results = []

    try:
        # Build WHERE clause — require at least one condition
        clauses = []
        params: list = []

        if ref:
            clauses.append("s.shipment_id ILIKE ?")
            params.append(f"%{ref}%")
        if customer:
            clauses.append("s.customer_id ILIKE ?")
            params.append(f"%{customer}%")

        if not clauses:
            return []

        where = " AND ".join(clauses)
        sql = f"""
            SELECT s.*
            FROM shipments s
            WHERE {where}
            ORDER BY s.created_at DESC
            LIMIT 20
        """
        rows = conn.execute(sql, params).fetchdf()

        for _, row in rows.iterrows():
            shipment = row.to_dict()
            ship_id = shipment.get("shipment_id")
            events: list[dict] = []
            if ship_id:
                ev_df = conn.execute(
                    "SELECT * FROM shipment_events WHERE shipment_id = ? ORDER BY event_date ASC",
                    [ship_id],
                ).fetchdf()
                events = ev_df.to_dict(orient="records")
            results.append({"shipment": shipment, "events": events})

    except Exception as exc:
        log.error(f"SQL lookup failed: {exc}")
        raise HTTPException(status_code=503, detail={"error": f"DB query failed: {exc}"})
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return results


def _read_vault(customer_id: str, shipment_ref: str) -> str:
    """Read vault markdown file, return last 2000 chars."""
    base = _vault_base()
    if not base:
        return ""
    path = base / "customers" / customer_id / f"{shipment_ref}.md"
    if path.exists():
        try:
            text = path.read_text(encoding="utf-8")
            return text[-2000:]  # last 2000 chars = most recent context
        except Exception as exc:
            log.warning(f"Vault read failed for {path}: {exc}")
    return ""


def _fuzzy_suggest(query: str, limit: int = 3) -> list[dict]:
    """Return top-N fuzzy matches against all shipment_ids in DB."""
    if not _DB_AVAILABLE:
        return []
    try:
        conn = get_conn()
        try:
            rows = conn.execute(
                "SELECT shipment_id, customer_id FROM shipments ORDER BY created_at DESC LIMIT 500"
            ).fetchall()
        finally:
            conn.close()
    except Exception:
        return []

    candidates = [f"{r[0]} ({r[1]})" for r in rows]
    ids = [r[0] for r in rows]

    if _FUZZY_AVAILABLE and candidates:
        matches = rf_process.extract(
            query, candidates, scorer=rf_fuzz.WRatio, limit=limit
        )
        return [{"shipment_id": ids[candidates.index(m[0])], "score": m[1]} for m in matches if m[1] > 30]

    # Naive fallback: substring match
    q = query.upper()
    results = []
    for i, c in enumerate(candidates):
        if any(part in c.upper() for part in q.split()):
            results.append({"shipment_id": ids[i], "score": 50})
            if len(results) >= limit:
                break
    return results


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/brief", response_model=BriefResponse)
async def post_brief(req: BriefRequest) -> BriefResponse:
    """Parse natural-language query and return Telegram markdown brief.

    - 1 match  → synthesize brief via LLM (or fallback template)
    - N matches → return list for user to pick
    - 0 matches → return fuzzy suggestions
    """
    _require_db()

    # Check cache
    cached = _cache_get(req.query)
    if cached is not None:
        log.debug(f"Cache hit for query: {req.query[:50]!r}")
        return BriefResponse(**cached)

    # Parse
    parsed = parse_query(req.query)
    ref      = parsed.get("ref")
    customer = parsed.get("customer")

    if not ref and not customer:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Cannot extract shipment ref or customer from query",
                "hint": "Include a shipment ref (e.g. ACB2604) or customer name",
            },
        )

    # DB lookup
    matches = _sql_lookup(ref, customer)

    if not matches:
        suggestions = _fuzzy_suggest(req.query)
        result = {"status": "not_found", "suggestions": suggestions}
        _cache_set(req.query, result)
        return BriefResponse(**result)

    if len(matches) > 1:
        shipments_summary = [
            {
                "shipment_id": m["shipment"]["shipment_id"],
                "customer_id": m["shipment"].get("customer_id"),
                "pol":         m["shipment"].get("pol"),
                "pod":         m["shipment"].get("pod"),
                "status":      m["shipment"].get("status"),
                "event_count": len(m["events"]),
            }
            for m in matches[:10]
        ]
        result = {"status": "multiple", "shipments": shipments_summary}
        _cache_set(req.query, result)
        return BriefResponse(**result)

    # Exactly 1 match — synthesize brief
    match = matches[0]
    shipment_row = match["shipment"]
    events       = match["events"]
    vault_text   = _read_vault(
        str(shipment_row.get("customer_id", "")),
        str(shipment_row.get("shipment_id", "")),
    )

    brief_md = await synthesize(shipment_row, events, vault_text)
    result = {"status": "ok", "brief": brief_md}
    _cache_set(req.query, result)
    return BriefResponse(**result)


@router.get("/top-active")
async def get_top_active(limit: int = Query(default=5, ge=1, le=20)) -> dict:
    """Return morning brief: top N active shipments ordered by latest event."""
    _require_db()

    cache_key = f"top_active_{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        conn = get_conn()
        try:
            sql = """
                SELECT s.shipment_id, s.customer_id, s.pol, s.pod, s.carrier,
                       s.status, MAX(e.event_date) AS last_event_date
                FROM shipments s
                LEFT JOIN shipment_events e ON s.shipment_id = e.shipment_id
                WHERE s.status NOT IN ('COMPLETED', 'CANCELLED', 'CLOSED')
                GROUP BY s.shipment_id, s.customer_id, s.pol, s.pod, s.carrier, s.status
                ORDER BY last_event_date DESC NULLS LAST
                LIMIT ?
            """
            rows = conn.execute(sql, [limit]).fetchdf()
        finally:
            conn.close()
    except Exception as exc:
        log.error(f"top-active query failed: {exc}")
        raise HTTPException(status_code=503, detail={"error": str(exc)})

    if rows.empty:
        return {"brief": "Không có lô hàng đang hoạt động.", "count": 0}

    # Build morning brief markdown
    lines = [f"🌅 TOP {limit} LÔ HÀNG ĐANG THEO DÕI — {time.strftime('%Y-%m-%d')}"]
    for i, (_, row) in enumerate(rows.iterrows(), 1):
        last = str(row.get("last_event_date", "?"))[:10]
        lines.append(
            f"{i}. 📦 {row['shipment_id']} · {row.get('customer_id','?')} "
            f"· {row.get('pol','?')}→{row.get('pod','?')} "
            f"· {row.get('status','?')} ({last})"
        )

    brief = "\n".join(lines)
    result = {"brief": brief, "count": len(rows)}
    _cache_set(cache_key, result)
    return result


@router.get("/{shipment_ref}")
async def get_shipment_detail(shipment_ref: str) -> dict:
    """Direct lookup by shipment_ref — returns full event list + vault path."""
    _require_db()

    # Validate ref format loosely (prevent path traversal etc.)
    import re as _re
    if not _re.match(r"^[A-Z0-9_\-]{3,20}$", shipment_ref.upper()):
        raise HTTPException(status_code=400, detail={"error": "Invalid shipment_ref format"})

    cache_key = f"detail_{shipment_ref.upper()}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        conn = get_conn()
        try:
            ship_df = conn.execute(
                "SELECT * FROM shipments WHERE shipment_id ILIKE ? LIMIT 1",
                [shipment_ref],
            ).fetchdf()
            if ship_df.empty:
                raise HTTPException(status_code=404, detail={"error": f"Shipment '{shipment_ref}' not found"})

            shipment = ship_df.iloc[0].to_dict()
            ev_df = conn.execute(
                "SELECT * FROM shipment_events WHERE shipment_id = ? ORDER BY event_date ASC",
                [shipment.get("shipment_id", shipment_ref)],
            ).fetchdf()
            events = ev_df.to_dict(orient="records")
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as exc:
        log.error(f"get_shipment_detail failed: {exc}")
        raise HTTPException(status_code=503, detail={"error": str(exc)})

    # Vault path (may or may not exist)
    base   = _vault_base()
    cid    = str(shipment.get("customer_id", ""))
    ref_id = str(shipment.get("shipment_id", shipment_ref))
    vault_path = str(base / "customers" / cid / f"{ref_id}.md") if base else None

    result = {
        "shipment":   shipment,
        "events":     events,
        "vault_path": vault_path,
        "event_count": len(events),
    }
    _cache_set(cache_key, result)
    return result
