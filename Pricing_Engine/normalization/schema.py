# -*- coding: utf-8 -*-
"""
schema.py — Rate Normalization Schema
=======================================
Defines the schema for normalized freight rates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

__all__ = ["NORMALIZATION_SCHEMA", "NormalizedRate"]


# Schema definition for normalized rate fields
NORMALIZATION_SCHEMA = {
    "surcharge_included": bool,     # HDL/BAF/PSS included in base rate
    "rate_basis": str,              # FAK | FIX | SCFI
    "normalized_amount": float,     # Pure ocean freight, HDL stripped
    "hdl_fee": float,               # Extracted HDL fee (handling fee)
    "carrier_commission": float,    # CAR COM value
    "raw_amount": float,            # Original amount before normalization
}

# Valid rate basis types
VALID_RATE_BASIS = {"FAK", "FIX", "SCFI"}


@dataclass
class NormalizedRate:
    """Result of rate normalization."""

    raw_amount: float
    normalized_amount: float
    hdl_fee: float
    carrier_commission: float
    rate_basis: str
    surcharge_included: bool
    carrier: str
    container_type: str
    pol: str

    def to_dict(self) -> dict:
        return {
            "raw_amount": self.raw_amount,
            "normalized_amount": self.normalized_amount,
            "hdl_fee": self.hdl_fee,
            "carrier_commission": self.carrier_commission,
            "rate_basis": self.rate_basis,
            "surcharge_included": self.surcharge_included,
            "carrier": self.carrier,
            "container_type": self.container_type,
            "pol": self.pol,
        }
