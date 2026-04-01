"""
quote_intelligence.py — Sales Intelligence Engine for Quotes
=============================================================
Features:
  - Win Probability calculation
  - Market Rate Monitor (price change detection)
  - Smart Alert generation (price drops, expiry, follow-up)
"""

import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import pandas as pd

log = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent  # Engine_test/
PARQUET_FILE = BASE_DIR / "Pricing_Engine" / "data" / "Cleaned_Master_History.parquet"

_df_cache = None
_df_loaded = None
_CACHE_TTL = 600


def _load_parquet():
    """Load Parquet with caching."""
    global _df_cache, _df_loaded
    now = datetime.now()
    if _df_cache is not None and _df_loaded and (now - _df_loaded).seconds < _CACHE_TTL:
        return _df_cache
    if not PARQUET_FILE.exists():
        return None
    df = pd.read_parquet(PARQUET_FILE)
    df['Exp'] = pd.to_datetime(df['Exp'], errors='coerce')
    df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')
    today = pd.Timestamp(date.today())
    df = df[(df['Exp'] >= today) & (df['Amount'] > 0)].copy()
    # Only keep Total Ocean Freight
    df = df[df['Charge_Name'].str.contains('Total Ocean Freight', na=False)]
    _df_cache = df
    _df_loaded = now
    return df


# ══════════════════════════════════════════════════════════════════════════════
# WIN PROBABILITY
# ══════════════════════════════════════════════════════════════════════════════

def calc_win_probability(quote: dict, all_quotes: list = None) -> int:
    """
    Calculate win probability (0-100%) based on:
    - Markup level
    - Carrier competitiveness (vs market)
    - Customer history
    - Quote age
    """
    score = 50  # baseline

    carriers = quote.get("carriers", [])
    if not carriers:
        return score

    # 1. Markup level analysis
    markups = []
    for c in carriers:
        for ct, p in c.get("containers", {}).items():
            of = p.get("ocean_freight", 0)
            mk = p.get("markup", 0)
            if of > 0:
                markups.append(mk / of * 100)  # markup %

    if markups:
        avg_markup_pct = sum(markups) / len(markups)
        if avg_markup_pct <= 3:
            score += 20  # very competitive
        elif avg_markup_pct <= 5:
            score += 15
        elif avg_markup_pct <= 8:
            score += 5
        elif avg_markup_pct <= 12:
            score -= 5
        else:
            score -= 15  # too expensive

    # 2. Carrier competitiveness (compare to market)
    df = _load_parquet()
    if df is not None:
        for c in carriers:
            carrier_name = c.get("carrier", "")
            for ct, p in c.get("containers", {}).items():
                of = p.get("ocean_freight", 0)
                if not of or not carrier_name:
                    continue

                route_rates = df[
                    (df['POL'].str.upper().str.strip() == quote.get("pol", "").upper()) &
                    (df['Container_Type'].str.upper() == ct.upper())
                ]
                if quote.get("place"):
                    route_rates = route_rates[
                        route_rates['Place'].astype(str).str.upper().str.contains(
                            quote["place"].upper(), na=False) |
                        route_rates['POD'].astype(str).str.upper().str.contains(
                            quote["place"].upper(), na=False)
                    ]

                if not route_rates.empty:
                    market_min = route_rates['Amount'].min()
                    market_avg = route_rates['Amount'].mean()
                    if of <= market_min * 1.05:
                        score += 10  # at or below market best
                    elif of <= market_avg:
                        score += 5
                    elif of > market_avg * 1.15:
                        score -= 10
                break  # Only check first container for efficiency
            break  # Only check first carrier

    # 3. Multi-carrier advantage
    if len(carriers) >= 3:
        score += 5  # more options = better service
    elif len(carriers) >= 2:
        score += 3

    # 4. Customer history bonus
    if all_quotes:
        customer = quote.get("customer", "")
        if customer:
            won = sum(1 for q in all_quotes
                      if q.get("customer") == customer
                      and q.get("status") in ("ACCEPTED", "CONVERTED"))
            if won >= 3:
                score += 10
            elif won >= 1:
                score += 5

    # 5. Quote freshness
    try:
        created = datetime.fromisoformat(quote.get("created_at", ""))
        age_days = (datetime.now() - created).days
        if age_days <= 3:
            score += 5  # fresh quote
        elif age_days >= 14:
            score -= 10  # stale
        elif age_days >= 7:
            score -= 5
    except (ValueError, TypeError):
        pass

    return max(0, min(100, score))


