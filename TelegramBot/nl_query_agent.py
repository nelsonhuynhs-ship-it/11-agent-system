# -*- coding: utf-8 -*-
"""
nl_query_agent.py — Bot v6 Feature #10
Natural Language Database Query Agent — converts Vietnamese natural language
questions into structured queries against Parquet/ERP data, returning insight cards.

Examples:
  "Tháng này carrier nào margin cao nhất?"
  "Khách nào chưa order tháng này?"
  "SIRI vs HML port nào dùng nhiều nhất?"
  "CMA vs ONE win rate ai cao hơn với PANDA?"

Uses Gemini to classify intent, then dispatches to the correct query function.
"""
import logging
import re
from datetime import datetime, timedelta

import pandas as pd

logger = logging.getLogger(__name__)

# ── Intent categories ────────────────────────────────────────────────────────
KNOWN_INTENTS = [
    "carrier_performance",    # Carrier nào margin/win rate cao nhất?
    "customer_activity",      # Khách nào active/inactive/chưa order?
    "rate_trend",             # Giá tuyến X đang trend lên/xuống?
    "route_popularity",       # Route nào hay đi nhất?
    "revenue_stats",          # Revenue tháng/quý/carrier là bao nhiêu?
    "win_loss_analysis",      # Win rate theo carrier/customer/route
    "comparison",             # A vs B comparison
    "general_stats",          # General stats không phân loại được
]


# ── Structured query functions ───────────────────────────────────────────────

def query_carrier_margin(jobs: list, carrier: str = None) -> str:
    """Calculate margin per carrier from active jobs."""
    if not jobs:
        return "Không có dữ liệu jobs để tính margin."

    carrier_stats = {}
    for job in jobs:
        c = str(job.get('carrier', 'Unknown')).upper()
        if carrier and carrier.upper() not in c:
            continue
        selling = job.get('selling', 0) or 0
        buying  = job.get('buying', 0) or 0
        margin  = selling - buying
        qty     = job.get('quantity', 1) or 1

        if c not in carrier_stats:
            carrier_stats[c] = {'jobs': 0, 'total_margin': 0, 'total_revenue': 0}
        carrier_stats[c]['jobs']          += 1
        carrier_stats[c]['total_margin']  += margin * qty
        carrier_stats[c]['total_revenue'] += selling * qty

    if not carrier_stats:
        return "Không có dữ liệu margin cho carrier này."

    # Sort by total margin descending
    sorted_carriers = sorted(
        carrier_stats.items(),
        key=lambda x: x[1]['total_margin'],
        reverse=True
    )

    lines = ["📊 CARRIER MARGIN ANALYSIS"]
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    for rank, (carrier_name, stats) in enumerate(sorted_carriers, 1):
        margin_pct = (stats['total_margin'] / stats['total_revenue'] * 100
                      if stats['total_revenue'] > 0 else 0)
        lines.append(
            f"{rank}. {carrier_name}: ${stats['total_margin']:,.0f} margin "
            f"({margin_pct:.1f}%) | {stats['jobs']} jobs"
        )
    return "\n".join(lines)


def query_inactive_customers(quote_history: list, days: int = 30) -> str:
    """Find customers who haven't had activity in N days."""
    if not quote_history:
        return "Không có dữ liệu để phân tích."

    cutoff = datetime.now() - timedelta(days=days)
    customer_last_activity = {}

    for q in quote_history:
        customer = str(q.get('customer', ''))
        qdate = q.get('date')
        if not customer or customer in ('nan', 'None', ''):
            continue
        if pd.notna(qdate) and hasattr(qdate, 'timestamp'):
            if customer not in customer_last_activity or qdate > customer_last_activity[customer]:
                customer_last_activity[customer] = qdate

    inactive = {
        c: dt for c, dt in customer_last_activity.items()
        if dt.replace(tzinfo=None) < cutoff
    }

    if not inactive:
        return f"✅ Tất cả khách hàng đều có activity trong {days} ngày qua."

    sorted_inactive = sorted(inactive.items(), key=lambda x: x[1])
    lines = [f"😴 INACTIVE CUSTOMERS (> {days} ngày)"]
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    for customer, last_dt in sorted_inactive[:10]:
        days_ago = (datetime.now() - last_dt.replace(tzinfo=None)).days
        lines.append(f"• {customer}: last activity {days_ago} ngày trước ({last_dt.strftime('%d/%m/%Y')})")
    lines.append(f"\n💡 Suggest: Chủ động liên hệ {len(inactive)} khách này để re-engage.")
    return "\n".join(lines)


