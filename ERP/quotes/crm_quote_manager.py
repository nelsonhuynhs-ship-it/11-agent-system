"""
Quote Manager - Quản lý báo giá và chuyển đổi WIN → Job
"""

import os
import sys
import pandas as pd
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUOTE_FILE = os.path.join(BASE_DIR, "CRM", "data", "Quote_History.xlsx")
JOBS_FILE = os.path.join(BASE_DIR, "Jobs", "data", "Jobs_Master.xlsx")

def load_quotes():
    """Load all quotes"""
    if not os.path.exists(QUOTE_FILE):
        return pd.DataFrame()
    return pd.read_excel(QUOTE_FILE)


def save_quotes(df):
    """Save quotes back to file"""
    df.to_excel(QUOTE_FILE, index=False)


def ensure_status_column(df):
    """Add Status column if not exists"""
    if 'Status' not in df.columns:
        df['Status'] = 'PENDING'
    if 'StatusDate' not in df.columns:
        df['StatusDate'] = None
    return df


def list_quotes(status_filter=None, customer_filter=None, month=None):
    """List quotes with optional filters"""
    df = load_quotes()
    if df.empty:
        print("   ❌ Không có quotes!")
        return df
    
    df = ensure_status_column(df)
    
    # Apply filters
    if status_filter and status_filter != 'ALL':
        df = df[df['Status'] == status_filter]
    
    if customer_filter:
        df = df[df['Customer'].str.contains(customer_filter, case=False, na=False)]
    
    if month:
        df['Date'] = pd.to_datetime(df['Date'])
        df = df[df['Date'].dt.month == month]
    
    return df


def display_quotes(df):
    """Display quotes in table format"""
    if df.empty:
        print("   Không có quotes phù hợp!")
        return
    
    # Group by QuoteID
    grouped = df.groupby('QuoteID').first().reset_index()
    
    print("\n" + "-"*90)
    print(f"{'QuoteID':<12} {'Date':<12} {'Customer':<15} {'POL→POD':<15} {'Carrier':<8} {'Status':<10}")
    print("-"*90)
    
    for _, row in grouped.iterrows():
        date_str = str(row.get('Date', '-'))[:10]
        route = f"{row.get('POL', '-')}→{row.get('POD', '-')}"
        status = row.get('Status', 'PENDING')
        emoji = "🟢" if status == 'WIN' else "🔴" if status == 'LOST' else "🟡"
        print(f"{row['QuoteID']:<12} {date_str:<12} {str(row.get('Customer', '-')):<15} {route:<15} {str(row.get('Carrier', '-')):<8} {emoji} {status:<8}")
    
    print("-"*90)
    print(f"Total: {len(grouped)} quotes")


def mark_quote_status(quote_id, new_status):
    """Mark quote as WIN/LOST"""
    df = load_quotes()
    df = ensure_status_column(df)
    
    mask = df['QuoteID'] == quote_id
    if not mask.any():
        print(f"   ❌ Quote {quote_id} không tìm thấy!")
        return False
    
    df.loc[mask, 'Status'] = new_status
    df.loc[mask, 'StatusDate'] = datetime.now()
    
    save_quotes(df)
    print(f"   ✅ Quote {quote_id} đã đánh dấu: {new_status}")
    
    # If WIN, create Job
    if new_status == 'WIN':
        create_job_from_quote(quote_id, df[mask])
    
    return True


