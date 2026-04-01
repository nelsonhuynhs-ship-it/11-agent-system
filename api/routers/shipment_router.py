# -*- coding: utf-8 -*-
"""
shipment_router.py — Shipment + Carrier Freetime Endpoints
============================================================
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

from fastapi import APIRouter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_access import dal

router = APIRouter(prefix="/api", tags=["Shipments"])


@router.get("/shipments")
def get_shipments():
    """Get all tracked shipments."""
    items = dal.get_shipments()
    return {"shipments": items, "total": len(items)}


@router.get("/shipments/{shipment_id}")
def get_shipment(shipment_id: str):
    """Get detailed shipment by ID."""
    rec = dal.get_shipment(shipment_id)
    if not rec:
        return {"error": "Shipment not found"}
    return {"shipment": rec}


@router.get("/carrier/freetime")
def get_carrier_freetime():
    """Return DEM/DET freetime and power charge rules per carrier."""
    rules = dal.get_carrier_rules()
    if not rules:
        return {"carriers": {}}
    result = {}
    for key, val in rules.items():
        if key.startswith("_") or not isinstance(val, dict):
            continue
        dry = val.get("dry", {})
        reefer = val.get("reefer", {})
        power = val.get("power_charge") or {}
        result[key] = {
            "name": val.get("name", key),
            "dry_combined": dry.get("combined", True),
            "dry_det_days": dry.get("det_days", 7),
            "dry_dem_days": dry.get("dem_days"),
            "dry_total_days": (dry.get("det_days", 0) or 0) + (dry.get("dem_days", 0) or 0)
                              if not dry.get("combined") else dry.get("det_days", 7),
            "reefer_det_days": reefer.get("det_days", 7),
            "reefer_dem_days": reefer.get("dem_days"),
            "reefer_total_days": (reefer.get("det_days", 0) or 0) + (reefer.get("dem_days", 0) or 0)
                                 if not reefer.get("combined") else reefer.get("det_days", 7),
            "power_free_days": power.get("free_days"),
            "power_free_hours": power.get("free_hours"),
            "power_rate_usd_hour": 1.6,
            "dem_rate_vnd_day": 500000,
        }
    return {"carriers": result}
