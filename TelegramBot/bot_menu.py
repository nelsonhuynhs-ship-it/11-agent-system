# -*- coding: utf-8 -*-
"""
bot_menu.py — Professional Multi-Level Menu UI System
======================================================
SaaS-grade hierarchical InlineKeyboard menu for Nelson Freight Bot.
Designed for mobile-first UX with clean categories and minimal clicks.

Architecture:
  /menu → Main Menu (6 categories)
       → Sub-menu per category (inline buttons → triggers command)
       → ⬅ Back always returns to main menu

Each button triggers a callback_query that either:
  1. Opens a sub-menu (category buttons)
  2. Executes a command (leaf buttons)
  3. Returns to main menu (back button)

Usage:
    from bot_menu import register_menu_handlers
    register_menu_handlers(app)
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler, CallbackQueryHandler, ContextTypes
)

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# MENU STRUCTURE
# ══════════════════════════════════════════════════════════════════════════════

MAIN_MENU_TEXT = (
    "🚢 *NELSON FREIGHT — Command Center*\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "Chọn chức năng bên dưới:"
)

MAIN_MENU_BUTTONS = [
    [
        InlineKeyboardButton("💰 Pricing", callback_data="menu_pricing"),
        InlineKeyboardButton("👥 Customers", callback_data="menu_customers"),
    ],
    [
        InlineKeyboardButton("📋 ERP & Jobs", callback_data="menu_erp"),
        InlineKeyboardButton("📊 KPI & Reports", callback_data="menu_kpi"),
    ],
    [
        InlineKeyboardButton("🧠 AI Brain", callback_data="menu_ai"),
        InlineKeyboardButton("⚙️ System", callback_data="menu_system"),
    ],
]

# ── Sub-menu definitions ─────────────────────────────────────────────────────

SUBMENUS = {
    "menu_pricing": {
        "title": (
            "💰 *PRICING*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Tra giá, báo giá, dự đoán giá tối ưu"
        ),
        "buttons": [
            [
                InlineKeyboardButton("🔍 Tra giá /quote", callback_data="cmd_quote"),
                InlineKeyboardButton("📧 Booking Email", callback_data="cmd_book"),
            ],
            [
                InlineKeyboardButton("🧠 AI Đề xuất giá", callback_data="cmd_predict"),
                InlineKeyboardButton("🛡️ Rate Guardian", callback_data="cmd_guardian"),
            ],
            [
                InlineKeyboardButton("💡 Hỏi giá (NL)", callback_data="cmd_ask"),
            ],
            [
                InlineKeyboardButton("⬅ Menu chính", callback_data="menu_main"),
            ],
        ],
    },

    "menu_customers": {
        "title": (
            "👥 *CUSTOMERS*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Quản lý khách hàng, profile, memory"
        ),
        "buttons": [
            [
                InlineKeyboardButton("📊 Intel 360°", callback_data="cmd_intel"),
                InlineKeyboardButton("🏢 CRM Profile", callback_data="cmd_crm"),
            ],
            [
                InlineKeyboardButton("📝 Lưu rule", callback_data="cmd_remember"),
                InlineKeyboardButton("📋 DS Khách", callback_data="cmd_customers"),
            ],
            [
                InlineKeyboardButton("📣 Churn Alert", callback_data="cmd_reachout"),
                InlineKeyboardButton("⚡ Risk Check", callback_data="cmd_risk"),
            ],
            [
                InlineKeyboardButton("⬅ Menu chính", callback_data="menu_main"),
            ],
        ],
    },

    "menu_erp": {
        "title": (
            "📋 *ERP & JOBS*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Quản lý quotes, jobs, booking"
        ),
        "buttons": [
            [
                InlineKeyboardButton("🚢 Active Jobs", callback_data="cmd_jobs"),
                InlineKeyboardButton("📜 Quotes", callback_data="cmd_quotes"),
            ],
            [
                InlineKeyboardButton("✅ Wins", callback_data="cmd_wins"),
                InlineKeyboardButton("❌ Losses", callback_data="cmd_losses"),
            ],
            [
                InlineKeyboardButton("📖 History", callback_data="cmd_history"),
                InlineKeyboardButton("🔍 Why Won?", callback_data="cmd_whywon"),
            ],
            [
                InlineKeyboardButton("⬅ Menu chính", callback_data="menu_main"),
            ],
        ],
    },

    "menu_kpi": {
        "title": (
            "📊 *KPI & REPORTS*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Theo dõi hiệu suất, báo cáo, dự báo"
        ),
        "buttons": [
            [
                InlineKeyboardButton("☀️ Briefing", callback_data="cmd_briefing"),
                InlineKeyboardButton("📊 Report", callback_data="cmd_report"),
            ],
            [
                InlineKeyboardButton("🎯 KPI", callback_data="cmd_kpi"),
                InlineKeyboardButton("🔮 Forecast", callback_data="cmd_forecast"),
            ],
            [
                InlineKeyboardButton("📈 Pipeline", callback_data="cmd_pipeline"),
                InlineKeyboardButton("🔬 Analyze", callback_data="cmd_analyze"),
            ],
            [
                InlineKeyboardButton("⬅ Menu chính", callback_data="menu_main"),
            ],
        ],
    },

    "menu_ai": {
        "title": (
            "🧠 *AI BRAIN*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Trí tuệ nhân tạo — dự đoán, phân tích, tự động hóa"
        ),
        "buttons": [
            [
                InlineKeyboardButton("🧠 Predict Price", callback_data="cmd_predict"),
                InlineKeyboardButton("🔍 Why Won/Lost", callback_data="cmd_whywon"),
            ],
            [
                InlineKeyboardButton("📣 Churn Alert", callback_data="cmd_reachout"),
                InlineKeyboardButton("⚡ Risk Check", callback_data="cmd_risk"),
            ],
            [
                InlineKeyboardButton("📊 Intel 360°", callback_data="cmd_intel"),
                InlineKeyboardButton("💬 Hỏi Data", callback_data="cmd_ask"),
            ],
            [
                InlineKeyboardButton("🔄 Sync Data", callback_data="cmd_sync"),
                InlineKeyboardButton("🛡️ Guardian", callback_data="cmd_guardian"),
            ],
            [
                InlineKeyboardButton("⬅ Menu chính", callback_data="menu_main"),
            ],
        ],
    },

    "menu_system": {
        "title": (
            "⚙️ *SYSTEM*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Hệ thống, reload data, markup"
        ),
        "buttons": [
            [
                InlineKeyboardButton("📊 Status", callback_data="cmd_status"),
                InlineKeyboardButton("🔄 Reload", callback_data="cmd_reload"),
            ],
            [
                InlineKeyboardButton("💵 Markup", callback_data="cmd_markup"),
                InlineKeyboardButton("🔄 Sync Lake", callback_data="cmd_sync"),
            ],
            [
                InlineKeyboardButton("❓ Help", callback_data="cmd_help"),
            ],
            [
                InlineKeyboardButton("⬅ Menu chính", callback_data="menu_main"),
            ],
        ],
    },
}

# ── Command info: what to show when a button needs arguments ─────────────────

CMD_PROMPTS = {
    "cmd_quote":     ("🔍 *Tra giá*\nGõ lệnh:\n`/quote HPH DENVER`\n`/quote HPH LAX SOC`\n`/quote HCM CHICAGO 40HQ`", True),
    "cmd_book":      ("📧 *Booking Email*\nGõ lệnh:\n`/book QUOTE_ID`\nVD: `/book 10MAR-5`", True),
    "cmd_predict":   ("🧠 *AI Predict*\nGõ lệnh:\n`/predict HPH Denver HML`\n`/predict HPH Atlanta SIRI`", True),
    "cmd_intel":     ("📊 *Customer Intel*\nGõ lệnh:\n`/intel HML`\n`/intel SIRI`", True),
    "cmd_crm":       ("🏢 *CRM Profile*\nGõ lệnh:\n`/crm PANDA`\n`/crm HML`", True),
    "cmd_remember":  ("📝 *Lưu Rule*\nGõ lệnh:\n`/remember PANDA no ZIM`\n`/remember SIRI prefer CMA ONE`", True),
    "cmd_history":   ("📖 *Quote History*\nGõ lệnh:\n`/history HML`\n`/history SIRI`", True),
    "cmd_whywon":    ("🔍 *Why Won/Lost*\nGõ lệnh:\n`/whywon QUOTE_ID`\nVD: `/whywon 10MAR-5`", True),
    "cmd_risk":      ("⚡ *Risk Check*\nGõ lệnh:\n`/risk HML`\n`/risk SIRI`", True),
    "cmd_ask":       ("💬 *Hỏi Data*\nGõ lệnh:\n`/ask Carrier nào margin cao nhất?`\n`/ask Giá Denver đang thế nào?`", True),
    "cmd_report":    ("📊 *Report*\nGõ lệnh:\n`/report` (tháng hiện tại)\n`/report 2026-03`", True),
}

# Commands that can run directly without arguments
CMD_DIRECT = {
    "cmd_status":    "/status",
    "cmd_reload":    "/reload",
    "cmd_help":      "/help",
    "cmd_briefing":  "/briefing",
    "cmd_kpi":       "/kpi",
    "cmd_forecast":  "/forecast",
    "cmd_pipeline":  "/pipeline",
    "cmd_analyze":   "/analyze",
    "cmd_jobs":      "/jobs",
    "cmd_quotes":    "/quotes",
    "cmd_wins":      "/wins",
    "cmd_losses":    "/losses",
    "cmd_customers": "/customers",
    "cmd_guardian":  "/guardian",
    "cmd_reachout":  "/reachout",
    "cmd_sync":      "/sync",
    "cmd_markup":    "/markup",
}


# ══════════════════════════════════════════════════════════════════════════════
# HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/menu — Show the main command center."""
    keyboard = InlineKeyboardMarkup(MAIN_MENU_BUTTONS)
    await update.message.reply_text(
        MAIN_MENU_TEXT,
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all inline keyboard button presses."""
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    data = query.data

    # ── Main menu ─────────────────────────────────────────────────────────
    if data == "menu_main":
        keyboard = InlineKeyboardMarkup(MAIN_MENU_BUTTONS)
        await query.edit_message_text(
            MAIN_MENU_TEXT,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
        return

    # ── Sub-menu navigation ───────────────────────────────────────────────
    if data in SUBMENUS:
        submenu = SUBMENUS[data]
        keyboard = InlineKeyboardMarkup(submenu["buttons"])
        await query.edit_message_text(
            submenu["title"],
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
        return

    # ── Command execution: needs arguments → show prompt ──────────────────
    if data in CMD_PROMPTS:
        prompt_text, needs_args = CMD_PROMPTS[data]
        back_btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅ Menu chính", callback_data="menu_main")]
        ])
        await query.edit_message_text(
            prompt_text,
            reply_markup=back_btn,
            parse_mode="Markdown",
        )
        return

    # ── Command execution: no arguments → run directly ────────────────────
    if data in CMD_DIRECT:
        cmd = CMD_DIRECT[data]
        back_btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅ Menu chính", callback_data="menu_main")]
        ])
        await query.edit_message_text(
            f"⏳ Đang chạy `{cmd}`...",
            reply_markup=back_btn,
            parse_mode="Markdown",
        )
        # Send the command as a new message to trigger the handler
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=cmd,
        )
        return

    # ── Unknown callback ──────────────────────────────────────────────────
    logger.warning(f"[Menu] Unknown callback: {data}")


# ══════════════════════════════════════════════════════════════════════════════
# REGISTRATION
# ══════════════════════════════════════════════════════════════════════════════

def register_menu_handlers(app):
    """
    Register menu command and callback handler.
    Call this from bot_v5.py main() after other handlers.
    """
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CallbackQueryHandler(handle_menu_callback))
    logger.info("[Menu] Registered /menu + callback handler")
