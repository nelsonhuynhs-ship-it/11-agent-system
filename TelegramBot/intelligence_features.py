# -*- coding: utf-8 -*-
"""
intelligence_features.py — Bot handlers for Email Intelligence Features
========================================================================
Exposes 10 Email Intelligence Features as Telegram bot commands.

Active commands:
  /trouble          → Feature #3 Carrier Trouble Index
  /route            → Feature #5 Route Health Map
  /churn            → Feature #1 Churn Radar (via ai_sales_intel + fallback)
  /risk [customer]  → Feature #3+ Multi-dimensional Risk Assessment
  /intel [customer] → Feature #9 Customer 360° Intelligence Card
  /intelligence     → Overview dashboard
  /custintel        → Customer summary

Future phases:
  /ghost, /dna, /commit, /market, /relationship, /coach

Usage:
    from intelligence_features import register_intelligence_handlers
    register_intelligence_handlers(app)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from email_analytics import (
    EmailAnalytics,
    format_trouble_index,
    format_route_health,
    format_customer_summary,
)

log = logging.getLogger(__name__)

# Singleton analytics instance (reloads each command for fresh data)
_analytics: EmailAnalytics | None = None


def _get_analytics() -> EmailAnalytics:
    """Get or create analytics instance."""
    global _analytics
    if _analytics is None:
        _analytics = EmailAnalytics()
    else:
        _analytics.reload()  # Reload fresh data each time
    return _analytics


# =============================================================================
# /trouble — Feature #3: Carrier Trouble Index
# =============================================================================

async def cmd_trouble(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /trouble          → All carriers ranked by trouble index
    /trouble ONE      → Filter for ONE carrier
    """
    try:
        analytics = _get_analytics()
        results = analytics.carrier_trouble_index()

        args = context.args
        if args:
            carrier_filter = " ".join(args).upper()
            results = [r for r in results if carrier_filter in r["carrier"].upper()]

        if not results:
            carrier_msg = f" cho '{' '.join(args)}'" if args else ""
            await update.message.reply_text(
                f"📊 Không tìm thấy dữ liệu carrier{carrier_msg}.\n"
                f"💡 Thử: /trouble (tất cả) hoặc /trouble ONE"
            )
            return

        output = format_trouble_index(results)
        await update.message.reply_text(output, parse_mode="HTML")

    except Exception as e:
        log.error("Error in /trouble: %s", e)
        await update.message.reply_text(f"❌ Lỗi phân tích: {e}")


# =============================================================================
# /route — Feature #5: Route Health Map
# =============================================================================