def get_win_priority(probability: int) -> str:
    """Convert probability to priority label."""
    if probability >= 70:
        return "HIGH"
    elif probability >= 45:
        return "MEDIUM"
    return "LOW"


# ══════════════════════════════════════════════════════════════════════════════
# MARKET RATE MONITOR
# ══════════════════════════════════════════════════════════════════════════════

def check_price_changes(quotes: list) -> list:
    """
    Compare O/F in each active quote vs latest market rate.
    Returns list of price change alerts.
    """
    df = _load_parquet()
    if df is None:
        return []

    alerts = []
    for quote in quotes:
        if quote.get("status") in ("REJECTED", "CONVERTED"):
            continue

        carriers = quote.get("carriers", [])
        for c in carriers:
            carrier_name = c.get("carrier", "")
            for ct, p in c.get("containers", {}).items():
                quoted_of = p.get("ocean_freight", 0)
                if not quoted_of or not carrier_name:
                    continue

                # Find current market rate for same carrier/route/container
                route = df[
                    (df['POL'].str.upper().str.strip() == quote.get("pol", "").upper()) &
                    (df['Carrier'].str.upper().str.strip() == carrier_name.upper()) &
                    (df['Container_Type'].str.upper() == ct.upper())
                ]
                if quote.get("place"):
                    route = route[
                        route['Place'].astype(str).str.upper().str.contains(
                            quote["place"].upper(), na=False) |
                        route['POD'].astype(str).str.upper().str.contains(
                            quote["place"].upper(), na=False)
                    ]

                if route.empty:
                    continue

                current_rate = float(route['Amount'].min())
                diff = current_rate - quoted_of

                # Only alert if significant change (>= $50)
                if abs(diff) >= 50:
                    alerts.append({
                        "quote_id": quote.get("quote_id"),
                        "customer": quote.get("customer", ""),
                        "carrier": carrier_name,
                        "container": ct,
                        "route": f"{quote.get('pol', '')} → {quote.get('place', '') or quote.get('pod', '')}",
                        "quoted_rate": quoted_of,
                        "current_rate": current_rate,
                        "diff": diff,
                        "direction": "DROP" if diff < 0 else "INCREASE",
                        "action": "Re-quote to customer — opportunity!" if diff < 0
                                  else "Rush customer to accept — rate increasing",
                        "status": quote.get("status"),
                    })

    # Sort: biggest drops first (most actionable)
    alerts.sort(key=lambda a: a["diff"])
    return alerts


# ══════════════════════════════════════════════════════════════════════════════
# SMART ALERTS
# ══════════════════════════════════════════════════════════════════════════════

