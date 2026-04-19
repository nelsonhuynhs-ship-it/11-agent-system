"""
pattern_learner.py — Email Pattern Intelligence
Agent A4 — Pattern Learning / AI Model

Analyzes email_log.csv + outlook_queue.db to surface actionable insights:
  - top_templates()     → best subject lines by reply rate
  - hot_industries()    → hottest campaign categories by engagement
  - send_heatmap()      → 7×24 open rate heatmap (VN timezone)
  - strategy_suggestion() → combined actionable hint per campaign
"""
from __future__ import annotations

import re
import sqlite3
import csv
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger("pattern-learner")

# ── Paths ──────────────────────────────────────────────────────────────────
_BASE = Path(__file__).parent.parent  # email_engine/
LOG_FILE = _BASE / "logs" / "email_log.csv"
QUEUE_DB = _BASE / "data" / "outlook_queue.db"

# Vietnam timezone offset (UTC+7)
_VN_OFFSET = timedelta(hours=7)

# Pattern strip: remove dynamic parts like WEEK 52, WEEK 1 etc.
_WEEK_RE = re.compile(r"\s*//\s*NELSON\s+WEEK\s+\d+", re.IGNORECASE)
_YEAR_RE = re.compile(r"\s*\d{4}$")

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# ── Helpers ────────────────────────────────────────────────────────────────

def _normalize_subject(subject: str) -> str:
    """Strip dynamic week/year suffixes to get a template pattern."""
    s = _WEEK_RE.sub("", subject or "")
    s = _YEAR_RE.sub("", s).strip()
    return s or subject or "(no subject)"


def _parse_ts(ts_str: str) -> Optional[datetime]:
    """Parse multiple timestamp formats, return UTC datetime or None."""
    if not ts_str or ts_str.strip() in ("", "None", "nan"):
        return None
    ts_str = ts_str.strip()
    for fmt in (
        "%d/%m/%Y %H:%M",   # email_log format: 25/12/2025 23:03
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
    ):
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            continue
    return None


def _cutoff(days: int) -> datetime:
    """Return datetime cutoff for filtering (naive, assume same TZ as data)."""
    return datetime.utcnow() - timedelta(days=days)


def _load_email_log(days: int = 30) -> list[dict]:
    """Load email_log.csv filtered to last N days."""
    if not LOG_FILE.exists():
        log.warning(f"email_log.csv not found at {LOG_FILE}")
        return []
    cutoff = _cutoff(days)
    rows = []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = _parse_ts(row.get("timestamp", ""))
                if ts is None or ts < cutoff:
                    continue
                row["_ts"] = ts
                rows.append(row)
    except Exception as e:
        log.error(f"Failed to load email_log: {e}")
    return rows


def _queue_query(sql: str, params: tuple = ()) -> list[dict]:
    """Run a read-only query on outlook_queue.db."""
    if not QUEUE_DB.exists():
        log.warning(f"outlook_queue.db not found at {QUEUE_DB}")
        return []
    try:
        conn = sqlite3.connect(str(QUEUE_DB), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        log.error(f"Queue DB query failed: {e}")
        return []


# ── Core Functions ──────────────────────────────────────────────────────────

def top_templates(days: int = 30, limit: int = 10, min_sent: int = 20) -> list[dict]:
    """
    Top N subject templates ranked by reply_rate%.
    Uses email_log.csv for sent/replied counts.
    Uses outlook_queue.db for opened counts.

    Returns list of dicts: {template_pattern, sent, opened, replied,
                             open_rate_pct, reply_rate_pct, score}
    """
    log_rows = _load_email_log(days)
    if not log_rows:
        log.warning("top_templates: no email_log data")
        return []

    # Aggregate by normalized pattern from email_log
    pattern_stats: dict[str, dict] = {}
    for row in log_rows:
        subject = row.get("subject", "") or ""
        pattern = _normalize_subject(subject)
        status = (row.get("status") or "").upper()
        if pattern not in pattern_stats:
            pattern_stats[pattern] = {"sent": 0, "replied": 0, "subjects": set()}
        if status in ("SENT", "1"):
            pattern_stats[pattern]["sent"] += 1
        elif status.startswith("REPLIED"):
            pattern_stats[pattern]["sent"] += 1
            pattern_stats[pattern]["replied"] += 1
        pattern_stats[pattern]["subjects"].add(subject)

    # Get opened counts from queue DB (last N days)
    cutoff_str = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    queue_rows = _queue_query(
        """
        SELECT subject, COUNT(*) as opened_count
        FROM email_queue
        WHERE opened_at IS NOT NULL
          AND sent_at >= ?
        GROUP BY subject
        """,
        (cutoff_str,),
    )
    # Map normalized pattern → opened count
    opens_by_pattern: dict[str, int] = {}
    for qr in queue_rows:
        pat = _normalize_subject(qr.get("subject", "") or "")
        opens_by_pattern[pat] = opens_by_pattern.get(pat, 0) + qr.get("opened_count", 0)

    # Build result
    results = []
    for pattern, stats in pattern_stats.items():
        sent = stats["sent"]
        if sent < min_sent:
            continue
        replied = stats["replied"]
        opened = opens_by_pattern.get(pattern, 0)
        open_rate = round((opened / sent * 100), 1) if sent > 0 else 0.0
        reply_rate = round((replied / sent * 100), 1) if sent > 0 else 0.0
        # Score: weighted (reply_rate * 3 + open_rate * 1) / 4
        score = round((reply_rate * 3 + open_rate) / 4, 2)
        results.append({
            "template_pattern": pattern,
            "sent": sent,
            "opened": opened,
            "replied": replied,
            "open_rate_pct": open_rate,
            "reply_rate_pct": reply_rate,
            "score": score,
            "sample_subjects": list(stats["subjects"])[:3],
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]


def hot_industries(days: int = 30) -> list[dict]:
    """
    All campaign_id groups ranked by composite engagement score.
    Uses email_log.csv for sent/replied + queue.db for opens.

    Returns list of dicts: {campaign_id, sent, opened, replied,
                             open_rate_pct, reply_rate_pct, score, rank}
    """
    log_rows = _load_email_log(days)
    if not log_rows:
        log.warning("hot_industries: no email_log data")
        return []

    camp_stats: dict[str, dict] = {}
    for row in log_rows:
        campaign = (row.get("campaign_id") or "UNKNOWN").strip().upper()
        status = (row.get("status") or "").upper()
        if campaign not in camp_stats:
            camp_stats[campaign] = {"sent": 0, "replied": 0}
        if status in ("SENT", "1"):
            camp_stats[campaign]["sent"] += 1
        elif status.startswith("REPLIED"):
            camp_stats[campaign]["sent"] += 1
            camp_stats[campaign]["replied"] += 1

    # Opens from queue DB
    cutoff_str = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    queue_rows = _queue_query(
        """
        SELECT campaign_id, COUNT(*) as opened_count
        FROM email_queue
        WHERE opened_at IS NOT NULL
          AND sent_at >= ?
        GROUP BY campaign_id
        """,
        (cutoff_str,),
    )
    opens_by_campaign: dict[str, int] = {}
    for qr in queue_rows:
        cid = (qr.get("campaign_id") or "UNKNOWN").strip().upper()
        opens_by_campaign[cid] = opens_by_campaign.get(cid, 0) + qr.get("opened_count", 0)

    results = []
    for campaign, stats in camp_stats.items():
        sent = stats["sent"]
        replied = stats["replied"]
        opened = opens_by_campaign.get(campaign, 0)
        open_rate = round((opened / sent * 100), 1) if sent > 0 else 0.0
        reply_rate = round((replied / sent * 100), 1) if sent > 0 else 0.0
        # Composite score: reply_rate weighted 2x, open_rate 1x
        score = round((reply_rate * 2 + open_rate) / 3, 2)
        results.append({
            "campaign_id": campaign,
            "sent": sent,
            "opened": opened,
            "replied": replied,
            "open_rate_pct": open_rate,
            "reply_rate_pct": reply_rate,
            "score": score,
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1

    return results


def send_heatmap(days: int = 30) -> dict:
    """
    Build 7×24 matrix of send activity + open rate.
    Based on sent_at field in outlook_queue.db (VN timezone = UTC+7).

    Returns:
    {
        "days": ["Mon"..."Sun"],
        "hours": [0..23],
        "matrix": [
            {
                "day": 0..6,
                "hour": 0..23,
                "sent": N,
                "opened": N,
                "open_rate_pct": float
            }, ...
        ],
        "best_slot": {"day": N, "hour": N, "open_rate_pct": float}
    }
    """
    cutoff_str = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    # Sent counts per (day_of_week, hour)
    sent_rows = _queue_query(
        """
        SELECT sent_at, opened_at
        FROM email_queue
        WHERE sent_at IS NOT NULL
          AND sent_at >= ?
        """,
        (cutoff_str,),
    )

    # Also try email_log for historical sent data (much larger dataset)
    log_rows = _load_email_log(days)

    # Build matrix dict: (dow, hour) -> {sent, opened}
    matrix: dict[tuple, dict] = {}
    for dow in range(7):
        for hr in range(24):
            matrix[(dow, hr)] = {"sent": 0, "opened": 0}

    # Process queue DB entries (have open tracking)
    for row in sent_rows:
        sent_str = row.get("sent_at") or ""
        ts = _parse_ts(sent_str)
        if ts is None:
            continue
        # Convert to VN time
        ts_vn = ts + _VN_OFFSET
        dow = ts_vn.weekday()  # 0=Mon, 6=Sun
        hr = ts_vn.hour
        matrix[(dow, hr)]["sent"] += 1
        if row.get("opened_at"):
            matrix[(dow, hr)]["opened"] += 1

    # Supplement with email_log (no open tracking but larger historical)
    for row in log_rows:
        ts = row.get("_ts")
        if ts is None:
            continue
        status = (row.get("status") or "").upper()
        if status not in ("SENT", "1") and not status.startswith("REPLIED"):
            continue
        ts_vn = ts + _VN_OFFSET
        dow = ts_vn.weekday()
        hr = ts_vn.hour
        matrix[(dow, hr)]["sent"] += 1

    # Build output list
    result_matrix = []
    best_slot = {"day": 1, "hour": 9, "open_rate_pct": 0.0}  # default Tue 9am
    for dow in range(7):
        for hr in range(24):
            cell = matrix[(dow, hr)]
            sent = cell["sent"]
            opened = cell["opened"]
            open_rate = round((opened / sent * 100), 1) if sent > 0 else 0.0
            result_matrix.append({
                "day": dow,
                "hour": hr,
                "sent": sent,
                "opened": opened,
                "open_rate_pct": open_rate,
            })
            if sent >= 5 and open_rate > best_slot["open_rate_pct"]:
                best_slot = {"day": dow, "hour": hr, "open_rate_pct": open_rate}

    return {
        "days": DAY_NAMES,
        "hours": list(range(24)),
        "matrix": result_matrix,
        "best_slot": best_slot,
    }


def strategy_suggestion(campaign_id: str, days: int = 30) -> dict:
    """
    Combine pattern insights into actionable strategy for a specific campaign.

    Returns: {
        best_template_pattern, best_industry_match, best_send_hour_vn,
        predicted_reply_rate, confidence, rationale_vn
    }
    """
    templates = top_templates(days=days, limit=5, min_sent=5)
    industries = hot_industries(days=days)
    heatmap = send_heatmap(days=days)

    # Best template (top by score)
    best_template = templates[0] if templates else None

    # Industry match — find campaign in list
    campaign_upper = (campaign_id or "").strip().upper()
    campaign_data = next(
        (ind for ind in industries if ind["campaign_id"] == campaign_upper), None
    )
    if campaign_data is None and industries:
        campaign_data = industries[0]  # fallback to top

    # Best send hour from heatmap
    best_slot = heatmap.get("best_slot", {"day": 1, "hour": 9, "open_rate_pct": 0.0})
    best_hour_vn = best_slot.get("hour", 9)
    best_day = best_slot.get("day", 1)

    # Predict reply rate
    camp_reply_rate = campaign_data["reply_rate_pct"] if campaign_data else 0.0
    template_reply_rate = best_template["reply_rate_pct"] if best_template else 0.0
    predicted_reply_rate = round((camp_reply_rate + template_reply_rate) / 2, 1)

    # Confidence based on data volume
    total_sent = campaign_data["sent"] if campaign_data else 0
    if total_sent >= 500:
        confidence = 85
    elif total_sent >= 100:
        confidence = 70
    elif total_sent >= 20:
        confidence = 55
    else:
        confidence = 30

    # Build Vietnamese rationale
    day_name_vn = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"][best_day]
    rationale_parts = []

    if best_template:
        rationale_parts.append(
            f"Subject '{best_template['template_pattern'][:40]}' "
            f"có reply rate {best_template['reply_rate_pct']}% "
            f"(trên {best_template['sent']} emails)."
        )

    if campaign_data:
        rank = campaign_data.get("rank", "?")
        rationale_parts.append(
            f"Ngành {campaign_upper} xếp hạng #{rank}, "
            f"reply rate {campaign_data['reply_rate_pct']}%."
        )

    best_rate = best_slot.get("open_rate_pct", 0)
    rationale_parts.append(
        f"Giờ tốt nhất: {day_name_vn} {best_hour_vn}h "
        f"(open rate {best_rate}%)."
    )

    if total_sent < 20:
        rationale_parts.append("Du lieu con it — do tin cay thap, nen test them.")

    return {
        "campaign_id": campaign_upper,
        "best_template_pattern": best_template["template_pattern"] if best_template else "",
        "best_send_hour_vn": best_hour_vn,
        "best_send_day": best_day,
        "best_send_day_name": day_name_vn,
        "predicted_reply_rate": predicted_reply_rate,
        "confidence": confidence,
        "rationale_vn": " ".join(rationale_parts),
        "template_reply_rate": best_template["reply_rate_pct"] if best_template else 0,
        "campaign_reply_rate": camp_reply_rate,
        "industry_rank": campaign_data.get("rank", 0) if campaign_data else 0,
    }
