# -*- coding: utf-8 -*-
"""
ai_risk_engine.py — AI Brain: Multi-Dimensional Risk Assessment
=================================================================
4 risk dimensions assessed for every customer/job:
  1. Weight Risk    — Commodity/customer prone to overweight
  2. Rate Expiry    — Rates expiring vs active jobs exposure
  3. Space Risk     — Peak season + carrier capacity signals
  4. Payment Risk   — Payment terms + outstanding jobs

Returns a composite risk card with scores and recommended actions.

Usage:
    from ai_risk_engine import RiskEngine
    re = RiskEngine(lake, parquet_df)
    card = re.assess_customer('HML')
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ── Risk thresholds ───────────────────────────────────────────────────────────
WEIGHT_HIGH_COMMODITIES = ['stone', 'slab', 'marble', 'granite', 'tile', 'ceramic', 'metal', 'steel']
WEIGHT_HIGH_CUSTOMERS   = ['HML']  # Known heavy shippers
CARRIER_WEIGHT_LIMITS   = {
    'CMA': 18.0, 'ONE': 18.0, 'MSK': 17.5, 'YML': 18.0,
    'ZIM': 18.0, 'OOCL': 18.0, 'WHL': 17.0, 'HMM': 18.0,
}  # Tons per 40HQ

PEAK_MONTHS  = [3, 4, 9, 10, 11]  # March-April, Sep-Nov tight space
HIGH_RISK_CARRIERS_SPACE = ['CMA', 'MSK']  # Often tight in peak

CREDIT_RISK_TERMS = ['30 days', '45 days', '60 days', 'NET30', 'NET45', 'NET60']


class RiskEngine:
    """Multi-dimensional freight risk assessor."""

    def __init__(self, lake=None, parquet_df: pd.DataFrame = None):
        self._lake = lake
        self._parquet_df = parquet_df

    def _weight_risk(self, customer: str, jobs: list) -> dict:
        """Assess weight risk based on customer profile and commodity."""
        score = 0.0
        signals = []

        # Customer-based weight risk
        if any(c in customer.upper() for c in WEIGHT_HIGH_CUSTOMERS):
            score += 0.4
            signals.append(f"⚠️ {customer} là known heavy shipper (Stone/Slab)")

        # Job-based signals
        if jobs:
            for job in jobs:
                commodity = str(job.get('commodity', '') or '').lower()
                carrier   = str(job.get('carrier', '') or '').upper()
                limit     = CARRIER_WEIGHT_LIMITS.get(carrier, 18.0)

                if any(w in commodity for w in WEIGHT_HIGH_COMMODITIES):
                    score += 0.3
                    signals.append(f"Heavy commodity: {commodity}")
                    break

        score = min(score, 1.0)
        return {
            'score':   round(score, 2),
            'level':   _score_to_level(score),
            'signals': signals,
            'action':  "Yêu cầu khai báo gross weight trước khi release BKG" if score > 0.4 else None,
        }

    def _rate_expiry_risk(self, customer: str, jobs: list) -> dict:
        """Assess risk from rates expiring while jobs are active."""
        score  = 0.0
        signals = []
        today  = datetime.now().date()

        if self._parquet_df is None or self._parquet_df.empty:
            return {'score': 0.0, 'level': 'UNKNOWN', 'signals': ['No rate data'], 'action': None}

        # For each active job, check if the carrier's rates on that route expire soon
        for job in (jobs or []):
            carrier   = str(job.get('carrier', '') or '').upper()
            routing   = str(job.get('routing', '') or '')
            etd       = job.get('etd')

            if not carrier or not etd or not pd.notna(etd):
                continue

            etd_date = etd.date() if hasattr(etd, 'date') else None
            if not etd_date:
                continue

            # Get expiry for this carrier's rates
            df = self._parquet_df
            carrier_mask = df['Carrier'].astype(str).str.upper().str.contains(carrier, na=False)
            carrier_rates = df[carrier_mask]

            if carrier_rates.empty:
                continue

            min_exp = carrier_rates['Exp'].min()
            if pd.notna(min_exp):
                days_to_exp = (min_exp.date() - today).days
                if days_to_exp < 0:
                    score += 0.5
                    signals.append(f"🔴 {carrier} rates đã expired! Job {job.get('job_id', '?')} vẫn active")
                elif days_to_exp <= 3:
                    score += 0.4
                    signals.append(f"🔴 {carrier} rates hết hạn trong {days_to_exp} ngày — Job active!")
                elif days_to_exp <= 7:
                    score += 0.25
                    signals.append(f"🟡 {carrier} rates hết hạn {days_to_exp} ngày")

        score = min(score, 1.0)
        return {
            'score':   round(score, 2),
            'level':   _score_to_level(score),
            'signals': signals,
            'action':  "Renew rates NGAY trước ETD" if score > 0.3 else None,
        }

    def _space_risk(self, jobs: list) -> dict:
        """Assess space availability risk based on peak season + carrier patterns."""
        score   = 0.0
        signals = []
        today   = datetime.now()

        # Peak season check
        if today.month in PEAK_MONTHS:
            score += 0.2
            signals.append(f"📅 Tháng {today.month}: peak season — space thường siết")

        # Check if any jobs using high-risk carriers in peak routes
        for job in (jobs or []):
            carrier = str(job.get('carrier', '') or '').upper()
            etd = job.get('etd')

            if not carrier or not etd or not pd.notna(etd):
                continue

            etd_date = etd.date() if hasattr(etd, 'date') else None
            if not etd_date:
                continue

            days_to_etd = (etd_date - datetime.now().date()).days

            if carrier in HIGH_RISK_CARRIERS_SPACE and days_to_etd <= 14:
                score += 0.2
                signals.append(f"🚢 {carrier} + ETD {days_to_etd} ngày → priority confirm BKG")

        # No booking number jobs
        no_bkg = [j for j in (jobs or []) if not j.get('bkg_no')]
        if no_bkg:
            score += 0.15 * len(no_bkg)
            signals.append(f"⚠️ {len(no_bkg)} job(s) chưa có booking number")

        score = min(score, 1.0)
        return {
            'score':   round(score, 2),
            'level':   _score_to_level(score),
            'signals': signals,
            'action':  "Confirm space với carrier NGAY, xin BKG number" if score > 0.3 else None,
        }

    def _payment_risk(self, customer: str, crm_profile: dict, jobs: list) -> dict:
        """Assess payment/credit risk."""
        score   = 0.0
        signals = []

        if crm_profile:
            terms = str(crm_profile.get('payment_terms', '') or '').upper()
            if any(t in terms for t in ['60', 'NET60', '45', 'NET45']):
                score += 0.2
                signals.append(f"💳 Long payment terms: {terms}")
            elif any(t in terms for t in ['30', 'NET30']):
                score += 0.1

        # Multiple active jobs = higher exposure
        if len(jobs) >= 3:
            score += 0.15
            signals.append(f"📦 {len(jobs)} active jobs — significant credit exposure")

        # Estimate outstanding revenue
        total_outstanding = sum(
            (j.get('selling', 0) or 0) * (j.get('quantity', 1) or 1)
            for j in (jobs or [])
        )
        if total_outstanding > 50000:
            score += 0.2
            signals.append(f"💰 Outstanding: ${total_outstanding:,.0f} — cao")
        elif total_outstanding > 20000:
            score += 0.1
            signals.append(f"💰 Outstanding: ${total_outstanding:,.0f}")

        score = min(score, 1.0)
        return {
            'score':   round(score, 2),
            'level':   _score_to_level(score),
            'signals': signals,
            'action':  "Kiểm tra công nợ trước lô tiếp theo" if score > 0.35 else None,
        }

    def assess_customer(self, customer: str) -> dict:
        """
        Full risk assessment for a customer.
        Returns dict with 4 risk dimensions + composite score.
        """
        from erp_reader import get_active_jobs, get_crm_profile
        from customer_profiles import get_profile

        jobs = get_active_jobs(customer_name=customer, limit=10)
        crm  = get_crm_profile(customer) or {}
        stat = get_profile(customer) or {}

        # Merge commodity info
        commodity_tags = stat.get('commodity', [])
        for job in jobs:
            if not job.get('commodity'):
                job['commodity'] = ' '.join(commodity_tags)

        weight  = self._weight_risk(customer, jobs)
        rate    = self._rate_expiry_risk(customer, jobs)
        space   = self._space_risk(jobs)
        payment = self._payment_risk(customer, crm, jobs)

        # Composite score (weighted)
        composite = (
            weight['score']  * 0.35 +
            rate['score']    * 0.30 +
            space['score']   * 0.20 +
            payment['score'] * 0.15
        )

        return {
            'customer':  customer,
            'composite': round(composite, 2),
            'level':     _score_to_level(composite),
            'weight':    weight,
            'rate':      rate,
            'space':     space,
            'payment':   payment,
            'active_jobs': len(jobs),
            'assessed_at': datetime.now().strftime('%H:%M %d/%m'),
        }

    def format_risk_card(self, assessment: dict) -> str:
        """Format risk assessment as Telegram message."""
        customer  = assessment['customer']
        level     = assessment['level']
        composite = assessment['composite']
        icon      = {'LOW': '🟢', 'MEDIUM': '🟡', 'HIGH': '🔴', 'CRITICAL': '🚨', 'UNKNOWN': '⚪'}.get(level, '⚪')

        lines = [
            f"⚡ RISK ASSESSMENT — {customer}",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"Overall: {icon} {level} (score: {composite:.0%})",
            f"Active jobs: {assessment['active_jobs']} | {assessment['assessed_at']}",
            "",
        ]

        for dim_key, label, emoji in [
            ('weight',  'Weight Risk',      '⚖️'),
            ('rate',    'Rate Expiry Risk',  '⏰'),
            ('space',   'Space Risk',        '🚢'),
            ('payment', 'Payment Risk',      '💳'),
        ]:
            dim = assessment[dim_key]
            lvl = dim['level']
            lvl_icon = {'LOW': '🟢', 'MEDIUM': '🟡', 'HIGH': '🔴', 'CRITICAL': '🚨', 'UNKNOWN': '⚪'}.get(lvl, '⚪')
            lines.append(f"{emoji} {label}: {lvl_icon} {lvl} ({dim['score']:.0%})")

            for sig in dim.get('signals', [])[:2]:
                lines.append(f"   {sig}")

            action = dim.get('action')
            if action and dim['score'] > 0.3:
                lines.append(f"   → {action}")

        priority_actions = [
            dim['action']
            for dim_key in ('weight', 'rate', 'space', 'payment')
            for dim in [assessment[dim_key]]
            if dim.get('action') and dim['score'] > 0.3
        ]

        if priority_actions:
            lines.append("\n🎯 PRIORITY ACTIONS:")
            for action in priority_actions[:3]:
                lines.append(f"  1. {action}")

        return "\n".join(lines)


def _score_to_level(score: float) -> str:
    """Convert numeric score to risk level string."""
    if score >= 0.75:   return 'CRITICAL'
    if score >= 0.50:   return 'HIGH'
    if score >= 0.25:   return 'MEDIUM'
    if score >= 0.01:   return 'LOW'
    return 'UNKNOWN'