def create_job_from_quote(quote_id, quote_df):
    """Create Job from winning quote"""
    # Load existing jobs
    if os.path.exists(JOBS_FILE):
        jobs_df = pd.read_excel(JOBS_FILE)
    else:
        jobs_df = pd.DataFrame()
    
    # Generate Job ID
    today = datetime.now().strftime('%y%m%d')
    existing_today = jobs_df[jobs_df['Job_ID'].str.startswith(f'JOB-{today}')] if not jobs_df.empty and 'Job_ID' in jobs_df.columns else pd.DataFrame()
    seq = len(existing_today) + 1
    job_id = f"JOB-{today}-{seq:03d}"
    
    # Get quote details
    first_row = quote_df.iloc[0]
    
    new_job = {
        'Job_ID': job_id,
        'Quote_ID': quote_id,
        'Customer_Name': first_row.get('Customer', ''),
        'Routing': f"{first_row.get('POL', '')}-{first_row.get('POD', '')}",
        'Carrier': first_row.get('Carrier', ''),
        'Selling_Rate': first_row.get('FinalPrice', 0),
        'Status': 'BOOKED',
        'Created_Date': datetime.now(),
    }
    
    jobs_df = pd.concat([jobs_df, pd.DataFrame([new_job])], ignore_index=True)
    jobs_df.to_excel(JOBS_FILE, index=False)
    
    print(f"   ✅ Job {job_id} đã tạo từ Quote {quote_id}!")
    return job_id


def get_monthly_stats():
    """Get monthly quote statistics"""
    df = load_quotes()
    if df.empty:
        return {}
    
    df = ensure_status_column(df)
    df['Date'] = pd.to_datetime(df['Date'])
    
    # Current month
    current_month = datetime.now().month
    current_year = datetime.now().year
    df_month = df[(df['Date'].dt.month == current_month) & (df['Date'].dt.year == current_year)]
    
    if df_month.empty:
        return {}
    
    # Count unique quotes
    grouped = df_month.groupby('QuoteID')['Status'].first()
    
    total = len(grouped)
    wins = (grouped == 'WIN').sum()
    lost = (grouped == 'LOST').sum()
    pending = (grouped == 'PENDING').sum()
    
    # Total value of wins
    win_quotes = grouped[grouped == 'WIN'].index
    win_value = df_month[df_month['QuoteID'].isin(win_quotes)].groupby('QuoteID')['FinalPrice'].max().sum()
    
    return {
        'month': f"{current_year}-{current_month:02d}",
        'total': total,
        'wins': wins,
        'lost': lost,
        'pending': pending,
        'win_rate': (wins / total * 100) if total > 0 else 0,
        'win_value': win_value
    }


def display_stats():
    """Display monthly statistics"""
    stats = get_monthly_stats()
    
    if not stats:
        print("   Không có dữ liệu tháng này!")
        return
    
    print("\n" + "="*50)
    print(f"📊 QUOTE STATISTICS - {stats['month']}")
    print("="*50)
    print(f"\nTotal Quotes: {stats['total']}")
    print(f"├── 🟡 PENDING: {stats['pending']}")
    print(f"├── 🟢 WIN: {stats['wins']} ({stats['win_rate']:.1f}%)")
    print(f"└── 🔴 LOST: {stats['lost']}")
    print(f"\nWin Value: ${stats['win_value']:,.0f}")
    print("="*50)


def quote_manager_menu():
    """Main Quote Manager menu"""
    while True:
        print("\n" + "="*50)
        print("📋 QUOTE MANAGER")
        print("="*50)
        print("\n  [1] Xem tất cả quotes")
        print("  [2] Xem quotes PENDING")
        print("  [3] Đánh dấu WIN (tạo Job)")
        print("  [4] Đánh dấu LOST")
        print("  [5] Thống kê tháng")
        print("\n  [0] Quay lại")
        
        choice = input("\nChọn: ").strip()
        
        if choice == '1':
            df = list_quotes()
            display_quotes(df)
        
        elif choice == '2':
            df = list_quotes(status_filter='PENDING')
            display_quotes(df)
        
        elif choice == '3':
            df = list_quotes(status_filter='PENDING')
            display_quotes(df)
            quote_id = input("\nNhập QuoteID để đánh dấu WIN: ").strip()
            if quote_id:
                mark_quote_status(quote_id, 'WIN')
        
        elif choice == '4':
            df = list_quotes(status_filter='PENDING')
            display_quotes(df)
            quote_id = input("\nNhập QuoteID để đánh dấu LOST: ").strip()
            if quote_id:
                mark_quote_status(quote_id, 'LOST')
        
        elif choice == '5':
            display_stats()
        
        elif choice == '0':
            break
        
        input("\n[Enter để tiếp tục...]")


if __name__ == "__main__":
    quote_manager_menu()
