# -*- coding: utf-8 -*-
"""
spot_cache.py — HPL Spot Rate Cache
====================================
Fetches spot rates from HPL Offers API (or mock data) and caches in SQLite.
Spot rates are NEVER written to Parquet — strictly isolated.

Usage:
    from ERP.intelligence.spot_cache import refresh_spot_cache, get_spot, get_spot_comparison

    # Refresh cache (mock mode if no API key)
    refresh_spot_cache()

    # Query a spot rate
    spot = get_spot("VNHPH", "USLAX", "40HQ")

    # Compare spot vs contract
    comparison = get_spot_comparison("VNHPH", "USLAX", "40HQ", contract_price=2400)
"""
import logging
import os
import random
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("nelson.spot_cache")

# ── Paths ─────────────────────────────────────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(os.path.dirname(_THIS_DIR), "data")
SPOT_DB = os.path.join(_DATA_DIR, "spot_cache.sqlite")

# ── Routes to monitor ────────────────────────────────────────
ROUTES_TO_WATCH = [
    ("VNHPH", "USLAX"),
    ("VNHPH", "USNYC"),
    ("VNHPH", "USLGB"),
    ("VNHPH", "USORF"),
    ("VNHPH", "USHOU"),
    ("VNHPH", "USSEA"),
    ("VNHPH", "USSAV"),
    ("VNSGN", "USLAX"),
    ("VNSGN", "USNYC"),
]

CONTAINER_TYPES = ["20GP", "40GP", "40HQ"]

# Base prices for mock data (realistic ranges)
_MOCK_BASE = {
    "USLAX": {"20GP": 1800, "40GP": 2800, "40HQ": 2900},
    "USNYC": {"20GP": 2100, "40GP": 3300, "40HQ": 3400},
    "USLGB": {"20GP": 1750, "40GP": 2700, "40HQ": 2850},
    "USORF": {"20GP": 2000, "40GP": 3100, "40HQ": 3200},
    "USHOU": {"20GP": 2200, "40GP": 3500, "40HQ": 3600},
    "USSEA": {"20GP": 1900, "40GP": 3000, "40HQ": 3100},
    "USSAV": {"20GP": 2050, "40GP": 3200, "40HQ": 3350},
}