def generate_smart_alerts(quotes: list) -> list:
    """
    Generate actionable sales alerts:
    - PRICE_DROP: Rate decreased → re-quote opportunity
    - PRICE_INCREASE: Rate increased → rush to close
    - EXPIRING: Validity ending soon
    - HIGH_WIN: High win probability → prioritize follow-up
    - STALE: Quote older than 7 days without action
    """
    alerts = []
    now = datetime.now()

    # Price change alerts
    price_changes = check_price_changes(quotes)
    for pc in price_changes:
        alert_type = "PRICE_DROP" if pc["direction"] == "DROP" else "PRICE_INCREASE"
        alerts.append({
            "type": alert_type,
            "severity": "HIGH" if abs(pc["diff"]) >= 100 else "MEDIUM",
            "quote_id": pc["quote_id"],
            "customer": pc["customer"],
            "message": f"{'📉 PRICE DROP' if pc['direction'] == 'DROP' else '📈 PRICE UP'}: "
                       f"{pc['carrier']} {pc['container']} ${pc['quoted_rate']:,.0f} → ${pc['current_rate']:,.0f} "
                       f"(${abs(pc['diff']):,.0f} {'decrease' if pc['diff'] < 0 else 'increase'})",
            "action": pc["action"],
            "data": pc,
        })

    # Expiry + staleness + high win
    for q in quotes:
        if q.get("status") in ("REJECTED", "CONVERTED"):
            continue

        qid = q.get("quote_id", "")

        # Check validity expiry
        try:
            exp_str = q.get("exp", "")
            if exp_str:
                exp_date = pd.to_datetime(exp_str, errors='coerce')
                if pd.notna(exp_date):
                    days_left = (exp_date - pd.Timestamp(now)).days
                    if 0 <= days_left <= 7:
                        alerts.append({
                            "type": "EXPIRING",
                            "severity": "HIGH" if days_left <= 3 else "MEDIUM",
                            "quote_id": qid,
                            "customer": q.get("customer", ""),
                            "message": f"⏰ Validity expires in {days_left} days",
                            "action": "Follow up with customer before rate expires",
                            "data": {"days_left": days_left},
                        })
        except (ValueError, TypeError):
            pass

        # Stale quotes
        try:
            created = datetime.fromisoformat(q.get("created_at", ""))
            age_days = (now - created).days
            if age_days >= 7 and q.get("status") in ("DRAFT", "SENT"):
                alerts.append({
                    "type": "STALE",
                    "severity": "LOW",
                    "quote_id": qid,
                    "customer": q.get("customer", ""),
                    "message": f"📋 Quote is {age_days} days old without resolution",
                    "action": "Follow up or archive",
                    "data": {"age_days": age_days},
                })
        except (ValueError, TypeError):
            pass

    # Sort by severity
    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    alerts.sort(key=lambda a: severity_order.get(a.get("severity", "LOW"), 3))
    return alerts


# ══════════════════════════════════════════════════════════════════════════════
# FULL INTELLIGENCE REPORT
# ══════════════════════════════════════════════════════════════════════════════

def get_intelligence_report(quotes: list) -> dict:
    """
    Full intelligence dashboard data:
    - Quote stats with win probabilities
    - Price change alerts
    - Smart sales alerts
    - Opportunity summary
    """
    # Calculate win probabilities
    enriched = []
    high_win = []
    for q in quotes:
        if q.get("status") in ("REJECTED", "CONVERTED"):
            wp = q.get("win_probability")
            enriched.append({**q, "win_probability": wp, "win_priority": "—"})
            continue

        wp = calc_win_probability(q, quotes)
        priority = get_win_priority(wp)
        enriched.append({**q, "win_probability": wp, "win_priority": priority})
        if priority == "HIGH" and q.get("status") in ("DRAFT", "SENT", "ACCEPTED"):
            high_win.append({
                "quote_id": q["quote_id"],
                "customer": q.get("customer", ""),
                "win_probability": wp,
                "status": q["status"],
            })

    # Price changes
    price_changes = check_price_changes(quotes)
    price_drops = [p for p in price_changes if p["direction"] == "DROP"]

    # Smart alerts
    alerts = generate_smart_alerts(quotes)

    # Opportunity summary
    return {
        "quotes": enriched,
        "price_changes": price_changes,
        "price_drops_count": len(price_drops),
        "alerts": alerts,
        "alerts_count": len(alerts),
        "high_win_quotes": high_win,
        "high_win_count": len(high_win),
        "opportunities": {
            "price_drops": len(price_drops),
            "high_win": len(high_win),
            "expiring": sum(1 for a in alerts if a["type"] == "EXPIRING"),
            "stale": sum(1 for a in alerts if a["type"] == "STALE"),
        },
    }
