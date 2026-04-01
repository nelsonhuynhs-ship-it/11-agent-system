# -*- coding: utf-8 -*-
"""
auto_rate_view.py — Unified Rate & Send View  (v2.2)
=====================================================
Combines Auto Rate (Parquet) + CMD Send (template) in one view.

Toggle switch selects mode:
  • AUTO RATE  — build rate table per customer from Parquet, Preview & Approve
  • CMD SEND   — send template email with auto-generated Parquet rate table

Key fixes v2.2:
  • POL nan/blank → query BOTH HPH + HCM, merge best rates
  • DEFAULT_DESTS expanded: WC / EC / Inland main ports
  • Send Email now generates rate table from Parquet (no manual HTML paste)
  • Mandatory Preview & Approve before any send
  • Subject auto-rotation from config templates, ISO week auto
"""
from __future__ import annotations

import csv
import random
import sys
import threading
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import customtkinter as ctk
import pandas as pd

from gui.theme import COLORS, FONTS

if TYPE_CHECKING:
    from gui.app_window import AppWindow

# ── Default fallback destinations when customer has no DESTINATION set ────────
# WC main ports
_WC_PORTS  = "USLAX,USLGB,USTIW,CAVAN"
# EC main ports
_EC_PORTS  = "USNYC,USEWR,USSAV,USCHS,CAHAL"
# Inland best hubs
_IN_PORTS  = "USDAL,USDEN,USSEA,USCHI"

DEFAULT_DESTS = f"{_WC_PORTS},{_EC_PORTS},{_IN_PORTS}"

# POLs to query when customer's POL is unknown
DEFAULT_POLS = ["HPH", "HCM"]


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS (shared by both modes)
# ─────────────────────────────────────────────────────────────────────────────

def _gen_subject(cfg: dict) -> str:
    """
    Auto-generate subject: random template from config + ISO week (system clock).
    ISO week is NEVER entered manually.
    """
    templates_raw = cfg.get("SUBJECTTEMPLATES", cfg.get("SubjectTemplates", ""))
    templates = [t.strip() for t in templates_raw.split("|") if t.strip()]
    if not templates:
        templates = ["Asia-US Ocean Freight Update"]
    suffix   = cfg.get("SUBJECTSUFFIX", cfg.get("SubjectSuffix", "NELSON"))
    iso_week = date.today().isocalendar()[1]
    return f"{random.choice(templates)} // {suffix} WEEK {iso_week}"


def _load_cfg(config_file: Path) -> dict:
    import openpyxl
    wb = openpyxl.load_workbook(str(config_file), data_only=True)
    cfg: dict = {}
    for row in wb.active.iter_rows(max_col=2, values_only=True):
        k = str(row[0] or "").strip()
        v = str(row[1] or "").strip() if row[1] else ""
        if k and k.lower() != "key":
            cfg[k] = v
            cfg[k.upper()] = v
    return cfg


def _resolve_pol(raw_pol: str) -> list[str]:
    """
    Return list of POLs to query.
    If POL is blank / 'nan' → query both HPH and HCM.
    """
    cleaned = raw_pol.strip().upper()
    if not cleaned or cleaned in ("NAN", "NONE", "", "N/A"):
        return list(DEFAULT_POLS)  # both HPH + HCM
    return [cleaned]


# ─────────────────────────────────────────────────────────────────────────────
# UNIFIED VIEW
# ─────────────────────────────────────────────────────────────────────────────

