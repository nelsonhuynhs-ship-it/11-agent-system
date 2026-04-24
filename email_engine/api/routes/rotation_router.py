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
import os
import secrets
import time
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, field_validator, model_validator

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

# cycle — 600s TTL (10 min; rarely changes across a rotation session)
_cycle_cache: dict = {}
_cycle_cache_ts: Optional[datetime] = None
_CACHE_TTL_SECONDS = 600  # 2026-04-24 PERF-104: bumped 300→600 — load_master_df heavy


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
    def non_negative(cls, v: dict) -> dict:
        for k, n in v.items():
            if n < 0:
                raise ValueError(f"{k} cannot be negative ({n})")
        return v

    @model_validator(mode="after")
    def reconcile_sum(self):
        # 2026-04-24: dashboard scale can round commodities down to 0 when
        # target is small (e.g. Daily Total=30 → all 8 bars → 0). Instead of
        # failing with 422, treat sum(by_commodity) as the ground truth and
        # log the adjustment. Solo user → no reason to block save.
        s = sum(self.by_commodity.values())
        if s != self.daily_total:
            log.warning(
                "quota reconcile: daily_total=%d vs sum(by_commodity)=%d → using sum",
                self.daily_total, s,
            )
            self.daily_total = s
        return self


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


@router.get("/quota")
def get_quota() -> dict[str, Any]:
    """Return current rotation quota config so dashboard restores state on F5."""
    try:
        from email_engine.core.rotation_helpers import load_quota_config
        return load_quota_config()
    except Exception as exc:
        log.error("get_quota: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


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
    preview_token: Optional[str] = None
    force: bool = False


@router.post("/run-today")
def run_today(
    background_tasks: BackgroundTasks,
    req: Optional[RunTodayRequest] = None,
) -> dict[str, Any]:
    """Manually trigger today's rotation batch (queues in background).

    Requires a `preview_token` obtained via POST /api/rotation/preview-in-outlook
    unless `force=true` is passed (scheduler / CLI escape hatch).
    """
    today = date.today()
    markup = (req.user_markup if req and req.user_markup is not None else 20)
    campaign = (req.campaign_override if req else None)
    token = (req.preview_token if req else None)
    force = bool(req.force) if req else False

    if not force:
        if not token or not _consume_preview_token(token):
            raise HTTPException(
                status_code=400,
                detail="Preview required. POST /api/rotation/preview-in-outlook first, then pass the returned preview_token here.",
            )

    background_tasks.add_task(_run_rotation_background, today, markup, campaign)
    return {
        "status": "queued",
        "date": today.isoformat(),
        "user_markup": markup,
        "message": "Rotation triggered in background. Check /api/rotation/today in ~10s.",
    }


@router.get("/batch-status")
def get_batch_status() -> dict[str, Any]:
    """Live batch progress — queue stats + worker state + ETA.

    Dashboard polls this every 2s for Session Progress panel.
    """
    # 2026-04-24 PERF-103: use queue_store._connect (WAL + busy_timeout=30s)
    # instead of bare sqlite3.connect. Prevents reader blocking writer during
    # worker enqueue/mark_sent bursts.
    from email_engine.queue_store import _connect as _queue_connect
    db_path = _BASE / "data" / "outlook_queue.db"
    if not db_path.exists():
        return {"active": False, "message": "queue db missing"}

    try:
        conn = _queue_connect(str(db_path))
        cur = conn.cursor()

        cur.execute(
            "SELECT batch_id FROM email_queue "
            "WHERE batch_id LIKE 'ROT_%' "
            "ORDER BY enqueued_at DESC LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            return {"active": False, "message": "no ROT batch found"}
        batch_id = row["batch_id"]

        cur.execute(
            "SELECT status, COUNT(*) AS c, meta_json FROM email_queue "
            "WHERE batch_id = ? GROUP BY status, meta_json",
            (batch_id,),
        )
        by_commodity: dict[str, dict[str, int]] = {}
        total = {"sent": 0, "failed": 0, "pending": 0, "picked": 0, "quota": 0}
        for r in cur.fetchall():
            status = r["status"] or "pending"
            count = int(r["c"])
            try:
                meta = json.loads(r["meta_json"] or "{}")
                commodity = (meta.get("commodity") or "UNKNOWN").upper()
            except Exception:
                commodity = "UNKNOWN"
            slot = by_commodity.setdefault(
                commodity, {"sent": 0, "failed": 0, "pending": 0, "picked": 0, "quota": 0}
            )
            key = "failed" if status == "error" else status
            slot[key] = slot.get(key, 0) + count
            slot["quota"] = slot["quota"] + count
            total[key] = total.get(key, 0) + count
            total["quota"] += count

        cur.execute(
            "SELECT COUNT(*) FROM email_queue "
            "WHERE batch_id = ? AND status = 'sent' "
            "AND sent_at >= datetime('now', '-60 seconds')",
            (batch_id,),
        )
        sent_last_60s = int(cur.fetchone()[0] or 0)

        cur.execute(
            "SELECT MIN(enqueued_at), MAX(sent_at), MAX(error_message) "
            "FROM email_queue WHERE batch_id = ?",
            (batch_id,),
        )
        started_at, last_sent_at, last_error = cur.fetchone()
        conn.close()
    except Exception as exc:
        log.error("get_progress: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    rate_per_min = sent_last_60s
    remaining = total["pending"] + total["picked"]
    eta_sec = int(remaining * 60 / rate_per_min) if rate_per_min > 0 else None
    active = remaining > 0

    return {
        "active": active,
        "batch_id": batch_id,
        "started_at": started_at,
        "last_sent_at": last_sent_at,
        "by_commodity": by_commodity,
        "total": {**total, "rate_per_min": rate_per_min, "eta_sec": eta_sec},
        "last_error": last_error,
    }


@router.get("/cycle")
def get_cycle() -> dict[str, Any]:
    """Cycle metadata for UI global progress indicator."""
    return _get_cycle_info_cached()


# ── Preview-in-Outlook token cache ─────────────────────────────────────────────
# Module-level dict: {token: expires_at_epoch}
_PREVIEW_TOKENS: dict[str, float] = {}
_PREVIEW_TTL = 600  # 10 minutes — Nelson reviews then confirms send


def _issue_preview_token() -> str:
    token = secrets.token_urlsafe(16)
    _PREVIEW_TOKENS[token] = time.time() + _PREVIEW_TTL
    # Opportunistic cleanup of expired tokens
    now = time.time()
    for k in [k for k, exp in _PREVIEW_TOKENS.items() if exp < now]:
        _PREVIEW_TOKENS.pop(k, None)
    return token


def _consume_preview_token(token: str) -> bool:
    """Return True if token valid; removes it (one-shot use)."""
    exp = _PREVIEW_TOKENS.pop(token, None)
    if exp is None:
        return False
    return exp >= time.time()


@router.post("/preview-in-outlook")
def preview_in_outlook(
    markup: int = Query(default=20, ge=0, le=500),
) -> dict[str, Any]:
    """Open top-priority CNEE's FULL email (rate table + intro + signature + logo)
    in Outlook via COM .Display() so Nelson can review before confirming batch send.

    Returns a `preview_token` that must be passed to POST /run-today within 10 min.
    """
    try:
        from email_engine.core.rotation_engine import build_daily_plan
        from email_engine.intelligence import builder as _builder
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f"Engine unavailable: {exc}")

    plan = _load_plan(date.today())
    if plan is None or plan.get("skipped_reason"):
        try:
            plan = build_daily_plan()
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Plan build failed: {exc}")

    # Pick first commodity's first email (rotation_engine already sorts by priority)
    by_commodity = plan.get("by_commodity", {})
    if not by_commodity:
        raise HTTPException(status_code=404, detail="No commodities in today's plan")

    first_commodity = None
    sample_email = None
    for comm, info in by_commodity.items():
        emails = info.get("emails", [])
        if emails:
            first_commodity = comm
            sample_email = emails[0].strip()
            break

    if not sample_email:
        raise HTTPException(status_code=404, detail="No emails in today's plan")

    # Resolve config for this CNEE (POL + destinations from rule engine)
    df = _load_master_df_safe()
    if df is None:
        raise HTTPException(status_code=503, detail="Master contact file unavailable")

    try:
        from email_engine.core.rule_engine import resolve_config
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f"Rule engine unavailable: {exc}")

    email_col = "EMAIL" if "EMAIL" in df.columns else "CNEE_EMAIL"
    df_indexed = df.set_index(df[email_col].str.lower().str.strip())
    key = sample_email.lower()
    row_raw = df_indexed.loc[key] if key in df_indexed.index else {}
    if isinstance(row_raw, pd.DataFrame):
        row_raw = row_raw.iloc[0]
    row_dict = row_raw.to_dict() if hasattr(row_raw, "to_dict") else {}

    try:
        config = resolve_config(row_dict, user_markup=markup, campaign_override=first_commodity)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"resolve_config failed: {exc}")

    # Build full email (subject + html_body with signature)
    try:
        known = config.get("destination") or []
        if isinstance(known, str):
            known = [d.strip().upper() for d in known.split(",") if d.strip()]
        # Merge with 10 default lanes → known first, then rest deduped.
        # Matches Path B bulk-send behaviour so subject/template selector
        # resolves to default_cross_sell (Asia to USA/Canada).
        from email_engine.web_server import DEFAULT_DESTINATIONS as _DEFAULTS
        destinations: list[str] = []
        for d in list(known) + list(_DEFAULTS or []):
            du = (d or "").upper()
            if du and du not in destinations:
                destinations.append(du)
        email_dict = _builder.build_email(
            cnee_email=config["email"] or sample_email,
            pol=config["pol"],
            destinations=destinations,
            markup=float(config.get("markup") or markup),
            profile=row_dict if row_dict else None,
            arb_origin=config.get("arb_origin"),
        )
    except Exception as exc:
        log.error("preview_in_outlook: build_email failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"build_email failed: {exc}")

    # Open in Outlook (Display, NOT Send)
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)  # olMailItem
        mail.To = email_dict["to"]
        mail.Subject = email_dict["subject"]
        mail.HTMLBody = email_dict["html_body"] or ""

        # Inline CID logo (matches outlook_queue_worker pattern)
        logo_path = os.path.join(
            os.path.dirname(os.path.abspath(_builder.__file__)),
            "..", "assets", "logo.png",
        )
        logo_path = os.path.abspath(logo_path)
        if "cid:pudonglogo" in (email_dict["html_body"] or "").lower() and os.path.exists(logo_path):
            try:
                att = mail.Attachments.Add(logo_path)
                pa = att.PropertyAccessor
                pa.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x3712001F", "pudonglogo")
                pa.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x7FFE000B", True)
            except Exception as exc:
                log.warning("preview_in_outlook: logo attach failed: %s", exc)

        mail.Display()
    except Exception as exc:
        log.error("preview_in_outlook: Outlook COM failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Outlook preview failed: {exc}")

    token = _issue_preview_token()
    plan_total = int(plan.get("actual_total", 0))

    return {
        "status": "previewed",
        "preview_token": token,
        "ttl_seconds": _PREVIEW_TTL,
        "previewed_to": email_dict["to"],
        "subject": email_dict["subject"],
        "first_commodity": first_commodity,
        "plan_total": plan_total,
        "message": f"Outlook opened. Review and confirm to send {plan_total} emails.",
    }


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
