"""
quote_store.py — Multi-Carrier/Container Quote CRUD + Intelligence
===================================================================
Schema: carriers[] array, each with containers{} dict
Supports: multi-carrier comparison, per-carrier markup, versioning
Data access: via data_access.py (DAL) — no direct file reads
Events: published via event_bus.py for lifecycle tracking
"""

import logging
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)

# ── Data Access + Events ──────────────────────────────────────────────────────
from data_access import dal
from event_bus import bus, Event


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_quotes() -> dict:
    return dal.load_quotes_data()


def _save_quotes(data: dict) -> None:
    dal.save_quotes_data(data)


def _next_quote_id(data: dict) -> str:
    counter = data["counter"]
    today = datetime.now().strftime("%Y%m%d")
    qid = f"Q-{today}-{counter + 1:03d}"
    while qid in data["quotes"]:
        counter += 1
        qid = f"Q-{today}-{counter + 1:03d}"
    data["counter"] = counter + 1
    return qid


def _next_shipment_id(data: dict) -> str:
    today = datetime.now().strftime("%Y%m%d")
    # Count existing S- shipments for today
    existing = [k for k in data.get("shipments", {}) if k.startswith(f"S-{today}")]
    seq = len(existing) + 1
    return f"S-{today}-{seq:03d}"


def _calc_carrier_totals(carriers: list) -> dict:
    """Calculate summary totals across all carriers."""
    all_sell = []
    all_buy = []
    for c in carriers:
        for ct, prices in c.get("containers", {}).items():
            all_sell.append(prices.get("sell_rate", 0))
            all_buy.append(prices.get("ocean_freight", 0))
    best_sell = min(all_sell) if all_sell else 0
    best_buy = min(all_buy) if all_buy else 0
    return {
        "best_sell_rate": best_sell,
        "best_buy_rate": best_buy,
        "best_margin": best_sell - best_buy if best_sell and best_buy else 0,
        "carrier_count": len(carriers),
        "container_count": len(set(ct for c in carriers for ct in c.get("containers", {}))),
    }


# ══════════════════════════════════════════════════════════════════════════════
# CRUD
# ══════════════════════════════════════════════════════════════════════════════

def create_quote(payload: dict) -> dict:
    """
    Create a multi-carrier/container quote.

    payload.carriers = [
      {
        "carrier": "CMA", "badge": "SOC",
        "containers": {
          "20GP": {"ocean_freight": 1500, "markup": 100},
          "40HQ": {"ocean_freight": 2926, "markup": 150}
        }
      }, ...
    ]
    """
    data = _load_quotes()
    qid = _next_quote_id(data)
    now = datetime.now().isoformat()

    # Process carriers — calculate sell_rate per container
    carriers_in = payload.get("carriers", [])
    global_markup = float(payload.get("global_markup", 0))
    markup_mode = payload.get("markup_mode", "global")  # "global" or "per_carrier"

    carriers = []
    for c in carriers_in:
        carrier_entry = {
            "carrier": c.get("carrier", ""),
            "badge": c.get("badge", ""),
            "containers": {},
        }
        for ct, prices in c.get("containers", {}).items():
            of = float(prices.get("ocean_freight", 0))
            if markup_mode == "global":
                mk = global_markup
            else:
                mk = float(prices.get("markup", 0))
            carrier_entry["containers"][ct] = {
                "ocean_freight": of,
                "markup": mk,
                "sell_rate": of + mk,
            }
        carriers.append(carrier_entry)

    # Optional charges
    optional_charges = payload.get("optional_charges", [])
    charges_total = sum(float(c.get("amount", 0)) for c in optional_charges)

    totals = _calc_carrier_totals(carriers)

    quote = {
        "quote_id": qid,
        "customer": payload.get("customer", ""),
        "service_type": payload.get("service_type", "CY-CY"),
        "pol": payload.get("pol", ""),
        "pod": payload.get("pod", ""),
        "place": payload.get("place", ""),
        "routing": payload.get("routing", ""),
        "carriers": carriers,
        "markup_mode": markup_mode,
        "global_markup": global_markup,
        "optional_charges": optional_charges,
        "charges_total": charges_total,
        "transit": payload.get("transit", ""),
        "freetime": payload.get("freetime", ""),
        "validity": payload.get("validity", ""),
        "eff": payload.get("eff", ""),
        "exp": payload.get("exp", ""),
        "status": "DRAFT",
        "version": 1,
        "parent_quote_id": None,
        "win_probability": None,
        "price_alerts": [],
        "created_at": now,
        "updated_at": now,
        "converted_shipment_id": None,
        **totals,
    }

    data["quotes"][qid] = quote
    _save_quotes(data)
    log.info("Created quote %s (%d carriers, %d containers)",
             qid, totals["carrier_count"], totals["container_count"])
    return quote


