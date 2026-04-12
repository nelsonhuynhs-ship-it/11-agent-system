# -*- coding: utf-8 -*-
"""
sync_router.py — ERP ↔ Cloud Sync Endpoints
=============================================
Endpoints for ERP Excel to push/pull quotes, customers, rates.
Single source of truth = PostgreSQL.

POST /api/sync/quote         — ERP pushes quote → DB
GET  /api/sync/quotes        — ERP pulls updates since last sync
POST /api/sync/customer      — ERP pushes customer → DB
GET  /api/sync/customers     — ERP pulls customer list
POST /api/sync/rates         — Import active rates from parquet
GET  /api/sync/status        — Sync health check
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database.connection import execute_sync, is_postgres_configured

log = logging.getLogger("nelson.sync")
router = APIRouter(prefix="/api/sync", tags=["ERP Sync"])

TENANT_ID = "0193a5b0-7000-7000-8000-000000000001"


# ── Models ────────────────────────────────────────────────────────────────────

class CarrierRate(BaseModel):
    carrier: str
    badge: Optional[str] = None
    container_rates: dict = {}
    carrier_markup: dict = {}
    transit: Optional[str] = None
    freetime: Optional[str] = None
    note: Optional[str] = None
    effective: Optional[str] = None
    expiry: Optional[str] = None


class QuoteSync(BaseModel):
    id: str
    customer: str
    pol: str
    pod: Optional[str] = None
    place: Optional[str] = None
    routing: Optional[str] = None
    service_type: str = "CY-CY"
    status: str = "DRAFT"
    markup_mode: str = "global"
    global_markup: float = 0
    transit: Optional[str] = None
    freetime: Optional[str] = None
    validity: Optional[str] = None
    eff: Optional[str] = None
    exp: Optional[str] = None
    carriers: List[CarrierRate] = []
    metadata: dict = {}


class CustomerSync(BaseModel):
    code: str
    name: str
    tax_code: Optional[str] = None
    sales_rep: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    ports: list = []
    cargo_type: Optional[str] = None
    contacts: list = []
    crm_status: str = "Potential"


# ── Quote Sync ────────────────────────────────────────────────────────────────

@router.post("/quote")
def push_quote(q: QuoteSync):
    """ERP pushes a quote to PostgreSQL."""
    if not is_postgres_configured():
        raise HTTPException(503, "PostgreSQL not configured")

    execute_sync("""
        INSERT INTO quotes (id, tenant_id, customer, pol, pod, place, routing,
            service_type, status, markup_mode, global_markup, transit, freetime,
            validity, eff, exp, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            customer = EXCLUDED.customer, pol = EXCLUDED.pol, pod = EXCLUDED.pod,
            place = EXCLUDED.place, routing = EXCLUDED.routing, status = EXCLUDED.status,
            global_markup = EXCLUDED.global_markup, transit = EXCLUDED.transit,
            freetime = EXCLUDED.freetime, validity = EXCLUDED.validity,
            eff = EXCLUDED.eff, exp = EXCLUDED.exp, metadata = EXCLUDED.metadata,
            updated_at = NOW()
    """, (q.id, TENANT_ID, q.customer, q.pol, q.pod, q.place, q.routing,
          q.service_type, q.status, q.markup_mode, q.global_markup,
          q.transit, q.freetime, q.validity, q.eff, q.exp,
          str(q.metadata) if q.metadata else "{}"))

    # Upsert carriers
    execute_sync("DELETE FROM quote_carriers WHERE quote_id = %s", (q.id,))
    for c in q.carriers:
        execute_sync("""
            INSERT INTO quote_carriers (quote_id, carrier, badge, container_rates,
                carrier_markup, transit, freetime, note, effective, expiry)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (q.id, c.carrier, c.badge, str(c.container_rates),
              str(c.carrier_markup), c.transit, c.freetime, c.note,
              c.effective, c.expiry))

    # Log event
    execute_sync("""
        INSERT INTO events (tenant_id, entity_type, entity_id, event_type, payload, source, actor)
        VALUES (%s, 'quote', %s, 'synced_from_erp', '{}', 'erp', 'nelson')
    """, (TENANT_ID, q.id))

    return {"status": "ok", "quote_id": q.id, "carriers": len(q.carriers)}


