"""
email_engine.intelligence — Smart template engine + per-lane market intel.

Public API:
    from email_engine.intelligence import (
        analyze_lane,            # market_engine
        load_rules, match, dominant_state,   # template_selector
        render_text, render_email,           # template_renderer
        build_email,             # builder
    )

Phase 03 — Nelson Freight "Smart Template Engine + Market Intel".
"""
from .market_engine import analyze_lane
from .template_selector import load_rules, match, dominant_state
from .template_renderer import render_text, render_email
from .builder import build_email

__all__ = [
    "analyze_lane",
    "load_rules",
    "match",
    "dominant_state",
    "render_text",
    "render_email",
    "build_email",
]
