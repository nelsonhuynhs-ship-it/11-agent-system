# -*- coding: utf-8 -*-
"""
customer_intelligence.py — Bot v6 Feature #6
Customer 360° Intelligence — builds a rich agentic intelligence card
merging Parquet history, ERP quotes/jobs, static profiles, and AI insights.

Usage:
  - Called by /intel CUSTOMER command
  - Also injected as context when customer name detected in any message
"""
import logging
from datetime import datetime, timedelta

import pandas as pd

logger = logging.getLogger(__name__)


def get_rate_trends(parquet_df: pd.DataFrame, place: str, days: int = 90) -> dict:
    """
    Analyze rate trends for a specific destination over last N days.
    Returns: {carrier: {current_rate, trend_direction, avg_90d}}
    """
    if parquet_df is None or parquet_df.empty or not place:
        return {}

    try:
        df = parquet_df.copy()
        place_upper = place.upper()

        # Filter by place
        mask = df['Place'].astype(str).str.upper().str.contains(place_upper, na=False)
        df = df[mask]

        if df.empty:
            return {}

        # Compute per-carrier stats
        trend = {}
        for carrier, grp in df.groupby('Carrier'):
            amounts = grp['Amount'].dropna()
            if amounts.empty:
                continue
            trend[str(carrier)] = {
                'best_rate':   float(amounts.min()),
                'avg_rate':    float(amounts.mean()),
                'count':       int(len(amounts)),
            }

        return trend

    except Exception as e:
        logger.error(f"[Intel] rate trends error: {e}")
        return {}


def build_negotiation_playbook(quote_history: list, customer_profile: dict) -> str:
    """
    Analyze quote history to build a negotiation playbook.
    Returns actionable tips based on win/loss patterns.
    """
    if not quote_history:
        return "Chưa có đủ dữ liệu để phân tích."

    wins  = [q for q in quote_history if q.get('status', '').upper() == 'WIN']
    loses = [q for q in quote_history if q.get('status', '').upper() == 'LOSS']

    tips = []

    # Win rate analysis
    total = len(quote_history)
    win_rate = len(wins) / total * 100 if total > 0 else 0
    tips.append(f"Win Rate: {win_rate:.0f}% ({len(wins)}/{total} quotes)")

    # Price analysis
    if wins:
        win_prices  = [q['price'] for q in wins  if q.get('price', 0) > 0]
        lose_prices = [q['price'] for q in loses if q.get('price', 0) > 0]

        if win_prices and lose_prices:
            avg_win  = sum(win_prices)  / len(win_prices)
            avg_lose = sum(lose_prices) / len(lose_prices)
            diff = avg_lose - avg_win
            if diff > 0:
                tips.append(
                    f"Pattern: Khi thua — giá cao hơn win trung bình ${diff:,.0f}/cont"
                )
                tips.append(
                    f"→ Suggest: Khi KH push giá, thử giảm tối đa ${diff*0.7:,.0f} để dưới threshold"
                )

    # Carrier preferences
    if wins:
        carrier_counts = {}
        for q in wins:
            c = q.get('carrier', 'Unknown')
            carrier_counts[c] = carrier_counts.get(c, 0) + 1
        top_carrier = max(carrier_counts, key=carrier_counts.get)
        tips.append(f"Best carrier choice: {top_carrier} ({carrier_counts[top_carrier]} wins)")

    # Behavior tags from profile
    behavior = customer_profile.get('behavior_tag', '') if customer_profile else ''
    if 'price sensitive' in behavior.lower():
        tips.append("⚡ KH nhạy cảm giá — nên offer giá tốt nhất ngay lần đầu")
    if 'delayed' in behavior.lower():
        tips.append("🕐 KH hay chần chừ — tạo urgency: 'Space siết / giá tăng tuần sau'")

    return "\n".join(f"  {t}" for t in tips)