def query_rate_trend(parquet_df: pd.DataFrame, place: str, months: int = 3) -> str:
    """Analyze rate trend for a specific place over N months."""
    if parquet_df is None or parquet_df.empty:
        return "Không có dữ liệu Parquet để phân tích trend."

    place_mask = parquet_df['Place'].astype(str).str.upper().str.contains(
        place.upper(), na=False
    )
    df = parquet_df[place_mask].copy()

    if df.empty:
        return f"Không tìm thấy dữ liệu cho '{place}'."

    # Group by carrier, get min rate (best rate per carrier)
    carrier_rates = {}
    for carrier, grp in df.groupby('Carrier'):
        amounts = grp['Amount'].dropna()
        if not amounts.empty:
            carrier_rates[str(carrier)] = {
                'best':  float(amounts.min()),
                'avg':   float(amounts.mean()),
                'count': int(len(amounts)),
            }

    if not carrier_rates:
        return f"Không có dữ liệu carrier cho '{place}'."

    best_carrier = min(carrier_rates, key=lambda x: carrier_rates[x]['best'])
    best_rate    = carrier_rates[best_carrier]['best']

    lines = [f"📈 RATE ANALYSIS — {place.upper()}"]
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")

    sorted_carriers = sorted(carrier_rates.items(), key=lambda x: x[1]['best'])
    for carrier_name, stats in sorted_carriers[:5]:
        tag = " ← BEST" if carrier_name == best_carrier else ""
        lines.append(
            f"• {carrier_name}: ${stats['best']:,.0f}/cont best rate | "
            f"avg ${stats['avg']:,.0f} ({stats['count']} options){tag}"
        )
    lines.append(f"\n💡 Best option: {best_carrier} ${best_rate:,.0f}/cont (hiện tại)")
    return "\n".join(lines)


def query_win_loss_comparison(quote_history: list, entity_a: str, entity_b: str,
                               field: str = 'carrier') -> str:
    """Compare win rates between two carriers or customers."""
    if not quote_history:
        return "Không có dữ liệu quote để so sánh."

    def calc_stats(name):
        relevant = [
            q for q in quote_history
            if name.upper() in str(q.get(field, '')).upper()
        ]
        if not relevant:
            return None
        wins = sum(1 for q in relevant if q.get('status','').upper() == 'WIN')
        wr = wins / len(relevant) * 100
        return {'total': len(relevant), 'wins': wins, 'win_rate': wr}

    stats_a = calc_stats(entity_a)
    stats_b = calc_stats(entity_b)

    if not stats_a and not stats_b:
        return f"Không tìm thấy dữ liệu cho '{entity_a}' hay '{entity_b}'."

    lines = [f"⚔️ COMPARISON: {entity_a.upper()} vs {entity_b.upper()}"]
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")

    for name, stats in [(entity_a, stats_a), (entity_b, stats_b)]:
        if stats:
            winner_tag = ""
            if stats_a and stats_b:
                winner_tag = " 🏆" if stats['win_rate'] == max(
                    stats_a['win_rate'], stats_b['win_rate']
                ) else ""
            lines.append(
                f"{name.upper()}{winner_tag}: {stats['win_rate']:.0f}% win rate "
                f"({stats['wins']}/{stats['total']} quotes)"
            )
        else:
            lines.append(f"{name.upper()}: Không có dữ liệu")

    return "\n".join(lines)


def query_route_popularity(jobs: list, top_n: int = 5) -> str:
    """Find most popular routes from active jobs and quote history."""
    if not jobs:
        return "Không có dữ liệu jobs."

    route_counts = {}
    for job in jobs:
        routing = str(job.get('routing', job.get('place', 'Unknown')))
        if routing and routing not in ('nan', 'None', 'Unknown'):
            route_counts[routing] = route_counts.get(routing, 0) + 1

    if not route_counts:
        return "Không xác định được route."

    sorted_routes = sorted(route_counts.items(), key=lambda x: x[1], reverse=True)

    lines = [f"🗺️ TOP {top_n} POPULAR ROUTES"]
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    for idx, (route, count) in enumerate(sorted_routes[:top_n], 1):
        lines.append(f"{idx}. {route}: {count} shipments")
    return "\n".join(lines)