def _get_conn() -> sqlite3.Connection:
    """Get SQLite connection with WAL mode for concurrent access."""
    conn = sqlite3.connect(SPOT_DB, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ── Mock Data ─────────────────────────────────────────────────

def _fetch_spot_mock(pol: str, pod: str) -> list[dict]:
    """Generate realistic mock spot rates for testing."""
    base = _MOCK_BASE.get(pod, {"20GP": 2000, "40GP": 3000, "40HQ": 3100})
    now = datetime.now()
    rates = []
    for ct in CONTAINER_TYPES:
        price = base.get(ct, 2500) + random.randint(-150, 150)
        rates.append({
            "pol": pol,
            "pod": pod,
            "carrier": "HPL",
            "cont_type": ct,
            "amount": price,
            "currency": "USD",
            "valid_from": now.strftime("%Y-%m-%d"),
            "valid_to": (now + timedelta(days=7)).strftime("%Y-%m-%d"),
            "offer_ref": f"MOCK-{pol[-3:]}-{pod[-3:]}-{ct}-{now.strftime('%m%d')}",
        })
    return rates


# ── Real HPL API ──────────────────────────────────────────────

def _fetch_spot_hpl(pol: str, pod: str) -> list[dict]:
    """
    Fetch spot rates from HPL Offers API v4.

    Requires HPL_CLIENT_ID and HPL_CLIENT_SECRET env vars.
    Returns normalized rate dicts matching the mock format.
    """
    try:
        from ERP.intelligence.hpl_auth import get_auth

        auth = get_auth()
        if not auth.is_configured:
            logger.warning("[Spot] No API key — falling back to mock")
            return _fetch_spot_mock(pol, pod)

        import requests as req

        headers = auth.headers(use_oauth=True)
        payload = {
            "placeOfReceipt": {"unLocationCode": pol},
            "placeOfDelivery": {"unLocationCode": pod},
            "plannedDepartureDate": datetime.now().strftime("%Y-%m-%d"),
            "commodities": [{"commodityType": "GENERAL_CARGO"}],
            "equipmentDetails": [
                {"isoEquipmentCode": "22G1", "equipmentQuantity": 1},  # 20GP
                {"isoEquipmentCode": "42G1", "equipmentQuantity": 1},  # 40GP
                {"isoEquipmentCode": "45G1", "equipmentQuantity": 1},  # 40HQ
            ],
        }

        resp = req.post(
            auth.get_endpoint("offers"),
            headers=headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        return _parse_hpl_offer_response(data, pol, pod)

    except Exception as e:
        logger.error("[Spot] HPL API error for %s->%s: %s", pol, pod, e)
        return []


def _parse_hpl_offer_response(data: dict, pol: str, pod: str) -> list[dict]:
    """Parse HPL Offers API response into normalized rate dicts."""
    rates = []
    iso_to_ct = {"22G1": "20GP", "42G1": "40GP", "45G1": "40HQ"}

    offers = data.get("offers", data.get("quotations", []))
    for offer in offers:
        offer_ref = offer.get("carrierOfferRequestReference", "")
        valid_from = offer.get("validityPeriod", {}).get("startDate", "")
        valid_to = offer.get("validityPeriod", {}).get("endDate", "")

        for charge_group in offer.get("chargeDetails", []):
            iso_code = charge_group.get("equipmentTypeCode", "")
            ct = iso_to_ct.get(iso_code, iso_code)

            total = sum(
                c.get("chargeAmount", 0)
                for c in charge_group.get("charges", [])
            )
            if total > 0:
                rates.append({
                    "pol": pol,
                    "pod": pod,
                    "carrier": "HPL",
                    "cont_type": ct,
                    "amount": total,
                    "currency": "USD",
                    "valid_from": valid_from,
                    "valid_to": valid_to,
                    "offer_ref": offer_ref,
                })

    return rates


# ── Cache Operations ──────────────────────────────────────────

def refresh_spot_cache(use_mock: bool = None) -> dict:
    """
    Refresh spot cache for all monitored routes.

    Args:
        use_mock: Force mock mode. If None, auto-detect from env vars.

    Returns:
        Summary dict with total rates inserted and any errors.
    """
    if use_mock is None:
        use_mock = not bool(os.getenv("HPL_CLIENT_ID"))

    conn = _get_conn()
    total = 0
    errors = []

    for pol, pod in ROUTES_TO_WATCH:
        try:
            if use_mock:
                rates = _fetch_spot_mock(pol, pod)
            else:
                rates = _fetch_spot_hpl(pol, pod)

            for r in rates:
                conn.execute("""
                    INSERT OR REPLACE INTO spot_rates
                    (pol, pod, carrier, cont_type, amount, currency,
                     valid_from, valid_to, offer_ref)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (r["pol"], r["pod"], r["carrier"], r["cont_type"],
                      r["amount"], r["currency"], r["valid_from"],
                      r["valid_to"], r["offer_ref"]))

            total += len(rates)

            conn.execute("""
                INSERT INTO spot_fetch_log (pol, pod, status, rows_inserted)
                VALUES (?, ?, 'OK', ?)
            """, (pol, pod, len(rates)))

        except Exception as e:
            error_msg = f"{pol}->{pod}: {e}"
            errors.append(error_msg)
            logger.error("[Spot] %s", error_msg)
            conn.execute("""
                INSERT INTO spot_fetch_log (pol, pod, status, error_msg)
                VALUES (?, ?, 'ERROR', ?)
            """, (pol, pod, str(e)))

    conn.commit()

    # Clean expired rates
    deleted = conn.execute(
        "DELETE FROM spot_rates WHERE valid_to < date('now')"
    ).rowcount
    conn.commit()
    conn.close()

    result = {
        "total_inserted": total,
        "routes_checked": len(ROUTES_TO_WATCH),
        "errors": errors,
        "expired_cleaned": deleted,
        "mode": "MOCK" if use_mock else "LIVE",
        "timestamp": datetime.now().isoformat(),
    }

    logger.info("[Spot] Refresh done: %d rates, %d errors, %d expired cleaned",
                total, len(errors), deleted)
    return result


def get_spot(pol: str, pod: str, cont_type: str = "40HQ") -> Optional[dict]:
    """
    Query the latest spot rate for a route + container type.

    Returns dict with: amount, valid_to, offer_ref, fetched_at, carrier
    Returns None if no valid spot rate found.
    """
    conn = _get_conn()
    row = conn.execute("""
        SELECT amount, valid_to, offer_ref, fetched_at, carrier
        FROM spot_rates
        WHERE pol = ? AND pod = ? AND cont_type = ?
          AND valid_to >= date('now')
        ORDER BY fetched_at DESC
        LIMIT 1
    """, (pol, pod, cont_type)).fetchone()
    conn.close()

    if not row:
        return None

    return {
        "amount": row[0],
        "valid_to": row[1],
        "offer_ref": row[2],
        "fetched_at": row[3],
        "carrier": row[4],
        "cont_type": cont_type,
        "pol": pol,
        "pod": pod,
    }


def get_all_spots(pol: str, pod: str) -> list[dict]:
    """Get spot rates for ALL container types on a route."""
    spots = []
    for ct in CONTAINER_TYPES:
        spot = get_spot(pol, pod, ct)
        if spot:
            spots.append(spot)
    return spots


def get_spot_comparison(pol: str, pod: str, cont_type: str = "40HQ",
                        contract_price: float = 0) -> dict:
    """
    Compare spot rate vs contract price to generate market signal.

    Returns:
        dict with: spot, contract_price, signal, insight, diff
    """
    spot = get_spot(pol, pod, cont_type)

    result = {
        "spot": spot,
        "contract_price": contract_price,
        "signal": "NO_SPOT",
        "insight": "",
        "diff": 0,
    }

    if not spot:
        result["insight"] = "Chua co Spot rate cho tuyen nay"
        return result

    if contract_price <= 0:
        result["signal"] = "SPOT_ONLY"
        result["insight"] = f"HPL Spot: ${spot['amount']:,.0f} (chua co contract de so sanh)"
        return result

    diff = spot["amount"] - contract_price
    result["diff"] = diff

    if diff > 50:
        result["signal"] = "SPOT_HIGHER"
        result["insight"] = (
            f"FAK tot hon Spot ${diff:,.0f}/cont "
            f"-- highlight cho khach de chot deal!"
        )
    elif diff < -50:
        result["signal"] = "SPOT_LOWER"
        result["insight"] = (
            f"Spot thap hon FAK ${abs(diff):,.0f} "
            f"-- khach price-sensitive can theo doi"
        )
    else:
        result["signal"] = "SPOT_EQUAL"
        result["insight"] = "Spot gan bang FAK -- thi truong dang canh tranh"

    return result


# ── CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)-5s | %(message)s")

    print("=== Spot Cache Refresh ===")
    result = refresh_spot_cache()
    print(f"Mode: {result['mode']}")
    print(f"Inserted: {result['total_inserted']} rates")
    print(f"Errors: {len(result['errors'])}")
    print(f"Expired cleaned: {result['expired_cleaned']}")

    print("\n=== Sample Query: VNHPH -> USLAX ===")
    for ct in CONTAINER_TYPES:
        s = get_spot("VNHPH", "USLAX", ct)
        if s:
            print(f"  {ct}: ${s['amount']:,.0f} (valid until {s['valid_to']})")
        else:
            print(f"  {ct}: No data")