async def cmd_route(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /route               → All routes ranked by shipment count
    /route HCM           → Filter by POL
    /route HCM SEATTLE   → Filter by POL + Place
    """
    try:
        analytics = _get_analytics()

        args = context.args
        pol = None
        place = None

        if args:
            if len(args) >= 2:
                pol = args[0]
                place = " ".join(args[1:])
            else:
                arg = args[0].upper()
                if arg in ("HCM", "HPH", "SGN", "DAD", "HAN"):
                    pol = arg
                else:
                    place = arg

        results = analytics.route_health_map(pol=pol, place=place)

        if not results:
            filter_msg = ""
            if pol:
                filter_msg += f" POL={pol}"
            if place:
                filter_msg += f" Place={place}"
            await update.message.reply_text(
                f"📊 Không tìm thấy route{filter_msg}.\n"
                f"💡 Thử: /route (tất cả) hoặc /route HCM hoặc /route HCM SEATTLE"
            )
            return

        output = format_route_health(results)
        await update.message.reply_text(output, parse_mode="HTML")

    except Exception as e:
        log.error("Error in /route: %s", e)
        await update.message.reply_text(f"❌ Lỗi phân tích: {e}")


# =============================================================================
# /churn — Feature #1: Churn Radar
# =============================================================================

async def cmd_churn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /churn → Churn Radar — phát hiện khách có nguy cơ rời bỏ.

    Strategy:
      1. Try ai_sales_intel.SalesIntelligence (needs DataLake)
      2. Fallback: analyze shipment_state.json directly
    """
    try:
        churn_output = None

        # ── Strategy 1: Use existing ai_sales_intel if DataLake ready ────────
        try:
            from data_lake import get_lake
            from ai_sales_intel import SalesIntelligence

            lake = get_lake()
            if lake.is_ready:
                si = SalesIntelligence(lake)
                # Get all known customers from analytics
                analytics = _get_analytics()
                customers = analytics.customer_summary()
                customer_codes = [c["customer"] for c in customers]

                churn_list = si.detect_churn(customer_codes)
                churn_output = si.format_reachout_list(churn_list)
                log.info("[Churn] Used ai_sales_intel with DataLake")
        except Exception as e:
            log.debug("[Churn] DataLake not ready, using fallback: %s", e)

        # ── Strategy 2: Fallback — analyze shipment_state.json directly ──────
        if churn_output is None:
            analytics = _get_analytics()
            customers = analytics.customer_summary()

            if not customers:
                await update.message.reply_text(
                    "📊 Không có dữ liệu khách hàng để phân tích churn."
                )
                return

            now = datetime.now()
            at_risk = []

            for c in customers:
                last_str = c.get("last_shipment", "")
                if not last_str:
                    continue
                try:
                    last_dt = datetime.strptime(last_str, "%Y-%m-%d")
                    days_since = (now - last_dt).days
                    months_active = c.get("months_active", 1) or 1
                    avg_interval = (months_active * 30) / max(c["shipments"], 1)

                    # Churn ratio: how overdue vs their normal pattern
                    churn_ratio = days_since / avg_interval if avg_interval > 0 else 0

                    if churn_ratio >= 1.2:  # 20%+ overdue
                        level = (
                            "CRITICAL" if churn_ratio >= 2.0 else
                            "HIGH" if churn_ratio >= 1.5 else
                            "MEDIUM"
                        )
                        at_risk.append({
                            "customer": c["customer"],
                            "days_since": days_since,
                            "avg_interval": round(avg_interval),
                            "churn_ratio": round(churn_ratio, 2),
                            "shipments": c["shipments"],
                            "profit": c["total_profit"],
                            "level": level,
                        })
                except (ValueError, TypeError):
                    continue

            at_risk.sort(key=lambda x: x["churn_ratio"], reverse=True)

            if not at_risk:
                churn_output = (
                    "✅ <b>CHURN RADAR</b>\n\n"
                    "Tất cả khách hàng đang active. Không phát hiện churn risk.\n\n"
                    f"📊 Analyzed: {len(customers)} customers"
                )
            else:
                icons = {"CRITICAL": "🔴", "HIGH": "🟡", "MEDIUM": "🟢"}
                lines = [
                    "🔮 <b>CHURN RADAR</b>",
                    f"<i>Phát hiện {len(at_risk)} khách có nguy cơ churn</i>",
                    "",
                ]
                for c in at_risk[:8]:
                    icon = icons.get(c["level"], "⚪")

                    # Memory-powered trend indicator
                    trend_str = ""
                    try:
                        import sys
                        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "email_engine"))
                        from memory_writer import get_customer_trend
                        trend = get_customer_trend(c["customer"], periods=3)
                        if trend:
                            arrows = {"UP": "📈", "STABLE": "➡️", "DOWN": "📉"}
                            freqs = trend.get("frequency_trend", [])
                            if freqs:
                                latest = freqs[-1]
                                trend_str = f" {arrows.get(latest, '')} {latest}"
                    except Exception:
                        pass

                    lines.append(
                        f"{icon} <b>{c['level']}</b> — {c['customer']}{trend_str}\n"
                        f"   {c['days_since']} ngày chưa ship "
                        f"(avg: {c['avg_interval']} ngày)\n"
                        f"   📦 {c['shipments']} lô | "
                        f"💰 ${c['profit']:,.0f} profit"
                    )

                lines.extend([
                    "",
                    "🎯 <b>Actions:</b>",
                    "  → Gửi proactive offer cho CRITICAL + HIGH",
                    "  → Dùng /intel CUSTOMER để xem chi tiết",
                    "  → Dùng /risk CUSTOMER để check risk",
                ])
                churn_output = "\n".join(lines)

            log.info("[Churn] Used shipment_state fallback")

        await update.message.reply_text(churn_output, parse_mode="HTML")

    except Exception as e:
        log.error("Error in /churn: %s", e)
        await update.message.reply_text(f"❌ Lỗi phân tích churn: {e}")


# =============================================================================
# /risk — Feature #3+: Multi-Dimensional Risk Assessment
# =============================================================================