@router.get("/quotes")
def pull_quotes(since: str = Query(None), status: str = Query(None), limit: int = Query(50)):
    """ERP pulls quotes updated since last sync."""
    if not is_postgres_configured():
        raise HTTPException(503, "PostgreSQL not configured")

    query = "SELECT * FROM quotes WHERE tenant_id = %s"
    params = [TENANT_ID]

    if since:
        query += " AND updated_at > %s"
        params.append(since)
    if status:
        query += " AND status = %s"
        params.append(status)

    query += " ORDER BY updated_at DESC LIMIT %s"
    params.append(limit)

    rows = execute_sync(query, tuple(params))
    return {"quotes": rows, "count": len(rows), "synced_at": datetime.now().isoformat()}


# ── Customer Sync ─────────────────────────────────────────────────────────────

@router.post("/customer")
def push_customer(c: CustomerSync):
    """ERP pushes a customer to PostgreSQL."""
    if not is_postgres_configured():
        raise HTTPException(503, "PostgreSQL not configured")

    execute_sync("""
        INSERT INTO customers (tenant_id, code, name, tax_code, sales_rep, email, phone,
            address, ports, cargo_type, contacts, crm_status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, code) DO UPDATE SET
            name = EXCLUDED.name, tax_code = EXCLUDED.tax_code,
            sales_rep = EXCLUDED.sales_rep, email = EXCLUDED.email,
            phone = EXCLUDED.phone, address = EXCLUDED.address,
            ports = EXCLUDED.ports, contacts = EXCLUDED.contacts,
            crm_status = EXCLUDED.crm_status, updated_at = NOW()
    """, (TENANT_ID, c.code, c.name, c.tax_code, c.sales_rep, c.email, c.phone,
          c.address, str(c.ports), c.cargo_type, str(c.contacts), c.crm_status))

    return {"status": "ok", "customer_code": c.code}


@router.get("/customers")
def pull_customers(since: str = Query(None), limit: int = Query(100)):
    """ERP pulls customer list."""
    if not is_postgres_configured():
        raise HTTPException(503, "PostgreSQL not configured")

    query = "SELECT * FROM customers WHERE tenant_id = %s"
    params = [TENANT_ID]

    if since:
        query += " AND updated_at > %s"
        params.append(since)

    query += " ORDER BY updated_at DESC LIMIT %s"
    params.append(limit)

    rows = execute_sync(query, tuple(params))
    return {"customers": rows, "count": len(rows)}


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/status")
def sync_status():
    """Sync health check — counts and last sync times."""
    if not is_postgres_configured():
        return {"postgres": False}

    quotes = execute_sync("SELECT COUNT(*) as cnt FROM quotes WHERE tenant_id = %s", (TENANT_ID,))
    customers = execute_sync("SELECT COUNT(*) as cnt FROM customers WHERE tenant_id = %s", (TENANT_ID,))
    cnee = execute_sync("SELECT COUNT(*) as cnt, COUNT(*) FILTER (WHERE status = 'active') as active FROM cnee_master")
    last_event = execute_sync("SELECT MAX(created_at) as ts FROM events WHERE source = 'erp'")

    return {
        "postgres": True,
        "quotes": quotes[0]["cnt"],
        "customers": customers[0]["cnt"],
        "cnee_total": cnee[0]["cnt"],
        "cnee_active": cnee[0]["active"],
        "last_erp_sync": last_event[0]["ts"] if last_event else None,
        "checked_at": datetime.now().isoformat(),
    }
