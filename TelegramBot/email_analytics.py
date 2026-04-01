# -*- coding: utf-8 -*-
"""
email_analytics.py — Email Intelligence Analytics Engine  v1.0
================================================================
Analytics functions that aggregate shipment_state.json + Parquet datasets
to power the 10 Email Intelligence Features.

Phase 1 delivers:
  - carrier_trouble_index()  → Feature #3
  - route_health_map()       → Feature #5

Future phases will add:
  - customer_frequency()     → Feature #1 Churn Radar
  - response_time()          → Feature #2 Response DNA
  - commitment_score()       → Feature #4 Commitment Score
  - ghost_pipeline()         → Feature #6 Ghost Pipeline

Usage:
    from email_analytics import EmailAnalytics
    analytics = EmailAnalytics()
    trouble = analytics.carrier_trouble_index()
    health  = analytics.route_health_map("HCM", "SEATTLE")
"""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).parent
ENGINE_TEST     = BASE_DIR.parent  # PricingSystem/Engine_test
EMAIL_ENGINE    = ENGINE_TEST / "email_engine"
STATE_FILE      = EMAIL_ENGINE / "data" / "shipment_state.json"
DATASET_DIR     = ENGINE_TEST / "Pricing_Engine" / "data"
EMAIL_DATASET   = DATASET_DIR / "email_knowledge.parquet"
SHIPMENT_HISTORY = DATASET_DIR / "email_knowledge.parquet"

# ── Stage precedence (from shipment_brain.py) ─────────────────────────────────
STAGE_ORDER = {
    "BOOKING_CONFIRMED": 10,
    "SI_SUBMITTED": 20,
    "DRAFT_BL_ISSUED": 30,
    "DRAFT_BL_CONFIRMED": 35,
    "LOADED": 50,
    "ATD": 60,
    "ETA_UPDATE": 65,
    "DN_SENT": 70,
    "INVOICE_ISSUED": 80,
    "PAYMENT_CONFIRMED": 100,
}


