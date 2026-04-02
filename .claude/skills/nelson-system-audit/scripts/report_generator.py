# -*- coding: utf-8 -*-
"""
report_generator.py — Audit Report Formatter
==============================================
Generates formatted text reports from audit results.
Outputs: console (colored), markdown file, JSON.
"""
import os
import json
from datetime import datetime

from architecture_rules import LayerScore, Finding, Severity, compute_total_score


SEVERITY_EMOJI = {
    Severity.CRITICAL: "🔴",
    Severity.HIGH:     "🟡",
    Severity.MEDIUM:   "🟢",
    Severity.LOW:      "⚪",
}


def format_architecture_report(layers: dict[str, LayerScore]) -> str:
    """Format Architecture Health Check as text report."""
    total = compute_total_score(layers)
    lines = [
        "═" * 60,
        "  NELSON FREIGHT — ARCHITECTURE HEALTH REPORT",
        "═" * 60,
        f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"  Architecture Score: {total} / 10.0",
        "═" * 60,
        "",
        "  LAYER SCORES",
        "  " + "─" * 40,
    ]

    for name, ls in layers.items():
        bar_len = int(ls.score)
        bar = "█" * bar_len + "░" * (10 - bar_len)
        findings_count = len(ls.findings)
        flag = f"  ({findings_count} findings)" if findings_count else ""
        lines.append(f"  {name:<20} {ls.score:>4.1f} {bar}{flag}")

    lines.extend(["", "  FINDINGS", "  " + "─" * 40])

    all_findings = []
    for ls in layers.values():
        all_findings.extend(ls.findings)

    all_findings.sort(key=lambda f: list(Severity).index(f.severity))

    if not all_findings:
        lines.append("  ✅ No architecture violations detected!")
    else:
        for f in all_findings:
            emoji = SEVERITY_EMOJI.get(f.severity, "⚪")
            lines.append(f"  {emoji} [{f.severity.value}] {f.title}")
            lines.append(f"     {f.detail}")
            if f.file_path:
                loc = f"{f.file_path}"
                if f.line_number:
                    loc += f":{f.line_number}"
                lines.append(f"     📁 {loc}")
            if f.suggestion:
                lines.append(f"     💡 {f.suggestion}")
            lines.append("")

    lines.extend([
        "═" * 60,
        f"  Conclusion: {'✅ Architecture conforms to Blueprint' if total >= 7 else '⚠️ Architecture needs attention' if total >= 5 else '🔴 Significant architecture drift detected'}",
        "═" * 60,
    ])
    return "\n".join(lines)


def format_drift_report(drift_report) -> str:
    """Format Drift Detection report."""
    lines = [
        "═" * 60,
        "  NELSON FREIGHT — ARCHITECTURE DRIFT REPORT",
        "═" * 60,
        f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"  Total Drifts: {drift_report.total_count}",
        f"  Critical: {drift_report.critical_count} | High: {drift_report.high_count} | Medium: {drift_report.medium_count}",
        "═" * 60,
        "",
    ]

    if not drift_report.violations:
        lines.append("  ✅ No architecture drift detected!")
        return "\n".join(lines)

    # Group by category
    categories: dict[str, list] = {}
    for v in drift_report.violations:
        categories.setdefault(v.category, []).append(v)

    for cat, violations in sorted(categories.items()):
        lines.append(f"  [{cat.upper()}]")
        lines.append("  " + "─" * 40)
        for v in violations:
            emoji = SEVERITY_EMOJI.get(v.severity, "⚪")
            lines.append(f"  {emoji} {v.description}")
            if v.file_path:
                loc = v.file_path
                if v.line_number:
                    loc += f":{v.line_number}"
                lines.append(f"     📁 {loc}")
            if v.suggestion:
                lines.append(f"     💡 {v.suggestion}")
        lines.append("")

    return "\n".join(lines)


def format_tech_debt_report(debt_report) -> str:
    """Format Technical Debt report."""
    lines = [
        "═" * 60,
        "  NELSON FREIGHT — TECHNICAL DEBT REPORT",
        "═" * 60,
        f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"  Total Debt Items: {debt_report.total_count}",
        f"  Debt Score: {debt_report.debt_score} / 10 (lower is better)",
        "═" * 60,
        "",
    ]

    if not debt_report.items:
        lines.append("  ✅ No significant technical debt detected!")
        return "\n".join(lines)

    # Group by severity
    for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]:
        items = [i for i in debt_report.items if i.severity == severity]
        if not items:
            continue
        emoji = SEVERITY_EMOJI.get(severity, "⚪")
        lines.append(f"  {emoji} {severity.value} ({len(items)} items)")
        lines.append("  " + "─" * 40)
        for item in items:
            lines.append(f"    • {item.title}")
            lines.append(f"      {item.detail}")
            if item.file_path:
                lines.append(f"      📁 {item.file_path}")
            if item.suggestion:
                lines.append(f"      💡 {item.suggestion}")
        lines.append("")

    return "\n".join(lines)


def format_self_eval_report(eval_report) -> str:
    """Format Self-Evaluation report."""
    lines = [
        "═" * 60,
        "  NELSON FREIGHT — SYSTEM SELF-EVALUATION",
        "═" * 60,
        f"  Date: {eval_report.timestamp[:19]}",
        f"  Architecture Score:  {eval_report.architecture_score:.1f} / 10",
        f"  Performance Score:   {eval_report.performance_score:.1f} / 10",
        f"  Reliability Score:   {eval_report.reliability_score:.1f} / 10",
        "═" * 60,
        "",
        "  HEALTH CHECKS",
        "  " + "─" * 40,
    ]

    status_emoji = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}

    for check in eval_report.checks:
        emoji = status_emoji.get(check.status, "❓")
        latency = f" ({check.latency_ms:.0f}ms)" if check.latency_ms else ""
        lines.append(f"  {emoji} {check.name:<20} {check.value}{latency}")
        if check.detail:
            lines.append(f"     {check.detail}")

    lines.append(f"\n  Passed: {eval_report.pass_count}/{eval_report.total_checks}")

    if eval_report.risk_flags:
        lines.extend(["", "  ⚠️ RISK FLAGS", "  " + "─" * 40])
        for flag in eval_report.risk_flags:
            lines.append(f"  🔴 {flag}")

    lines.append("")
    return "\n".join(lines)


def format_full_report(arch_text: str, drift_text: str, debt_text: str, eval_text: str) -> str:
    """Combine all reports into unified full audit report."""
    header = [
        "╔" + "═" * 58 + "╗",
        "║    NELSON FREIGHT — FULL SYSTEM AUDIT REPORT            ║",
        "║    Generated: " + datetime.now().strftime('%Y-%m-%d %H:%M') + " " * 28 + "║",
        "╚" + "═" * 58 + "╝",
        "",
    ]
    return "\n".join(header) + "\n\n" + arch_text + "\n\n" + drift_text + "\n\n" + debt_text + "\n\n" + eval_text


def save_report(content: str, filename: str = None) -> str:
    """Save report to file, return path."""
    if filename is None:
        filename = f"audit_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path