async def cmd_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /risk [customer] → 4-dimension risk assessment: weight/rate/space/payment
    """
    try:
        args = context.args
        if not args:
            await update.message.reply_text(
                "⚡ <b>RISK ASSESSMENT</b>\n\n"
                "Usage: /risk CUSTOMER_NAME\n\n"
                "Ví dụ:\n"
                "  /risk HML\n"
                "  /risk PANDA\n"
                "  /risk SIRI\n\n"
                "Phân tích 4 chiều:\n"
                "  ⚖️ Weight Risk\n"
                "  ⏰ Rate Expiry Risk\n"
                "  🚢 Space Risk\n"
                "  💳 Payment Risk",
                parse_mode="HTML",
            )
            return

        customer = " ".join(args).upper()

        try:
            from ai_risk_engine import RiskEngine
            from query_engine import load_parquet_data

            parquet_df = load_parquet_data()
            re = RiskEngine(parquet_df=parquet_df)
            assessment = re.assess_customer(customer)
            output = re.format_risk_card(assessment)
            await update.message.reply_text(output)
            log.info("[Risk] Assessed %s via ai_risk_engine", customer)
            return

        except Exception as e:
            log.warning("[Risk] ai_risk_engine failed for %s: %s", customer, e)

        # ── Fallback: simple risk from shipment_state ────────────────────────
        analytics = _get_analytics()
        cust_data = None
        for c in analytics.customer_summary():
            if customer in c["customer"].upper():
                cust_data = c
                break

        if not cust_data:
            await update.message.reply_text(
                f"⚠️ Không tìm thấy khách hàng '{customer}'.\n"
                f"💡 Thử: /custintel để xem danh sách"
            )
            return

        # Basic risk from shipment data
        risk_count = cust_data.get("risk_count", 0)
        shipments = cust_data["shipments"]
        risk_rate = risk_count / shipments if shipments > 0 else 0

        if risk_rate >= 0.5:
            level, icon = "HIGH", "🔴"
        elif risk_rate >= 0.25:
            level, icon = "MEDIUM", "🟡"
        else:
            level, icon = "LOW", "🟢"

        output = (
            f"⚡ RISK ASSESSMENT — {cust_data['customer']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Overall: {icon} {level}\n\n"
            f"📦 Shipments: {shipments}\n"
            f"⚠️ Risk events: {risk_count} ({risk_rate:.0%})\n"
            f"💰 Total profit: ${cust_data['total_profit']:,.0f}\n"
            f"📍 Routes: {', '.join(cust_data.get('top_routes', []))}\n"
            f"🚢 Carriers: {', '.join(cust_data.get('top_carriers', []))}\n"
            f"\n💡 Dùng full risk engine khi ERP data sẵn sàng (/sync)"
        )
        await update.message.reply_text(output)

    except Exception as e:
        log.error("Error in /risk: %s", e)
        await update.message.reply_text(f"❌ Lỗi risk assessment: {e}")


# =============================================================================
# /intel — Feature #9: Customer 360° Intelligence Card
# =============================================================================

async def cmd_intel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /intel [customer] → 360° Customer Intelligence Card
    """
    try:
        args = context.args
        if not args:
            # Show top customers overview
            analytics = _get_analytics()
            customers = analytics.customer_summary()

            lines = [
                "🔍 <b>CUSTOMER INTELLIGENCE</b>",
                "",
                "Usage: /intel CUSTOMER_NAME",
                "",
                "<b>Top customers:</b>",
            ]
            for c in customers[:10]:
                lines.append(
                    f"  • <b>{c['customer']}</b> — {c['shipments']} lô | "
                    f"${c['total_profit']:,.0f}"
                )
            lines.append("\nVí dụ: /intel HML hoặc /intel PANDA")
            await update.message.reply_text("\n".join(lines), parse_mode="HTML")
            return

        customer = " ".join(args).upper()

        # ── Try full intel card from customer_intelligence.py ────────────────
        try:
            from customer_intelligence import build_intel_card
            from erp_reader import get_quotes_history, get_active_jobs, get_crm_profile
            from customer_profiles import get_profile
            from query_engine import load_parquet_data

            crm = get_crm_profile(customer) or {}
            quotes = get_quotes_history(customer_name=customer)
            jobs = get_active_jobs(customer_name=customer)
            parquet_df = load_parquet_data()
            static_profile = get_profile(customer)

            card = build_intel_card(
                customer_name=customer,
                crm_profile=crm,
                quote_history=quotes,
                active_jobs=jobs,
                parquet_df=parquet_df,
                static_profile=static_profile,
            )
            await update.message.reply_text(card)
            log.info("[Intel] Full card for %s via customer_intelligence", customer)
            return

        except Exception as e:
            log.warning("[Intel] Full intel card failed for %s: %s", customer, e)

        # ── Fallback: build card from shipment_state ─────────────────────────
        analytics = _get_analytics()
        cust_data = None
        for c in analytics.customer_summary():
            if customer in c["customer"].upper():
                cust_data = c
                break

        if not cust_data:
            await update.message.reply_text(
                f"⚠️ Không tìm thấy '{customer}'.\n"
                f"💡 Dùng /intel (không tham số) để xem danh sách"
            )
            return

        # Get shipments for this customer from analytics
        trouble = analytics.carrier_trouble_index()
        routes = analytics.route_health_map()

        # Filter relevant routes
        cust_routes = [r for r in routes
                       if cust_data["customer"].upper() in
                       str(r.get("top_customers", {})).upper()]

        lines = [
            f"🔍 CUSTOMER INTELLIGENCE — {cust_data['customer']}",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"📅 As of {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            "",
            "📈 PERFORMANCE",
            f"  📦 Total shipments: {cust_data['shipments']}",
            f"  💰 Total profit: ${cust_data['total_profit']:,.0f}",
            f"  💵 Avg profit/ship: ${cust_data['avg_profit_per_ship']:,.0f}",
            f"  ⚠️ Risk events: {cust_data['risk_count']}",
            f"  📅 Active: {cust_data['months_active']} months",
            f"  📅 First: {cust_data.get('first_shipment', '?')}",
            f"  📅 Last: {cust_data.get('last_shipment', '?')}",
            "",
            "📍 ROUTES",
            f"  {', '.join(cust_data.get('top_routes', ['N/A']))}",
            "",
            "🚢 CARRIERS",
            f"  {', '.join(cust_data.get('top_carriers', ['N/A']))}",
        ]

        # Churn check
        last = cust_data.get("last_shipment", "")
        if last:
            try:
                days_since = (datetime.now() - datetime.strptime(last, "%Y-%m-%d")).days
                if days_since > 30:
                    lines.extend([
                        "",
                        f"⚠️ CHURN WARNING: {days_since} ngày chưa có shipment mới",
                        "  → Chủ động liên hệ khách hàng",
                    ])
            except ValueError:
                pass

        lines.extend([
            "",
            "💡 ACTIONS",
            f"  → /risk {cust_data['customer']} — Risk assessment",
            f"  → /trouble — Carrier reliability cho routes này",
        ])

        await update.message.reply_text("\n".join(lines))

    except Exception as e:
        log.error("Error in /intel: %s", e)
        await update.message.reply_text(f"❌ Lỗi: {e}")


