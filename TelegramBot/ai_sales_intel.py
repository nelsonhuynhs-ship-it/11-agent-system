# -*- coding: utf-8 -*-
"""
ai_sales_intel.py — AI Brain: Sales Intelligence
=================================================
Two core capabilities:
  1. Win/Loss Explainer — "Tại sao thắng/thua quote này?"
  2. Churn Detector + Reach-out Recommender — "Khách nào đang im lặng?"
  3. Next-Order Prediction — "Ai sắp order?"

Uses DataLake for historical pattern analysis.
No ML framework required — statistical pattern matching.

Usage:
    from ai_sales_intel import SalesIntelligence
    si = SalesIntelligence(lake)
    explanation = si.explain_quote(quote_dict)
    churn_list  = si.detect_churn(all_quotes)
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Churn risk thresholds
CHURN_RATIO_CRITICAL = 2.0   # > 2x normal interval = very at risk
CHURN_RATIO_HIGH     = 1.5   # > 1.5x = at risk
CHURN_RATIO_MEDIUM   = 1.2   # > 1.2x = watch


class SalesIntelligence:
    """Sales Intelligence — win/loss analysis + churn detection."""

    def __init__(self, lake=None):
        self._lake = lake

    def explain_quote(self, quote: dict) -> str:
        """
        Analyze a specific quote and explain why it won or lost.
        Works even without DataLake using the quote's own data.
        """
        status    = str(quote.get('status', '')).upper()
        customer  = str(quote.get('customer', 'Unknown'))
        carrier   = str(quote.get('carrier', 'Unknown'))
        price     = float(quote.get('price', 0) or 0)
        place     = str(quote.get('place', ''))
        quote_id  = str(quote.get('quote_id', ''))

        lines = [
            f"🔍 WIN/LOSS ANALYSIS — {quote_id}",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"Customer: {customer} | Carrier: {carrier}",
            f"Route: {quote.get('pol','')} → {place}",
            f"Price: ${price:,.0f}/cont | Status: {status}",
            "",
        ]

        reasons = []
        recommendations = []

        # ── Get market context from DataLake ──────────────────────────────────
        market_avg = None
        avg_win_price = None

        if self._lake and self._lake.is_ready:
            benchmarks = self._lake.get_rate_benchmarks(place, carrier)
            if not benchmarks.empty:
                market_avg = float(benchmarks['avg'].mean())

            cust_stats = self._lake.get_win_loss_stats(customer=customer)
            if not cust_stats.empty and 'avg_win_price' in cust_stats.columns:
                avg_win_data = cust_stats['avg_win_price'].dropna()
                avg_win_price = float(avg_win_data.mean()) if not avg_win_data.empty else None

        # ── Analysis: WIN case ────────────────────────────────────────────────
        if status == 'WIN':
            lines.append("✅ THẮNG — Phân tích:")
            if market_avg and price:
                ratio = price / market_avg
                if ratio < 0.95:
                    reasons.append(f"Giá cạnh tranh ({ratio:.0%} vs market avg ${market_avg:,.0f}) — thấp hơn thị trường")
                elif ratio <= 1.02:
                    reasons.append(f"Giá phù hợp ({ratio:.0%} vs market avg) — customer satisfied")
                else:
                    reasons.append(f"Giá hơi cao ({ratio:.0%} vs market avg) nhưng vẫn win → customer ưu tiên carrier này")

            if avg_win_price and price <= avg_win_price * 1.05:
                reasons.append(f"Trong range win price lịch sử của {customer} (${avg_win_price:,.0f})")

            recommendations.append("Lưu price point này làm benchmark cho lần sau")
            recommendations.append(f"HML/SIRI-style: check xem có thể giữ margin cao hơn không")

        # ── Analysis: LOSS case ───────────────────────────────────────────────
        elif status == 'LOSS':
            lines.append("❌ THUA — Phân tích:")
            if market_avg and price:
                ratio = price / market_avg
                if ratio > 1.10:
                    reasons.append(f"Giá quá cao: ${price:,.0f} ({ratio:.0%} vs market avg ${market_avg:,.0f})")
                    diff = price - market_avg
                    recommendations.append(f"Cần giảm ${diff:,.0f} để về market level")
                elif ratio > 1.05:
                    reasons.append(f"Giá hơi cao: ${price:,.0f} vs market avg")
                    recommendations.append("Thử giảm 3-5% ở lần báo giá tiếp theo")
                else:
                    reasons.append(f"Giá không phải vấn đề chính (gần market avg)")
                    reasons.append("Có thể thua vì: timing, carrier preference, service issue")

            if avg_win_price and price > avg_win_price * 1.08:
                diff = price - avg_win_price
                reasons.append(f"Cao hơn win price lịch sử với {customer}: +${diff:,.0f}")
                recommendations.append(f"Next time: offer ${avg_win_price:,.0f} to match historical win rate")

            # Carrier-specific insight
            if 'SOC' in carrier.upper() or carrier.upper() in ('ONE', 'YML', 'ZIM'):
                reasons.append("SOC carrier — check nếu KH cần SOC hay COC")

        else:
            lines.append(f"⏳ PENDING — Chưa có kết quả")
            if market_avg and price:
                ratio = price / market_avg
                prob = 80 if ratio < 0.95 else (70 if ratio < 1.0 else 55 if ratio < 1.05 else 35)
                lines.append(f"Win probability estimate: ~{prob}% (giá {ratio:.0%} vs market)")

        for r in reasons:
            lines.append(f"  • {r}")

        if recommendations:
            lines.append("\n💡 Recommendations:")
            for rec in recommendations:
                lines.append(f"  → {rec}")

        return "\n".join(lines)

    def detect_churn(self, all_customer_codes: list) -> list:
        """
        Analyze all customers for churn risk.
        Returns list of at-risk customers sorted by urgency.
        """
        if not self._lake or not self._lake.is_ready:
            return []

        risk_customers = []
        for code in all_customer_codes:
            try:
                pattern = self._lake.get_customer_order_pattern(code)
                if not pattern or pattern.get('pattern') in ('unknown', 'insufficient_data'):
                    continue

                churn_ratio = pattern.get('churn_ratio', 0)
                if churn_ratio < CHURN_RATIO_MEDIUM:
                    continue  # Active customer, no concern

                level = (
                    'CRITICAL' if churn_ratio >= CHURN_RATIO_CRITICAL else
                    'HIGH'     if churn_ratio >= CHURN_RATIO_HIGH else
                    'MEDIUM'
                )
                risk_customers.append({
                    **pattern,
                    'risk_level': level,
                    'churn_ratio': churn_ratio,
                })
            except Exception:
                continue

        # Sort: most overdue first
        return sorted(risk_customers, key=lambda x: x.get('churn_ratio', 0), reverse=True)

    def format_reachout_list(self, churn_list: list) -> str:
        """Format churn risk list for Telegram."""
        if not churn_list:
            return "✅ Tất cả khách hàng đang active. Không có churn risk.\n\n💡 Sync data trước: /sync"

        lines = [
            "📣 CUSTOMER REACH-OUT LIST",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"Phát hiện {len(churn_list)} khách có nguy cơ churn:",
            "",
        ]

        icons = {'CRITICAL': '🔴', 'HIGH': '🟡', 'MEDIUM': '🟢'}
        for c in churn_list[:8]:
            icon     = icons.get(c['risk_level'], '⚪')
            customer = c.get('customer', '?')
            days     = c.get('days_since_last_order', '?')
            avg_int  = c.get('avg_order_interval_days', '?')
            last     = c.get('last_order_date', '?')
            wins     = c.get('total_wins', 0)

            lines.append(
                f"{icon} {c['risk_level']} — {customer}\n"
                f"   {days} ngày chưa order (avg: {avg_int:.0f} ngày)\n"
                f"   Last order: {last} | Total wins: {wins}"
            )

        lines.append("")
        lines.append("🎯 Suggested actions:")
        lines.append("  → Gửi proactive offer cho CRITICAL + HIGH")
        lines.append("  → Mention: 'Space đang available / Giá tốt tháng này'")
        lines.append("  → Dùng /intel CUSTOMER để xem recommended offer")

        return "\n".join(lines)

    def predict_next_orders(self, all_customer_codes: list) -> str:
        """
        Predict which customers are likely to order next.
        Based on their historical order intervals.
        """
        if not self._lake or not self._lake.is_ready:
            return "DataLake not ready — run /sync first."

        predictions = []
        for code in all_customer_codes:
            try:
                pattern = self._lake.get_customer_order_pattern(code)
                if not pattern or pattern.get('avg_order_interval_days', 0) == 0:
                    continue

                avg_int = pattern['avg_order_interval_days']
                days_since = pattern['days_since_last_order']
                days_until_next = max(0, avg_int - days_since)

                if days_until_next <= 14:  # Order due within 2 weeks
                    predictions.append({
                        'customer':          code,
                        'days_until_next':   round(days_until_next),
                        'avg_interval':      round(avg_int),
                        'last_order':        pattern.get('last_order_date', '?'),
                        'total_wins':        pattern.get('total_wins', 0),
                    })
            except Exception:
                continue

        predictions.sort(key=lambda x: x['days_until_next'])

        if not predictions:
            return "📊 Không có customer nào dự kiến order trong 14 ngày tới."

        lines = ["🔮 NEXT ORDER PREDICTIONS (14 ngày tới)"]
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        for p in predictions[:5]:
            urgency = "🔥" if p['days_until_next'] <= 3 else ("⏰" if p['days_until_next'] <= 7 else "📅")
            lines.append(
                f"{urgency} {p['customer']}: order trong ~{p['days_until_next']} ngày\n"
                f"   (avg {p['avg_interval']} ngày, last {p['last_order']})"
            )
        lines.append("\n💡 Proactive offer ngay cho những khách này!")
        return "\n".join(lines)
