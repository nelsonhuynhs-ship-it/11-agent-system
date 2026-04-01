"""
AI Chat Module — Gemini integration for freight assistant
Uses google.genai SDK + shared query_parser for smart context building
"""
from google import genai
from google.genai import types
import pandas as pd
from datetime import datetime

from config import GEMINI_API_KEY, GEMINI_MODEL, ADMIN_NAME
from database import get_customer_rules, get_excluded_carriers, get_pending_commissions
from query_parser import build_ai_pricing_context

# ── System Prompt ──
SYSTEM_PROMPT = f"""Bạn là trợ lý freight logistics cho {ADMIN_NAME} — một freight forwarder Việt Nam.

QUY TẮC GIAO TIẾP:
- Luôn gọi user là "{ADMIN_NAME}"
- Xưng "Em"
- Trả lời ngắn gọn, đi thẳng vào vấn đề
- Dùng emoji phù hợp
- Format bảng giá bằng monospace khi cần

KIẾN THỨC FREIGHT:
- POL: cảng xuất (HCM, HPH = Hải Phòng)
- POD: cảng đến (USLAX, USNYC, USWC...)
- Place: địa điểm inland (Denver, Dallas, Chicago...)
- Container: 20GP, 40GP, 40HQ, 45HQ, 20RF, 40RF, 40NOR
- Carrier: CMA, COSCO, EMC, HPL, MSC, ONE, WHL, YML, ZIM
- SOC = Shipper Own Container, COC = Carrier Own Container
- FAK = Freight All Kinds, GARMENT = hàng may mặc
- REEFER = container lạnh (20RF, 40RF)
- Selling = Base + Markup + PUC (nếu SOC)
- Buying = Base + PUC

KHI TRA GIÁ:
- Tìm cả POD và Place columns
- Trả về top 5-10 kết quả thấp nhất
- Nếu biết customer → check customer rules để loại carrier bị exclude
- Phân biệt SOC vs COC (FAK), DIRECT vs TRANSIT
- Hiển thị: Carrier | Place | Price | Exp date | Note

KHI KHÔNG CÓ DATA:
- Nói rõ "Em không tìm thấy" và gợi ý thử từ khóa khác
"""

# ── Gemini Client ──
_client = None
_chat = None


def init_gemini():
    """Initialize Gemini client using google.genai SDK."""
    global _client, _chat
    if not GEMINI_API_KEY:
        return False
    
    try:
        _client = genai.Client(api_key=GEMINI_API_KEY)
        _chat = _client.chats.create(
            model=GEMINI_MODEL,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.7,
                max_output_tokens=2048,
            ),
        )
        return True
    except Exception as e:
        print(f"[AI] Gemini init error: {e}")
        return False


def build_customer_context(query_text: str) -> str:
    """
    Sprint 8: Build rich CRM context from ERP when a known customer is mentioned.
    Merges static deepmemory profile + DB rules + ERP Quotes history + Active Jobs.
    """
    from database import get_all_customers_with_rules, get_customer_rules
    from customer_profiles import list_profile_customers, STATIC_PROFILES

    query_upper = query_text.upper()
    words = set(query_upper.split())

    # Build set of all known customers (DB + static profiles)
    db_customers = {r['customer'] for r in get_all_customers_with_rules()}
    all_customers = db_customers | set(list_profile_customers())

    matched_customer = None
    for cust in all_customers:
        if cust in words:
            matched_customer = cust
            break
    # Fallback: partial match
    if not matched_customer:
        for cust in all_customers:
            if cust in query_upper:
                matched_customer = cust
                break

    if not matched_customer:
        return ""

    parts = []

    # DB rules (exclude/prefer/note)
    rules = get_customer_rules(matched_customer)
    if rules:
        rule_lines = [f"\nCUSTOMER RULES ({matched_customer}):"]
        for r in rules:
            rule_lines.append(f"  - {r['rule_type']}: {r['rule_value']}")
        parts.append("\n".join(rule_lines))

    # ERP full context (CRM + Quotes + Active Jobs)
    try:
        from erp_reader import build_full_context
        erp_ctx = build_full_context(matched_customer)
        if erp_ctx and 'Không có dữ liệu' not in erp_ctx:
            parts.append(erp_ctx)
    except Exception as e:
        parts.append(f"[ERP Read Error: {e}]")

    return "\n\n".join(parts)



async def chat_with_ai(user_message, pricing_df=None, oracle_context=None):
    """Send message to Gemini and get response.
    
    Args:
        user_message: the user's text
        pricing_df: optional Parquet DataFrame for pricing context
        oracle_context: optional string from Oracle.build_context() — 
                        injects conversation history + customer profile
    """
    global _chat
    
    if not _client:
        if not init_gemini():
            return None
    
    # Build context
    context_parts = []

    # ORACLE memory context (conversation history + profile)
    if oracle_context:
        context_parts.append(f"[MEMORY CONTEXT]\n{oracle_context}")

    # RAG context — system knowledge retrieval
    try:
        from intelligence.rag_engine import RAGEngine
        if not hasattr(chat_with_ai, '_rag'):
            chat_with_ai._rag = RAGEngine()
        rag_ctx = chat_with_ai._rag.build_context_for_query(user_message)
        if rag_ctx:
            context_parts.append(rag_ctx)
    except Exception:
        pass  # RAG is optional, don't break chat
    
    # Check if pricing-related
    pricing_keywords = ['giá', 'price', 'rate', 'quote', 'bao nhiêu', 'tra', 'tìm', 'check',
                        'báo', 'search', 'find', 'LAX', 'NYC', 'HCM', 'HPH', 'CMA', 'ONE',
                        'COSCO', 'EMC', 'HPL', 'MSC', 'ZIM', 'WHL', 'YML',
                        '20GP', '40GP', '40HQ', '45HQ', '40RF', '20RF', '40NOR',
                        'SOC', 'COC', 'REEFER', 'GARMENT', 'FAK', 'DIRECT', 'TRANSIT',
                        'DENVER', 'CHICAGO', 'ATLANTA', 'DALLAS', 'HOUSTON']
    
    is_pricing = any(kw.lower() in user_message.lower() for kw in pricing_keywords)
    
    if is_pricing and pricing_df is not None:
        pricing_context = build_ai_pricing_context(pricing_df, user_message)
        if pricing_context:
            context_parts.append(pricing_context)
    
    # Customer context
    customer_ctx = build_customer_context(user_message)
    if customer_ctx:
        context_parts.append(customer_ctx)
    
    # Commission context
    if any(kw in user_message.lower() for kw in ['com', 'commission', 'thanh toán', 'pending']):
        pending = get_pending_commissions()
        if pending:
            com_lines = [f"\nCOMMISSION PENDING ({len(pending)} lô):"]
            for c in pending:
                com_lines.append(f"  - {c['customer']} | {c['carrier']} {c['container']}×{c['quantity']} = ${c['total']:,.0f}")
            context_parts.append("\n".join(com_lines))
    
    # Build full message
    full_message = user_message
    if context_parts:
        full_message = user_message + "\n\n---\n" + "\n".join(context_parts)
    
    try:
        response = _chat.send_message(full_message)
        return response.text
    except Exception as e:
        # If chat history too long or quota exceeded, reset chat
        if "quota" in str(e).lower() or "limit" in str(e).lower() or "429" in str(e):
            _chat = _client.chats.create(
                model=GEMINI_MODEL,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.7,
                    max_output_tokens=2048,
                ),
            )
            try:
                response = _chat.send_message(full_message)
                return response.text
            except:
                pass
        return f"⚠️ AI error: {str(e)[:150]}"