def list_quotes(status: Optional[str] = None) -> list:
    data = _load_quotes()
    quotes = list(data["quotes"].values())
    if status:
        quotes = [q for q in quotes if q.get("status", "").upper() == status.upper()]
    quotes.sort(key=lambda q: q.get("created_at", ""), reverse=True)
    return quotes


def get_quote(quote_id: str) -> Optional[dict]:
    data = _load_quotes()
    return data["quotes"].get(quote_id)


def update_quote(quote_id: str, updates: dict) -> Optional[dict]:
    data = _load_quotes()
    quote = data["quotes"].get(quote_id)
    if not quote or quote.get("converted_shipment_id"):
        return None

    # Update allowed fields
    for field in ["customer", "service_type", "optional_charges",
                  "carriers", "markup_mode", "global_markup"]:
        if field in updates:
            quote[field] = updates[field]

    # Recalculate if carriers changed
    if "carriers" in updates or "global_markup" in updates:
        carriers = quote.get("carriers", [])
        gm = float(quote.get("global_markup", 0))
        mode = quote.get("markup_mode", "global")
        for c in carriers:
            for ct, prices in c.get("containers", {}).items():
                of = float(prices.get("ocean_freight", 0))
                mk = gm if mode == "global" else float(prices.get("markup", 0))
                prices["markup"] = mk
                prices["sell_rate"] = of + mk
        quote["carriers"] = carriers
        totals = _calc_carrier_totals(carriers)
        quote.update(totals)

    if "optional_charges" in updates:
        quote["charges_total"] = sum(
            float(c.get("amount", 0)) for c in quote.get("optional_charges", []))

    quote["updated_at"] = datetime.now().isoformat()
    data["quotes"][quote_id] = quote
    _save_quotes(data)
    return quote


def update_status(quote_id: str, new_status: str) -> Optional[dict]:
    valid = {"DRAFT", "SENT", "ACCEPTED", "REJECTED", "CONVERTED"}
    if new_status.upper() not in valid:
        return None
    data = _load_quotes()
    quote = data["quotes"].get(quote_id)
    if not quote:
        return None
    quote["status"] = new_status.upper()
    quote["updated_at"] = datetime.now().isoformat()
    data["quotes"][quote_id] = quote
    _save_quotes(data)
    log.info("Quote %s status → %s", quote_id, new_status)
    return quote


# ══════════════════════════════════════════════════════════════════════════════
# CONVERT TO SHIPMENT
# ══════════════════════════════════════════════════════════════════════════════

def convert_to_shipment(quote_id: str, winning_carrier: str = "") -> dict:
    """
    Convert ACCEPTED quote → shipment.
    winning_carrier: which carrier won (required for multi-carrier quotes).
    """
    data = _load_quotes()
    quote = data["quotes"].get(quote_id)

    if not quote:
        return {"success": False, "error": "Quote not found"}
    if quote["status"] != "ACCEPTED":
        return {"success": False, "error": f"Must be ACCEPTED (current: {quote['status']})"}
    if quote.get("converted_shipment_id"):
        return {"success": False, "error": f"Already converted to {quote['converted_shipment_id']}"}

    carriers = quote.get("carriers", [])
    if not carriers:
        return {"success": False, "error": "No carriers in quote"}

    # Find winning carrier
    winner = None
    if winning_carrier:
        winner = next((c for c in carriers if c["carrier"].upper() == winning_carrier.upper()), None)
    if not winner:
        winner = carriers[0]  # default to first

    # Pick best sell_rate container for shipment summary
    containers = winner.get("containers", {})
    if not containers:
        return {"success": False, "error": "No containers for winning carrier"}

    # Use first container for primary shipment data
    primary_ct = list(containers.keys())[0]
    primary = containers[primary_ct]

    # Generate shipment ID
    state = dal.load_shipment_state()
    if "shipments" not in state:
        state["shipments"] = {}

    sid = _next_shipment_id(state)
    now = datetime.now()

    routing = quote.get("routing", "") or f"{quote['pol']}-{quote['pod']}"
    if quote.get("place") and quote["place"] != quote["pod"] and quote["place"] not in routing:
        routing = f"{quote['pol']}-{quote['place']} ({quote['pod']})"

    sell_rate = float(primary.get("sell_rate", 0))
    buy_rate = float(primary.get("ocean_freight", 0))
    markup = float(primary.get("markup", 0))

    shipment = {
        "customer": quote["customer"],
        "type": quote.get("service_type", "CY-CY"),
        "stage": "BOOKING_PENDING",
        "routing": routing,
        "carrier": winner["carrier"],
        "container": primary_ct,
        "quantity": 1,
        "etd": "", "eta": "", "ata": "",
        "selling_rate": sell_rate,
        "buying_rate": buy_rate,
        "profit": markup,
        "profit_margin": f"{(markup / sell_rate * 100):.1f}%" if sell_rate > 0 else "0%",
        "delay_count": 0,
        "stage_history": [{
            "stage": "BOOKING_PENDING",
            "at": now.strftime("%Y-%m-%d"),
            "subject": f"Converted from quote {quote_id} — {winner['carrier']}",
        }],
        "risks": [],
        "created_at": now.strftime("%Y-%m-%d"),
        "updated_at": now.strftime("%Y-%m-%d"),
        "last_subject": f"Quote {quote_id} converted",
        "last_sender": "",
        "source": "Quote",
        "quote_id": quote_id,
        "all_containers": containers,
        "optional_charges": quote.get("optional_charges", []),
    }

    state["shipments"][sid] = shipment
    try:
        dal.save_shipment_state(state)
    except Exception as e:
        return {"success": False, "error": str(e)}

    quote["converted_shipment_id"] = sid
    quote["status"] = "CONVERTED"
    quote["updated_at"] = now.isoformat()
    data["quotes"][quote_id] = quote
    _save_quotes(data)

    # Publish event
    bus.publish(Event(
        type="quote.converted",
        payload={"quote_id": quote_id, "shipment_id": sid,
                 "carrier": winner["carrier"], "customer": quote["customer"]},
        source="api",
    ))

    log.info("Converted quote %s → shipment %s (carrier: %s)", quote_id, sid, winner["carrier"])
    return {"success": True, "shipment_id": sid, "quote_id": quote_id}


