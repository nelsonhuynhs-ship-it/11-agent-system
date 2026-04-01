# -*- coding: utf-8 -*-
"""
theme.py — Email Engine v2.0 Theme Configuration
=================================================
Professional dark theme for freight forwarding operations.
"""

# ── Color Palette ────────────────────────────────────────────
COLORS = {
    # Background
    "bg_dark":        "#1a1a2e",
    "bg_sidebar":     "#16213e",
    "bg_card":        "#0f3460",
    "bg_input":       "#1a1a2e",
    "bg_hover":       "#1e3a5f",
    "bg_selected":    "#e94560",

    # Text
    "text_primary":   "#ffffff",
    "text_secondary": "#8892b0",
    "text_muted":     "#5a6380",
    "text_accent":    "#64ffda",

    # Accent
    "accent":         "#e94560",
    "accent_green":   "#64ffda",
    "accent_blue":    "#53c0f0",
    "accent_yellow":  "#ffd93d",
    "accent_orange":  "#ff8c42",

    # Status
    "success":        "#4ade80",
    "warning":        "#fbbf24",
    "danger":         "#ef4444",
    "info":           "#60a5fa",

    # Border
    "border":         "#233554",
    "border_light":   "#2d4a6f",

    # Table
    "table_header":   "#0f3460",
    "table_row_even": "#1a1a2e",
    "table_row_odd":  "#16213e",
    "table_selected": "#1e3a5f",
}

# ── Fonts ────────────────────────────────────────────────────
FONTS = {
    "heading_large":  ("Segoe UI", 24, "bold"),
    "heading":        ("Segoe UI", 18, "bold"),
    "heading_small":  ("Segoe UI", 14, "bold"),
    "body":           ("Segoe UI", 12),
    "body_bold":      ("Segoe UI", 12, "bold"),
    "small":          ("Segoe UI", 10),
    "mono":           ("Consolas", 11),
    "sidebar":        ("Segoe UI", 13),
    "sidebar_active":  ("Segoe UI", 13, "bold"),
    "stat_number":    ("Segoe UI", 32, "bold"),
    "stat_label":     ("Segoe UI", 11),
    "button":         ("Segoe UI", 12, "bold"),
}

# ── Dimensions ───────────────────────────────────────────────
DIMENSIONS = {
    "sidebar_width":  220,
    "window_width":   1280,
    "window_height":  800,
    "card_padding":   16,
    "corner_radius":  10,
    "button_height":  38,
}

# ── Sidebar Menu Items ──────────────────────────────────────
SIDEBAR_ITEMS = [
    {"key": "dashboard",  "label": "Dashboard",        "icon": "📊"},
    {"key": "auto_rate",  "label": "Rate & Send",      "icon": "💰"},
    {"key": "scan",       "label": "Scan & Classify",  "icon": "🔍"},
    {"key": "history",    "label": "History",           "icon": "📋"},
    {"key": "settings",   "label": "Settings",          "icon": "⚙️"},
]
