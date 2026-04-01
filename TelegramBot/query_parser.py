"""
Smart Rate Query Parser — Shared between /quote command and AI chat.
Parses natural freight rate queries into structured filters.

Examples:
    HPH-ATLANTA              → POL=HPH, Place=ATLANTA, Cont=40HQ
    HCM-CHICAGO VIA TACOMA   → POL=HCM, Place=CHICAGO, POD=TACOMA
    HPH DENVER cont 40       → POL=HPH, Place=DENVER, Cont=40GP
    CMA HPH-LAX SOC          → Carrier=CMA, POL=HPH, Place=LAX, service=SOC
    HCM-LAX REEFER           → POL=HCM, Place=LAX, service=REEFER
"""
import re
import pandas as pd

# Optional markup engine — works even if ERP unavailable
try:
    from markup_engine import calculate_selling_price, is_markup_loaded
    _MARKUP_AVAILABLE = True
except ImportError:
    _MARKUP_AVAILABLE = False
    def is_markup_loaded(): return False
    def calculate_selling_price(base, carrier, container, place='', is_soc=False):
        return {'selling': base, 'base': base, 'global_mk': 0,
                'carrier_mk': 0, 'puc': 0, 'breakdown': f'Base ${base:,.0f}'}

# Known POLs
KNOWN_POLS = {'HCM', 'HPH', 'DAD', 'UIH', 'VUT'}

# Container shortcuts
CONTAINER_MAP = {
    '20': '20GP', '20GP': '20GP', '20DC': '20GP',
    '40': '40GP', '40GP': '40GP', '40DC': '40GP',
    'HQ': '40HQ', '40HQ': '40HQ', '40HC': '40HQ', '40HG': '40HQ',
    '45': "45'HQ", "45'HQ": "45'HQ", '45HQ': "45'HQ", '45HC': "45'HQ",
    'NOR': '40NOR', '40NOR': '40NOR',
    '20RF': '20RF', '40RF': '40RF',
    'RF': '40RF',
}


# Service type keywords → Note column filter
SERVICE_KEYWORDS = {
    'SOC': 'SOC',
    'COC': 'COC',           # Carrier Own Container (FAK = default COC)
    'REEFER': 'REEFER',
    'LẠNH': 'REEFER',       # Vietnamese
    'LANH': 'REEFER',       # Without diacritics
    'DIRECT': 'DIRECT',
    'TRANSIT': 'TRANSIT',
}

# Commodity keywords → Commodity column filter
COMMODITY_KEYWORDS = {
    'FAK': 'FAK',
    'GARMENT': 'GARMENT',
    'GDSM': 'GDSM',
    'VEHICLES': 'VEHICLES',
    'CARS': 'VEHICLES',
    'XE': 'VEHICLES',       # Vietnamese
}

# Stop words (Vietnamese with/without diacritics + English)
STOP_WORDS = {
    # Vietnamese (with diacritics)
    'GIÁ', 'BAO', 'NHIÊU', 'CHO', 'ĐI', 'CỦA', 'CÓ', 'NHƯ', 'THẾ', 'NÀO',
    'MỚI', 'NHẤT', 'TỐT', 'RẺ', 'BÁO', 'KIỂM', 'TRA', 'TÌM', 'HÃNG', 'TÀU',
    'SAO', 'TỪ', 'ĐẾN', 'VỀ', 'LÀ', 'NÀY', 'ĐÓ', 'VÀ', 'HAY', 'HOẶC',
    'ĐƯỢC', 'KHÔNG', 'CÒN', 'NỮA', 'RỒI', 'SẾP', 'ANH', 'EM',
    'XEM', 'COI', 'THỬ', 'GIÚP', 'HỎI', 'NHẮN', 'NHỜ', 'CHỈ', 'LÀM',
    'HIỆN', 'NAY', 'HÔM', 'XIN', 'VUI', 'LÒNG', 'NGAY', 'LIỀN',
    'MỘT', 'HAI', 'CÁI', 'CON', 'CẢNG', 'XUẤT', 'NHẬP', 'HÀNG',
    'ĐƯỜNG', 'BIỂN', 'SHIP', 'SHIPPING', 'FREIGHT', 'ROUTE',
    # Vietnamese (WITHOUT diacritics — common in chat)
    'GIA', 'DI', 'TU', 'DEN', 'VE', 'LA', 'NAO', 'NHIEU', 'MOI', 'TOT',
    'RE', 'SAO', 'CO', 'KHONG', 'THE', 'DUOC', 'NHAT', 'TAU',
    'TIM', 'KIEM', 'HANG', 'CANG', 'XUAT', 'NHAP', 'DUONG', 'BIEN',
    'HIEN', 'HOM', 'NGAY', 'LIEN', 'SEP', 'GIUP', 'HOI',
    # English
    'HOW', 'MUCH', 'THE', 'FOR', 'AND', 'WITH', 'FROM', 'WHAT', 'WHICH',
    'QUOTE', 'PRICE', 'RATE', 'CHECK', 'FIND', 'SEARCH', 'SHOW', 'LIST',
    'CONTAINER', 'CARRIER', 'PLEASE', 'CAN', 'YOU', 'GIVE', 'TELL',
    'BEST', 'CHEAP', 'CHEAPEST', 'LOWEST', 'COST',
}

