# -*- coding: utf-8 -*-
"""
audit_engine.py — Nelson Freight Architecture Audit CLI
========================================================
Orchestrates all audit subsystems: Architecture Health Check,
Drift Detector, Tech Debt Scanner, and Self-Evaluator.

Usage:
    python audit_engine.py --architecture     # Architecture health check
    python audit_engine.py --drift            # Drift detection
    python audit_engine.py --tech-debt        # Tech debt scan
    python audit_engine.py --self-eval        # System self-evaluation
    python audit_engine.py --full             # Full audit (all 4)
    python audit_engine.py --full --save      # Full audit + save to file
"""
import sys
import os
import argparse
import time

# Ensure scripts dir is in path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from architecture_rules import create_layers, compute_total_score
from rules import data_rules, api_rules, service_rules, security_rules, coupling_rules
from drift_detector import run_drift_detection
from tech_debt_scanner import run_tech_debt_scan
from self_evaluator import run_self_evaluation
from report_generator import (
    format_architecture_report, format_drift_report,
    format_tech_debt_report, format_self_eval_report,
    format_full_report, save_report,
)


def run_architecture_check() -> tuple[str, float]:
    """Run Architecture Health Check against all 6 layers."""
    layers = create_layers()

    # Run all rule checks
    data_rules.run_all(layers)
    api_rules.run_all(layers)
    service_rules.run_all(layers)
    security_rules.run_all(layers)
    coupling_rules.run_all(layers)

    score = compute_total_score(layers)
    report_text = format_architecture_report(layers)
    return report_text, score


def run_drift_check() -> str:
    """Run Architecture Drift Detection."""
    drift_report = run_drift_detection()
    return format_drift_report(drift_report)


def run_debt_check() -> str:
    """Run Technical Debt Scanner."""
    debt_report = run_tech_debt_scan()
    return format_tech_debt_report(debt_report)


def run_self_eval_check(architecture_score: float = 0) -> str:
    """Run System Self-Evaluation."""
    eval_report = run_self_evaluation(architecture_score)
    return format_self_eval_report(eval_report)


def run_full_audit(save_to_file: bool = False) -> str:
    """Run all 4 audit subsystems and produce unified report."""
    start = time.time()

    print("🔍 Running Architecture Health Check...")
    arch_text, arch_score = run_architecture_check()

    print("🔍 Running Architecture Drift Detection...")
    drift_text = run_drift_check()

    print("🔍 Running Technical Debt Scan...")
    debt_text = run_debt_check()

    print("🔍 Running System Self-Evaluation...")
    eval_text = run_self_eval_check(arch_score)

    elapsed = time.time() - start

    full = format_full_report(arch_text, drift_text, debt_text, eval_text)
    full += f"\n\n⏱️ Audit completed in {elapsed:.1f} seconds\n"

    if save_to_file:
        path = save_report(full)
        print(f"\n📄 Report saved: {path}")

    return full


def main():
    parser = argparse.ArgumentParser(
        description="Nelson Freight Architecture Audit Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python audit_engine.py --architecture     # Architecture health check
  python audit_engine.py --drift            # Drift detection
  python audit_engine.py --tech-debt        # Tech debt scan
  python audit_engine.py --self-eval        # System self-evaluation
  python audit_engine.py --full             # Full audit (all 4)
  python audit_engine.py --full --save      # Full audit + save to file
        """,
    )
    parser.add_argument("--architecture", action="store_true", help="Run Architecture Health Check")
    parser.add_argument("--drift", action="store_true", help="Run Architecture Drift Detection")
    parser.add_argument("--tech-debt", action="store_true", help="Run Technical Debt Scanner")
    parser.add_argument("--self-eval", action="store_true", help="Run System Self-Evaluation")
    parser.add_argument("--full", action="store_true", help="Run full audit (all 4 subsystems)")
    parser.add_argument("--save", action="store_true", help="Save report to file")

    args = parser.parse_args()

    # Default to --full if no flags specified
    if not any([args.architecture, args.drift, args.tech_debt, args.self_eval, args.full]):
        args.full = True

    if args.full:
        report = run_full_audit(save_to_file=args.save)
        print(report)
    else:
        if args.architecture:
            text, score = run_architecture_check()
            print(text)
            if args.save:
                save_report(text, "architecture_check.txt")

        if args.drift:
            text = run_drift_check()
            print(text)
            if args.save:
                save_report(text, "drift_report.txt")

        if args.tech_debt:
            text = run_debt_check()
            print(text)
            if args.save:
                save_report(text, "tech_debt_report.txt")

        if args.self_eval:
            text = run_self_eval_check()
            print(text)
            if args.save:
                save_report(text, "self_eval_report.txt")


if __name__ == "__main__":
    main()
