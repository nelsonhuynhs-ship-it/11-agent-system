"""
dashboard_builder.py — Sprint 10: Visual Dashboard Generator
Builds a rich PNG dashboard image from monthly freight data.
Returns io.BytesIO ready to be sent via Telegram bot.send_photo().

Layout (1200×900 px):
  ┌─────────────────────────────────────────┐
  │  HEADER: Month, Key Stats               │
  ├──────────────┬─────────────────────────┤
  │  BAR CHART  │   PIE CHART             │
  │  Revenue by │   Direct vs Coload      │
  │  Carrier    │   Customer Segments     │
  ├─────────────┴─────────────────────────┤
  │  PROGRESS BARS — KPI vs Actual        │
  └─────────────────────────────────────────┘
"""
import io
import logging
from datetime import datetime

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend — no display needed
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import numpy as np

logger = logging.getLogger(__name__)

# ── Color Palette ──
COLORS = {
    'bg':        '#0D1117',   # Dark background
    'surface':   '#161B22',   # Card surface
    'border':    '#30363D',   # Borders
    'text':      '#E6EDF3',   # Primary text
    'sub':       '#8B949E',   # Secondary text
    'accent':    '#58A6FF',   # Blue accent
    'green':     '#3FB950',   # WIN / positive
    'red':       '#F85149',   # LOSS / negative
    'yellow':    '#D29922',   # PENDING / warning
    'purple':    '#BC8CFF',   # Coload
    'orange':    '#FFA657',   # Direct
}

CARRIER_COLORS = [
    '#58A6FF', '#3FB950', '#FFA657', '#BC8CFF',
    '#F85149', '#D29922', '#79C0FF', '#56D364',
]


def _setup_fig_style(fig, axes_list):
    """Apply dark theme to all axes."""
    fig.patch.set_facecolor(COLORS['bg'])
    for ax in axes_list:
        if ax is None:
            continue
        ax.set_facecolor(COLORS['surface'])
        ax.tick_params(colors=COLORS['sub'], labelsize=9)
        ax.xaxis.label.set_color(COLORS['sub'])
        ax.yaxis.label.set_color(COLORS['sub'])
        for spine in ax.spines.values():
            spine.set_edgecolor(COLORS['border'])


