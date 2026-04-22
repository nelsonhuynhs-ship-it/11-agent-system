"""
rotation_router.py — Daily Rotation Progress API
==================================================
Phase 2 — Progress Tracking API

5 endpoints under prefix /api/rotation:
  GET  /today           — today's plan + live progress
  GET  /progress        — cumulative campaign progress bars
  GET  /history         — past N days summary
  POST /quota           — update daily quota config
  POST /run-today       — manually trigger today's rotation batch
  GET  /cycle           — cycle metadata (week #, global progress)
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, field_validator

log = logging.getLogger("rotation_router")

router = APIRouter(prefix="/api/rotation", tags=["rotation"])

# ── Paths ─────────────────────────────────────────────────────────────────────
_BASE      = Path(__file__).parent.parent.parent   # email_engine/
_PLANS_DIR = _BASE / "data" / "daily_plans"
_PLANS_DIR.mkdir(parents=True, exist_ok=True)

# ── In-process TTL caches ──────────────────────────────────────────────────────
# today — 30s TTL (polled frequently by dashboard)
_today_cache:    dict = {"data": None, "expires_at": 0.0}
_TODAY_TTL       = 30

# progress — 60s TTL (heavy: scans full master df)
_progress_cache: dict = {"data": None, "expires_at": 0.0}
_PROGRESS_TTL    = 60

# cycle — 300s TTL (5 min; rarely changes)
_cycle_cache: dict = {}
_cycle_cache_ts: Optional[datetime] = None
_CACHE_TTL_SECONDS = 300  # reduced from 900 → 5 min; still safe


def _invalidate_caches() -> None:
    """Reset all response caches after a rotation run completes."""
    _today_cache["expires_at"]    = 0.0
    _progress_cache["expires_at"] = 0.0
    _cycle_cache_ts_reset()


def _cycle_cache_ts_reset() -> None:
    global _cycle_cache_ts
    _cycle_cache_ts = None


def _get_cycle_info_cached() -> dict:
    global _cycle_cache, _cycle_cache_ts
    now = datetime.now()
    if _cycle_cache_ts and (now - _cycle_cache_ts).seconds < _CACHE_TTL_SECONDS:
        return _cycle_cache
    try:
        from email_engine.core.rotation_helpers import (
            load_master_df, load_quota_config, _compute_cycle_info
        )
        cfg = load_quota_config()
        df = load_master_df()
        _cycle_cache = _compute_cycle_info(df, cfg["daily_total"])
        _cycle_cache_ts = now
    except Exception as exc:
        log.warning("_get_cycle_info_cached: %s", exc)
        _cycle_cache = {}
    return _cycle_cache


def _load_plan(target_date: date) -> Optional[dict]:
    """Load archived plan JSON for a given date. Returns None if not found."""
    plan_file = _PLANS_DIR / f"{target_date.isoformat()}.json"
    if not plan_file.exists():
        return None
    try:
        return json.loads(plan_file.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("_load_plan %s: %s", target_date, exc)
        return None


def _load_master_df_safe() -> Optional[pd.DataFrame]:
    try:
        from email_engine.core.rotation_helpers import load_master_df
        return load_master_df()
    except Exception as exc:
        log.error("_load_master_df_safe: %s", exc)
        return None


# ── Models ────────────────────────────────────────────────────────────────────

class QuotaUpdateBody(BaseModel):
    daily_total: int
    by_commodity: dict[str, int]

    @field_validator("by_commodity")
    @classmethod
    def validate_sum(cls, v: dict, info) -> dict:
        total = info.data.get("daily_total", 0)
        if sum(v.values()) != total:
            raise ValueError(
                f"Sum of by_commodity ({sum(v.values())}) must equal daily_total ({total})"
            )
        return v


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/today")
def get_today_plan() -> dict[str, Any]:
    """Return today's plan + live progress (sent so far vs target). TTL-cached 30s."""
    now_ts = time.time()
    if _today_cache["data"] is not None and _today_cache["expires_at"] > now_ts:
        return _today_cache["data"]

    today = date.today()
    plan = _load_plan(today)

    if plan is None:
        result = {
            "date": today.isoformat(),
            "status": "not_built",
            "message": "No plan for today. POST /api/rotation/run-today to generate.",
            "target": 0,
            "sent_so_far": 0,
            "pending": 0,
            "by_commodity": [],
        }
        _today_cache["data"] = result
        _today_cache["expires_at"] = now_ts + _TODAY_TTL
        return result

    if plan.get("skipped_reason"):
        result = {
            "date": today.isoformat(),
            "status": "skipped",
            "skipped_reason": plan["skipped_reason"],
            "target": 0,
            "sent_so_far": 0,
            "pending": 0,
            "by_commodity": [],
        }
        _today_cache["data"] = result
        _today_cache["expires_at"] = now_ts + _TODAY_TTL
        return result

    # Compute live sent_so_far by reading master data
    sent_today = _count_sent_today(today)
    target = plan.get("actual_total", 0)
    pending = max(0, target - sent_today)

    # ETA
    eta_str = None
    if sent_today > 0 and sent_today < target:
        # Naive: assume linear rate since midnight
        now = datetime.now()
        seconds_since_midnight = (now - now.replace(hour=0, minute=0, second=0)).seconds
        if seconds_since_midnight > 0:
            rate_per_sec = sent_today / seconds_since_midnight
            secs_remaining = pending / rate_per_sec if rate_per_sec > 0 else 0
            eta = now + timedelta(seconds=secs_remaining)
            eta_str = eta.strftime("%Y-%m-%d %H:%M")

    status = "complete" if pending == 0 and target > 0 else ("in_progress" if sent_today > 0 else "queued")

    by_commodity_list = []
    for name, info in plan.get("by_commodity", {}).items():
        tgt = info.get("picked", 0)
        by_commodity_list.append({
            "name": name,
            "target": tgt,
            "sent": min(sent_today, tgt),   # approximate
            "pct": round(min(sent_today, tgt) / tgt * 100, 1) if tgt else 0,
        })

    result = {
        "date": today.isoformat(),
        "status": status,
        "target": target,
        "sent_so_far": sent_today,
        "pending": pending,
        "eta_complete": eta_str,
        "by_commodity": by_commodity_list,
        "cycle_info": plan.get("cycle_info", {}),
    }
    _today_cache["data"] = result
    _today_cache["expires_at"] = now_ts + _TODAY_TTL
    return result


@router.get("/progress")
def get_progress() -> dict[str, Any]:
    """Cumulative campaign progress — anchor metric for UI progress bars. TTL-cached 60s."""
    now_ts = time.time()
    if _progress_cache["data"] is not None and _progress_cache["expires_at"] > now_ts:
        return _progress_cache["data"]

    df = _load_master_df_safe()
    if df is None:
        raise HTTPException(status_code=503, detail="Master contact file unavailable")

    try:
        from email_engine.core.rotation_helpers import load_quota_config
        cfg = load_quota_config()
    except Exception:
        cfg = {"by_commodity": {}, "daily_total": 700}

    cycle_info = _get_cycle_info_cached()

    commodity_stats: list[dict] = []
    if "COMMODITY_CATEGORY" in df.columns:
        for commodity, quota in cfg.get("by_commodity", {}).items():
            cdf = df[df["COMMODITY_CATEGORY"].astype(str).str.upper().str.strip() == commodity.upper()]
            total = len(cdf)
            if "SEND_COUNT" in cdf.columns:
                sc = pd.to_numeric(cdf["SEND_COUNT"], errors="coerce").fillna(0)
                sent_cycle = int((sc >= 1).sum())
            else:
                sent_cycle = 0
            remaining = max(0, total - sent_cycle)
            pct = round(sent_cycle / total * 100, 1) if total > 0 else 0.0
            days_to_finish = round(remaining / quota) if quota > 0 else 0
            commodity_stats.append({
                "name": commodity,
                "total": total,
                "sent_cycle": sent_cycle,
                "remaining": remaining,
                "pct_done": pct,
                "days_to_finish": days_to_finish,
            })

    # Grand total
    total_all = len(df)
    sent_all = 0
    if "SEND_COUNT" in df.columns:
        sc_all = pd.to_numeric(df["SEND_COUNT"], errors="coerce").fillna(0)
        sent_all = int((sc_all >= 1).sum())

    result = {
        "cycle_number": cycle_info.get("cycle_number", 1),
        "week_in_cycle": cycle_info.get("week_in_cycle", 1),
        "weeks_to_finish_cycle": cycle_info.get("weeks_total_estimate", 0.0),
        "by_commodity": commodity_stats,
        "grand_total": {
            "all": total_all,
            "sent": sent_all,
            "remaining": max(0, total_all - sent_all),
        },
    }
    _progress_cache["data"] = result
    _progress_cache["expires_at"] = now_ts + _PROGRESS_TTL
    return result


