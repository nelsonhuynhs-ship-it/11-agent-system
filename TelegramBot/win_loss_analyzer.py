"""
win_loss_analyzer.py — Sprint 9: Win/Loss AI Deep-Dive
Uses Gemini to analyze quote patterns and generate actionable insights.

Modes:
  - by_customer(name)  → Win/Loss pattern for one customer
  - by_carrier(name)   → Which carriers perform best/worst
  - by_route(pol, place) → Market intelligence for a lane
  - pending_alerts()   → Quotes PENDING > 7 days needing follow-up
"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Lazy imports to avoid circular
_gemini_client = None
_gemini_model = None


def _get_gemini():
    """Get Gemini client (reuse from config)."""
    global _gemini_client, _gemini_model
    if _gemini_client:
        return _gemini_client
    try:
        from google import genai
        from google.genai import types
        from config import GEMINI_API_KEY, GEMINI_MODEL
        client = genai.Client(api_key=GEMINI_API_KEY)
        _gemini_client = client
        _gemini_model = GEMINI_MODEL
        return client
    except Exception as e:
        logger.error(f"[WinLoss] Gemini init failed: {e}")
        return None


def _format_quotes_for_ai(quotes: list[dict]) -> str:
    """Format quotes list into compact CSV-like text for Gemini context."""
    if not quotes:
        return "(no data)"
    lines = ["QuoteID | Date | Customer | Carrier | Container | Route | Price | Status"]
    for q in quotes:
        date_str = q['date'].strftime('%d-%b') if hasattr(q.get('date'), 'strftime') else '?'
        route = f"{q.get('pol','')}→{q.get('place','')}"
        lines.append(
            f"{q.get('quote_id','')} | {date_str} | {q.get('customer','')} | "
            f"{q.get('carrier','')} | {q.get('container','')} | "
            f"{route} | ${q.get('price',0):,.0f} | {q.get('status','')}"
        )
    return "\n".join(lines)


async def _ask_gemini(prompt: str) -> str:
    """Send a one-shot analysis prompt to Gemini and return the text response."""
    client = _get_gemini()
    if not client:
        return "❌ Gemini không khả dụng."
    try:
        from google.genai import types
        response = client.models.generate_content(
            model=_gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=1500,
            )
        )
        return response.text
    except Exception as e:
        logger.error(f"[WinLoss] Gemini error: {e}")
        return f"❌ AI error: {str(e)[:100]}"


async def analyze_by_customer(customer_name: str) -> str:
    """
    Analyze win/loss patterns for one customer.
    Returns formatted Telegram-ready markdown string.
    """
    from erp_reader import get_quote_history, get_quote_stats
    quotes = get_quote_history(customer_name, limit=50)
    stats = get_quote_stats(customer_name)

    if not quotes:
        return f"📋 Không có dữ liệu quotes cho **{customer_name}**."

    data_text = _format_quotes_for_ai(quotes)

    prompt = f"""Bạn là AI Freight Analytics cho công ty logistics Việt Nam. Phân tích lịch sử báo giá sau:

CUSTOMER: {customer_name}
STATS: {stats['total']} quotes | WIN={stats['WIN']} | LOSS={stats['LOSS']} | PENDING={stats['PENDING']} | Win Rate={stats['win_rate']}%

DATA:
{data_text}

Hãy phân tích NGẮN GỌN (tối đa 200 từ), trả lời bằng tiếng Việt:
1. **Pattern thắng/thua:** Xu hướng nào rõ ràng? (Thua nhiều ở carrier nào? Giá ngưỡng nào thường thắng?)
2. **Root Cause:** Tại sao Win Rate thấp/cao?
3. **Action cụ thể (1-2 bước):** Sếp nên làm gì ngay để tăng Win Rate?

Format: dùng bullet points, emoji, số liệu cụ thể. Đừng lý thuyết suông."""

    ai_response = await _ask_gemini(prompt)

    header = (
        f"🤖 **AI Win/Loss — {customer_name}**\n"
        f"📊 {stats['total']} quotes | WIN={stats['WIN']} LOSS={stats['LOSS']} "
        f"PENDING={stats['PENDING']} | Win Rate: **{stats['win_rate']}%**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
    )
    return header + ai_response


async def analyze_by_carrier(carrier_name: str) -> str:
    """Analyze which customers and routes perform best/worst with this carrier."""
    from erp_reader import get_quote_history
    # Get all quotes for this carrier
    all_quotes = get_quote_history(limit=200)
    carrier_quotes = [q for q in all_quotes
                      if carrier_name.upper() in q.get('carrier', '').upper()]

    if not carrier_quotes:
        return f"📋 Không có quotes nào cho carrier **{carrier_name}**."

    data_text = _format_quotes_for_ai(carrier_quotes[:50])
    wins = sum(1 for q in carrier_quotes if q['status'].upper() == 'WIN')
    total = len(carrier_quotes)
    win_rate = round(wins / total * 100, 1) if total else 0

    prompt = f"""Phân tích hiệu suất báo giá của carrier {carrier_name}:

STATS: {total} quotes | WIN={wins} | Win Rate={win_rate}%

DATA (50 gần nhất):
{data_text}

Phân tích NGẮN (150 từ), tiếng Việt:
1. **Tuyến nào {carrier_name} đang WIN nhiều nhất?**
2. **Tuyến/Khách nào đang LOSS? Tại sao?**
3. **Action: Nên tăng hay giảm markup của {carrier_name}?** (đề xuất con số cụ thể nếu có thể)"""

    ai_response = await _ask_gemini(prompt)

    header = (
        f"🚢 **AI Carrier Analysis — {carrier_name}**\n"
        f"📊 {total} quotes | WIN={wins} | Win Rate: **{win_rate}%**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
    )
    return header + ai_response


async def analyze_by_route(pol: str, place: str) -> str:
    """Market intelligence for a specific trade lane."""
    from erp_reader import get_quote_history
    all_quotes = get_quote_history(limit=200)
    route_quotes = [
        q for q in all_quotes
        if pol.upper() in q.get('pol', '').upper()
        and place.upper() in q.get('place', '').upper()
    ]

    if not route_quotes:
        return f"📋 Không có data cho tuyến **{pol}→{place}**."

    data_text = _format_quotes_for_ai(route_quotes[:40])
    wins = sum(1 for q in route_quotes if q['status'].upper() == 'WIN')
    prices = [q['price'] for q in route_quotes if q['price'] > 0]
    avg_win = sum(q['price'] for q in route_quotes if q['status'].upper() == 'WIN' and q['price'] > 0) / max(wins, 1)

    prompt = f"""Market Intelligence cho tuyến {pol} → {place}:
{len(route_quotes)} quotes lịch sử | WIN={wins} | Avg price=${sum(prices)/len(prices):,.0f} | Avg WIN price=${avg_win:,.0f}

DATA:
{data_text}

Phân tích (150 từ), tiếng Việt:
1. **Carrier nào Win Rate cao nhất trên tuyến này?**
2. **Ngưỡng giá WIN là bao nhiêu?** (dưới $X thường thắng)
3. **Xu hướng giá** gần đây tăng hay giảm?
4. **Recommendation:** Nên quote $X với carrier Y để tối ưu?"""

    ai_response = await _ask_gemini(prompt)

    header = (
        f"🗺️ **AI Route Intel — {pol}→{place}**\n"
        f"📊 {len(route_quotes)} quotes | Win Rate: **{round(wins/len(route_quotes)*100,1)}%** | "
        f"Avg Price: ${sum(prices)/len(prices):,.0f}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
    )
    return header + ai_response


async def pending_alerts() -> str:
    """Return list of quotes PENDING > 7 days that need immediate follow-up."""
    from erp_reader import get_quote_history
    all_pending = get_quote_history(status='PENDING', limit=100)

    now = datetime.now()
    overdue = []
    for q in all_pending:
        date = q.get('date')
        if hasattr(date, 'days'):
            days = (now - date.replace(tzinfo=None)).days
        elif hasattr(date, '__sub__'):
            try:
                days = (now - date.replace(tzinfo=None)).days
            except Exception:
                continue
        else:
            continue
        if days > 7:
            q['days_pending'] = days
            overdue.append(q)

    overdue.sort(key=lambda x: x.get('days_pending', 0), reverse=True)

    if not overdue:
        return "✅ Không có quotes PENDING quá 7 ngày."

    lines = [f"⚠️ **{len(overdue)} Quotes PENDING > 7 ngày — Cần Follow Up!**\n━━━━━━━━━━━━━━━━━━━━"]
    for q in overdue[:10]:
        days = q.get('days_pending', '?')
        alert = "🔴" if days > 14 else "⚠️"
        lines.append(
            f"{alert} `{q['quote_id']:<12} {q['customer']:<10} "
            f"{q['carrier']:<5} {q['container']:<5} ${q['price']:>7,.0f} "
            f"({days}d)`"
        )
    lines.append(f"\n💡 `/crm CUSTOMER` để xem chi tiết | `/history CUSTOMER` để theo dõi")
    return "\n".join(lines)
