# -*- coding: utf-8 -*-
"""
app_window.py — Email Engine v2.0 Main Window
==============================================
Main application window with sidebar navigation and view switching.
"""
from __future__ import annotations

import customtkinter as ctk
from pathlib import Path
from typing import Optional

from gui.theme import COLORS, FONTS, DIMENSIONS, SIDEBAR_ITEMS


class AppWindow(ctk.CTk):
    """Main application window for Email Engine v2.0."""

    def __init__(self):
        super().__init__()

        # ── Window Setup ─────────────────────────────────────
        self.title("Email Engine v2.0 — Pudong Prime")
        self.geometry(f"{DIMENSIONS['window_width']}x{DIMENSIONS['window_height']}")
        self.minsize(1024, 700)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Project paths
        self.project_root = Path(__file__).parent.parent
        self.data_dir = self.project_root / "data"
        self.logs_dir = self.project_root / "logs"
        self.config_dir = self.project_root / "config"
        self.core_dir = self.project_root / "core"

        # State
        self._current_view: Optional[str] = None
        self._views: dict = {}
        self._sidebar_buttons: dict = {}

        # ── Build Layout ─────────────────────────────────────
        self._build_sidebar()
        self._build_main_area()
        self._build_status_bar()

        # ── Load Default View ────────────────────────────────
        self.switch_view("dashboard")

    # ══════════════════════════════════════════════════════════
    # SIDEBAR
    # ══════════════════════════════════════════════════════════

    def _build_sidebar(self):
        """Build the left sidebar with navigation buttons."""
        self.sidebar = ctk.CTkFrame(
            self,
            width=DIMENSIONS["sidebar_width"],
            corner_radius=0,
            fg_color=COLORS["bg_sidebar"],
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # ── Logo / Title ─────────────────────────────────────
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=16, pady=(20, 8))

        ctk.CTkLabel(
            logo_frame,
            text="📧 Email Engine",
            font=FONTS["heading_small"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            logo_frame,
            text="Pudong Prime v2.0",
            font=FONTS["small"],
            text_color=COLORS["text_muted"],
            anchor="w",
        ).pack(fill="x")

        # ── Separator ────────────────────────────────────────
        sep = ctk.CTkFrame(self.sidebar, height=1, fg_color=COLORS["border"])
        sep.pack(fill="x", padx=16, pady=(12, 8))

        # ── Menu Buttons ─────────────────────────────────────
        for item in SIDEBAR_ITEMS:
            btn = ctk.CTkButton(
                self.sidebar,
                text=f"  {item['icon']}  {item['label']}",
                font=FONTS["sidebar"],
                fg_color="transparent",
                text_color=COLORS["text_secondary"],
                hover_color=COLORS["bg_hover"],
                anchor="w",
                height=42,
                corner_radius=8,
                command=lambda k=item["key"]: self.switch_view(k),
            )
            btn.pack(fill="x", padx=10, pady=2)
            self._sidebar_buttons[item["key"]] = btn

        # ── Bottom spacer + version ─────────────────────────
        spacer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        ctk.CTkLabel(
            self.sidebar,
            text="v2.2.0 — 2026-03-31",
            font=("Segoe UI", 9),
            text_color=COLORS["text_muted"],
        ).pack(side="bottom", pady=(0, 12))

    # ══════════════════════════════════════════════════════════
    # MAIN AREA
    # ══════════════════════════════════════════════════════════

    def _build_main_area(self):
        """Build the main content area where views are displayed."""
        self.main_area = ctk.CTkFrame(
            self,
            corner_radius=0,
            fg_color=COLORS["bg_dark"],
        )
        self.main_area.pack(side="left", fill="both", expand=True)

        # Container for views (stacked, only one visible at a time)
        self.view_container = ctk.CTkFrame(
            self.main_area,
            fg_color="transparent",
        )
        self.view_container.pack(fill="both", expand=True, padx=20, pady=(16, 0))

    # ══════════════════════════════════════════════════════════
    # STATUS BAR
    # ══════════════════════════════════════════════════════════

    def _build_status_bar(self):
        """Build the bottom status bar."""
        self.status_bar = ctk.CTkFrame(
            self.main_area,
            height=32,
            corner_radius=0,
            fg_color=COLORS["bg_sidebar"],
        )
        self.status_bar.pack(fill="x", side="bottom")
        self.status_bar.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            self.status_bar,
            text="  Ready",
            font=FONTS["small"],
            text_color=COLORS["text_muted"],
            anchor="w",
        )
        self.status_label.pack(side="left", padx=12)

        self.status_right = ctk.CTkLabel(
            self.status_bar,
            text="",
            font=FONTS["small"],
            text_color=COLORS["text_muted"],
            anchor="e",
        )
        self.status_right.pack(side="right", padx=12)

    # ══════════════════════════════════════════════════════════
    # VIEW SWITCHING
    # ══════════════════════════════════════════════════════════

    def switch_view(self, view_key: str):
        """Switch the main content area to a different view."""
        if view_key == self._current_view:
            return

        # Update sidebar highlight
        for key, btn in self._sidebar_buttons.items():
            if key == view_key:
                btn.configure(
                    fg_color=COLORS["bg_card"],
                    text_color=COLORS["text_primary"],
                    font=FONTS["sidebar_active"],
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=COLORS["text_secondary"],
                    font=FONTS["sidebar"],
                )

        # Hide all current children
        for widget in self.view_container.winfo_children():
            widget.pack_forget()

        # Create or show the requested view
        if view_key not in self._views:
            self._views[view_key] = self._create_view(view_key)

        view = self._views[view_key]
        if view is not None:
            view.pack(fill="both", expand=True)

        self._current_view = view_key

    def _create_view(self, view_key: str) -> Optional[ctk.CTkFrame]:
        """Lazy-create a view by key."""
        from gui.views.dashboard_view import DashboardView
        from gui.views.auto_rate_view import AutoRateView
        from gui.views.scan_view import ScanView
        from gui.views.history_view import HistoryView
        from gui.views.settings_view import SettingsView

        creators = {
            "dashboard":  DashboardView,
            "auto_rate":  AutoRateView,   # unified Rate & Send view
            "scan":       ScanView,
            "history":    HistoryView,
            "settings":   SettingsView,
        }
        cls = creators.get(view_key)
        if cls is None:
            return None
        return cls(self.view_container, app=self)

    # ══════════════════════════════════════════════════════════
    # STATUS UPDATES
    # ══════════════════════════════════════════════════════════

    def set_status(self, text: str, right_text: str = ""):
        """Update the status bar text."""
        self.status_label.configure(text=f"  {text}")
        if right_text:
            self.status_right.configure(text=right_text)

    def set_status_busy(self, text: str = "Processing..."):
        """Show busy indicator in status bar."""
        self.set_status(f"⏳ {text}")
        self.update_idletasks()

    def set_status_done(self, text: str = "Done"):
        """Show completion in status bar."""
        self.set_status(f"✓ {text}")