@router.get("/history")
def get_history(days: int = Query(default=7, ge=1, le=90)) -> dict[str, Any]:
    """Past N days summary from archived plan files."""
    today = date.today()
    result = []
    total_sent = 0

    for i in range(days):
        d = today - timedelta(days=i)
        plan = _load_plan(d)
        if plan is None or plan.get("skipped_reason"):
            continue
        sent = plan.get("actual_total", 0)
        total_sent += sent
        by_comm = {k: v.get("picked", 0) for k, v in plan.get("by_commodity", {}).items()}
        result.append({"date": d.isoformat(), "sent": sent, "by_commodity": by_comm})

    active_days = len(result)
    return {
        "days": result,
        f"total_{days}d": total_sent,
        "avg_per_day": round(total_sent / active_days, 1) if active_days else 0,
    }


@router.post("/quota")
def update_quota(body: QuotaUpdateBody) -> dict[str, Any]:
    """Update rotation quota config. Validates sum == daily_total."""
    try:
        from email_engine.core.rotation_helpers import QUOTA_FILE
        current = json.loads(QUOTA_FILE.read_text(encoding="utf-8")) if QUOTA_FILE.exists() else {}
        current["daily_total"] = body.daily_total
        current["by_commodity"] = body.by_commodity
        QUOTA_FILE.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("ROTATION: Quota updated — total=%d", body.daily_total)
        return {"status": "ok", "daily_total": body.daily_total, "by_commodity": body.by_commodity}
    except Exception as exc:
        log.error("update_quota: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


class RunTodayRequest(BaseModel):
    user_markup: Optional[int] = 20
    campaign_override: Optional[str] = None


@router.post("/run-today")
def run_today(
    background_tasks: BackgroundTasks,
    req: Optional[RunTodayRequest] = None,
) -> dict[str, Any]:
    """Manually trigger today's rotation batch (queues in background).

    Accepts optional JSON body::

        { "user_markup": 30, "campaign_override": "FLOORING" }

    Both fields are optional — defaults: markup=20, no campaign override.
    """
    today = date.today()
    markup = (req.user_markup if req and req.user_markup is not None else 20)
    campaign = (req.campaign_override if req else None)
    background_tasks.add_task(_run_rotation_background, today, markup, campaign)
    return {
        "status": "queued",
        "date": today.isoformat(),
        "user_markup": markup,
        "message": "Rotation triggered in background. Check /api/rotation/today in ~10s.",
    }


@router.get("/cycle")
def get_cycle() -> dict[str, Any]:
    """Cycle metadata for UI global progress indicator."""
    return _get_cycle_info_cached()


@router.get("/preview-sample")
def preview_sample(
    count: int = Query(default=3, ge=1, le=10),
    markup: int = Query(default=20, ge=0, le=500),
) -> dict[str, Any]:
    """Return N sample emails as they would render — for UI preview modal.

    Picks the first contact from each of the top `count` commodities in
    today's plan and resolves their rate table + subject via rule_engine.
    Falls back to a fresh build_daily_plan() if no archived plan exists.
    """
    try:
        from email_engine.core.rule_engine import resolve_config
        from email_engine.core.auto_rate_builder import build_rate_table_for_customer
        from email_engine.core.rotation_engine import build_daily_plan
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f"Engine unavailable: {exc}")

    # Load or build plan
    plan = _load_plan(date.today())
    if plan is None or plan.get("skipped_reason"):
        try:
            plan = build_daily_plan()
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Plan build failed: {exc}")

    # Load master contact data
    df = _load_master_df_safe()
    if df is None:
        raise HTTPException(status_code=503, detail="Master contact file unavailable")

    email_col = "EMAIL" if "EMAIL" in df.columns else "CNEE_EMAIL"
    df_indexed = df.set_index(df[email_col].str.lower().str.strip())

    samples: list[dict[str, Any]] = []
    commodities = list(plan.get("by_commodity", {}).items())[:count]

    for commodity, info in commodities:
        emails = info.get("emails", [])
        if not emails:
            continue

        sample_email = emails[0].strip()
        key = sample_email.lower()
        row_raw = df_indexed.loc[key] if key in df_indexed.index else {}

        if isinstance(row_raw, pd.DataFrame):
            row_raw = row_raw.iloc[0]

        row_dict = row_raw.to_dict() if hasattr(row_raw, "to_dict") else {}

        try:
            config = resolve_config(row_dict, user_markup=markup, campaign_override=commodity)
        except Exception as exc:
            log.warning("preview_sample: resolve_config error for %s: %s", sample_email, exc)
            continue

        rate_html = ""
        try:
            result = build_rate_table_for_customer(
                pol=config["pol"],
                destinations=config["destination"],
                markup=config["markup"],
                arb_origin=config["arb_origin"],
            )
            rate_html = result.get("html", "")
        except Exception as exc:
            log.warning("preview_sample: rate build failed for %s: %s", sample_email, exc)

        samples.append({
            "commodity":  commodity,
            "email":      config["email"] or sample_email,
            "company":    config["company"],
            "pic":        config["pic"],
            "country":    config["country"],
            "pol":        config["pol"],
            "arb_origin": config["arb_origin"],
            "subject":    config["subject"],
            "rate_html":  rate_html,
        })

    return {"samples": samples, "markup": markup, "count": len(samples)}


# ── Background task ───────────────────────────────────────────────────────────

def _run_rotation_background(
    target_date: date,
    user_markup: int = 20,
    campaign_override: Optional[str] = None,
) -> None:
    try:
        from email_engine.core.rotation_engine import build_daily_plan, queue_to_outlook_worker
        plan = build_daily_plan(target_date=target_date)
        queued = queue_to_outlook_worker(
            plan,
            user_markup=user_markup,
            campaign_override=campaign_override,
        )
        log.info(
            "ROTATION_BG: date=%s queued=%d markup=%d campaign=%s",
            target_date, queued, user_markup, campaign_override or "all",
        )
    except Exception as exc:
        log.error("_run_rotation_background: %s", exc)
    finally:
        # Invalidate response caches so next poll sees fresh data
        _invalidate_caches()


def _count_sent_today(today: date) -> int:
    """Approximate: count rows in master where LAST_SENT_DATE == today."""
    try:
        df = _load_master_df_safe()
        if df is None or "LAST_SENT_DATE" not in df.columns:
            return 0
        lsd = pd.to_datetime(df["LAST_SENT_DATE"], errors="coerce")
        today_ts = pd.Timestamp(today)
        return int((lsd == today_ts).sum())
    except Exception:
        return 0