def build_dashboard(stats: dict, kpi_targets: dict, month: str) -> io.BytesIO:
    """
    Build the full dashboard PNG.

    Args:
        stats: Output from erp_reader.get_monthly_stats(month)
        kpi_targets: Output from kpi_store.get_kpi(month)
        month: 'YYYY-MM' string

    Returns:
        io.BytesIO PNG image
    """
    try:
        month_label = datetime.strptime(month, '%Y-%m').strftime('%B %Y')
    except Exception:
        month_label = month

    fig = plt.figure(figsize=(14, 10), dpi=100)
    fig.patch.set_facecolor(COLORS['bg'])

    gs = gridspec.GridSpec(
        3, 2,
        figure=fig,
        height_ratios=[0.8, 3.5, 2.2],
        hspace=0.45,
        wspace=0.35,
        left=0.07, right=0.97, top=0.95, bottom=0.05
    )

    # ── HEADER ROW ────────────────────────────────────────────
    ax_header = fig.add_subplot(gs[0, :])
    ax_header.set_facecolor(COLORS['bg'])
    ax_header.axis('off')

    header_text = f"📊  FREIGHT REPORT — {month_label.upper()}"
    ax_header.text(0.0, 0.85, header_text, transform=ax_header.transAxes,
                   fontsize=18, fontweight='bold', color=COLORS['text'])

    # Summary stats in header
    total_jobs = stats.get('total_jobs', 0)
    total_revenue = stats.get('total_revenue', 0)
    total_customers = stats.get('total_customers', 0)
    win_rate = stats.get('win_rate', 0)
    total_teu = stats.get('total_teu', 0)

    summary_items = [
        ('🚢 SHIPMENTS', f"{total_jobs:,}"),
        ('📦 TEU', f"{total_teu:,}"),
        ('💰 REVENUE', f"${total_revenue:,.0f}"),
        ('🏢 CUSTOMERS', f"{total_customers:,}"),
        ('🎯 WIN RATE', f"{win_rate:.1f}%"),
    ]
    for i, (label, value) in enumerate(summary_items):
        x = 0.0 + i * 0.20
        ax_header.text(x, 0.38, label, transform=ax_header.transAxes,
                       fontsize=8, color=COLORS['sub'], fontweight='bold')
        ax_header.text(x, 0.0, value, transform=ax_header.transAxes,
                       fontsize=15, color=COLORS['accent'], fontweight='bold')

    # ── BAR CHART: Revenue by Carrier ─────────────────────────
    ax_bar = fig.add_subplot(gs[1, 0])
    carrier_data = stats.get('revenue_by_carrier', {})
    if carrier_data:
        carriers = list(carrier_data.keys())[:8]
        revenues = [carrier_data[c] for c in carriers]
        sorted_pairs = sorted(zip(revenues, carriers), reverse=True)
        revenues_s, carriers_s = zip(*sorted_pairs) if sorted_pairs else ([], [])

        bars = ax_bar.barh(
            range(len(carriers_s)), revenues_s,
            color=CARRIER_COLORS[:len(carriers_s)],
            edgecolor='none', height=0.65
        )
        ax_bar.set_yticks(range(len(carriers_s)))
        ax_bar.set_yticklabels(carriers_s, color=COLORS['text'], fontsize=10)
        ax_bar.set_xlabel('Revenue (USD)', color=COLORS['sub'], fontsize=9)
        ax_bar.set_title('Revenue by Carrier', color=COLORS['text'], fontsize=12,
                         fontweight='bold', pad=10)
        # Value labels
        for bar, val in zip(bars, revenues_s):
            ax_bar.text(bar.get_width() + max(revenues_s) * 0.01, bar.get_y() + bar.get_height() / 2,
                        f'${val:,.0f}', va='center', color=COLORS['sub'], fontsize=8)
        ax_bar.set_xlim(0, max(revenues_s) * 1.20 if revenues_s else 1)
    else:
        ax_bar.text(0.5, 0.5, 'No carrier data', ha='center', va='center',
                    color=COLORS['sub'], transform=ax_bar.transAxes, fontsize=11)
        ax_bar.set_title('Revenue by Carrier', color=COLORS['text'], fontsize=12,
                         fontweight='bold', pad=10)

    _setup_fig_style(fig, [ax_bar])

    # ── PIE CHART: Direct vs Coload ───────────────────────────
    ax_pie = fig.add_subplot(gs[1, 1])
    segment_data = stats.get('customer_segments', {})
    direct_count = segment_data.get('Direct', 0)
    coload_count = segment_data.get('Coload', 0)
    total_seg = direct_count + coload_count

    if total_seg > 0:
        sizes = [direct_count, coload_count]
        labels = [f'Direct\n{direct_count} KH', f'Coload\n{coload_count} KH']
        pie_colors = [COLORS['orange'], COLORS['purple']]
        wedge_props = {'edgecolor': COLORS['bg'], 'linewidth': 2.5}
        wedges, texts, autotexts = ax_pie.pie(
            sizes, labels=labels, colors=pie_colors,
            autopct='%1.0f%%', startangle=90,
            wedgeprops=wedge_props,
            textprops={'color': COLORS['text'], 'fontsize': 10}
        )
        for at in autotexts:
            at.set_color(COLORS['bg'])
            at.set_fontsize(11)
            at.set_fontweight('bold')
    else:
        ax_pie.text(0.5, 0.5, 'No customer data', ha='center', va='center',
                    color=COLORS['sub'], transform=ax_pie.transAxes, fontsize=11)

    ax_pie.set_title('Customer Segments', color=COLORS['text'], fontsize=12,
                     fontweight='bold', pad=10)
    ax_pie.set_facecolor(COLORS['surface'])

    # ── KPI PROGRESS BARS ─────────────────────────────────────
    ax_kpi = fig.add_subplot(gs[2, :])
    ax_kpi.set_facecolor(COLORS['surface'])
    ax_kpi.axis('off')
    ax_kpi.set_title('KPI Performance', color=COLORS['text'], fontsize=12,
                      fontweight='bold', pad=10, loc='left')

    kpi_metrics = [
        ('shipments',     'Shipments',  total_jobs,    'lô'),
        ('revenue',       'Revenue',    total_revenue, 'USD'),
        ('win_rate',      'Win Rate',   win_rate,      '%'),
        ('new_customers', 'New KH',     stats.get('new_customers', 0), 'KH'),
    ]

    n = len(kpi_metrics)
    bar_height = 0.12
    y_start = 0.82

    for i, (field, label, actual, unit) in enumerate(kpi_metrics):
        target = kpi_targets.get(field)
        y = y_start - i * 0.24

        # Label
        ax_kpi.text(0.0, y + 0.04, label, transform=ax_kpi.transAxes,
                    color=COLORS['sub'], fontsize=9, fontweight='bold')

        if target and target > 0:
            pct = min(actual / target, 1.0)
            color = COLORS['green'] if pct >= 0.8 else (COLORS['yellow'] if pct >= 0.5 else COLORS['red'])

            # Background bar
            ax_kpi.barh(y, 0.62, left=0.17, height=bar_height,
                        color=COLORS['border'], transform=ax_kpi.transAxes)
            # Progress bar
            ax_kpi.barh(y, 0.62 * pct, left=0.17, height=bar_height,
                        color=color, transform=ax_kpi.transAxes)

            # Actual / Target
            fmt_actual = f"${actual:,.0f}" if field == 'revenue' else f"{actual:,.0f}"
            fmt_target = f"${target:,.0f}" if field == 'revenue' else f"{target:,.0f}"
            ax_kpi.text(0.82, y + 0.01, f"{fmt_actual} / {fmt_target} {unit}",
                        transform=ax_kpi.transAxes, color=COLORS['text'], fontsize=9, va='center')
            ax_kpi.text(0.96, y + 0.01, f"{pct*100:.0f}%",
                        transform=ax_kpi.transAxes, color=color, fontsize=10,
                        fontweight='bold', va='center', ha='right')
        else:
            # No KPI set — show actual only
            ax_kpi.barh(y, 0.62, left=0.17, height=bar_height,
                        color=COLORS['border'], transform=ax_kpi.transAxes)
            fmt_actual = f"${actual:,.0f}" if field == 'revenue' else f"{actual:,.0f} {unit}"
            ax_kpi.text(0.82, y + 0.01, f"{fmt_actual}  (no target set)",
                        transform=ax_kpi.transAxes, color=COLORS['sub'], fontsize=9, va='center')

    _setup_fig_style(fig, [ax_kpi])

    # ── Render to BytesIO ──────────────────────────────────────
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=120, bbox_inches='tight',
                facecolor=COLORS['bg'], edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf
