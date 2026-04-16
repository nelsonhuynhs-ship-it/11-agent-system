# -*- coding: utf-8 -*-
"""
template_selector.py — YAML-driven email template matcher with hot-reload.

Loads `email_rules.yaml` once and re-loads on mtime change (hot-reload — no restart).

Public API
----------
load_rules(yaml_path=None) -> dict
    Returns full rules dict {version, defaults, templates}.
match(destinations: list, states: list) -> dict
    Returns the best-matching template dict {id, subject, intro, cta, match_reason}.
dominant_state(lane_intels: list[dict]) -> str
    Priority: URGENT > DECLINING > COMPETITIVE > STABLE.

Template match priority (most-specific first):
    1. Exact destination + exact state
    2. Exact destination + "any" state
    3. "any" destination + exact state
    4. "any" destination + "any" state (→ default)
"""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any

log = logging.getLogger("template_selector")

# ── Default YAML path ─────────────────────────────────────────────────────────
_DEFAULT_YAML = Path(__file__).resolve().parent.parent / "templates" / "email_rules.yaml"

# ── Cache (path → (mtime, rules_dict)) ───────────────────────────────────────
_cache_lock = threading.Lock()
_cache: dict[str, tuple[float, dict]] = {}

# ── State priority (higher value = more important) ──────────────────────────
_STATE_PRIORITY = {
    "URGENT": 4,
    "DECLINING": 3,
    "COMPETITIVE": 2,
    "STABLE": 1,
    "UNKNOWN": 0,
}


def _resolve_path(yaml_path: str | Path | None) -> Path:
    if yaml_path is None:
        return _DEFAULT_YAML
    return Path(yaml_path)


def _load_yaml_file(path: Path) -> dict:
    """Load + parse YAML file. Returns {} on any error (logged)."""
    try:
        import yaml  # type: ignore
    except ImportError:
        log.error("[templates] PyYAML not installed")
        return {}

    if not path.exists():
        log.warning("[templates] YAML not found: %s", path)
        return {}

    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            log.error("[templates] YAML root is not dict: %s", path)
            return {}
        return data
    except Exception as e:
        log.error("[templates] YAML load error %s: %s", path, e)
        return {}


def load_rules(yaml_path: str | Path | None = None) -> dict:
    """
    Load (or hot-reload) rules from YAML.

    Hot-reload: checks file mtime; if changed since last load, re-parse.
    """
    path = _resolve_path(yaml_path)
    key = str(path.resolve()) if path.exists() else str(path)

    with _cache_lock:
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            mtime = 0.0

        cached = _cache.get(key)
        if cached and cached[0] == mtime and mtime != 0.0:
            return cached[1]

        rules = _load_yaml_file(path)
        _cache[key] = (mtime, rules)
        return rules


def _normalize_list(val: Any) -> list[str]:
    """Coerce YAML field into a list of uppercase strings."""
    if val is None:
        return []
    if isinstance(val, str):
        return [val.strip().upper()]
    if isinstance(val, (list, tuple)):
        return [str(v).strip().upper() for v in val if v is not None]
    return [str(val).strip().upper()]


def _score_template(
    tmpl: dict,
    destinations: list[str],
    states: list[str],
) -> tuple[int, str] | None:
    """
    Return (score, reason) if template matches — else None.

    Higher score = more specific.
        - Exact dest + exact state  → 4
        - Exact dest + any state    → 3
        - Any dest  + exact state   → 2
        - Any dest  + any state     → 1
    """
    match_cfg = tmpl.get("match") or {}
    tmpl_dests = _normalize_list(match_cfg.get("destinations"))
    tmpl_states = _normalize_list(match_cfg.get("states"))

    if not tmpl_dests:
        tmpl_dests = ["ANY"]
    if not tmpl_states:
        tmpl_states = ["ANY"]

    dests_u = [d.upper() for d in destinations if d]
    states_u = [s.upper() for s in states if s]

    any_dest = "ANY" in tmpl_dests
    any_state = "ANY" in tmpl_states

    dest_match = any_dest or any(d in tmpl_dests for d in dests_u)
    state_match = any_state or any(s in tmpl_states for s in states_u)

    if not (dest_match and state_match):
        return None

    # Scoring
    if not any_dest and not any_state:
        return (4, "exact_lane_and_state")
    if not any_dest and any_state:
        return (3, "exact_lane_any_state")
    if any_dest and not any_state:
        return (2, "any_lane_exact_state")
    return (1, "default")


def match(destinations: list[str], states: list[str], yaml_path: str | Path | None = None) -> dict:
    """
    Pick the best-matching template.

    Returns dict with at minimum: id, subject, intro, cta, match_reason.
    Falls back to a hard-coded safe template if YAML is missing or has no templates.
    """
    rules = load_rules(yaml_path)
    templates = rules.get("templates") or []

    if not templates:
        return _safe_default(reason="no_templates")

    best: tuple[int, str, dict] | None = None
    for tmpl in templates:
        if not isinstance(tmpl, dict):
            continue
        scored = _score_template(tmpl, destinations, states)
        if scored is None:
            continue
        score, reason = scored
        if best is None or score > best[0]:
            best = (score, reason, tmpl)

    if best is None:
        # Try explicit "default" id
        for tmpl in templates:
            if isinstance(tmpl, dict) and str(tmpl.get("id", "")).lower() == "default":
                return _shape_template(tmpl, "fallback_default")
        return _safe_default(reason="no_match")

    return _shape_template(best[2], best[1])


def _shape_template(raw: dict, match_reason: str) -> dict:
    """Return a dict with canonical keys (id, subject, intro, cta, match_reason)."""
    return {
        "id": str(raw.get("id", "unknown")),
        "subject": str(raw.get("subject", "Asia-US Ocean Freight Update")),
        "intro": str(raw.get("intro", "")).strip(),
        "cta": str(raw.get("cta", "")).strip(),
        "match_reason": match_reason,
        "_raw": raw,  # retain raw for advanced access
    }


def _safe_default(reason: str = "safe_default") -> dict:
    return {
        "id": "safe_default",
        "subject": "Asia-US Ocean Freight Weekly Update",
        "intro": "Dear {{first_name}},\nWeekly ocean freight update for {{company}}.",
        "cta": "Let me know if you need rate quotes or have specific lanes in mind.",
        "match_reason": reason,
        "_raw": {},
    }


def dominant_state(lane_intels: list[dict]) -> str:
    """
    Given a list of lane-intel dicts (each with a 'state' key), return the dominant state.

    Priority: URGENT > DECLINING > COMPETITIVE > STABLE.
    Returns "STABLE" if list is empty.
    """
    best = "STABLE"
    best_score = _STATE_PRIORITY["STABLE"]
    for lane in lane_intels or []:
        s = str(lane.get("state", "STABLE")).upper()
        sc = _STATE_PRIORITY.get(s, 0)
        if sc > best_score:
            best = s
            best_score = sc
    return best


def clear_cache() -> None:
    """Clear YAML cache — forces reload on next call."""
    with _cache_lock:
        _cache.clear()
