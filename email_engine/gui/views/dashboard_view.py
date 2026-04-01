# -*- coding: utf-8 -*-
"""
dashboard_view.py — Dashboard Overview
=======================================
Shows key stats (sent, replies, HOT leads, bounces),
recent activity log, and follow-up alerts.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import customtkinter as ctk

from gui.theme import COLORS, FONTS

if TYPE_CHECKING:
    from gui.app_window import AppWindow


class DashboardView(ctk.CTkFrame):
    """Main dashboard with stats cards, activity, and alerts."""

    def __init__(self, parent, app: AppWindow):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._build_ui()
        self._load_data()

    # ══════════════════════════════════════════════════════════
    # UI BUILD
    # ══════════════════════════════════════════════════════════

    def _build_ui(self):
        # ── Header ───────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            header,
            text="Dashboard",
            font=FONTS["heading"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(side="left")

        self.refresh_btn = ctk.CTkButton(
            header,
            text="🔄 Refresh",
            font=FONTS["button"],
            width=120,
            height=FONTS["button"][1] + 20,
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["bg_hover"],
            command=self._load_data,
        )
        self.refresh_btn.pack(side="right")

        # ── Stats Cards Row ──────────────────────────────────
        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="x", pady=(0, 16))

        self.stat_cards = {}
        stats_config = [
            ("sent",    "Emails Sent",   "0", COLORS["accent_blue"]),
            ("replies", "Total Replies",  "0", COLORS["accent_green"]),
            ("hot",     "HOT Leads",      "0", COLORS["accent"]),
            ("bounced", "Bounced",        "0", COLORS["warning"]),
        ]
        for key, label, default, color in stats_config:
            card = self._make_stat_card(self.stats_frame, label, default, color)
            card.pack(side="left", fill="both", expand=True, padx=(0, 12))
            self.stat_cards[key] = card

        # ── Two-column: Activity + Alerts ────────────────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)

        # Left: Recent Activity
        act_frame = ctk.CTkFrame(body, fg_color=COLORS["bg_sidebar"], corner_radius=10)
        act_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=0)

        ctk.CTkLabel(
            act_frame,
            text="  Recent Activity",
            font=FONTS["heading_small"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(fill="x", padx=12, pady=(12, 4))

        self.activity_text = ctk.CTkTextbox(
            act_frame,
            font=FONTS["mono"],
            fg_color="transparent",
            text_color=COLORS["text_secondary"],
            wrap="word",
            height=300,
        )
        self.activity_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # Right: Follow-up Alerts
        alert_frame = ctk.CTkFrame(body, fg_color=COLORS["bg_sidebar"], corner_radius=10)
        alert_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=0)

        ctk.CTkLabel(
            alert_frame,
            text="  Follow-up Alerts",
            font=FONTS["heading_small"],
            text_color=COLORS["accent"],
            anchor="w",
        ).pack(fill="x", padx=12, pady=(12, 4))

        self.alerts_text = ctk.CTkTextbox(
            alert_frame,
            font=FONTS["small"],
            fg_color="transparent",
            text_color=COLORS["text_secondary"],
            wrap="word",
            height=300,
        )
        self.alerts_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    # ══════════════════════════════════════════════════════════
    # WIDGETS
    # ══════════════════════════════════════════════════════════

    def _make_stat_card(self, parent, label: str, value: str, color: str) -> ctk.CTkFrame:
        """Create a single stat card widget."""
        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_sidebar"], corner_radius=10)

        val_label = ctk.CTkLabel(
            card,
            text=value,
            font=FONTS["stat_number"],
            text_color=color,
        )
        val_label.pack(padx=16, pady=(16, 2))
        card._val_label = val_label  # store reference for updates

        ctk.CTkLabel(
            card,
            text=label,
            font=FONTS["stat_label"],
            text_color=COLORS["text_muted"],
        ).pack(padx=16, pady=(0, 14))

        return card

    def _update_stat(self, key: str, value: str):
        """Update a stat card's value."""
        card = self.stat_cards.get(key)
        if card and hasattr(card, "_val_label"):
            card._val_label.configure(text=value)

    # ══════════════════════════════════════════════════════════
    # DATA LOADING
    # ══════════════════════════════════════════════════════════

    def _load_data(self):
        """Load stats from CSV/Excel files."""
        self.app.set_status_busy("Loading dashboard data...")

        try:
            self._load_stats()
            self._load_activity()
            self._load_alerts()
            self.app.set_status_done("Dashboard updated")
        except Exception as e:
            self.app.set_status(f"Error: {e}")

    def _load_stats(self):
        """Read email_log.csv + tier_history.csv for stats."""
        logs_dir = self.app.logs_dir

        # Count sent emails
        email_log = logs_dir / "email_log.csv"
        sent_count = 0
        if email_log.exists():
            with open(email_log, encoding="utf-8", errors="replace") as f:
                sent_count = max(0, sum(1 for _ in f) - 1)  # minus header
        self._update_stat("sent", str(sent_count))

        # Count replies from email_knowledge.csv
        knowledge = logs_dir / "email_knowledge.csv"
        reply_count = 0
        if knowledge.exists():
            with open(knowledge, encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    signal = row.get("signal_type", "").lower()
                    if signal == "human_reply":
                        reply_count += 1
        self._update_stat("replies", str(reply_count))

        # Count HOT leads (REPLY_3+) from tier_history.csv
        tier_history = logs_dir / "tier_history.csv"
        hot_count = 0
        if tier_history.exists():
            with open(tier_history, encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                # Get latest tier per email
                latest = {}
                for row in reader:
                    email = row.get("email", "")
                    tier = row.get("tier", "")
                    if email:
                        latest[email] = tier
                hot_count = sum(1 for t in latest.values() if t in ("REPLY_3", "REPLY_4"))
        self._update_stat("hot", str(hot_count))

        # Count bounced from bounce_log.csv
        bounce_log = logs_dir / "bounce_log.csv"
        bounce_count = 0
        if bounce_log.exists():
            with open(bounce_log, encoding="utf-8", errors="replace") as f:
                bounce_count = max(0, sum(1 for _ in f) - 1)
        self._update_stat("bounced", str(bounce_count))

    def _load_activity(self):
        """Load recent activity from email_log.csv."""
        self.activity_text.configure(state="normal")
        self.activity_text.delete("1.0", "end")

        email_log = self.app.logs_dir / "email_log.csv"
        if not email_log.exists():
            self.activity_text.insert("1.0", "No activity log found.\nRun a send or scan to generate data.")
            self.activity_text.configure(state="disabled")
            return

        lines = []
        with open(email_log, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = row.get("timestamp", "")
                email = row.get("email", "")
                campaign = row.get("campaign_id", "")
                status = row.get("status", "")
                lines.append(f"[{ts}] {status:6s} → {email}  ({campaign})")

        # Show last 50, newest first
        lines.reverse()
        display = "\n".join(lines[:50]) if lines else "No recent activity."
        self.activity_text.insert("1.0", display)
        self.activity_text.configure(state="disabled")

    def _load_alerts(self):
        """Load follow-up alerts from followup_alerts.csv."""
        self.alerts_text.configure(state="normal")
        self.alerts_text.delete("1.0", "end")

        alerts_file = self.app.logs_dir / "followup_alerts.csv"
        if not alerts_file.exists():
            self.alerts_text.insert("1.0", "No pending alerts.\n\nRun Scan & Classify to detect follow-up opportunities.")
            self.alerts_text.configure(state="disabled")
            return

        lines = []
        with open(alerts_file, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                company = row.get("company", row.get("cnee_name", "Unknown"))
                tier = row.get("tier", "")
                days = row.get("days_since_reply", "?")
                lines.append(f"⚠ {company}\n   Tier: {tier} | {days} days since reply\n")

        display = "\n".join(lines) if lines else "No pending follow-up alerts."
        self.alerts_text.insert("1.0", display)
        self.alerts_text.configure(state="disabled")