# =============================================================================
# /intelligence — Overview Dashboard (UPDATED)
# =============================================================================

async def cmd_intelligence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /intelligence → Quick overview of all intelligence data
    """
    try:
        analytics = _get_analytics()
        stats = analytics.overall_stats()

        features = [
            ("🔮 Churn Radar", "✅ /churn"),
            ("⏱️ Response DNA", "⏳ Phase 3"),
            ("🌊 Carrier Trouble", "✅ /trouble"),
            ("🧬 Commitment Score", "⏳ Phase 3"),
            ("🗺️ Route Health", "✅ /route"),
            ("👻 Ghost Pipeline", "⏳ Phase 2"),
            ("🎯 Coaching Radar", "⏳ Phase 5"),
            ("📡 Market Sentiment", "⏳ Phase 4"),
            ("💎 Relationship Depth", "✅ /intel"),
            ("🔄 Autopilot Mode", "⏳ Phase 5"),
        ]

        lines = [
            "🧠 <b>NELSON FREIGHT INTELLIGENCE</b>",
            f"<i>Email Intelligence Platform — {stats['total_shipments']} shipments</i>",
            "",
            f"📊 <b>System Overview</b>",
            f"  📦 Shipments: {stats['total_shipments']}",
            f"  👥 Customers: {stats['unique_customers']}",
            f"  🚢 Carriers: {stats['unique_carriers']}",
            f"  💰 Total Profit: ${stats['total_profit']:,.0f}",
            f"  ⚠️ Risk Events: {stats['total_risks']}",
            "",
            "📋 <b>10 Features Status</b>",
        ]

        done = 0
        for name, status in features:
            lines.append(f"  {name}: {status}")
            if "✅" in status:
                done += 1

        lines.extend([
            "",
            f"📈 Progress: <b>{done}/10</b> features active",
            "",
            "💡 <b>Commands:</b>",
            "  /trouble — Carrier reliability ranking",
            "  /route — Route health analysis",
            "  /churn — Customer churn detection",
            "  /risk CUSTOMER — 4D risk assessment",
            "  /intel CUSTOMER — 360° customer card",
            "  /custintel — Customer summary",
        ])

        await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    except Exception as e:
        log.error("Error in /intelligence: %s", e)
        await update.message.reply_text(f"❌ Lỗi: {e}")


# =============================================================================
# /custintel — Customer Intelligence Summary
# =============================================================================

async def cmd_customers_intel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /custintel  → Customer intelligence summary
    """
    try:
        analytics = _get_analytics()
        results = analytics.customer_summary()
        output = format_customer_summary(results)
        await update.message.reply_text(output, parse_mode="HTML")

    except Exception as e:
        log.error("Error in /custintel: %s", e)
        await update.message.reply_text(f"❌ Lỗi: {e}")