class AutoRateView(ctk.CTkFrame):
    """
    Unified Rate & Send view.
    Toggle switch: AUTO RATE mode  ↔  CMD SEND mode
    """

    MODE_AUTO = "auto"   # build Parquet rate table per customer
    MODE_CMD  = "cmd"    # template email + auto Parquet table

    def __init__(self, parent, app: "AppWindow"):
        super().__init__(parent, fg_color="transparent")
        self.app  = app
        self._mode = self.MODE_AUTO
        self._results:    list[dict] = []
        self._customers:  list[dict] = []
        self._checkboxes: dict[int, ctk.BooleanVar] = {}
        self._build_ui()
        self._load_cmd_list()

    # ══════════════════════════════════════════════════════════
    # UI BUILD
    # ══════════════════════════════════════════════════════════

    def _build_ui(self):
        # ── Title row + mode toggle ───────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 10))

        self.title_label = ctk.CTkLabel(
            hdr, text="💰 Auto Rate Send",
            font=FONTS["heading"], text_color=COLORS["text_primary"], anchor="w",
        )
        self.title_label.pack(side="left")

        # Mode toggle (right side of header)
        tog = ctk.CTkFrame(hdr, fg_color=COLORS["bg_sidebar"], corner_radius=20)
        tog.pack(side="right")
        self.auto_btn = ctk.CTkButton(
            tog, text="💰 Auto Rate", font=FONTS["button"], width=130, height=32,
            corner_radius=16,
            fg_color=COLORS["accent_green"], text_color=COLORS["bg_dark"],
            hover_color="#2e7d5e",
            command=lambda: self._switch_mode(self.MODE_AUTO),
        )
        self.auto_btn.pack(side="left", padx=4, pady=4)
        self.cmd_toggle_btn = ctk.CTkButton(
            tog, text="📧 CMD Send", font=FONTS["button"], width=130, height=32,
            corner_radius=16,
            fg_color="transparent", text_color=COLORS["text_secondary"],
            hover_color=COLORS["bg_hover"],
            command=lambda: self._switch_mode(self.MODE_CMD),
        )
        self.cmd_toggle_btn.pack(side="left", padx=4, pady=4)

        # ── Controls row ──────────────────────────────────────
        ctrl = ctk.CTkFrame(self, fg_color=COLORS["bg_sidebar"], corner_radius=10)
        ctrl.pack(fill="x", pady=(0, 6))
        ci = ctk.CTkFrame(ctrl, fg_color="transparent")
        ci.pack(fill="x", padx=16, pady=10)

        ctk.CTkLabel(ci, text="Campaign:", font=FONTS["body_bold"],
                     text_color=COLORS["text_primary"]).pack(side="left", padx=(0, 8))
        self.cmd_var = ctk.StringVar(value="-- Select CMD --")
        self.cmd_menu = ctk.CTkOptionMenu(
            ci, variable=self.cmd_var, values=["Loading..."],
            width=200, font=FONTS["body"],
            fg_color=COLORS["bg_input"], button_color=COLORS["bg_card"],
        )
        self.cmd_menu.pack(side="left", padx=(0, 16))

        # Markup (Auto Rate only)
        self.markup_lbl = ctk.CTkLabel(ci, text="Markup $:", font=FONTS["body_bold"],
                                       text_color=COLORS["text_primary"])
        self.markup_lbl.pack(side="left", padx=(0, 6))
        self.markup_var = ctk.StringVar(value="20")
        self.markup_entry = ctk.CTkEntry(ci, textvariable=self.markup_var, width=60,
                                         font=FONTS["body"], fg_color=COLORS["bg_input"])
        self.markup_entry.pack(side="left", padx=(0, 16))

        self.load_btn = ctk.CTkButton(
            ci, text="🔍 Load Rates", font=FONTS["button"], width=140,
            fg_color=COLORS["accent_blue"], hover_color=COLORS["bg_hover"],
            command=self._on_load,
        )
        self.load_btn.pack(side="left", padx=(0, 8))

        self.action_btn = ctk.CTkButton(
            ci, text="👁 Preview & Approve", font=FONTS["button"], width=200,
            fg_color=COLORS["accent_green"], hover_color="#2e7d5e",
            command=self._on_action, state="disabled",
            text_color=COLORS["bg_dark"],
        )
        self.action_btn.pack(side="right")

        # ── Subject preview (auto) ────────────────────────────
        subj_row = ctk.CTkFrame(self, fg_color="transparent")
        subj_row.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(subj_row, text="Subject (auto):", font=FONTS["body_bold"],
                     text_color=COLORS["text_secondary"]).pack(side="left", padx=(0, 8))
        self.subject_label = ctk.CTkLabel(
            subj_row, text="— (rotates on each send)",
            font=FONTS["body"], text_color=COLORS["accent_yellow"], anchor="w",
        )
        self.subject_label.pack(side="left")

        # ── Summary label ─────────────────────────────────────
        self.summary_label = ctk.CTkLabel(
            self, text="Select a campaign and click Load.",
            font=FONTS["body"], text_color=COLORS["text_muted"], anchor="w",
        )
        self.summary_label.pack(fill="x", pady=(0, 4))

        # ── Progress bar (hidden until loading) ───────────────
        self.progress = ctk.CTkProgressBar(
            self, mode="indeterminate",
            fg_color=COLORS["bg_card"], progress_color=COLORS["accent_blue"],
        )

        # ── Table area ────────────────────────────────────────
        self.table_frame = ctk.CTkScrollableFrame(
            self, fg_color=COLORS["bg_sidebar"], corner_radius=10,
        )
        self.table_frame.pack(fill="both", expand=True, pady=(0, 6))

        self._build_table_header_auto()
        self._rows_container = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        self._rows_container.pack(fill="both", expand=True)

        # ── Detail preview (bottom) ───────────────────────────
        pf = ctk.CTkFrame(self, fg_color=COLORS["bg_sidebar"], corner_radius=10, height=120)
        pf.pack(fill="x")
        ctk.CTkLabel(pf, text="  Rate Detail Preview (click a row)",
                     font=FONTS["heading_small"], text_color=COLORS["accent_green"],
                     anchor="w").pack(fill="x", padx=12, pady=(6, 2))
        self.preview_text = ctk.CTkTextbox(
            pf, font=FONTS["mono"], height=72, fg_color="transparent",
            text_color=COLORS["text_secondary"], wrap="word",
        )
        self.preview_text.pack(fill="x", padx=12, pady=(0, 6))
        self.preview_text.insert("1.0", "Click a customer row to see matched routes & carriers.")
        self.preview_text.configure(state="disabled")

    def _build_table_header_auto(self):
        """Header columns for Auto Rate mode."""
        for w in self.table_frame.winfo_children():
            if isinstance(w, ctk.CTkFrame) and w != self._rows_container if hasattr(self, "_rows_container") else True:
                pass
        th = ctk.CTkFrame(self.table_frame, fg_color=COLORS["table_header"], height=36)
        th.pack(fill="x", pady=(0, 2))
        th.pack_propagate(False)
        self._select_all_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(th, variable=self._select_all_var, text="",
                        width=24, checkbox_width=18, checkbox_height=18,
                        command=self._toggle_all).pack(side="left", padx=(8, 4))
        cols = [("Company", 190), ("Email", 220), ("POL", 80),
                ("Routes", 70), ("Rates", 50), ("Destinations", 210)]
        for col, w in cols:
            ctk.CTkLabel(th, text=col, font=FONTS["body_bold"],
                         text_color=COLORS["text_primary"], width=w, anchor="w").pack(side="left", padx=4)

    def _build_table_header_cmd(self):
        """Header columns for CMD Send mode."""
        th = ctk.CTkFrame(self.table_frame, fg_color=COLORS["table_header"], height=36)
        th.pack(fill="x", pady=(0, 2))
        th.pack_propagate(False)
        self._select_all_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(th, variable=self._select_all_var, text="",
                        width=24, checkbox_width=18, checkbox_height=18,
                        command=self._toggle_all).pack(side="left", padx=(8, 4))
        cols = [("Company", 210), ("Email", 240), ("PIC", 120),
                ("POL", 80), ("Destinations", 200)]
        for col, w in cols:
            ctk.CTkLabel(th, text=col, font=FONTS["body_bold"],
                         text_color=COLORS["text_primary"], width=w, anchor="w").pack(side="left", padx=4)

    # ══════════════════════════════════════════════════════════
    # MODE SWITCH
    # ══════════════════════════════════════════════════════════

    def _switch_mode(self, mode: str):
        if mode == self._mode:
            return
        self._mode = mode
        self._clear_rows()
        self._results   = []
        self._customers = []

        # Clear table header (destroy all children of table_frame)
        for w in self.table_frame.winfo_children():
            w.destroy()

        if mode == self.MODE_AUTO:
            self.title_label.configure(text="💰 Auto Rate Send")
            self.load_btn.configure(text="🔍 Load Rates")
            self.action_btn.configure(text="👁 Preview & Approve", state="disabled")
            self.markup_lbl.pack(side="left", padx=(0, 6))
            self.markup_entry.pack(side="left", padx=(0, 16))
            self.auto_btn.configure(fg_color=COLORS["accent_green"],
                                    text_color=COLORS["bg_dark"])
            self.cmd_toggle_btn.configure(fg_color="transparent",
                                          text_color=COLORS["text_secondary"])
            self._build_table_header_auto()
        else:  # CMD
            self.title_label.configure(text="📧 CMD Send (Auto Rate Table)")
            self.load_btn.configure(text="📋 Load List")
            self.action_btn.configure(text="📧 Preview & Send", state="disabled")
            self.markup_lbl.pack_forget()
            self.markup_entry.pack_forget()
            self.cmd_toggle_btn.configure(fg_color=COLORS["accent_blue"],
                                          text_color=COLORS["bg_dark"])
            self.auto_btn.configure(fg_color="transparent",
                                    text_color=COLORS["text_secondary"])
            self._build_table_header_cmd()

        self._rows_container = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        self._rows_container.pack(fill="both", expand=True)
        self.summary_label.configure(
            text="Select a campaign and click Load.",
            text_color=COLORS["text_muted"],
        )

    # ══════════════════════════════════════════════════════════
    # CMD LIST LOADER
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

    # ══════════════════════════════════════════════════════════
    # LOAD DISPATCHER
    # ══════════════════════════════════════════════════════════

    def _on_load(self):
        if self._mode == self.MODE_AUTO:
            self._load_auto_rates()
        else:
            self._load_cmd_customers()

    def _on_action(self):
        if self._mode == self.MODE_AUTO:
            self._open_preview_auto()
        else:
            self._open_preview_cmd()

    # ══════════════════════════════════════════════════════════
    # AUTO RATE — Load & Worker
    # ══════════════════════════════════════════════════════════

    def _load_auto_rates(self):
        cmd = self.cmd_var.get()
        if not cmd or cmd.startswith(("-", "(")):
            return
        self._clear_rows()
        self._results = []
        self.load_btn.configure(state="disabled", text="⏳ Loading...")
        self.action_btn.configure(state="disabled")
        self.progress.pack(fill="x", pady=(0, 6))
        self.progress.start()
        self.summary_label.configure(
            text=f"Building rates for '{cmd}'…",
            text_color=COLORS["accent_blue"],
        )
        self.app.set_status_busy(f"Loading rates for {cmd}…")
        threading.Thread(target=self._worker_auto, args=(cmd,), daemon=True).start()

    def _worker_auto(self, cmd: str):
        try:
            core_dir = str(self.app.core_dir)
            if core_dir not in sys.path:
                sys.path.insert(0, core_dir)

            from auto_rate_builder import (
                _load_parquet, _load_port_map,
                _query_best_rates, _query_best_rates_multi_pol,
                _build_html_table, _plain_to_html,
                check_expiry_warnings, MARKUP_MIN,
            )

            # ── Step A: customer list ─────────────────────────
            data_file = self.app.project_root / "data.xlsx"
            raw = pd.read_excel(data_file)
            raw.columns = raw.columns.str.strip().str.upper()
            subset = raw[raw["CMD_NAME"] == cmd].copy()
            subset = subset[subset["CNEE_EMAIL"].notna()]
            subset["_email_norm"] = subset["CNEE_EMAIL"].astype(str).str.strip().str.lower()
            subset = subset[subset["_email_norm"].str.contains("@", na=False)]
            subset = subset.drop_duplicates(subset="_email_norm")

            if subset.empty:
                self.after(0, lambda: self._on_error("No valid emails in this CMD."))
                return

            # ── Step B: load Parquet ONCE ─────────────────────
            df_parquet = _load_parquet()
            port_map   = _load_port_map()
            markup     = float(self.markup_var.get() or 20)

            if df_parquet.empty:
                self.after(0, lambda: self._on_error(
                    "Parquet not found. Check Settings → Parquet path."))
                return

            # Pre-filter TOTAL charges + valid dates once
            charge_mask = df_parquet["Charge_Name"].astype(str).str.upper().str.contains(
                "TOTAL", na=False)
            df_total = df_parquet[charge_mask].copy()
            if "Exp" in df_total.columns:
                df_total["_exp_dt"] = pd.to_datetime(df_total["Exp"], errors="coerce")
                today_ts  = pd.Timestamp.now()
                valid_mask = df_total["_exp_dt"] >= today_ts
                df_valid  = df_total[valid_mask | df_total["_exp_dt"].isna()].copy()
            else:
                df_valid = df_total.copy()

            # ── Step C: per-customer query ────────────────────
            results = []
            total   = len(subset)

            for i, (_, row) in enumerate(subset.iterrows()):
                email   = str(row.get("CNEE_EMAIL", "")).strip()

                # FIX: POL nan → query both HPH + HCM
                raw_pol = str(row.get("POL", "")).strip()
                pol_list = _resolve_pol(raw_pol)

                raw_dst = row.get("DESTINATION")
                dest    = (str(raw_dst).strip()
                           if pd.notna(raw_dst) and str(raw_dst).strip().lower()
                           not in ("", "nan")
                           else DEFAULT_DESTS)

                pic     = str(row.get("CNEE_PIC",  "")).strip()
                company = str(row.get("CNEE_NAME", "")).strip()

                dest_codes = [d.strip().upper() for d in dest.split(",") if d.strip()]
                all_rows:  list[dict] = []
                detail:    list[dict] = []

                for pod_code in dest_codes:
                    city = port_map.get(pod_code, "")
                    if not city:
                        short = pod_code.lstrip("US")
                        city  = next((v for k, v in port_map.items()
                                      if short and short in k), "")
                    if not city:
                        continue

                    search = city.split(",")[0].strip()

                    # Multi-POL query
                    if len(pol_list) > 1:
                        best = _query_best_rates_multi_pol(
                            pol_list, search, df_valid, top_n=2)
                    else:
                        best = _query_best_rates(
                            pol_list[0], search, df_valid, top_n=2)

                    if best.empty:
                        continue

                    carriers = []
                    for _, rr in best.iterrows():
                        r20   = rr.get("rate_20")
                        r40   = rr.get("rate_40")
                        s20   = int(r20 + markup) if r20 and pd.notna(r20) else None
                        s40   = int(r40 + markup) if r40 and pd.notna(r40) else None
                        pol_used = str(rr.get("pol", pol_list[0]))
                        all_rows.append({
                            "pol":        pol_used,
                            "pod_code":   pod_code,
                            "place_name": city,
                            "carrier":    str(rr["carrier"]),
                            "rate_20":    s20,
                            "rate_40":    s40,
                            # Validity dates — pass raw Timestamps for _build_html_table
                            "exp":        rr.get("exp"),   # pd.Timestamp or NaT
                            "eff":        rr.get("eff"),   # pd.Timestamp or NaT
                        })
                        # Show expiry in detail panel if available
                        exp_raw = rr.get("exp")
                        exp_tag = ""
                        if exp_raw is not None:
                            try:
                                import pandas as _pd
                                if not _pd.isnull(exp_raw):
                                    exp_tag = _pd.Timestamp(exp_raw).strftime("%-d%b")
                            except Exception:
                                pass
                        carriers.append(
                            f"{str(rr['carrier'])} ({pol_used})"
                            + (f" exp:{exp_tag}" if exp_tag else "")
                        )

                    detail.append({"port": pod_code, "place": city,
                                   "carriers": carriers})

                html = _build_html_table(all_rows)
                expiry_info = check_expiry_warnings(all_rows)
                pol_display = "/".join(pol_list) if len(pol_list) > 1 else pol_list[0]
                results.append({
                    "email":   email,
                    "pic":     pic if pic and pic.lower() not in ("nan", "") else "Team",
                    "company": company,
                    "pol":     pol_display,
                    "dest":    dest,
                    "html":    html,
                    "routes":  len(detail),
                    "rates":   len(all_rows),
                    "detail":  detail,
                    "cmd":     cmd,
                    "expiry":  expiry_info,   # {block, warn_msg, expired, expiring}
                })

                if i % 10 == 0:
                    msg = f"Processing {i + 1}/{total}…"
                    self.after(0, lambda m=msg: self.summary_label.configure(text=m))

            self._results = results
            self.after(0, lambda: self._display_auto_results(results))

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.after(0, lambda: self._on_error(f"{e}\n{tb}"))

    # ══════════════════════════════════════════════════════════
    # AUTO RATE — Display
    # ══════════════════════════════════════════════════════════

    def _display_auto_results(self, results: list[dict]):
        self._stop_progress()
        self.load_btn.configure(state="normal", text="🔍 Load Rates")

        with_rates    = [r for r in results if r["routes"] > 0]
        without_rates = [r for r in results if r["routes"] == 0]

        self.summary_label.configure(
            text=(f"✓  {len(with_rates)} with rates  |  "
                  f"{len(without_rates)} without routes  |  "
                  f"Markup: ${self.markup_var.get()}  |  "
                  f"Select rows → Preview & Approve"),
            text_color=COLORS["accent_green"] if with_rates else COLORS["warning"],
        )

        try:
            cfg = _load_cfg(self.app.project_root / "data" / "config.xlsx")
            self.subject_label.configure(text=f'e.g. "{_gen_subject(cfg)}"')
        except Exception:
            pass

        for i, r in enumerate(with_rates + without_rates):
            self._add_row_auto(i, r)

        if with_rates:
            self.action_btn.configure(
                state="normal",
                text=f"👁 Preview & Approve ({len(with_rates)})",
            )
        self.app.set_status_done(
            f"Loaded: {len(with_rates)} matches / {len(results)} total")

    def _add_row_auto(self, idx: int, data: dict):
        has = data["routes"] > 0
        bg  = COLORS["table_row_even"] if idx % 2 == 0 else COLORS["table_row_odd"]
        tc  = COLORS["text_primary"] if has else COLORS["text_muted"]

        row = ctk.CTkFrame(self._rows_container, fg_color=bg, height=34, corner_radius=0)
        row.pack(fill="x", pady=1)
        row.pack_propagate(False)

        var = ctk.BooleanVar(value=has)
        self._checkboxes[idx] = var
        ctk.CTkCheckBox(row, variable=var, text="", width=24,
                        checkbox_width=18, checkbox_height=18,
                        command=self._update_action_count).pack(side="left", padx=(8, 4))

        for text, w in [
            (data["company"][:27], 190),
            (data["email"][:30],   220),
            (data["pol"],           80),
            (str(data["routes"]),   70),
            (str(data["rates"]),    50),
            (data["dest"][:28],    210),
        ]:
            ctk.CTkLabel(row, text=text, font=FONTS["small"],
                         text_color=tc, width=w, anchor="w").pack(side="left", padx=4)

        for child in row.winfo_children():
            if not isinstance(child, ctk.CTkCheckBox):
                child.bind("<Button-1>", lambda e, d=data: self._show_detail_auto(d))
        row.bind("<Button-1>", lambda e, d=data: self._show_detail_auto(d))

    def _show_detail_auto(self, data: dict):
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")
        lines = [
            f"  {data['company']}  <{data['email']}>",
            f"  POL: {data['pol']}  |  Routes matched: {data['routes']}  |  Rate rows: {data['rates']}",
            "",
        ]
        for d in data["detail"]:
            lines.append(
                f"  {d['port']:8s} ({d['place'][:22]:22s})  →  {', '.join(d['carriers'])}")
        if not data["detail"]:
            lines.append("  No matching rates — will use DEFAULT ports on send.")
        self.preview_text.insert("1.0", "\n".join(lines))
        self.preview_text.configure(state="disabled")

    # ══════════════════════════════════════════════════════════
    # AUTO RATE — Preview & Approve window
    # ══════════════════════════════════════════════════════════

    def _open_preview_auto(self):
        selected = self._get_selected_auto()
        if not selected:
            return
        try:
            cfg = _load_cfg(self.app.project_root / "data" / "config.xlsx")
        except Exception as e:
            self.app.set_status(f"Config error: {e}")
            return

        subject = _gen_subject(cfg)
        intro   = cfg.get("IntroText",   cfg.get("INTROTEXT",   ""))
        closing = cfg.get("ClosingText", cfg.get("CLOSINGTEXT", ""))
        sample  = selected[0]

        # ── Expiry check across ALL selected customers ────────
        from auto_rate_builder import check_expiry_warnings
        all_rate_rows = []
        for s in selected:
            # Collect all_rows from detail (we stored them in result dict)
            for d in s.get("detail", []):
                pass  # detail doesn't hold raw rows — use per-customer expiry
        # Aggregate expiry status from pre-computed expiry info
        any_blocked  = any(s.get("expiry", {}).get("block", False) for s in selected)
        any_expiring = any(s.get("expiry", {}).get("expiring") for s in selected)
        blocked_companies = [s["company"] for s in selected
                             if s.get("expiry", {}).get("block", False)]
        expiring_companies = [s["company"] for s in selected
                              if s.get("expiry", {}).get("expiring")]

        win = ctk.CTkToplevel(self)
        win.title("📧 Email Preview & Approve — Auto Rate")
        win.geometry("900x720")
        win.transient(self.winfo_toplevel())
        win.grab_set()

        hdr = ctk.CTkFrame(win, fg_color=COLORS["bg_sidebar"], corner_radius=0)
        hdr.pack(fill="x")
        hdr_color = COLORS["danger"] if any_blocked else COLORS["accent_green"]
        hdr_text  = (f"  ⛔ BLOCKED — {len(blocked_companies)} expired rate(s)"
                     if any_blocked
                     else f"  Previewing 1 of {len(selected)} emails  —  Approve to send all")
        ctk.CTkLabel(
            hdr, text=hdr_text,
            font=FONTS["heading_small"], text_color=hdr_color, anchor="w",
        ).pack(side="left", padx=16, pady=12)

        # ── Expiry warning banner (if needed) ─────────────────
        if any_blocked or any_expiring:
            warn_frame = ctk.CTkFrame(win, fg_color="#3b1010" if any_blocked else "#3b2a00",
                                      corner_radius=0)
            warn_frame.pack(fill="x")
            if any_blocked:
                warn_text = (f"⛔  EXPIRED RATES — cannot send until Parquet is refreshed.\n"
                             f"   Affected: {', '.join(blocked_companies[:5])}")
                warn_color = COLORS["danger"]
            else:
                warn_text = (f"⚠️  Rates expire TODAY for: {', '.join(expiring_companies[:5])}\n"
                             f"   Confirm with carrier before sending.")
                warn_color = COLORS["warning"]
            ctk.CTkLabel(warn_frame, text=warn_text, font=FONTS["small"],
                         text_color=warn_color, anchor="w", justify="left",
                         wraplength=860).pack(padx=16, pady=8)

        meta = ctk.CTkFrame(win, fg_color=COLORS["bg_card"], corner_radius=0)
        meta.pack(fill="x")
        for lbl, val in [
            ("To:",         f"{sample['company']}  <{sample['email']}>"),
            ("Subject:",    subject),
            ("POL:",        sample["pol"]),
            ("Markup:",     f"${self.markup_var.get()} / container"),
            ("Recipients:", f"{len(selected)} selected"),
        ]:
            r = ctk.CTkFrame(meta, fg_color="transparent")
            r.pack(fill="x", padx=16, pady=2)
            ctk.CTkLabel(r, text=lbl, font=FONTS["body_bold"],
                         text_color=COLORS["text_secondary"], width=90, anchor="w").pack(side="left")
            ctk.CTkLabel(r, text=val, font=FONTS["body"],
                         text_color=COLORS["text_primary"], anchor="w").pack(side="left")

        ctk.CTkLabel(win, text="  Rate Table Preview (first customer):",
                     font=FONTS["body_bold"], text_color=COLORS["text_secondary"],
                     anchor="w").pack(fill="x", padx=16, pady=(10, 2))

        body_box = ctk.CTkTextbox(win, font=FONTS["small"], fg_color=COLORS["bg_input"],
                                  text_color=COLORS["text_primary"], wrap="word")
        body_box.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        rate_lines = "\n".join(
            f"  {d['port']:8s} ({d['place'][:22]:22s}) → {', '.join(d['carriers'])}"
            for d in sample["detail"]
        ) or "  (No matching rates — using defaults)"

        body_box.insert("1.0",
            f"Dear {sample['pic']},\n\n"
            f"{intro}\n\n"
            f"[HTML RATE TABLE — {sample['routes']} route(s) — includes Eff/Exp columns]\n"
            f"{rate_lines}\n\n"
            f"--- CLOSING ---\n{closing}"
        )
        body_box.configure(state="disabled")

        bf = ctk.CTkFrame(win, fg_color=COLORS["bg_sidebar"], corner_radius=0)
        bf.pack(fill="x", side="bottom")
        ctk.CTkButton(bf, text="Cancel", width=120, font=FONTS["button"],
                      fg_color=COLORS["bg_card"], hover_color=COLORS["bg_hover"],
                      command=win.destroy).pack(side="left", padx=16, pady=12)

        # Block send if any expired rates
        if any_blocked:
            ctk.CTkLabel(bf,
                text="⛔ Refresh Parquet data before sending",
                font=FONTS["body_bold"], text_color=COLORS["danger"],
            ).pack(side="right", padx=16, pady=12)
        else:
            approve_text = (f"⚠️ Send Anyway ({len(selected)})"
                            if any_expiring
                            else f"✅ Approve & Send All ({len(selected)} emails)")
            approve_color = COLORS["warning"] if any_expiring else COLORS["accent"]
            ctk.CTkButton(
                bf,
                text=approve_text,
                width=300, font=FONTS["button"],
                fg_color=approve_color, hover_color="#c62828",
                command=lambda: self._approved_send_auto(win, selected, subject, cfg),
            ).pack(side="right", padx=16, pady=12)

    def _approved_send_auto(self, win, selected: list[dict], subject: str, cfg: dict):
        win.destroy()
        self.action_btn.configure(state="disabled", text="⏳ Sending…")
        self.app.set_status_busy(f"Sending {len(selected)} emails…")
        threading.Thread(
            target=self._send_worker_auto,
            args=(selected, subject, cfg), daemon=True,
        ).start()

    def _send_worker_auto(self, contacts: list[dict], subject: str, cfg: dict):
        try:
            import win32com.client
            from auto_rate_builder import _plain_to_html
            intro_raw   = cfg.get("IntroText",   cfg.get("INTROTEXT",   ""))
            closing_raw = cfg.get("ClosingText", cfg.get("CLOSINGTEXT", ""))
            sig         = cfg.get("Signature",   cfg.get("SIGNATURE",   ""))
            ph_pool     = cfg.get("Preheader",   cfg.get("PREHEADER",   "")).split("|")
            profile = self.app.project_root / "assets" / "PUDONG PRIME PROFILE.pdf"
            logo    = self.app.project_root / "assets" / "logo.png"
            log_f   = self.app.logs_dir / "email_log.csv"

            # Convert plain-text blocks to HTML once (shared across all emails)
            intro_html   = intro_raw   # IntroText is usually a short plain line
            closing_html = _plain_to_html(closing_raw)  # ClosingText has \n bullet points

            outlook  = win32com.client.Dispatch("Outlook.Application")
            campaign = f"AUTO_RATE_{datetime.now():%Y%m%d_%H%M}"
            sent = 0

            for c in contacts:
                this_subject = _gen_subject(cfg)
                ph = random.choice(ph_pool).strip() if ph_pool else ""
                ph_html = (
                    f'<span style="display:none!important;visibility:hidden;'
                    f'opacity:0;color:transparent;height:0;width:0;'
                    f'overflow:hidden;mso-hide:all;">{ph}</span>'
                )
                m = outlook.CreateItem(0)
                m.To = c["email"]
                m.Subject = this_subject
                if profile.exists():
                    m.Attachments.Add(str(profile))
                if logo.exists():
                    lg = m.Attachments.Add(str(logo))
                    lg.PropertyAccessor.SetProperty(
                        "http://schemas.microsoft.com/mapi/proptag/0x3712001F",
                        "pudonglogo")
                m.HTMLBody = (
                    f"<html><body>{ph_html}"
                    f"<p>Dear {c['pic']},</p>"
                    f"<p>{intro_html}</p>"
                    f"{c['html']}"
                    f"<br>"
                    f"{closing_html}"
                    f"<br>{sig}</body></html>"
                )
                m.Send()
                sent += 1

                exists = log_f.exists()
                with open(log_f, "a", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    if not exists:
                        w.writerow(["timestamp", "email", "subject",
                                    "campaign_id", "cycle_id", "status"])
                    w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                c["email"], this_subject, campaign, "1", "SENT"])

            self.after(0, lambda: self._send_done(sent, campaign))
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.after(0, lambda: self._on_error(f"Send error: {e}\n{tb}"))

    # ══════════════════════════════════════════════════════════
    # CMD SEND — Load customers
    # ══════════════════════════════════════════════════════════

    def _load_cmd_customers(self):
        cmd = self.cmd_var.get()
        if not cmd or cmd.startswith("-"):
            return
        self._clear_rows()
        self._customers = []
        self.load_btn.configure(state="disabled", text="⏳ Loading...")
        self.action_btn.configure(state="disabled")
        self.app.set_status_busy(f"Loading {cmd}…")
        threading.Thread(target=self._worker_cmd, args=(cmd,), daemon=True).start()

    def _worker_cmd(self, cmd: str):
        try:
            core_dir = str(self.app.core_dir)
            if core_dir not in sys.path:
                sys.path.insert(0, core_dir)

            data_file = self.app.project_root / "data.xlsx"
            raw = pd.read_excel(data_file)
            raw.columns = raw.columns.str.strip().str.upper()
            subset = raw[raw["CMD_NAME"] == cmd].copy()
            subset = subset[subset["CNEE_EMAIL"].notna()]
            subset = subset.drop_duplicates(subset="CNEE_EMAIL")

            # Load Parquet for rate table generation
            from auto_rate_builder import (
                _load_parquet, _load_port_map,
                _query_best_rates, _query_best_rates_multi_pol,
                _build_html_table, _plain_to_html,
                check_expiry_warnings, MARKUP_MIN,
            )
            df_parquet = _load_parquet()
            port_map   = _load_port_map()
            markup     = float(self.markup_var.get() or 20) if hasattr(self, "markup_var") else MARKUP_MIN

            parquet_ok = not df_parquet.empty
            if parquet_ok:
                charge_mask = df_parquet["Charge_Name"].astype(str).str.upper().str.contains(
                    "TOTAL", na=False)
                df_total = df_parquet[charge_mask].copy()
                if "Exp" in df_total.columns:
                    df_total["_exp_dt"] = pd.to_datetime(df_total["Exp"], errors="coerce")
                    today_ts = pd.Timestamp.now()
                    valid_mask = df_total["_exp_dt"] >= today_ts
                    df_valid = df_total[valid_mask | df_total["_exp_dt"].isna()].copy()
                else:
                    df_valid = df_total.copy()

            customers = []
            total = len(subset)

            for i, (_, row) in enumerate(subset.iterrows()):
                email   = str(row.get("CNEE_EMAIL", "")).strip()
                if not email or "@" not in email:
                    continue

                raw_pol  = str(row.get("POL", "")).strip()
                pol_list = _resolve_pol(raw_pol)
                pol_display = "/".join(pol_list) if len(pol_list) > 1 else pol_list[0]

                raw_dst = row.get("DESTINATION")
                dest    = (str(raw_dst).strip()
                           if pd.notna(raw_dst) and str(raw_dst).strip().lower()
                           not in ("", "nan")
                           else DEFAULT_DESTS)

                pic     = str(row.get("CNEE_PIC",  "")).strip()
                company = str(row.get("CNEE_NAME", "")).strip()

                # Build rate table from Parquet for this customer
                html = ""
                routes_found = 0
                if parquet_ok:
                    dest_codes = [d.strip().upper() for d in dest.split(",") if d.strip()]
                    all_rows: list[dict] = []
                    for pod_code in dest_codes:
                        city = port_map.get(pod_code, "")
                        if not city:
                            short = pod_code.lstrip("US")
                            city = next((v for k, v in port_map.items()
                                         if short and short in k), "")
                        if not city:
                            continue
                        search = city.split(",")[0].strip()
                        if len(pol_list) > 1:
                            best = _query_best_rates_multi_pol(
                                pol_list, search, df_valid, top_n=2)
                        else:
                            best = _query_best_rates(
                                pol_list[0], search, df_valid, top_n=2)
                        if best.empty:
                            continue
                        for _, rr in best.iterrows():
                            r20  = rr.get("rate_20")
                            r40  = rr.get("rate_40")
                            s20  = int(r20 + markup) if r20 and pd.notna(r20) else None
                            s40  = int(r40 + markup) if r40 and pd.notna(r40) else None
                            pol_used = str(rr.get("pol", pol_list[0]))
                            all_rows.append({
                                "pol":        pol_used,
                                "pod_code":   pod_code,
                                "place_name": city,
                                "carrier":    str(rr["carrier"]),
                                "rate_20":    s20,
                                "rate_40":    s40,
                            })
                        routes_found += 1
                    html = _build_html_table(all_rows)

                customers.append({
                    "email":        email,
                    "company":      company,
                    "pic":          pic if pic and pic.lower() not in ("nan", "") else "Team",
                    "pol":          pol_display,
                    "dest":         dest,
                    "cmd":          cmd,
                    "html":         html,
                    "routes_found": routes_found,
                })

                if i % 10 == 0:
                    msg = f"Loading {i + 1}/{total}…"
                    self.after(0, lambda m=msg: self.summary_label.configure(text=m))

            self._customers = customers
            self.after(0, lambda: self._display_cmd_results(customers))

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.after(0, lambda: self._on_error(f"{e}\n{tb}"))

    def _display_cmd_results(self, customers: list[dict]):
        self._stop_progress()
        self.load_btn.configure(state="normal", text="📋 Load List")

        with_rates = [c for c in customers if c["routes_found"] > 0]

        self.summary_label.configure(
            text=(f"✓  {len(customers)} contacts  |  "
                  f"{len(with_rates)} with auto rate table  |  "
                  f"Select rows → Preview & Send"),
            text_color=COLORS["accent_green"],
        )

        try:
            cfg = _load_cfg(self.app.project_root / "data" / "config.xlsx")
            self.subject_label.configure(text=f'e.g. "{_gen_subject(cfg)}"')
        except Exception:
            pass

        for i, c in enumerate(customers):
            self._add_row_cmd(i, c)

        if customers:
            self.action_btn.configure(
                state="normal",
                text=f"📧 Preview & Send ({len(customers)})",
            )
        self.app.set_status_done(f"Loaded {len(customers)} contacts")

    def _add_row_cmd(self, idx: int, data: dict):
        has_rate = data["routes_found"] > 0
        bg = COLORS["table_row_even"] if idx % 2 == 0 else COLORS["table_row_odd"]
        tc = COLORS["text_primary"]
        tag_color = COLORS["accent_green"] if has_rate else COLORS["warning"]

        row = ctk.CTkFrame(self._rows_container, fg_color=bg, height=34, corner_radius=0)
        row.pack(fill="x", pady=1)
        row.pack_propagate(False)

        var = ctk.BooleanVar(value=True)
        self._checkboxes[idx] = var
        ctk.CTkCheckBox(row, variable=var, text="", width=24,
                        checkbox_width=18, checkbox_height=18,
                        command=self._update_action_count).pack(side="left", padx=(8, 4))

        # Rate tag (✓ / --) at the end
        rate_tag = "✓ Rate" if has_rate else "-- No rate"
        for text, w in [
            (data["company"][:30], 210),
            (data["email"][:33],   240),
            (data["pic"][:16],     120),
            (data["pol"],           80),
            (data["dest"][:28],    200),
        ]:
            ctk.CTkLabel(row, text=text, font=FONTS["small"],
                         text_color=tc, width=w, anchor="w").pack(side="left", padx=4)
        ctk.CTkLabel(row, text=rate_tag, font=FONTS["small"],
                     text_color=tag_color, anchor="w").pack(side="left", padx=4)

        for child in row.winfo_children():
            if not isinstance(child, ctk.CTkCheckBox):
                child.bind("<Button-1>", lambda e, d=data: self._show_detail_cmd(d))
        row.bind("<Button-1>", lambda e, d=data: self._show_detail_cmd(d))

    def _show_detail_cmd(self, data: dict):
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")
        lines = [
            f"  {data['company']}  <{data['email']}>",
            f"  POL: {data['pol']}  |  Auto Rate Routes: {data['routes_found']}",
            f"  Dest: {data['dest'][:80]}",
        ]
        self.preview_text.insert("1.0", "\n".join(lines))
        self.preview_text.configure(state="disabled")

    # ══════════════════════════════════════════════════════════
    # CMD SEND — Preview & Send window
    # ══════════════════════════════════════════════════════════

    def _open_preview_cmd(self):
        selected = self._get_selected_cmd()
        if not selected:
            return
        try:
            cfg = _load_cfg(self.app.project_root / "data" / "config.xlsx")
        except Exception as e:
            self.app.set_status(f"Config error: {e}")
            return

        subject = _gen_subject(cfg)
        intro   = cfg.get("IntroText",   cfg.get("INTROTEXT",   ""))
        closing = cfg.get("ClosingText", cfg.get("CLOSINGTEXT", ""))
        sample  = selected[0]

        win = ctk.CTkToplevel(self)
        win.title("📧 Preview & Approve — CMD Send")
        win.geometry("900x680")
        win.transient(self.winfo_toplevel())
        win.grab_set()

        hdr = ctk.CTkFrame(win, fg_color=COLORS["bg_sidebar"], corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(
            hdr,
            text=f"  Previewing 1 of {len(selected)} emails  —  Approve to send all",
            font=FONTS["heading_small"], text_color=COLORS["accent_blue"], anchor="w",
        ).pack(side="left", padx=16, pady=12)

        meta = ctk.CTkFrame(win, fg_color=COLORS["bg_card"], corner_radius=0)
        meta.pack(fill="x")
        for lbl, val in [
            ("To:",        f"{sample['company']}  <{sample['email']}>"),
            ("Subject:",   subject),
            ("POL:",       sample["pol"]),
            ("Rate Table:", f"Auto-generated ({sample['routes_found']} routes)" if sample["routes_found"] > 0 else "No rates found (empty table)"),
            ("Recipients:", f"{len(selected)} selected"),
        ]:
            r = ctk.CTkFrame(meta, fg_color="transparent")
            r.pack(fill="x", padx=16, pady=2)
            ctk.CTkLabel(r, text=lbl, font=FONTS["body_bold"],
                         text_color=COLORS["text_secondary"], width=100, anchor="w").pack(side="left")
            ctk.CTkLabel(r, text=val, font=FONTS["body"],
                         text_color=COLORS["text_primary"], anchor="w").pack(side="left")

        ctk.CTkLabel(win, text="  Email Body Preview:",
                     font=FONTS["body_bold"], text_color=COLORS["text_secondary"],
                     anchor="w").pack(fill="x", padx=16, pady=(10, 2))

        box = ctk.CTkTextbox(win, font=FONTS["small"], fg_color=COLORS["bg_input"],
                             text_color=COLORS["text_primary"], wrap="word")
        box.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        rate_info = (f"[AUTO RATE TABLE — {sample['routes_found']} routes]"
                     if sample["routes_found"] > 0
                     else "[No rates available — empty table]")
        box.insert("1.0",
            f"Dear {sample['pic']},\n\n"
            f"{intro}\n\n"
            f"{rate_info}\n\n"
            f"{closing}"
        )
        box.configure(state="disabled")

        bf = ctk.CTkFrame(win, fg_color=COLORS["bg_sidebar"], corner_radius=0)
        bf.pack(fill="x", side="bottom")
        ctk.CTkButton(bf, text="Cancel", width=120, font=FONTS["button"],
                      fg_color=COLORS["bg_card"], hover_color=COLORS["bg_hover"],
                      command=win.destroy).pack(side="left", padx=16, pady=12)
        ctk.CTkButton(
            bf,
            text=f"✅ Approve & Send ({len(selected)} emails)",
            width=280, font=FONTS["button"],
            fg_color=COLORS["accent_blue"], hover_color="#1565c0",
            command=lambda: self._approved_send_cmd(win, selected, subject, cfg),
        ).pack(side="right", padx=16, pady=12)

    def _approved_send_cmd(self, win, selected: list[dict], subject: str, cfg: dict):
        win.destroy()
        self.action_btn.configure(state="disabled", text="⏳ Sending…")
        self.app.set_status_busy(f"Sending {len(selected)} emails…")
        threading.Thread(
            target=self._send_worker_cmd,
            args=(selected, subject, cfg), daemon=True,
        ).start()

    def _send_worker_cmd(self, contacts: list[dict], subject: str, cfg: dict):
        try:
            import win32com.client
            from auto_rate_builder import _plain_to_html
            intro_raw   = cfg.get("IntroText",   cfg.get("INTROTEXT",   ""))
            closing_raw = cfg.get("ClosingText", cfg.get("CLOSINGTEXT", ""))
            sig         = cfg.get("Signature",   cfg.get("SIGNATURE",   ""))
            ph_pool     = cfg.get("Preheader",   cfg.get("PREHEADER",   "")).split("|")
            profile = self.app.project_root / "assets" / "PUDONG PRIME PROFILE.pdf"
            logo    = self.app.project_root / "assets" / "logo.png"
            log_f   = self.app.logs_dir / "email_log.csv"

            intro_html   = intro_raw
            closing_html = _plain_to_html(closing_raw)

            outlook  = win32com.client.Dispatch("Outlook.Application")
            cmd_name = contacts[0].get("cmd", "CMD") if contacts else "CMD"
            campaign = f"CMD_{cmd_name}_{datetime.now():%Y%m%d_%H%M}"
            sent = 0

            for c in contacts:
                this_subject = _gen_subject(cfg)
                ph = random.choice(ph_pool).strip() if ph_pool else ""
                ph_html = (
                    f'<span style="display:none!important;visibility:hidden;'
                    f'opacity:0;color:transparent;height:0;width:0;'
                    f'overflow:hidden;mso-hide:all;">{ph}</span>'
                )
                # Use auto-generated Parquet table; fallback to config HTML
                rate_html = c.get("html", "")
                if not rate_html or rate_html.strip().startswith("<p><em>No rates"):
                    rate_html = cfg.get("RateTableHTML", cfg.get("RATETABLEHTML", ""))

                m = outlook.CreateItem(0)
                m.To = c["email"]
                m.Subject = this_subject
                if profile.exists():
                    m.Attachments.Add(str(profile))
                if logo.exists():
                    lg = m.Attachments.Add(str(logo))
                    lg.PropertyAccessor.SetProperty(
                        "http://schemas.microsoft.com/mapi/proptag/0x3712001F",
                        "pudonglogo")
                m.HTMLBody = (
                    f"<html><body>{ph_html}"
                    f"<p>Dear {c['pic']},</p>"
                    f"<p>{intro_html}</p>"
                    f"{rate_html}"
                    f"<br>"
                    f"{closing_html}"
                    f"<br>{sig}</body></html>"
                )
                m.Send()
                sent += 1

                exists = log_f.exists()
                with open(log_f, "a", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    if not exists:
                        w.writerow(["timestamp", "email", "subject",
                                    "campaign_id", "cycle_id", "status"])
                    w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                c["email"], this_subject, campaign, "1", "SENT"])

            self.after(0, lambda: self._send_done(sent, campaign))
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.after(0, lambda: self._on_error(f"Send error: {e}\n{tb}"))

    # ══════════════════════════════════════════════════════════
    # SHARED SEND DONE / ERROR
    # ══════════════════════════════════════════════════════════

    def _send_done(self, count: int, campaign: str):
        self.action_btn.configure(state="normal",
                                  text="👁 Preview & Approve" if self._mode == self.MODE_AUTO
                                  else "📧 Preview & Send")
        self.app.set_status_done(f"✓ {count} emails sent — {campaign}")
        dlg = ctk.CTkToplevel(self)
        dlg.title("Sent")
        dlg.geometry("340x130")
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()
        ctk.CTkLabel(dlg, text=f"✓ {count} emails sent!",
                     font=FONTS["heading"]).pack(pady=(20, 4))
        ctk.CTkLabel(dlg, text=campaign, font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(pady=(0, 12))
        ctk.CTkButton(dlg, text="OK", width=80, command=dlg.destroy).pack()

    def _on_error(self, msg: str):
        self._stop_progress()
        self.load_btn.configure(
            state="normal",
            text="🔍 Load Rates" if self._mode == self.MODE_AUTO else "📋 Load List",
        )
        self.action_btn.configure(state="disabled")
        self.summary_label.configure(text=f"❌ {msg[:120]}",
                                     text_color=COLORS["danger"])
        self.app.set_status(f"Error: {msg[:80]}")

    def _stop_progress(self):
        self.progress.stop()
        self.progress.pack_forget()

    # ══════════════════════════════════════════════════════════
    # CHECKBOX HELPERS
    # ══════════════════════════════════════════════════════════

    def _get_selected_auto(self) -> list[dict]:
        with_rates = [r for r in self._results if r["routes"] > 0]
        no_rates   = [r for r in self._results if r["routes"] == 0]
        ordered = with_rates + no_rates
        return [ordered[i] for i, v in self._checkboxes.items()
                if v.get() and i < len(ordered) and ordered[i]["routes"] > 0]

    def _get_selected_cmd(self) -> list[dict]:
        return [self._customers[i] for i, v in self._checkboxes.items()
                if v.get() and i < len(self._customers)]

    def _toggle_all(self):
        val = self._select_all_var.get()
        for v in self._checkboxes.values():
            v.set(val)
        self._update_action_count()

    def _update_action_count(self):
        if self._mode == self.MODE_AUTO:
            n = len(self._get_selected_auto())
            self.action_btn.configure(
                text=f"👁 Preview & Approve ({n})" if n > 0 else "👁 Preview & Approve",
                state="normal" if n > 0 else "disabled",
            )
        else:
            n = len(self._get_selected_cmd())
            self.action_btn.configure(
                text=f"📧 Preview & Send ({n})" if n > 0 else "📧 Preview & Send",
                state="normal" if n > 0 else "disabled",
            )

    def _clear_rows(self):
        if hasattr(self, "_rows_container"):
            for w in self._rows_container.winfo_children():
                w.destroy()
        self._checkboxes.clear()
