# -*- coding: utf-8 -*-
"""
customer_check_router.py — Tax Code Double-Check + Customer Lookup
===================================================================
Check if a customer (by MST/tax code) is already assigned to another salesman.
Supports cross-sales lookup per Softek CRM requirements.

GET  /api/customers/check?tax_code=0312345678
GET  /api/customers/search?q=company+name
POST /api/customers/bulk_check  — check multiple tax codes at once
"""
from __future__ import annotations

import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database.connection import execute_sync, is_postgres_configured

log = logging.getLogger("nelson.customer_check")
router = APIRouter(prefix="/api/customers", tags=["Customer Check"])

TENANT_ID = "0193a5b0-7000-7000-8000-000000000001"


class BulkCheckRequest(BaseModel):
    tax_codes: List[str]


@router.get("/check")
def check_tax_code(tax_code: str = Query(..., min_length=3)):
    """
    Check if a customer with this tax code already exists.
    Used for double-check before creating new customer in CRM.
    Returns: existing customer info + assigned salesman, or not found.
    """
    if not is_postgres_configured():
        raise HTTPException(503, "PostgreSQL not configured")

    # Check in local customers table
    rows = execute_sync("""
        SELECT code, name, tax_code, sales_rep, crm_status, email, phone,
               crm_id, updated_at
        FROM customers
        WHERE tenant_id = %s AND tax_code = %s
    """, (TENANT_ID, tax_code.strip()))

    if rows:
        c = rows[0]
        return {
            "exists": True,
            "source": "local_db",
            "customer": {
                "code": c["code"],
                "name": c["name"],
                "tax_code": c["tax_code"],
                "sales_rep": c["sales_rep"],
                "crm_status": c["crm_status"],
                "email": c["email"],
                "phone": c["phone"],
                "crm_id": c["crm_id"],
            },
            "message": f"Customer already exists — assigned to {c['sales_rep'] or 'unassigned'}",
        }

    # Check in CNEE master (prospects)
    cnee = execute_sync("""
        SELECT company_name, email, contact_name, campaign, status
        FROM cnee_master
        WHERE company_name ILIKE '%' || %s || '%'
        LIMIT 5
    """, (tax_code,))

    if cnee:
        return {
            "exists": False,
            "source": "cnee_prospect",
            "prospects": [dict(r) for r in cnee],
            "message": "Not in customer DB, but found in prospect list",
        }

    return {
        "exists": False,
        "source": None,
        "message": "No customer or prospect found with this tax code",
    }


@router.get("/search")
def search_customers(q: str = Query(..., min_length=2), limit: int = Query(20)):
    """Search customers by name, email, or tax code."""
    if not is_postgres_configured():
        raise HTTPException(503, "PostgreSQL not configured")

    rows = execute_sync("""
        SELECT code, name, tax_code, sales_rep, crm_status, email, phone, updated_at
        FROM customers
        WHERE tenant_id = %s
          AND (name ILIKE %s OR email ILIKE %s OR tax_code ILIKE %s OR code ILIKE %s)
        ORDER BY updated_at DESC
        LIMIT %s
    """, (TENANT_ID, f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%", limit))

    # Also search CNEE
    cnee = execute_sync("""
        SELECT company_name, email, contact_name, campaign, status
        FROM cnee_master
        WHERE (company_name ILIKE %s OR email ILIKE %s)
          AND status = 'active'
        LIMIT %s
    """, (f"%{q}%", f"%{q}%", limit))

    return {
        "customers": [dict(r) for r in rows],
        "prospects": [dict(r) for r in cnee],
        "total": len(rows) + len(cnee),
    }


@router.post("/bulk_check")
def bulk_check_tax_codes(req: BulkCheckRequest):
    """Check multiple tax codes at once (for ERP import validation)."""
    if not is_postgres_configured():
        raise HTTPException(503, "PostgreSQL not configured")

    results = {}
    for tc in req.tax_codes[:100]:  # max 100 per request
        tc = tc.strip()
        if not tc:
            continue
        rows = execute_sync("""
            SELECT code, name, sales_rep, crm_status
            FROM customers WHERE tenant_id = %s AND tax_code = %s
        """, (TENANT_ID, tc))

        if rows:
            results[tc] = {"exists": True, "name": rows[0]["name"], "sales_rep": rows[0]["sales_rep"]}
        else:
            results[tc] = {"exists": False}

    return {"results": results, "checked": len(results)}