# =============================================================================
# /memory — Memory Layer Status
# =============================================================================

async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /memory → Intelligence Memory Layer status + trends
    """
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "email_engine"))
        from memory_writer import get_memory_status

        status = get_memory_status()

        lines = [
            "🧠 <b>INTELLIGENCE MEMORY</b>",
            "",
        ]

        total_rows = 0
        for name, info in status.items():
            rows = info.get("rows", 0)
            periods = info.get("periods", 0)
            first = info.get("first", "?")
            last = info.get("last", "?")
            total_rows += max(rows, 0)

            icon = "✅" if rows > 0 else "⬜"
            display = name.replace("_", " ").title()
            lines.append(
                f"  {icon} <b>{display}</b>\n"
                f"     {rows} rows | {periods} periods | {first} → {last}"
            )

        lines.extend([
            "",
            f"📊 Total: <b>{total_rows}</b> memory rows",
            "",
            "💡 Memory giúp hệ thống phát hiện trends:",
            "  • Customer frequency UP/DOWN",
            "  • Carrier trouble IMPROVING/WORSENING",
            "  • Route demand RISING/FALLING",
            "  • Market sentiment TIGHTENING/LOOSENING",
        ])

        await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    except Exception as e:
        log.error("Error in /memory: %s", e)
        await update.message.reply_text(f"❌ Lỗi: {e}")

# =============================================================================
# /news — Logistics News Intelligence
# =============================================================================

async def cmd_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /news → Logistics news digest with market signal detection.
    """
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "email_engine"))
        from news_ingester import ingest_news, get_recent_news, format_news_digest

        await update.message.reply_text("📰 Đang fetch tin tức logistics...")

        # Ingest latest
        result = ingest_news()

        # Get recent articles
        articles = get_recent_news(days=7)
        output = format_news_digest(articles)

        if result.get("new_articles", 0) > 0:
            output += (
                f"\n\n🆕 <b>{result['new_articles']}</b> tin mới | "
                f"⚡ {result['signals_detected']} signals | "
                f"🔴 {result['high_urgency']} high urgency"
            )

        await update.message.reply_text(output, parse_mode="HTML")

    except Exception as e:
        log.error("Error in /news: %s", e)
        await update.message.reply_text(f"❌ Lỗi: {e}")


# =============================================================================
# /carrier — Carrier Reliability Ranking
# =============================================================================

async def cmd_carrier_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /carrier [NAME] → Carrier reliability ranking or detail report.
    """
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "email_engine"))
        from carrier_scorer import (
            score_all_carriers, get_carrier_report,
            format_carrier_ranking, format_carrier_detail,
        )

        if context.args:
            # Specific carrier detail
            carrier = " ".join(context.args).upper()
            report = get_carrier_report(carrier)
            output = format_carrier_detail(report)
        else:
            # Full ranking
            scores = score_all_carriers()
            output = format_carrier_ranking(scores)

        await update.message.reply_text(output, parse_mode="HTML")

    except Exception as e:
        log.error("Error in /carrier: %s", e)
        await update.message.reply_text(f"❌ Lỗi: {e}")

# =============================================================================
# /4c — 4C Market Intelligence Report
# =============================================================================

async def cmd_4c(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /4c → Full 4C Freight Intelligence report (Capacity, Costing, Challenge, Chances).
    """
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "email_engine"))
        from opportunity_detector import build_4c_report, format_4c_report

        report = build_4c_report()
        output = format_4c_report(report)
        await update.message.reply_text(output, parse_mode="HTML")

    except Exception as e:
        log.error("Error in /4c: %s", e)
        await update.message.reply_text(f"❌ Lỗi: {e}")