class EmailAnalytics:
    """Central analytics engine for Email Intelligence features."""

    def __init__(self):
        self.state = self._load_state()
        self.shipments = self.state.get("shipments", {})
        log.info("[Analytics] Loaded %d shipments", len(self.shipments))

    def _load_state(self) -> dict:
        if not STATE_FILE.exists():
            log.warning("[Analytics] shipment_state.json not found")
            return {"shipments": {}}
        with STATE_FILE.open(encoding="utf-8") as f:
            return json.load(f)

    def reload(self):
        """Reload state from disk."""
        self.state = self._load_state()
        self.shipments = self.state.get("shipments", {})

    # =========================================================================
    # FEATURE #3: CARRIER TROUBLE INDEX
    # =========================================================================

    def carrier_trouble_index(self, months: int = 6) -> list[dict]:
        """
        Calculate trouble index per carrier.

        Trouble Index = (shipments with risks / total shipments) × 100

        Returns list of dicts sorted by trouble_index desc:
        [{"carrier": "ONE SOC", "total": 10, "troubled": 5,
          "trouble_index": 50.0, "risk_types": {"ETD_CHANGED": 4}, ...}]
        """
        cutoff = datetime.now() - timedelta(days=months * 30)
        carrier_stats: dict[str, dict] = defaultdict(lambda: {
            "total": 0, "troubled": 0, "risk_count": 0,
            "risk_types": Counter(), "risk_levels": Counter(),
            "routes": Counter(), "customers": Counter(),
            "avg_profit": [], "delayed_days": [],
        })

        for sid, ship in self.shipments.items():
            carrier = ship.get("carrier", "").strip()
            if not carrier:
                continue

            # Date filter
            created = ship.get("created_at", "")
            try:
                dt = datetime.fromisoformat(created) if "T" in created else datetime.strptime(created, "%Y-%m-%d")
                if dt < cutoff:
                    continue
            except (ValueError, TypeError):
                pass

            stats = carrier_stats[carrier]
            stats["total"] += 1

            # Routes and customers
            routing = ship.get("routing", "")
            customer = ship.get("customer", "")
            if routing:
                stats["routes"][routing] += 1
            if customer:
                stats["customers"][customer] += 1

            # Profit tracking
            profit = ship.get("profit", 0)
            if isinstance(profit, (int, float)):
                stats["avg_profit"].append(profit)

            # Risk analysis
            risks = ship.get("risks", [])
            if risks:
                stats["troubled"] += 1
                stats["risk_count"] += len(risks)
                for r in risks:
                    stats["risk_types"][r.get("type", "UNKNOWN")] += 1
                    stats["risk_levels"][r.get("level", "UNKNOWN")] += 1

            # ETD delay analysis
            etd = ship.get("etd", "")
            stage_hist = ship.get("stage_history", [])
            for event in stage_hist:
                if event.get("stage") == "ATD":
                    try:
                        etd_dt = datetime.strptime(etd, "%Y-%m-%d") if etd else None
                        atd_str = event.get("at", "")
                        atd_dt = (datetime.fromisoformat(atd_str)
                                  if "T" in atd_str
                                  else datetime.strptime(atd_str, "%Y-%m-%d"))
                        if etd_dt and atd_dt > etd_dt:
                            delay_days = (atd_dt - etd_dt).days
                            stats["delayed_days"].append(delay_days)
                    except (ValueError, TypeError):
                        pass

        # Build results
        results = []
        for carrier, stats in carrier_stats.items():
            total = stats["total"]
            troubled = stats["troubled"]
            profits = stats["avg_profit"]
            delays = stats["delayed_days"]

            results.append({
                "carrier": carrier,
                "total_shipments": total,
                "troubled_shipments": troubled,
                "trouble_index": round((troubled / total * 100), 1) if total > 0 else 0,
                "risk_count": stats["risk_count"],
                "risk_types": dict(stats["risk_types"]),
                "risk_levels": dict(stats["risk_levels"]),
                "top_routes": [r for r, _ in stats["routes"].most_common(3)],
                "top_customers": [c for c, _ in stats["customers"].most_common(3)],
                "avg_profit": round(sum(profits) / len(profits), 2) if profits else 0,
                "avg_delay_days": round(sum(delays) / len(delays), 1) if delays else 0,
                "delay_count": len(delays),
            })

        results.sort(key=lambda x: x["trouble_index"], reverse=True)
        return results

    # =========================================================================
    # FEATURE #5: ROUTE HEALTH MAP
    # =========================================================================

    def route_health_map(self, pol: str = None, place: str = None) -> list[dict]:
        """
        Calculate health metrics per route.

        Health Score = weighted sum of:
          - Risk rate (lower is better) × 40%
          - Avg profit margin × 30%
          - Stage completion rate × 30%

        Filters by pol/place if provided (fuzzy partial match).
        Returns sorted by total shipments desc.
        """
        route_stats: dict[str, dict] = defaultdict(lambda: {
            "shipments": [],
            "risk_count": 0, "risk_types": Counter(),
            "carriers": Counter(), "customers": Counter(),
            "profits": [], "margins": [],
            "stage_durations": [],
            "delayed_ships": 0,
        })

        for sid, ship in self.shipments.items():
            routing = ship.get("routing", "").strip()
            if not routing:
                continue

            # Filter by POL/Place
            routing_upper = routing.upper()
            if pol and pol.upper() not in routing_upper:
                continue
            if place and place.upper() not in routing_upper:
                continue

            stats = route_stats[routing]
            stats["shipments"].append(sid)

            # Carrier
            carrier = ship.get("carrier", "").strip()
            if carrier:
                stats["carriers"][carrier] += 1

            # Customer
            customer = ship.get("customer", "")
            if customer:
                stats["customers"][customer] += 1

            # Profit
            profit = ship.get("profit", 0)
            margin_str = ship.get("profit_margin", "0%")
            if isinstance(profit, (int, float)):
                stats["profits"].append(profit)
            try:
                margin_val = float(margin_str.replace("%", ""))
                stats["margins"].append(margin_val)
            except (ValueError, TypeError):
                pass

            # Risks
            risks = ship.get("risks", [])
            if risks:
                stats["risk_count"] += len(risks)
                stats["delayed_ships"] += 1
                for r in risks:
                    stats["risk_types"][r.get("type", "")] += 1

            # Stage durations (booking → ATD)
            etd = ship.get("etd", "")
            created = ship.get("created_at", "")
            if etd and created:
                try:
                    etd_dt = datetime.strptime(etd, "%Y-%m-%d")
                    cr_dt = (datetime.fromisoformat(created)
                             if "T" in created
                             else datetime.strptime(created, "%Y-%m-%d"))
                    days = (etd_dt - cr_dt).days
                    if 0 < days < 120:
                        stats["stage_durations"].append(days)
                except (ValueError, TypeError):
                    pass

        # Build results
        results = []
        for route, stats in route_stats.items():
            total = len(stats["shipments"])
            if total == 0:
                continue

            risk_rate = stats["risk_count"] / total if total > 0 else 0
            avg_profit = sum(stats["profits"]) / len(stats["profits"]) if stats["profits"] else 0
            avg_margin = sum(stats["margins"]) / len(stats["margins"]) if stats["margins"] else 0
            avg_duration = (sum(stats["stage_durations"]) / len(stats["stage_durations"])
                           if stats["stage_durations"] else 0)

            # Health score: 100 = perfect, lower = worse
            risk_score = max(0, 100 - (risk_rate * 100))  # 40% weight
            margin_score = min(100, avg_margin * 10)       # 30% weight (10% margin = 100 score)
            completion_score = 100 if avg_duration > 0 else 50  # 30% weight

            health_score = round(
                risk_score * 0.4 + margin_score * 0.3 + completion_score * 0.3, 1
            )

            # Split POL-PLACE
            parts = route.split("-", 1)
            route_pol = parts[0] if len(parts) > 0 else ""
            route_place = parts[1] if len(parts) > 1 else ""

            results.append({
                "route": route,
                "pol": route_pol,
                "place": route_place,
                "total_shipments": total,
                "health_score": health_score,
                "risk_rate": round(risk_rate * 100, 1),
                "risk_count": stats["risk_count"],
                "delayed_shipments": stats["delayed_ships"],
                "risk_types": dict(stats["risk_types"]),
                "avg_profit": round(avg_profit, 2),
                "avg_margin": round(avg_margin, 1),
                "avg_booking_to_etd_days": round(avg_duration, 1),
                "top_carriers": dict(stats["carriers"].most_common(5)),
                "top_customers": dict(stats["customers"].most_common(5)),
            })

        results.sort(key=lambda x: x["total_shipments"], reverse=True)
        return results

    # =========================================================================
    # HELPER: CUSTOMER SUMMARY
    # =========================================================================

    def customer_summary(self) -> list[dict]:
        """Quick summary of all customers for Intelligence overview."""
        cust_stats: dict[str, dict] = defaultdict(lambda: {
            "shipments": 0, "total_profit": 0, "routes": Counter(),
            "carriers": Counter(), "risk_count": 0,
            "first_date": None, "last_date": None,
        })

        for sid, ship in self.shipments.items():
            customer = ship.get("customer", "").strip()
            if not customer:
                continue

            stats = cust_stats[customer]
            stats["shipments"] += 1
            stats["total_profit"] += ship.get("profit", 0) or 0

            routing = ship.get("routing", "")
            carrier = ship.get("carrier", "")
            if routing:
                stats["routes"][routing] += 1
            if carrier:
                stats["carriers"][carrier] += 1

            stats["risk_count"] += len(ship.get("risks", []))

            # Date tracking
            created = ship.get("created_at", "")
            if created:
                try:
                    dt = (datetime.fromisoformat(created)
                          if "T" in created
                          else datetime.strptime(created, "%Y-%m-%d"))
                    if not stats["first_date"] or dt < stats["first_date"]:
                        stats["first_date"] = dt
                    if not stats["last_date"] or dt > stats["last_date"]:
                        stats["last_date"] = dt
                except (ValueError, TypeError):
                    pass

        results = []
        for customer, stats in cust_stats.items():
            months_active = 0
            if stats["first_date"] and stats["last_date"]:
                months_active = max(1, (stats["last_date"] - stats["first_date"]).days // 30)

            results.append({
                "customer": customer,
                "shipments": stats["shipments"],
                "total_profit": round(stats["total_profit"], 2),
                "avg_profit_per_ship": round(stats["total_profit"] / stats["shipments"], 2) if stats["shipments"] > 0 else 0,
                "risk_count": stats["risk_count"],
                "top_routes": [r for r, _ in stats["routes"].most_common(3)],
                "top_carriers": [c for c, _ in stats["carriers"].most_common(3)],
                "months_active": months_active,
                "first_shipment": stats["first_date"].strftime("%Y-%m-%d") if stats["first_date"] else "",
                "last_shipment": stats["last_date"].strftime("%Y-%m-%d") if stats["last_date"] else "",
            })

        results.sort(key=lambda x: x["shipments"], reverse=True)
        return results

    # =========================================================================
    # HELPER: OVERALL STATS
    # =========================================================================

    def overall_stats(self) -> dict:
        """Quick system overview for /intelligence-audit."""
        total = len(self.shipments)
        carriers = set()
        customers = set()
        total_profit = 0
        total_risks = 0

        for s in self.shipments.values():
            c = s.get("carrier", "").strip()
            if c:
                carriers.add(c)
            cust = s.get("customer", "").strip()
            if cust:
                customers.add(cust)
            total_profit += s.get("profit", 0) or 0
            total_risks += len(s.get("risks", []))

        return {
            "total_shipments": total,
            "unique_carriers": len(carriers),
            "unique_customers": len(customers),
            "total_profit": round(total_profit, 2),
            "total_risks": total_risks,
            "avg_profit_per_ship": round(total_profit / total, 2) if total > 0 else 0,
        }


# =============================================================================
# FORMAT FUNCTIONS — For Telegram/Bot output
# =============================================================================

def format_trouble_index(results: list[dict], top_n: int = 10) -> str:
    """Format carrier trouble index for Telegram output."""
    if not results:
        return "📊 Không có dữ liệu carrier để phân tích."

    lines = [
        "🌊 <b>CARRIER TROUBLE INDEX</b>",
        f"<i>Dữ liệu từ {sum(r['total_shipments'] for r in results)} shipments</i>",
        "",
    ]

    for i, r in enumerate(results[:top_n], 1):
        # Color coding
        idx = r["trouble_index"]
        if idx >= 40:
            icon = "🔴"
        elif idx >= 20:
            icon = "🟡"
        else:
            icon = "🟢"

        lines.append(
            f"{icon} <b>{r['carrier']}</b> — "
            f"Trouble: {idx}% | {r['troubled_shipments']}/{r['total_shipments']} lô"
        )
        if r["risk_types"]:
            types = ", ".join(f"{t}: {c}" for t, c in r["risk_types"].items())
            lines.append(f"   ⚠️ {types}")
        if r["top_routes"]:
            lines.append(f"   📍 Routes: {', '.join(r['top_routes'][:3])}")
        if r["avg_profit"] > 0:
            lines.append(f"   💰 Avg profit: ${r['avg_profit']:.0f}/ship")
        lines.append("")

    # Summary
    total_ships = sum(r["total_shipments"] for r in results)
    total_troubled = sum(r["troubled_shipments"] for r in results)
    overall_rate = round(total_troubled / total_ships * 100, 1) if total_ships > 0 else 0
    lines.append(f"📊 Overall: {total_troubled}/{total_ships} troubled ({overall_rate}%)")

    # Recommendations
    if results and results[0]["trouble_index"] > 30:
        worst = results[0]
        lines.append("")
        lines.append(
            f"💡 <b>Tip:</b> {worst['carrier']} trouble cao nhất ({worst['trouble_index']}%). "
            f"Consider alternative carrier cho routes: {', '.join(worst['top_routes'][:2])}"
        )

    return "\n".join(lines)


def format_route_health(results: list[dict], top_n: int = 10) -> str:
    """Format route health map for Telegram output."""
    if not results:
        return "📊 Không có dữ liệu route để phân tích."

    lines = [
        "🗺️ <b>ROUTE HEALTH MAP</b>",
        f"<i>Dữ liệu từ {sum(r['total_shipments'] for r in results)} shipments</i>",
        "",
    ]

    for i, r in enumerate(results[:top_n], 1):
        # Health score color
        score = r["health_score"]
        if score >= 80:
            icon = "🟢"
        elif score >= 60:
            icon = "🟡"
        else:
            icon = "🔴"

        lines.append(
            f"{icon} <b>{r['route']}</b> — "
            f"Health: {score}/100 | {r['total_shipments']} lô"
        )
        lines.append(
            f"   📊 Risk: {r['risk_rate']}% | "
            f"Margin: {r['avg_margin']}% | "
            f"Profit: ${r['avg_profit']:.0f}/ship"
        )
        if r["top_carriers"]:
            carrier_str = ", ".join(f"{c}({n})" for c, n in r["top_carriers"].items())
            lines.append(f"   🚢 Carriers: {carrier_str}")
        if r["risk_types"]:
            types = ", ".join(f"{t}:{c}" for t, c in r["risk_types"].items())
            lines.append(f"   ⚠️ Risks: {types}")
        lines.append("")

    # Pain points
    worst = [r for r in results if r["risk_rate"] > 30]
    if worst:
        lines.append("⚠️ <b>Pain Points:</b>")
        for r in worst[:3]:
            lines.append(
                f"  • {r['route']}: {r['risk_rate']}% risk rate "
                f"({r['delayed_shipments']} delayed)"
            )

    return "\n".join(lines)


def format_customer_summary(results: list[dict], top_n: int = 10) -> str:
    """Format customer summary for Telegram output."""
    if not results:
        return "📊 Không có dữ liệu khách hàng."

    lines = [
        "👥 <b>CUSTOMER INTELLIGENCE</b>",
        f"<i>{len(results)} customers | {sum(r['shipments'] for r in results)} shipments total</i>",
        "",
    ]

    for r in results[:top_n]:
        lines.append(
            f"<b>{r['customer']}</b> — {r['shipments']} lô | "
            f"${r['total_profit']:.0f} profit | {r['months_active']}mo active"
        )
        if r["top_routes"]:
            lines.append(f"  📍 {', '.join(r['top_routes'][:2])}")

    return "\n".join(lines)


# =============================================================================
# CLI — Quick test
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    analytics = EmailAnalytics()

    print("\n" + "=" * 60)
    print("OVERALL STATS")
    print("=" * 60)
    stats = analytics.overall_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")

    print("\n" + "=" * 60)
    print("CARRIER TROUBLE INDEX")
    print("=" * 60)
    trouble = analytics.carrier_trouble_index()
    for r in trouble[:5]:
        print(f"  {r['carrier']}: {r['trouble_index']}% trouble "
              f"({r['troubled_shipments']}/{r['total_shipments']})")

    print("\n" + "=" * 60)
    print("ROUTE HEALTH MAP")
    print("=" * 60)
    health = analytics.route_health_map()
    for r in health[:5]:
        print(f"  {r['route']}: {r['health_score']}/100 health "
              f"({r['total_shipments']} ships, {r['risk_rate']}% risk)")

    print("\n" + "=" * 60)
    print("CUSTOMER SUMMARY")
    print("=" * 60)
    customers = analytics.customer_summary()
    for r in customers[:5]:
        print(f"  {r['customer']}: {r['shipments']} ships, "
              f"${r['total_profit']:.0f} profit, {r['months_active']}mo active")
