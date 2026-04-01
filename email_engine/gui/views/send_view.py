# -*- coding: utf-8 -*-
"""
send_view.py — CMD Send View
=============================
Select a campaign (CMD), preview customer list, and send emails interactively.
"""
from __future__ import annotations

import csv
import sys
import threading
from datetime import datetime, date
from pathlib import Path
from typing import TYPE_CHECKING

import customtkinter as ctk
import pandas as pd

from gui.theme import COLORS, FONTS
from gui.views.auto_rate_view import _gen_subject, _load_cfg

if TYPE_CHECKING:
    from gui.app_window import AppWindow


class SendView(ctk.CTkFrame):
    """CMD Send: select campaign → review list → send emails."""

    def __init__(self, parent, app: AppWindow):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._customers: list[dict] = []
        self._checkboxes: dict[int, ctk.BooleanVar] = {}
        self._build_ui()
        self._load_cmd_list()

    # ══════════════════════════════════════════════════════════
    # UI BUILD
    # ══════════════════════════════════════════════════════════

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(header, text="Send Email", font=FONTS["heading"],
                     text_color=COLORS["text_primary"], anchor="w").pack(side="left")

        # Controls
        ctrl = ctk.CTkFrame(self, fg_color=COLORS["bg_sidebar"], corner_radius=10)
        ctrl.pack(fill="x", pady=(0, 12))
        inner = ctk.CTkFrame(ctrl, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(inner, text="Campaign:", font=FONTS["body_bold"],
                     text_color=COLORS["text_primary"]).pack(side="left", padx=(0, 8))
        self.cmd_var = ctk.StringVar(value="-- Select --")
        self.cmd_menu = ctk.CTkOptionMenu(
            inner, variable=self.cmd_var, values=["Loading..."],
            width=220, font=FONTS["body"],
            fg_color=COLORS["bg_input"], button_color=COLORS["bg_card"],
            command=self._on_cmd_change,
        )
        self.cmd_menu.pack(side="left", padx=(0, 16))

        self.load_btn = ctk.CTkButton(
            inner, text="📋 Load List", font=FONTS["button"], width=130,
            fg_color=COLORS["accent_blue"], hover_color=COLORS["bg_hover"],
            command=self._load_customers,
        )
        self.load_btn.pack(side="left", padx=(0, 8))

        self.send_btn = ctk.CTkButton(
            inner, text="📧 Send Selected", font=FONTS["button"], width=160,
            fg_color=COLORS["accent"], hover_color="#c62828",
            command=self._confirm_send, state="disabled",
        )
        self.send_btn.pack(side="right")

        # Summary
        self.summary = ctk.CTkLabel(
            self, text="Select a campaign and click 'Load List'.",
            font=FONTS["body"], text_color=COLORS["text_muted"], anchor="w",
        )
        self.summary.pack(fill="x", pady=(0, 8))

        # Table
        tbl = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_sidebar"], corner_radius=10)
        tbl.pack(fill="both", expand=True)

        # Header row
        hdr = ctk.CTkFrame(tbl, fg_color=COLORS["table_header"], height=36)
        hdr.pack(fill="x", pady=(0, 2))
        hdr.pack_propagate(False)

        self._all_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(hdr, variable=self._all_var, text="",
                        width=24, checkbox_width=18, checkbox_height=18,
                        command=self._toggle_all).pack(side="left", padx=(8, 4))

        for col, w in [("Company", 220), ("Email", 260), ("PIC", 120),
                       ("POL", 60), ("Destination", 200)]:
            ctk.CTkLabel(hdr, text=col, font=FONTS["body_bold"],
                         text_color=COLORS["text_primary"], width=w, anchor="w").pack(side="left", padx=4)

        self._rows = ctk.CTkFrame(tbl, fg_color="transparent")
        self._rows.pack(fill="both", expand=True)

    # ══════════════════════════════════════════════════════════
    # DATA
    # ══════════════════════════════════════════════════════════

    def _load_cmd_list(self):
        data_file = self.app.project_root / "data.xlsx"
        if not data_file.exists():
            return
        try:
            df = pd.read_excel(data_file)
            df.columns = df.columns.str.strip().str.upper()
            cmds = sorted(df["CMD_NAME"].dropna().unique().tolist())
            if cmds:
                self.cmd_menu.configure(values=cmds)
                self.cmd_var.set(cmds[0])
        except Exception:
            pass

    def _on_cmd_change(self, val):
        self._clear_rows()
        self.summary.configure(text=f"Campaign: {val} — Click 'Load List' to preview.",
                               text_color=COLORS["text_muted"])
        self.send_btn.configure(state="disabled")

    def _load_customers(self):
        cmd = self.cmd_var.get()
        if not cmd or cmd.startswith("-"):
            return
        self._clear_rows()
        self.app.set_status_busy(f"Loading {cmd}...")
        try:
            df = pd.read_excel(self.app.project_root / "data.xlsx")
            df.columns = df.columns.str.strip().str.upper()
            subset = df[df["CMD_NAME"] == cmd].copy()
            subset = subset[subset["CNEE_EMAIL"].notna()]
            subset = subset.drop_duplicates(subset="CNEE_EMAIL")

            self._customers = []
            for _, row in subset.iterrows():
                self._customers.append({
                    "email":   str(row.get("CNEE_EMAIL", "")).strip(),
                    "company": str(row.get("CNEE_NAME", "")).strip(),
                    "pic":     str(row.get("CNEE_PIC", "Team")).strip(),
                    "pol":     str(row.get("POL", "HPH")).strip(),
                    "dest":    str(row.get("DESTINATION", "")).strip(),
                    "cmd":     cmd,
                })

            self._render_rows()
            self.summary.configure(
                text=f"✓ {len(self._customers)} contacts in '{cmd}'",
                text_color=COLORS["accent_green"])
            if self._customers:
                self.send_btn.configure(state="normal",
                                        text=f"📧 Send Selected ({len(self._customers)})")
            self.app.set_status_done(f"Loaded {len(self._customers)} contacts")
        except Exception as e:
            self.app.set_status(f"Error: {e}")

    def _render_rows(self):
        self._clear_rows()
        self._checkboxes.clear()
        for i, c in enumerate(self._customers):
            bg = COLORS["table_row_even"] if i % 2 == 0 else COLORS["table_row_odd"]
            row = ctk.CTkFrame(self._rows, fg_color=bg, height=34, corner_radius=0)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)

            var = ctk.BooleanVar(value=True)
            self._checkboxes[i] = var
            ctk.CTkCheckBox(row, variable=var, text="", width=24,
                            checkbox_width=18, checkbox_height=18,
                            command=self._update_count).pack(side="left", padx=(8, 4))

            for text, w in [(c["company"][:30], 220), (c["email"][:35], 260),
                            (c["pic"][:18], 120), (c["pol"], 60), (c["dest"][:28], 200)]:
                ctk.CTkLabel(row, text=text, font=FONTS["small"],
                             text_color=COLORS["text_primary"], width=w, anchor="w").pack(side="left", padx=4)

    def _clear_rows(self):
        for w in self._rows.winfo_children():
            w.destroy()
        self._checkboxes.clear()

    # ══════════════════════════════════════════════════════════
    # ACTIONS
    # ══════════════════════════════════════════════════════════

    def _toggle_all(self):
        val = self._all_var.get()
        for v in self._checkboxes.values():
            v.set(val)
        self._update_count()

    def _update_count(self):
        n = sum(1 for v in self._checkboxes.values() if v.get())
        self.send_btn.configure(
            text=f"📧 Send Selected ({n})",
            state="normal" if n > 0 else "disabled")

    def _confirm_send(self):
        """FIX 2: Open preview window — send only after explicit Approve."""
        selected = [self._customers[i] for i, v in self._checkboxes.items() if v.get()]
        if not selected:
            return

        try:
            cfg = _load_cfg(self.app.project_root / "data" / "config.xlsx")
        except Exception as e:
            self.app.set_status(f"Config error: {e}")
            return

        subject = _gen_subject(cfg)   # FIX 3: auto ISO week, random template
        intro   = cfg.get("IntroText",  cfg.get("INTROTEXT", ""))
        closing = cfg.get("ClosingText", cfg.get("CLOSINGTEXT", ""))
        sample  = selected[0]

        win = ctk.CTkToplevel(self)
        win.title("📧 Preview & Approve")
        win.geometry("760x540")
        win.transient(self.winfo_toplevel())
        win.grab_set()

        # Header
        hdr = ctk.CTkFrame(win, fg_color=COLORS["bg_sidebar"], corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text=f"  Previewing 1 of {len(selected)} emails",
                     font=FONTS["heading_small"], text_color=COLORS["accent_green"],
                     anchor="w").pack(side="left", padx=16, pady=12)

        # Meta
        meta = ctk.CTkFrame(win, fg_color=COLORS["bg_card"], corner_radius=0)
        meta.pack(fill="x")
        for lbl, val in [("To:", f"{sample['company']}  <{sample['email']}>"),
                         ("Subject:", subject),
                         ("Recipients:", f"{len(selected)} customers")]:
            r = ctk.CTkFrame(meta, fg_color="transparent")
            r.pack(fill="x", padx=16, pady=2)
            ctk.CTkLabel(r, text=lbl, font=FONTS["body_bold"],
                         text_color=COLORS["text_secondary"], width=90, anchor="w").pack(side="left")
            ctk.CTkLabel(r, text=val, font=FONTS["body"],
                         text_color=COLORS["text_primary"], anchor="w").pack(side="left")

        ctk.CTkLabel(win, text="  Email Body Preview:", font=FONTS["body_bold"],
                     text_color=COLORS["text_secondary"], anchor="w").pack(fill="x", padx=16, pady=(10, 2))

        box = ctk.CTkTextbox(win, font=FONTS["small"], fg_color=COLORS["bg_input"],
                             text_color=COLORS["text_primary"], wrap="word")
        box.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        box.insert("1.0", f"Dear {sample['pic']},\n\n{intro}\n\n[Rate table will appear here]\n\n{closing}")
        box.configure(state="disabled")

        bf = ctk.CTkFrame(win, fg_color=COLORS["bg_sidebar"], corner_radius=0)
        bf.pack(fill="x", side="bottom")
        ctk.CTkButton(bf, text="Cancel", width=110, fg_color=COLORS["bg_card"],
                      command=win.destroy).pack(side="left", padx=16, pady=12)
        ctk.CTkButton(bf, text=f"✅ Approve & Send ({len(selected)})", width=240,
                      font=FONTS["button"], fg_color=COLORS["accent"], hover_color="#c62828",
                      command=lambda: self._approved_send(win, selected)).pack(side="right", padx=16, pady=12)

    def _approved_send(self, win, selected: list[dict]):
        win.destroy()
        self.send_btn.configure(state="disabled", text="⏳ Sending...")
        self.app.set_status_busy(f"Sending {len(selected)} emails...")
        threading.Thread(target=self._send_worker, args=(selected,), daemon=True).start()

    def _send_worker(self, contacts: list[dict]):
        try:
            import win32com.client, openpyxl, random

            cfg_file = self.app.project_root / "data" / "config.xlsx"
            wb = openpyxl.load_workbook(str(cfg_file), data_only=True)
            cfg = {str(r[0] or "").strip().upper(): str(r[1] or "").strip()
                   for r in wb.active.iter_rows(max_col=2, values_only=True)
                   if r[0] and str(r[0]).strip().upper() != "KEY"}

            # FIX 3: subject auto-rotated from config, ISO week from system clock
            subject = _gen_subject(cfg)
            intro = cfg.get("INTROTEXT", "")
            closing = cfg.get("CLOSINGTEXT", "")
            sig = cfg.get("SIGNATURE", "")
            profile = self.app.project_root / "assets" / "PUDONG PRIME PROFILE.pdf"
            logo = self.app.project_root / "assets" / "logo.png"

            outlook = win32com.client.Dispatch("Outlook.Application")
            campaign = f"CMD_{contacts[0]['cmd']}_{datetime.now():%Y%m%d_%H%M}"
            log_file = self.app.logs_dir / "email_log.csv"
            sent = 0

            for c in contacts:
                m = outlook.CreateItem(0)
                m.To = c["email"]
                m.Subject = subject
                if profile.exists():
                    m.Attachments.Add(str(profile))
                if logo.exists():
                    lg = m.Attachments.Add(str(logo))
                    lg.PropertyAccessor.SetProperty(
                        "http://schemas.microsoft.com/mapi/proptag/0x3712001F", "pudonglogo")
                m.HTMLBody = (f"<html><body>Dear {c['pic']},<br><br>"
                              f"{intro}<br><br>{closing}<br><br>{sig}</body></html>")
                m.Send()

                exists = log_file.exists()
                with open(log_file, "a", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    if not exists:
                        w.writerow(["timestamp", "email", "subject", "campaign_id", "cycle_id", "status"])
                    w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                c["email"], subject, campaign, "1", "SENT"])
                sent += 1

            self.after(0, lambda: self._done(sent, campaign))
        except Exception as e:
            self.after(0, lambda: self.app.set_status(f"❌ Send error: {e}"))

    def _done(self, count: int, campaign: str):
        self.send_btn.configure(state="normal", text="📧 Send Selected")
        self.app.set_status_done(f"✓ {count} emails sent — {campaign}")
        dlg = ctk.CTkToplevel(self)
        dlg.title("Done")
        dlg.geometry("320x130")
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()
        ctk.CTkLabel(dlg, text=f"✓ {count} emails sent!", font=FONTS["heading"]).pack(pady=(20, 4))
        ctk.CTkLabel(dlg, text=campaign, font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(pady=(0, 12))
        ctk.CTkButton(dlg, text="OK", width=80, command=dlg.destroy).pack()