CONTAINERS = {'20GP', '40GP', '40HQ', '45HQ', '40NOR', '20RF', '40RF'}


def parse_rate_query(query_text, known_carriers=None):
    """
    Parse a natural language rate query into structured filters.
    
    Returns dict with keys:
        pol, pod, place_terms, carrier, container, service, commodity, customer
    """
    if known_carriers is None:
        known_carriers = []
    carriers_upper = {c.upper() for c in known_carriers}
    
    # Normalize: split on spaces, dashes, slashes, commas, arrows
    tokens = re.split(r'[\s\-/,→>]+', query_text.upper().strip())
    tokens = [t.strip() for t in tokens if t.strip()]
    
    result = {
        'pol': None,
        'pod': None,
        'place_terms': [],
        'carrier': None,
        'container': '40HQ',
        'container_specified': False,  # True if user explicitly said a container
        'service': None,      # SOC / COC / REEFER / DIRECT / TRANSIT
        'commodity': None,     # FAK / GARMENT / GDSM / VEHICLES
        'customer': None,
        'adhoc_markup': 0.0,  # Sprint 8: +N or -N custom markup per query
    }
    
    i = 0
    while i < len(tokens):
        t = tokens[i]
        
        # VIA keyword → next token is POD filter
        if t == 'VIA' and i + 1 < len(tokens):
            result['pod'] = tokens[i + 1]
            i += 2
            continue
        
        # CONT/CONTAINER keyword → next token is container type
        if t in ('CONT', 'CONTAINER') and i + 1 < len(tokens):
            next_t = tokens[i + 1]
            if next_t in CONTAINER_MAP:
                result['container'] = CONTAINER_MAP[next_t]
                result['container_specified'] = True
                i += 2
                continue
        
        # Service type: SOC / COC / REEFER / DIRECT / TRANSIT
        if t in SERVICE_KEYWORDS:
            result['service'] = SERVICE_KEYWORDS[t]
            # If REEFER, auto-switch container to 40RF if not explicitly set
            if result['service'] == 'REEFER' and result['container'] == '40HQ':
                result['container'] = '40RF'
            i += 1
            continue
        
        # Commodity: FAK / GARMENT / GDSM / VEHICLES
        if t in COMMODITY_KEYWORDS:
            result['commodity'] = COMMODITY_KEYWORDS[t]
            i += 1
            continue
        
        # Direct container match
        if t in CONTAINERS:
            result['container'] = t
            result['container_specified'] = True
            i += 1
            continue
        
        # Container shorthand (e.g. "40" alone)
        if t in CONTAINER_MAP and t not in carriers_upper and t not in KNOWN_POLS:
            result['container'] = CONTAINER_MAP[t]
            result['container_specified'] = True
            i += 1
            continue
        
        # Known carrier
        if t in carriers_upper:
            result['carrier'] = t
            i += 1
            continue
        
        # Known POL
        if t in KNOWN_POLS:
            result['pol'] = t
            i += 1
            continue
        

        # Sprint 8: Adhoc markup token — e.g. +100 or -50
        if re.match(r'^[+\-]\d+$', t):
            try:
                result['adhoc_markup'] += float(t)
            except ValueError:
                pass
            i += 1
            continue

        # Stop word → skip
        if t in STOP_WORDS:
            i += 1
            continue
        
        # Remaining meaningful tokens → place/POD search terms
        if len(t) >= 2:
            result['place_terms'].append(t)
        
        i += 1
    
    return result