# =============================================================================
# /market — Market Intelligence
# =============================================================================

async def cmd_market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /market → Market memory trends + sentiment analysis.
    """
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "email_engine"))
        from memory_writer import get_memory_status
        import pandas as pd

        mm_path = Path(__file__).parent.parent.parent / "email_engine" / "memory" / "market_memory.parquet"

        if not mm_path.exists():
            await update.message.reply_text("📊 Chưa có market memory. Chạy /memory để kiểm tra.")
            return

        df = pd.read_parquet(str(mm_path))
        df = df.sort_values("period")

        sentiment_icons = {
            "TIGHTENING": "🔴", "NORMAL": "🟢", "LOOSENING": "🔵", "QUIET": "⚪",
        }

        lines = [
            "📡 <b>MARKET INTELLIGENCE</b>",
            f"<i>{len(df)} months of data</i>",
            "",
        ]

        # Latest snapshot
        latest = df.iloc[-1]
        sent = latest.get("sentiment", "?")
        lines.extend([
            f"📊 <b>Current ({latest['period']}):</b>",
            f"  {sentiment_icons.get(sent, '⚪')} Sentiment: <b>{sent}</b>",
            f"  📦 Ships: {latest.get('total_shipments', 0)} | "
            f"👥 Active: {latest.get('active_customers', 0)}",
            f"  💰 Profit: ${latest.get('total_profit', 0):,.0f} | "
            f"⚠️ Risk: {latest.get('avg_risk_rate', 0):.1%}",
            f"  🆕 New: {latest.get('new_customers', 0)} | "
            f"👻 Churned: {latest.get('churned_customers', 0)}",
            "",
        ])

        # Trend over last 6 months
        recent = df.tail(6)
        lines.append("📈 <b>6-Month Trend:</b>")
        for _, row in recent.iterrows():
            icon = sentiment_icons.get(row.get("sentiment", ""), "⚪")
            lines.append(
                f"  {row['period']} {icon} {row.get('sentiment', '?'):11s} | "
                f"{row.get('total_shipments', 0):2d} ships | "
                f"${row.get('total_profit', 0):>7,.0f} | "
                f"{row.get('active_customers', 0)} custs"
            )

        # Top routes
        routes = latest.get("top_demand_routes", "")
        if routes:
            lines.extend(["", f"🗺️ <b>Hot routes:</b> {routes}"])

        await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    except Exception as e:
        log.error("Error in /market: %s", e)
        await update.message.reply_text(f"❌ Lỗi: {e}")


# =============================================================================
# /opportunities — Business Opportunities
# =============================================================================

async def cmd_opportunities(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /opportunities → Detected business opportunities from 4C analysis.
    """
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "email_engine"))
        from opportunity_detector import detect_opportunities, format_opportunities

        opps = detect_opportunities()
        output = format_opportunities(opps)
        await update.message.reply_text(output, parse_mode="HTML")

    except Exception as e:
        log.error("Error in /opportunities: %s", e)
        await update.message.reply_text(f"❌ Lỗi: {e}")


# =============================================================================
# REGISTER ALL HANDLERS
# =============================================================================

def register_intelligence_handlers(app, skip_commands: list[str] | None = None) -> None:
    """Register intelligence command handlers, skipping any already registered."""
    skip = set(skip_commands or [])
    registered = []

    handlers = {
        "trouble": cmd_trouble,
        "route": cmd_route,
        "churn": cmd_churn,
        "risk": cmd_risk,
        "intel": cmd_intel,
        "intelligence": cmd_intelligence,
        "custintel": cmd_customers_intel,
        "memory": cmd_memory,
        "news": cmd_news,
        "carrier": cmd_carrier_score,
        "market": cmd_market,
        "opportunities": cmd_opportunities,
        "fc": cmd_4c,
    }

    for name, handler in handlers.items():
        if name not in skip:
            app.add_handler(CommandHandler(name, handler))
            registered.append(f"/{name}")

    log.info(
        "[Intelligence] Registered %d handlers: %s (skipped: %s)",
        len(registered), " ".join(registered), ", ".join(f"/{s}" for s in skip) or "none",
    )