# ══════════════════════════════════════════════════════════════════════════════
# VERSION CONTROL
# ══════════════════════════════════════════════════════════════════════════════

def requote(quote_id: str, new_carriers: list = None) -> Optional[dict]:
    """Create a new version of an existing quote with updated rates."""
    data = _load_quotes()
    old = data["quotes"].get(quote_id)
    if not old:
        return None

    new_qid = _next_quote_id(data)
    now = datetime.now().isoformat()

    # Copy old quote, bump version
    new_quote = {**old}
    new_quote["quote_id"] = new_qid
    new_quote["version"] = old.get("version", 1) + 1
    new_quote["parent_quote_id"] = quote_id
    new_quote["status"] = "DRAFT"
    new_quote["created_at"] = now
    new_quote["updated_at"] = now
    new_quote["converted_shipment_id"] = None
    new_quote["price_alerts"] = []

    # Update carriers if new rates provided
    if new_carriers:
        gm = float(new_quote.get("global_markup", 0))
        mode = new_quote.get("markup_mode", "global")
        for c in new_carriers:
            for ct, prices in c.get("containers", {}).items():
                of = float(prices.get("ocean_freight", 0))
                mk = gm if mode == "global" else float(prices.get("markup", 0))
                prices["markup"] = mk
                prices["sell_rate"] = of + mk
        new_quote["carriers"] = new_carriers
        new_quote.update(_calc_carrier_totals(new_carriers))

    data["quotes"][new_qid] = new_quote
    _save_quotes(data)
    log.info("Requoted %s → %s (v%d)", quote_id, new_qid, new_quote["version"])
    return new_quote


def get_quote_versions(quote_id: str) -> list:
    """Get all versions of a quote chain."""
    data = _load_quotes()
    quote = data["quotes"].get(quote_id)
    if not quote:
        return []

    # Find root
    root_id = quote_id
    visited = {root_id}
    while quote.get("parent_quote_id") and quote["parent_quote_id"] not in visited:
        root_id = quote["parent_quote_id"]
        visited.add(root_id)
        quote = data["quotes"].get(root_id, {})

    # Collect all versions from root
    chain = []
    all_quotes = data["quotes"]
    # BFS from root
    to_check = [root_id]
    seen = set()
    while to_check:
        qid = to_check.pop(0)
        if qid in seen:
            continue
        seen.add(qid)
        q = all_quotes.get(qid)
        if q:
            chain.append(q)
            # Find children
            for other_id, other_q in all_quotes.items():
                if other_q.get("parent_quote_id") == qid:
                    to_check.append(other_id)

    chain.sort(key=lambda q: q.get("version", 1))
    return chain


# ══════════════════════════════════════════════════════════════════════════════
# STATS
# ══════════════════════════════════════════════════════════════════════════════

def get_quote_stats() -> dict:
    data = _load_quotes()
    quotes = list(data["quotes"].values())
    by_status = {}
    for q in quotes:
        s = q.get("status", "DRAFT")
        by_status[s] = by_status.get(s, 0) + 1
    return {
        "total": len(quotes),
        "draft": by_status.get("DRAFT", 0),
        "sent": by_status.get("SENT", 0),
        "accepted": by_status.get("ACCEPTED", 0),
        "rejected": by_status.get("REJECTED", 0),
        "converted": by_status.get("CONVERTED", 0),
    }