# ── Intent dispatcher ─────────────────────────────────────────────────────────

def dispatch_nl_query(
    question: str,
    parquet_df: pd.DataFrame,
    all_jobs: list,
    all_quotes: list,
    ai_classify_fn=None,
) -> str:
    """
    Main entry point: parse a natural language question and return the answer.

    Args:
        question:        Vietnamese NL question from Sếp
        parquet_df:      Loaded Parquet DataFrame
        all_jobs:        List of all active jobs from erp_reader
        all_quotes:      List of all quotes from erp_reader
        ai_classify_fn:  Optional function(question) → dict with intent + entities

    Returns:
        Formatted string answer.
    """
    q_lower = question.lower()

    # ── Rule-based routing (fast path — no AI call needed) ───────────────────

    # Margin/profit analysis
    if any(w in q_lower for w in ['margin', 'profit', 'lời', 'lãi', 'markup']):
        carrier_match = re.search(r'\b(cma|one|msk|yml|zim|oocl|whl|hmm|pil|tsl|esl|mck|apl)\b',
                                   q_lower, re.IGNORECASE)
        carrier = carrier_match.group(1).upper() if carrier_match else None
        return query_carrier_margin(all_jobs, carrier)

    # Inactive customers
    if any(w in q_lower for w in ['inactive', 'chưa order', 'chưa mua', 'im lặng', 'lâu rồi', 'không thấy']):
        days_match = re.search(r'(\d+)\s*(ngày|day)', q_lower)
        days = int(days_match.group(1)) if days_match else 30
        return query_inactive_customers(all_quotes, days)

    # Rate trend for specific place
    if any(w in q_lower for w in ['giá', 'rate', 'trend', 'tuyến', 'lane']):
        places = ['denver', 'el paso', 'atlanta', 'houston', 'kansas', 'chicago',
                  'los angeles', 'lax', 'seattle', 'new york']
        for place in places:
            if place in q_lower:
                return query_rate_trend(parquet_df, place)

    # Win/loss comparison
    cmp_match = re.search(
        r'\b(cma|one|msk|yml|zim|hml|siri|panda)\b.*vs.*\b(cma|one|msk|yml|zim|hml|siri|panda)\b',
        q_lower, re.IGNORECASE
    )
    if cmp_match:
        a, b   = cmp_match.group(1), cmp_match.group(2)
        field  = 'carrier' if a.upper() in ('CMA','ONE','MSK','YML','ZIM') else 'customer'
        return query_win_loss_comparison(all_quotes, a, b, field)

    # Route popularity
    if any(w in q_lower for w in ['route', 'lane phổ biến', 'hay đi', 'tuyến nào']):
        return query_route_popularity(all_jobs)

    # Revenue stats
    if any(w in q_lower for w in ['revenue', 'doanh thu', 'bao nhiêu tiền', 'tổng']):
        total_rev = sum(
            (j.get('selling', 0) or 0) * (j.get('quantity', 1) or 1)
            for j in all_jobs
        )
        total_profit = sum(
            ((j.get('selling', 0) or 0) - (j.get('buying', 0) or 0)) * (j.get('quantity', 1) or 1)
            for j in all_jobs
        )
        return (
            f"💰 REVENUE SUMMARY\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Total Revenue (active jobs): ${total_rev:,.0f}\n"
            f"Total Profit:               ${total_profit:,.0f}\n"
            f"Jobs analyzed:              {len(all_jobs)}\n"
            f"\n💡 Dùng /kpi để xem dashboard đầy đủ hơn."
        )

    # Fallback: generic stats summary
    return (
        f"📊 QUICK STATS\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Active jobs:  {len(all_jobs)}\n"
        f"Total quotes: {len(all_quotes)}\n"
        f"Rates loaded: {len(parquet_df) if parquet_df is not None else 0:,}\n"
        f"\n💡 Thử hỏi cụ thể hơn:\n"
        f'  "Carrier nào margin cao nhất?"\n'
        f'  "Khách nào chưa order 30 ngày?"\n'
        f'  "Giá tuyến Denver đang thế nào?"'
    )