def apply_rate_filters(df, parsed, top_n=5):
    """
    Apply parsed rate query filters to pricing DataFrame.
    Returns (filtered_df, container_name, cont_col_name) or (None, container, error_msg).
    """
    result = df.copy()
    container = parsed['container']
    
    # Filter by carrier
    if parsed['carrier'] and 'Carrier' in result.columns:
        result = result[result['Carrier'].str.upper() == parsed['carrier']]
    
    # Filter by POL
    if parsed['pol'] and 'POL' in result.columns:
        result = result[result['POL'].str.upper().str.strip() == parsed['pol']]
    
    # Filter by POD
    if parsed['pod'] and 'POD' in result.columns:
        result = result[result['POD'].astype(str).str.upper().str.contains(parsed['pod'], na=False)]
    
    # Filter by service type (Note column)
    if parsed['service'] and 'Note' in result.columns:
        service = parsed['service']
        if service == 'SOC':
            result = result[result['Note'].astype(str).str.upper().str.contains('SOC', na=False)]
        elif service == 'COC':
            # COC = NOT SOC (standard carrier container)
            result = result[~result['Note'].astype(str).str.upper().str.contains('SOC', na=False)]
        elif service == 'REEFER':
            result = result[result['Note'].astype(str).str.upper().str.contains('REEFER', na=False) |
                           result['Commodity'].astype(str).str.upper().str.contains('REEFER', na=False)]
        elif service == 'DIRECT':
            result = result[result['Note'].astype(str).str.upper().str.contains('DIRECT', na=False)]
        elif service == 'TRANSIT':
            result = result[result['Note'].astype(str).str.upper().str.contains('TRANSIT', na=False)]
    
    # Filter by commodity
    if parsed['commodity'] and 'Commodity' in result.columns:
        commodity = parsed['commodity']
        result = result[result['Commodity'].astype(str).str.upper().str.contains(commodity, na=False)]
    
    # Filter by place terms (search in Place and POD columns)
    for term in parsed['place_terms']:
        mask = pd.Series(False, index=result.index)
        for col in ['Place', 'POD']:
            if col in result.columns:
                mask |= result[col].astype(str).str.upper().str.contains(term, na=False)
        if mask.any():
            result = result[mask]
    
    # Find container column
    cont_col = [c for c in result.columns if container in str(c)]
    if not cont_col:
        return None, container, f"Không tìm thấy cột {container}"
    cont_col = cont_col[0]
    
    # Filter valid prices
    result = result[pd.to_numeric(result[cont_col], errors='coerce').notna()]
    result = result[pd.to_numeric(result[cont_col], errors='coerce') > 0]
    
    if len(result) == 0:
        return None, container, "Không tìm thấy giá"
    
    # Sort by price
    result['_price'] = pd.to_numeric(result[cont_col], errors='coerce')
    
    if not parsed['carrier']:
        # Get best price per carrier, then sort across carriers
        best = result.sort_values('_price').drop_duplicates(subset=['Carrier'], keep='first')
        best = best.sort_values('_price').head(top_n)
    else:
        best = result.sort_values('_price').head(top_n)
    
    return best, container, cont_col