def build_intel_card(
    customer_name: str,
    crm_profile: dict,
    quote_history: list,
    active_jobs: list,
    parquet_df: pd.DataFrame,
    static_profile: dict = None,
) -> str:
    """
    Build a full 360° intelligence card for a customer.
    Used by /intel command and context injection.

    Returns formatted message string.
    """
    today = datetime.now()
    lines = [
        f"🔍 CUSTOMER INTELLIGENCE — {customer_name.upper()}",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📅 As of {today.strftime('%d/%m/%Y %H:%M')}",
        ""
    ]

    # ── Section 1: Identity ──────────────────────────────────────────────────
    lines.append("👤 IDENTITY")
    if crm_profile:
        name = crm_profile.get('name', customer_name)
        contact = crm_profile.get('contact', '—')
        email   = crm_profile.get('email', '—')
        phone   = crm_profile.get('phone', '—')
        terms   = crm_profile.get('payment_terms', '—')
        lines.append(f"  {name} | Contact: {contact}")
        lines.append(f"  📧 {email} | 📞 {phone}")
        lines.append(f"  💳 Payment: {terms}")
    if static_profile:
        lanes = ', '.join(static_profile.get('preferred_lanes', []))
        comm  = ', '.join(static_profile.get('commodity', []))
        behav = static_profile.get('behavior_tag', '')
        if lanes: lines.append(f"  Lanes: {lanes}")
        if comm:  lines.append(f"  Hàng:  {comm}")
        if behav: lines.append(f"  📊 Behavior: {behav}")
    lines.append("")

    # ── Section 2: Performance ───────────────────────────────────────────────
    lines.append("📈 PERFORMANCE (3 tháng gần nhất)")
    recent_90 = [
        q for q in quote_history
        if q.get('date') and pd.notna(q['date'])
        and q['date'] >= pd.Timestamp(today - timedelta(days=90))
    ]

    if recent_90:
        wins_90   = [q for q in recent_90 if q.get('status','').upper() == 'WIN']
        losses_90 = [q for q in recent_90 if q.get('status','').upper() == 'LOSS']
        pending   = [q for q in recent_90 if q.get('status','').upper() == 'PENDING']
        wr = len(wins_90) / len(recent_90) * 100

        lines.append(f"  Quotes: {len(recent_90)} | ✅ Win: {len(wins_90)} | ❌ Loss: {len(losses_90)} | ⏳ Pending: {len(pending)}")
        lines.append(f"  Win Rate: {wr:.0f}%")

        if wins_90:
            rev = sum(q['price'] for q in wins_90 if q.get('price', 0) > 0)
            lines.append(f"  Revenue won: ${rev:,.0f}")
    else:
        lines.append("  Không có quote trong 90 ngày qua")
    lines.append("")

    # ── Section 3: Active Jobs ───────────────────────────────────────────────
    if active_jobs:
        lines.append(f"🚢 ACTIVE JOBS ({len(active_jobs)} shipments)")
        for job in active_jobs[:5]:
            etd = job['etd'].strftime('%d/%m') if pd.notna(job.get('etd')) else '?'
            eta = job['eta'].strftime('%d/%m') if pd.notna(job.get('eta')) else '?'
            profit = job.get('selling', 0) - job.get('buying', 0)
            bkg = f" BKG:{job['bkg_no']}" if job.get('bkg_no') else " ⚠️ No BKG"
            lines.append(
                f"  [{job['status']}] {job['job_id']} | "
                f"{job['carrier']} {job['container']}×{job.get('quantity',1)} "
                f"ETD {etd}→ETA {eta} | Profit: ${profit:,.0f}{bkg}"
            )
        lines.append("")

    # ── Section 4: Rate Opportunities ───────────────────────────────────────
    lanes = static_profile.get('preferred_lanes', []) if static_profile else []
    if lanes and parquet_df is not None and not parquet_df.empty:
        lines.append("💰 RATE OPPORTUNITIES (Lanes hay đi)")
        for lane in lanes[:2]:  # Show top 2 preferred lanes
            trends = get_rate_trends(parquet_df, lane)
            if trends:
                best_carrier = min(trends, key=lambda x: trends[x]['best_rate'])
                best_rate    = trends[best_carrier]['best_rate']
                lines.append(f"  {lane}: Best = {best_carrier} ${best_rate:,.0f}/cont")
        lines.append("")

    # ── Section 5: Negotiation Playbook ─────────────────────────────────────
    lines.append("🤝 NEGOTIATION PLAYBOOK")
    playbook = build_negotiation_playbook(quote_history, static_profile)
    lines.append(playbook)
    lines.append("")

    # ── Section 6: AI Recommendation ────────────────────────────────────────
    lines.append("💡 RECOMMENDED ACTIONS")

    # Check if customer has been quiet
    if not recent_90:
        lines.append("  → KH chưa có quote 90 ngày — xem xét chủ động liên hệ")
    elif not active_jobs:
        lines.append("  → Có quotes nhưng không có jobs — follow up pending quotes")

    # Check preferred lanes for proactive reach-out
    if lanes:
        lines.append(f"  → Proactive offer cho lanes: {', '.join(lanes[:2])}")

    # Summarize key risk
    if active_jobs:
        no_bkg = [j for j in active_jobs if not j.get('bkg_no')]
        if no_bkg:
            lines.append(
                f"  ⚠️ {len(no_bkg)} job(s) chưa có booking number — cần confirm với hãng tàu!"
            )

    return "\n".join(lines)
