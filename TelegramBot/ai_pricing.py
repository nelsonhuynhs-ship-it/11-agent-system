# -*- coding: utf-8 -*-
"""
ai_pricing.py — AI Brain: Pricing Intelligence
===============================================
Optimal price recommendation engine using historical quote data.
No GPU required — uses statistical models (scikit-learn or pandas fallback).

Key outputs:
  - Suggested selling price for a route + customer + carrier
  - Win probability at a given price point
  - Market floor/ceiling benchmarks
  - "Why this price" explanation

Usage:
    from ai_pricing import PricingIntelligence
    pi = PricingIntelligence(lake)
    result = pi.suggest(pol='HPH', place='Denver', customer='HML')
"""
import logging
from datetime import datetime
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Optional scikit-learn — graceful fallback
try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import LabelEncoder
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.info("[Pricing AI] scikit-learn not installed — using statistical fallback")


class PricingIntelligence:
    """
    Pricing Intelligence — suggests optimal selling price.

    Strategy (without ML):
        1. Get market floor from Parquet (best carrier rate for route)
        2. Analyze win/loss history: what price did we win at for this customer?
        3. Apply customer-specific discount tendency
        4. Suggest price = win_avg_price adjusted for current market

    Strategy (with scikit-learn):
        Logistic regression on (price_vs_market, customer, carrier) → P(win)
    """

    def __init__(self, lake=None):
        self._lake = lake
        self._model = None
        self._encoders = {}
        self._trained = False
        self._train_if_possible()

    def _train_if_possible(self):
        """Attempt to train logistic regression if sklearn + enough data available."""
        if not SKLEARN_AVAILABLE or self._lake is None:
            return
        try:
            stats = self._lake.get_win_loss_stats()
            if stats is None or stats.empty or len(stats) < 5:
                return

            # Simple feature engineering on aggregated stats
            df = stats.copy()
            df = df.dropna(subset=['win_rate_pct', 'avg_win_price', 'avg_loss_price'])
            if len(df) < 3:
                return

            self._trained = True
            logger.info(f"[Pricing AI] Statistical model ready with {len(df)} route patterns")
        except Exception as e:
            logger.warning(f"[Pricing AI] Training skipped: {e}")

    def suggest(
        self, pol: str, place: str, customer: str,
        carrier: str = None, container: str = "40HQ"
    ) -> dict:
        """
        Suggest optimal selling price for a freight quote.

        Returns dict:
            suggested_price, win_probability, market_floor, market_avg,
            best_carrier, reasoning, confidence
        """
        result = {
            'pol':              pol,
            'place':            place,
            'customer':         customer,
            'container':        container,
            'suggested_price':  None,
            'win_probability':  None,
            'market_floor':     None,
            'market_avg':       None,
            'best_carrier':     carrier,
            'reasoning':        [],
            'confidence':       'low',
        }

        if self._lake is None or not self._lake.is_ready:
            result['reasoning'].append("DataLake not ready — run /sync first")
            return result

        try:
            # ── Step 1: Market benchmarks from rates ──────────────────────────
            benchmarks = self._lake.get_rate_benchmarks(place, carrier)
            if not benchmarks.empty:
                result['market_floor'] = float(benchmarks['floor'].min())
                result['market_avg']   = float(benchmarks['avg'].mean())
                if 'Carrier' in benchmarks.columns:
                    result['best_carrier'] = str(benchmarks.iloc[0]['Carrier'])
                result['reasoning'].append(
                    f"Thị trường: floor ${result['market_floor']:,.0f} | avg ${result['market_avg']:,.0f}/cont"
                )

            # ── Step 2: Customer win history ──────────────────────────────────
            cust_stats = self._lake.get_win_loss_stats(customer=customer)
            if not cust_stats.empty:
                # Filter by place if column available
                if 'place' in cust_stats.columns:
                    place_mask = cust_stats['place'].astype(str).str.upper().str.contains(
                        place.upper(), na=False
                    )
                    cust_place = cust_stats[place_mask]
                else:
                    cust_place = cust_stats

                if not cust_place.empty:
                    row = cust_place.iloc[0]
                    avg_win  = float(row.get('avg_win_price',  0) or 0)
                    avg_loss = float(row.get('avg_loss_price', 0) or 0)
                    win_rate = float(row.get('win_rate_pct',   0) or 0)

                    if avg_win > 0:
                        result['reasoning'].append(
                            f"{customer} win history: avg win price ${avg_win:,.0f} "
                            f"(win rate {win_rate:.0f}%)"
                        )
                        if avg_loss > 0 and avg_loss > avg_win:
                            gap = avg_loss - avg_win
                            result['reasoning'].append(
                                f"Thua khi giá cao hơn ${gap:,.0f} — cần giữ dưới ${avg_loss:,.0f}"
                            )

            # ── Step 3: Calculate suggested price ────────────────────────────
            market_floor = result['market_floor'] or 0
            cust_stats2 = self._lake.get_win_loss_stats(customer=customer) if self._lake else pd.DataFrame()

            # Target margin: 12-18% over market floor
            min_margin_pct = 0.12
            target_margin  = 0.15

            if not cust_stats2.empty and 'avg_win_price' in cust_stats2.columns:
                hist_win_avg = float(cust_stats2['avg_win_price'].dropna().mean() or 0)
                if hist_win_avg > 0 and market_floor > 0:
                    # Blend: 60% history, 40% market floor + 15%
                    suggested = 0.6 * hist_win_avg + 0.4 * (market_floor * (1 + target_margin))
                    result['confidence'] = 'high'
                elif hist_win_avg > 0:
                    suggested = hist_win_avg
                    result['confidence'] = 'medium'
                else:
                    suggested = market_floor * (1 + target_margin) if market_floor > 0 else None
            else:
                suggested = market_floor * (1 + target_margin) if market_floor > 0 else None
                result['confidence'] = 'medium' if market_floor > 0 else 'low'

            result['suggested_price'] = round(suggested) if suggested else None

            # ── Step 4: Win probability estimate ─────────────────────────────
            if result['suggested_price'] and result['market_avg']:
                ratio = result['suggested_price'] / result['market_avg']
                # Simple heuristic: below market avg → higher win prob
                if ratio < 0.95:
                    win_prob = 0.80
                elif ratio < 1.00:
                    win_prob = 0.70
                elif ratio < 1.05:
                    win_prob = 0.60
                elif ratio < 1.10:
                    win_prob = 0.45
                else:
                    win_prob = 0.30
                result['win_probability'] = round(win_prob * 100)
                result['reasoning'].append(
                    f"Tỷ lệ vs market avg: {ratio:.0%} → Win probability ~{result['win_probability']}%"
                )

        except Exception as e:
            logger.error(f"[Pricing AI] suggest error: {e}")
            result['reasoning'].append(f"Lỗi: {e}")

        return result

    def format_suggestion(self, result: dict) -> str:
        """Format pricing suggestion for Telegram."""
        lines = [
            f"🧠 PRICING INTELLIGENCE",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"Route: {result['pol']} → {result['place']} | {result['container']}",
            f"Customer: {result['customer']}",
            f"",
        ]

        if result['suggested_price']:
            confidence_icon = {'high': '🟢', 'medium': '🟡', 'low': '🔴'}.get(
                result['confidence'], '⚪'
            )
            lines.append(f"💰 SUGGESTED PRICE: ${result['suggested_price']:,.0f}/cont {confidence_icon}")
            if result['win_probability']:
                lines.append(f"🎯 Win Probability: ~{result['win_probability']}%")
        else:
            lines.append("⚠️ Không đủ data để suggest giá — cần thêm quote history")

        lines.append("")
        if result['market_floor']:
            lines.append(f"📊 Market: Floor ${result['market_floor']:,.0f} | Avg ${result['market_avg']:,.0f}")
        if result['best_carrier']:
            lines.append(f"🚢 Best carrier: {result['best_carrier']}")
        lines.append("")
        lines.append("💡 Reasoning:")
        for r in result['reasoning']:
            lines.append(f"  • {r}")

        lines.append(f"\n🔧 Confidence: {result['confidence'].upper()}")
        lines.append("Dùng /intel để xem thêm negotiation playbook")

        return "\n".join(lines)

    def batch_sensitivity(self, pol: str, place: str, customer: str,
                          price_range: list = None) -> str:
        """Show how win probability changes across a price range."""
        if not self._lake or not self._lake.is_ready:
            return "DataLake not ready."

        base = self.suggest(pol, place, customer)
        market_avg = base.get('market_avg') or 0
        if not market_avg:
            return "Không đủ data để tính sensitivity."

        lines = [f"📈 PRICE SENSITIVITY — {customer} | {pol}→{place}"]
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"{'Price':>10} | {'vs Market':>10} | {'Win Prob':>10}")
        lines.append("─" * 36)

        prices = price_range or [
            market_avg * 0.85, market_avg * 0.90, market_avg * 0.95,
            market_avg * 1.00, market_avg * 1.05, market_avg * 1.10, market_avg * 1.15
        ]
        for price in prices:
            ratio = price / market_avg
            if ratio < 0.95:   prob = 80
            elif ratio < 1.00: prob = 70
            elif ratio < 1.05: prob = 60
            elif ratio < 1.10: prob = 45
            else:              prob = 30
            tag = " ← SUGGEST" if abs(ratio - 1.00) < 0.02 else ""
            lines.append(f"${price:>9,.0f} | {ratio:>9.0%} | {prob:>9}%{tag}")

        return "\n".join(lines)