def format_rate_results(results_df, container, cont_col, parsed):
    """Format rate results for Telegram - Sprint 7: Selling Price with markup."""
    if results_df is None or len(results_df) == 0:
        terms = ' '.join(parsed['place_terms'])
        svc = f" [{parsed['service']}]" if parsed['service'] else ""
        return f"\U0001f50d Khong tim thay gia {container}{svc} cho: {terms}"

    is_soc = parsed.get('service', '') == 'SOC'
    markup_active = is_markup_loaded()

    pol = parsed['pol'] or 'ALL'
    place_info = ' '.join(parsed['place_terms']) if parsed['place_terms'] else '(all)'
    pod_info = f" via {parsed['pod']}" if parsed['pod'] else ""
    carrier_info = f" [{parsed['carrier']}]" if parsed['carrier'] else ""
    svc_info = f" | {parsed['service']}" if parsed['service'] else ""
    commodity_info = f" | {parsed['commodity']}" if parsed['commodity'] else ""
    adhoc = parsed.get("adhoc_markup", 0.0)
    markup_badge = " \U0001f4b0" if markup_active else " (net)"
    if adhoc:
        markup_badge += f" (+${int(adhoc):,} custom)" if adhoc > 0 else f" (-${int(abs(adhoc)):,} disc)"

    lines = [f"\U0001f4ca **{pol} \u2192 {place_info}{pod_info}{carrier_info}** ({container}{svc_info}{commodity_info}{markup_badge})"]
    lines.append("\u2501" * 20)

    for idx, (_, row) in enumerate(results_df.iterrows(), 1):
        carrier = str(row.get('Carrier', ''))[:5]
        place = str(row.get('Place', ''))[:15]
        pod = str(row.get('POD', ''))[:8]
        note = str(row.get('Note', ''))[:6]

        try:
            base_price = float(row[cont_col])
        except (TypeError, ValueError):
            base_price = 0.0

        try:
            exp = row.get('Exp', '')
            exp_str = pd.to_datetime(exp, errors='coerce').strftime('%d-%b') if pd.notna(exp) else ''
        except Exception:
            exp_str = ''

        if markup_active and base_price > 0:
            mk = calculate_selling_price(base_price, carrier, container, place, is_soc, adhoc_markup=parsed.get('adhoc_markup', 0.0))
            selling = mk['selling']
            selling_str = f"${int(selling):,}"
            has_markup = (mk['global_mk'] + mk['carrier_mk'] + mk['puc']) != 0
            if has_markup:
                bd = f"base ${int(base_price):,}"
                if mk['carrier_mk']: bd += f"+{carrier.strip()} ${int(mk['carrier_mk']):,}"
                if mk['global_mk']:  bd += f"+G ${int(mk['global_mk']):,}"
                if mk['puc']:        bd += f"+PUC ${int(mk['puc']):,}"
                line = f" {idx}. `{carrier:<5} {selling_str:>7}  {pod:<8} {place:<15} {exp_str:>5} {note}` _({bd})_"
            else:
                line = f" {idx}. `{carrier:<5} {selling_str:>7}  {pod:<8} {place:<15} {exp_str:>5} {note}` _(net)_"
        else:
            price_str = f"${int(base_price):,}" if base_price else str(row[cont_col])
            line = f" {idx}. `{carrier:<5} {price_str:>7}  {pod:<8} {place:<15} {exp_str:>5} {note}`"

        lines.append(line)

    total = len(results_df)
    hint = f"\n\U0001f4a1 Luu: `/savequote CUSTOMER {' '.join(str(i) for i in range(1, total+1))}`"
    if markup_active:
        hint += "\n\U0001f4b0 = Selling price (da cong markup)"
    lines.append(hint)
    return "\n".join(lines)



def build_ai_pricing_context(df, query_text):
    """Build pricing context for AI chat using smart parser."""
    if df is None:
        return "Không có dữ liệu giá."
    
    known_carriers = list(df['Carrier'].dropna().unique()) if 'Carrier' in df.columns else []
    parsed = parse_rate_query(query_text, known_carriers)
    
    # Only build context if there are meaningful search terms or carrier/POL specified
    if not parsed['place_terms'] and not parsed['carrier'] and not parsed['pol']:
        return ""
    
    results_df, container, cont_col = apply_rate_filters(df, parsed, top_n=15)
    
    if results_df is None or len(results_df) == 0:
        terms = ' '.join(parsed['place_terms'])
        return f"Không tìm thấy giá {container} cho: {terms}"
    
    # Build text table for AI context
    lines = [f"DATA ({len(results_df)} kết quả, {container}):"]
    lines.append(f"{'Carrier':<6} {'POL':<5} {'POD':<7} {'Place':<18} {'Price':>7} {'Exp':>8} {'Note':<8}")
    lines.append("-" * 70)
    
    for _, row in results_df.iterrows():
        carrier = str(row.get('Carrier', ''))[:5]
        pol = str(row.get('POL', ''))[:4]
        pod = str(row.get('POD', ''))[:6]
        place = str(row.get('Place', ''))[:17]
        price = row[cont_col]
        note = str(row.get('Note', ''))[:7]
        try:
            price_str = f"${int(float(price)):,}"
        except:
            price_str = str(price)
        try:
            exp_str = pd.to_datetime(row.get('Exp', ''), errors='coerce').strftime('%d-%b') if pd.notna(row.get('Exp', None)) else ''
        except:
            exp_str = ''
        lines.append(f"{carrier:<6} {pol:<5} {pod:<7} {place:<18} {price_str:>7} {exp_str:>8} {note:<8}")
    
    return "\n".join(lines)
