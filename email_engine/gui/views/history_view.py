# -*- coding: utf-8 -*-
"""
history_view.py — Send History & Activity Log
"""
from __future__ import annotations

import csv
from datetime import datetime
from typing import TYPE_CHECKING

import customtkinter as ctk

from gui.theme import COLORS, FONTS

if TYPE_CHECKING:
    from gui.app_window import AppWindow


class HistoryView(ctk.CTkFrame):

    def __init__(self, parent, app: AppWindow):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._all_rows: list[dict] = []
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(hdr, text="History", font=FONTS["heading"],
                     text_color=COLORS["text_primary"], anchor="w").pack(side="left")
        ctk.CTkButton(hdr, text="🔄 Refresh", font=FONTS["button"], width=110,
                      fg_color=COLORS["bg_card"], hover_color=COLORS["bg_hover"],
                      command=self._load_data).pack(side="right")

        # Filters
        flt = ctk.CTkFrame(self, fg_color=COLORS["bg_sidebar"], corner_radius=10)
        flt.pack(fill="x", pady=(0, 12))
        fi = ctk.CTkFrame(flt, fg_color="transparent")
        fi.pack(fill="x", padx=16, pady=10)

        ctk.CTkLabel(fi, text="Filter:", font=FONTS["body_bold"],
                     text_color=COLORS["text_primary"]).pack(side="left", padx=(0, 8))
        self.filter_var = ctk.StringVar(value="All")
        ctk.CTkOptionMenu(fi, variable=self.filter_var,
                          values=["All", "SENT", "SCAN", "TIER_UP", "BOUNCE", "CLEAN"],
                          width=140, font=FONTS["body"],
                          fg_color=COLORS["bg_input"], button_color=COLORS["bg_card"],
                          command=self._apply_filter).pack(side="left", padx=(0, 16))

        ctk.CTkLabel(fi, text="Search:", font=FONTS["body_bold"],
                     text_color=COLORS["text_primary"]).pack(side="left", padx=(0, 6))
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._apply_filter())
        ctk.CTkEntry(fi, textvariable=self.search_var, width=200, font=FONTS["body"],
                     fg_color=COLORS["bg_input"], placeholder_text="Search email / campaign...").pack(side="left")

        self.count_label = ctk.CTkLabel(fi, text="", font=FONTS["small"],
                                        text_color=COLORS["text_muted"])
        self.count_label.pack(side="right")

        # Table header
        tbl_wrap = ctk.CTkFrame(self, fg_color=COLORS["bg_sidebar"], corner_radius=10)
        tbl_wrap.pack(fill="both", expand=True)

        col_hdr = ctk.CTkFrame(tbl_wrap, fg_color=COLORS["table_header"], height=36)
        col_hdr.pack(fill="x", pady=(0, 0))
        col_hdr.pack_propagate(False)
        for col, w in [("Date / Time", 150), ("Action", 80), ("Email / Company", 260),
                       ("Campaign", 200), ("Details", 200)]:
            ctk.CTkLabel(col_hdr, text=col, font=FONTS["body_bold"],
                         text_color=COLORS["text_primary"], width=w, anchor="w").pack(side="left", padx=8)

        self.table = ctk.CTkScrollableFrame(tbl_wrap, fg_color="transparent")
        self.table.pack(fill="both", expand=True, padx=4, pady=4)

    def _load_data(self):
        self.app.set_status_busy("Loading history...")
        self._all_rows = []

        # email_log.csv → SENT actions
        log = self.app.logs_dir / "email_log.csv"
        if log.exists():
            with open(log, encoding="utf-8", errors="replace") as f:
                for row in csv.DictReader(f):
                    self._all_rows.append({
                        "ts":       row.get("timestamp", ""),
                        "action":   "SENT",
                        "email":    row.get("email", ""),
                        "campaign": row.get("campaign_id", ""),
                        "detail":   row.get("status", ""),
                    })

        # tier_history.csv → TIER_UP actions
        tier_f = self.app.logs_dir / "tier_history.csv"
        if tier_f.exists():
            with open(tier_f, encoding="utf-8", errors="replace") as f:
                for row in csv.DictReader(f):
                    self._all_rows.append({
                        "ts":       row.get("timestamp", row.get("date", "")),
                        "action":   "TIER_UP",
                        "email":    row.get("email", ""),
                        "campaign": row.get("campaign_id", ""),
                        "detail":   f"→ {row.get('tier', '')}",
                    })

        # bounce_log.csv → BOUNCE actions
        bounce_f = self.app.logs_dir / "bounce_log.csv"
        if bounce_f.exists():
            with open(bounce_f, encoding="utf-8", errors="replace") as f:
                for row in csv.DictReader(f):
                    self._all_rows.append({
                        "ts":       row.get("timestamp", row.get("date", "")),
                        "action":   "BOUNCE",
                        "email":    row.get("email", ""),
                        "campaign": "",
                        "detail":   row.get("signal_type", row.get("bounce_type", "")),
                    })

        # Sort newest first
        def _sort_key(r):
            try:
                return datetime.strptime(r["ts"][:19], "%Y-%m-%d %H:%M:%S")
            except Exception:
                return datetime.min
        self._all_rows.sort(key=_sort_key, reverse=True)

        self._apply_filter()
        self.app.set_status_done(f"History: {len(self._all_rows)} records")

    def _apply_filter(self, *_):
        flt = self.filter_var.get()
        search = self.search_var.get().lower()

        filtered = []
        for r in self._all_rows:
            if flt != "All" and r["action"] != flt:
                continue
            if search and search not in (r["email"] + r["campaign"] + r["detail"]).lower():
                continue
            filtered.append(r)

        self._render(filtered)
        self.count_label.configure(text=f"{len(filtered)} records")

    def _render(self, rows: list[dict]):
        for w in self.table.winfo_children():
            w.destroy()

        action_colors = {
            "SENT":    COLORS["accent_blue"],
            "TIER_UP": COLORS["accent_green"],
            "BOUNCE":  COLORS["warning"],
            "SCAN":    COLORS["text_secondary"],
            "CLEAN":   COLORS["text_muted"],
        }

        for i, r in enumerate(rows[:200]):  # cap at 200 for performance
            bg = COLORS["table_row_even"] if i % 2 == 0 else COLORS["table_row_odd"]
            row = ctk.CTkFrame(self.table, fg_color=bg, height=30, corner_radius=0)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)

            color = action_colors.get(r["action"], COLORS["text_secondary"])
            for text, w in [
                (r["ts"][:19],            150),
                (r["action"],              80),
                (r["email"][:35],         260),
                (r["campaign"][:30],      200),
                (r["detail"][:30],        200),
            ]:
                ctk.CTkLabel(
                    row, text=text, font=FONTS["small"],
                    text_color=color if text == r["action"] else COLORS["text_secondary"],
                    width=w, anchor="w",
                ).pack(side="left", padx=8)
