"""
rotation_engine.py — Daily Rotation Engine
============================================
Phase 1 — Daily Rotation Engine Core

Builds a daily send plan of 700 emails distributed across commodity quotas.
Enforces cooldown (7d), hard-limit (3 sends/30d), and excluded-email list.
Auto-redistributes quota when a commodity has fewer candidates than its quota.

Main API:
    build_daily_plan(target_date, quota_override, cooldown_days, hard_limit)
    queue_to_outlook_worker(plan)
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from email_engine.core.rotation_helpers import (
    PLANS_DIR,
    _compute_cycle_info,
    _get_eligible_candidates,
    load_excluded_emails,
    load_master_df,
    load_quota_config,
)
from email_engine.core.vn_holidays import is_vn_holiday

log = logging.getLogger("rotation_engine")


def build_daily_plan(
    target_date: Optional[date] = None,
    quota_override: Optional[dict[str, int]] = None,
    cooldown_days: Optional[int] = None,
    hard_limit: Optional[int] = None,
) -> dict[str, Any]:
    """Build today's rotation plan.

    Returns a dict with keys: date, target_total, actual_total, by_commodity,
    redistributed, cycle_info, skipped_reason (if weekend/holiday).

    Raises FileNotFoundError if master contact file is missing.
    """
    today = target_date or date.today()

    # Weekend / holiday skip
    if today.weekday() >= 5:
        day_name = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][today.weekday()]
        log.info("ROTATION_SKIP_WEEKEND: %s is %s", today, day_name)
        return _empty_plan(today, reason=f"Weekend ({day_name})")

    if is_vn_holiday(today):
        from email_engine.core.vn_holidays import holiday_name
        name = holiday_name(today) or "VN Holiday"
        log.info("ROTATION_SKIP_HOLIDAY: %s — %s", today, name)
        return _empty_plan(today, reason=name)

    # Load config
    cfg = load_quota_config()
    if quota_override:
        cfg["by_commodity"].update(quota_override)
    if cooldown_days is not None:
        cfg["cooldown_days"] = cooldown_days
    if hard_limit is not None:
        cfg["hard_limit_count"] = hard_limit

    daily_total: int     = cfg["daily_total"]
    quota_map: dict      = cfg["by_commodity"]       # commodity → target count
    cd_days: int         = cfg["cooldown_days"]
    hl_count: int        = cfg["hard_limit_count"]
    hl_window: int       = cfg["hard_limit_window_days"]

    # Load master data
    df = load_master_df()
    excluded = load_excluded_emails()

    # Mark "OTHERS" rows (commodities not in main quota map)
    defined_commodities = {c.upper() for c in quota_map if c != "OTHERS"}
    if "COMMODITY_CATEGORY" in df.columns:
        df["_is_others"] = ~df["COMMODITY_CATEGORY"].astype(str).str.upper().str.strip().isin(
            defined_commodities
        )
    else:
        df["_is_others"] = False

    # First pass: collect candidates per commodity and their deficits
    candidates: dict[str, pd.DataFrame] = {}
    deficits: dict[str, int] = {}   # commodity → how many short of quota

    for commodity, quota in quota_map.items():
        cdf = _get_eligible_candidates(
            df, commodity, excluded, cd_days, hl_count, hl_window, today
        )
        candidates[commodity] = cdf
        deficit = max(0, quota - len(cdf))
        if deficit:
            deficits[commodity] = deficit

    # Second pass: redistribute deficit to commodities with surplus
    redistributed: dict[str, int] = {}
    if deficits:
        total_deficit = sum(deficits.values())
        surplus_commodities = [
            c for c, cdf in candidates.items()
            if len(cdf) > quota_map[c]
        ]
        # Distribute deficit proportionally across surplus commodities
        surplus_totals = {c: len(candidates[c]) - quota_map[c] for c in surplus_commodities}
        total_surplus = sum(surplus_totals.values())

        if total_surplus > 0:
            for c in surplus_commodities:
                extra = min(
                    surplus_totals[c],
                    round(total_deficit * surplus_totals[c] / total_surplus)
                )
                quota_map[c] = quota_map[c] + extra
                redistributed[c] = extra
        # Zero-out under-filled commodities (take what we have)
        for c, deficit in deficits.items():
            redistributed[c] = -deficit   # negative = shortfall

    # Final pick
    by_commodity: dict[str, Any] = {}
    all_picked_emails: list[str] = []
    picked_emails_set: set[str] = set()  # dedup across commodities

    for commodity, quota in quota_map.items():
        cdf = candidates[commodity]
        email_col = "EMAIL" if "EMAIL" in cdf.columns else "CNEE_EMAIL"

        # Exclude already picked from other commodities
        if not cdf.empty and email_col in cdf.columns:
            cdf = cdf[~cdf[email_col].astype(str).str.lower().str.strip().isin(picked_emails_set)]

        pick = cdf.head(quota) if not cdf.empty else pd.DataFrame()

        emails: list[str] = []
        if not pick.empty and email_col in pick.columns:
            emails = pick[email_col].astype(str).str.strip().tolist()
            picked_emails_set.update(e.lower() for e in emails)
            all_picked_emails.extend(emails)

        remaining_count = max(0, len(cdf) - len(emails))
        by_commodity[commodity] = {
            "quota": quota_map[commodity],
            "picked": len(emails),
            "candidates_remaining": remaining_count,
            "emails": emails,
        }

    actual_total = len(all_picked_emails)

    plan: dict[str, Any] = {
        "date": today.isoformat(),
        "target_total": daily_total,
        "actual_total": actual_total,
        "by_commodity": by_commodity,
        "redistributed": redistributed,
        "cycle_info": _compute_cycle_info(df, daily_total),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "skipped_reason": None,
    }

    # Archive to daily_plans/
    _save_plan(plan, today)

    log.info(
        "ROTATION: Built plan for %s · target=%d actual=%d redistributed=%s",
        today, daily_total, actual_total,
        {k: v for k, v in redistributed.items() if v}
    )
    return plan


_DEFAULT_DESTS = "USLAX,USLGB,USNYC"


def queue_to_outlook_worker(
    plan: dict[str, Any],
    user_markup: int = 20,
    campaign_override: str | None = None,
) -> int:
    """Build email content per contact and INSERT into email_queue via enqueue_batch.

    Uses rule_engine.resolve_config to derive POL/ARB/markup per contact, then
    routes through intelligence.builder.build_email() — the central pipeline that
    includes branded signature, state-colored rate table, skip-no-rates guard, and
    subject from template selector.

    Args:
        plan:              Daily plan dict from build_daily_plan().
        user_markup:       USD markup Nelson entered for this batch (default 20).
        campaign_override: Force commodity label for all contacts (optional).

    Returns number of rows actually inserted.
    """
    if plan.get("skipped_reason"):
        log.info("queue_to_outlook_worker: plan skipped (%s) — nothing queued", plan["skipped_reason"])
        return 0

    from email_engine.core.rule_engine import resolve_config
    from email_engine.intelligence.builder import build_email
    from email_engine.queue_store import enqueue_batch, init_db
    init_db()  # idempotent — ensures schema exists

    df = load_master_df()
    email_col = "EMAIL" if "EMAIL" in df.columns else "CNEE_EMAIL"
    df_lookup = df.set_index(df[email_col].str.lower().str.strip())

    # ── Pass 1: resolve per-email config via rule_engine ─────────────────────
    email_meta: list[dict[str, Any]] = []

    for commodity, info in plan.get("by_commodity", {}).items():
        for email in info.get("emails", []):
            try:
                key = email.strip().lower()
                row = df_lookup.loc[key] if key in df_lookup.index else None
                if row is None:
                    log.debug("queue_to_outlook_worker: email not in master — %s", email)
                    continue

                # pandas returns DataFrame if multiple rows match; use first
                if isinstance(row, pd.DataFrame):
                    row = row.iloc[0]

                config = resolve_config(
                    row.to_dict() if hasattr(row, "to_dict") else dict(row),
                    user_markup=user_markup,
                    campaign_override=campaign_override or commodity,
                )

                email_meta.append({
                    "email":        config["email"] or email.strip(),
                    "pol":          config["pol"],
                    "destinations": config["destination"],
                    "arb_origin":   config["arb_origin"],
                    "markup":       config["markup"],
                    "company":      config["company"],
                    "pic":          config["pic"],
                    "tier":         config["tier"],
                    "commodity":    config["commodity"],
                    "country":      config["country"],
                })
            except Exception as exc:
                log.warning("queue_to_outlook_worker: metadata error for %s: %s", email, exc)

    if not email_meta:
        log.warning("queue_to_outlook_worker: no valid emails found in plan")
        return 0

    # ── Pass 2: build each email via central builder (has all safety + branding) ──
    batch_id  = f"ROT_{int(time.time())}"
    plan_date = plan.get("date", date.today().isoformat())

    batch_emails: list[dict[str, Any]] = []
    for meta in email_meta:
        try:
            destinations_list = [
                d.strip().upper()
                for d in meta["destinations"].split(",")
                if d.strip()
            ]
            result = build_email(
                cnee_email=meta["email"],
                pol=meta["pol"],
                destinations=destinations_list,
                markup=float(meta["markup"]),
                profile={"first_name": meta["pic"], "company": meta["company"]},
            )
            html_body = result.get("html_body", "")
            if not html_body or "No rates available" in html_body:
                log.info("queue_to_outlook_worker: skip %s — no rates", meta["email"])
                continue

            batch_emails.append({
                "cnee_email":     meta["email"],
                "subject":        result.get("subject", ""),
                "html_body":      html_body,
                "tier":           meta["tier"],
                "priority_score": 50,
                "campaign_id":    meta["commodity"],
                "meta_json": {
                    "source":     "daily_rotation",
                    "commodity":  meta["commodity"],
                    "plan_date":  plan_date,
                    "pol":        meta["pol"],
                    "arb_origin": meta["arb_origin"],
                    "country":    meta["country"],
                },
            })
        except Exception as exc:
            log.warning("queue_to_outlook_worker: build error for %s: %s", meta.get("email"), exc)

    if not batch_emails:
        log.warning("queue_to_outlook_worker: batch_emails empty after build")
        return 0

    queued = enqueue_batch(batch_id, batch_emails)
    log.info(
        "ROTATION: Enqueued %d/%d emails · batch_id=%s",
        queued, len(batch_emails), batch_id,
    )

    _notify_telegram(plan, queued)
    return queued


def _notify_telegram(plan: dict[str, Any], queued: int) -> None:
    """Send Telegram notification after batch queued. Fails silently."""
    try:
        from email_engine.core.notify import send_telegram  # type: ignore
        msg = (
            f"Daily rotation ready: {queued} emails queued "
            f"({plan.get('date', 'today')}) · "
            f"cycle {plan.get('cycle_info', {}).get('cycle_number', '?')}"
        )
        send_telegram(msg)
    except Exception as exc:
        log.debug("Telegram notify skipped: %s", exc)


def _empty_plan(today: date, reason: str) -> dict[str, Any]:
    return {
        "date": today.isoformat(),
        "target_total": 0,
        "actual_total": 0,
        "by_commodity": {},
        "redistributed": {},
        "cycle_info": {},
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "skipped_reason": reason,
    }


def _save_plan(plan: dict[str, Any], today: date) -> None:
    """Archive plan JSON to daily_plans/YYYY-MM-DD.json."""
    try:
        out = PLANS_DIR / f"{today.isoformat()}.json"
        out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        log.debug("ROTATION: Plan archived to %s", out)
    except Exception as exc:
        log.warning("_save_plan: could not archive plan: %s", exc)
