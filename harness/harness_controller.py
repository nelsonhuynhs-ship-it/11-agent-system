#!/usr/bin/env python3
"""
harness_controller.py - 11-Agent Harness Orchestration
Nelson Freight AI System

Handles:
- Context injection
- State machine
- Phase routing
- Validation
- Retry engine
- Reporting
"""

import os
import sys
import json
import yaml
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any

# Config paths
ENGINE_ROOT = Path("D:/NELSON/2. Areas/Engine_test")
HARNESS_DIR = ENGINE_ROOT / "harness"
VALIDATORS_DIR = HARNESS_DIR / "validators"
REPORTS_DIR = ENGINE_ROOT / "plans" / "reports"
PLANS_DIR = ENGINE_ROOT / "plans"

# Default config
DEFAULT_TIMEOUT = 300
MAX_RETRIES = 3


class HarnessController:
    def __init__(self, config_path: Optional[Path] = None):
        self.config = self._load_config(config_path)
        self.state = {
            "workflow": None,
            "current_phase": None,
            "phase_status": {},
            "start_time": None,
            "errors": []
        }

    def _load_config(self, config_path: Optional[Path]) -> Dict:
        """Load harness configuration"""
        if config_path is None:
            config_path = HARNESS_DIR / "harness-config.yaml"

        if not config_path.exists():
            print(f"[harness] WARNING: Config not found at {config_path}, using defaults")
            return self._default_config()

        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def _default_config(self) -> Dict:
        """Fallback default configuration"""
        return {
            "version": "1.0",
            "phases": [
                {"name": "design-finder", "timeout": 300, "retry": 3},
                {"name": "ux-reviewer", "timeout": 300, "retry": 3},
                {"name": "code-reviewer", "timeout": 300, "retry": 3},
                {"name": "security-auditor", "timeout": 300, "retry": 3},
                {"name": "perf-analyzer", "timeout": 300, "retry": 3},
                {"name": "master-executor", "timeout": 600, "retry": 3},
                {"name": "test-writer", "timeout": 300, "retry": 3},
                {"name": "doc-writer", "timeout": 300, "retry": 3},
                {"name": "tech-debt-tracker", "timeout": 300, "retry": 3},
                {"name": "git-commit", "timeout": 120, "retry": 1}
            ],
            "retry": {"max_attempts": 3, "backoff_multiplier": 2, "initial_delay": 10},
            "notification": {"telegram_group": True, "on_failure": True, "on_success": True}
        }

    def _load_validator(self, phase_name: str) -> Dict:
        """Load validator for specific phase"""
        validator_path = VALIDATORS_DIR / f"{phase_name}.yaml"
        if validator_path.exists():
            with open(validator_path, 'r') as f:
                return yaml.safe_load(f)
        return {"phase": phase_name, "criteria": {}, "pass_conditions": [], "fail_actions": []}

    def inject_context(self, task: str, context: Optional[Dict] = None) -> Dict:
        """Prepare context for agent execution"""
        return {
            "task": task,
            "timestamp": datetime.now().isoformat(),
            "context": context or {},
            "workspace": str(ENGINE_ROOT),
            "reports_dir": str(REPORTS_DIR),
            "plans_dir": str(PLANS_DIR),
            "harness_version": self.config.get("version", "1.0")
        }

    def validate_phase(self, phase_name: str, output: Optional[Dict] = None) -> Dict:
        """Validate phase output against validator criteria"""
        validator = self._load_validator(phase_name)
        result = {
            "phase": phase_name,
            "status": "passed",
            "timestamp": datetime.now().isoformat(),
            "details": []
        }

        # Check output exists
        if output:
            output_path = Path(output.get("path", ""))
            if output_path and not output_path.exists():
                result["status"] = "failed"
                result["details"].append(f"Output file missing: {output_path}")

        # Check pass conditions
        pass_conditions = validator.get("pass_conditions", [])
        for condition in pass_conditions:
            if condition == "output_exists":
                # Handled above
                pass
            elif condition == "output_not_empty":
                if output and output.get("size", 0) < 100:
                    result["status"] = "failed"
                    result["details"].append("Output too small")

        # Fail actions
        if result["status"] == "failed":
            fail_actions = validator.get("fail_actions", [])
            result["actions"] = fail_actions

        return result

    def retry_phase(self, phase_name: str, attempt: int, max_retries: int) -> bool:
        """Calculate retry delay and determine if should retry"""
        if attempt >= max_retries:
            return False

        config = self.config.get("retry", {})
        initial_delay = config.get("initial_delay", 10)
        multiplier = config.get("backoff_multiplier", 2)

        delay = initial_delay * (multiplier ** attempt)
        print(f"[harness] Retry {phase_name}: attempt {attempt + 1}/{max_retries}, waiting {delay}s")
        time.sleep(delay)
        return True

    def execute_phase(self, phase_name: str, task_context: Dict) -> Dict:
        """Execute a single phase with retry logic"""
        phase_config = next(
            (p for p in self.config.get("phases", []) if p["name"] == phase_name),
            {"timeout": DEFAULT_TIMEOUT, "retry": MAX_RETRIES}
        )

        max_retries = phase_config.get("retry", MAX_RETRIES)
        timeout = phase_config.get("timeout", DEFAULT_TIMEOUT)
        attempt = 0

        while attempt <= max_retries:
            print(f"[harness] Executing {phase_name} (attempt {attempt + 1}/{max_retries + 1})")

            # Build phase plan file
            phase_plan = {
                "phase": phase_name,
                "task": task_context.get("task"),
                "context": task_context,
                "attempt": attempt + 1
            }

            plan_file = PLANS_DIR / f"phase-{phase_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
            with open(plan_file, 'w') as f:
                json.dump(phase_plan, f, indent=2)

            # Execute via mm-delegate-phase.sh
            start_time = time.time()
            try:
                result = subprocess.run(
                    [
                        "bash",
                        str(Path.home() / ".claude" / "bin" / "mm-delegate-phase.sh"),
                        str(plan_file),
                        "harness-workflow",
                        phase_name
                    ],
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                duration = time.time() - start_time

                if result.returncode == 0:
                    print(f"[harness] {phase_name} completed in {duration:.1f}s")
                    return {
                        "phase": phase_name,
                        "status": "completed",
                        "duration": duration,
                        "output": str(plan_file)
                    }
                else:
                    print(f"[harness] {phase_name} failed: {result.stderr[:200]}")

            except subprocess.TimeoutExpired:
                print(f"[harness] {phase_name} timed out after {timeout}s")
            except Exception as e:
                print(f"[harness] {phase_name} error: {str(e)}")

            attempt += 1

            # Check if should retry
            if not self.retry_phase(phase_name, attempt, max_retries):
                break

        # All retries exhausted
        return {
            "phase": phase_name,
            "status": "failed",
            "attempts": attempt,
            "error": "Max retries exceeded"
        }

    def run_workflow(self, task: str, phases: Optional[List[str]] = None) -> Dict:
        """Run full 11-agent workflow"""
        self.state["workflow"] = "11-agent-harness"
        self.state["start_time"] = datetime.now().isoformat()
        self.state["task"] = task

        # Default phases if not specified
        if phases is None:
            phases = [p["name"] for p in self.config.get("phases", [])]

        print(f"[harness] Starting workflow with {len(phases)} phases")
        print(f"[harness] Task: {task[:100]}...")

        context = self.inject_context(task)
        results = []

        for phase_name in phases:
            self.state["current_phase"] = phase_name

            result = self.execute_phase(phase_name, context)
            results.append(result)

            self.state["phase_status"][phase_name] = result["status"]

            # Validation
            validation = self.validate_phase(phase_name, result)
            if validation["status"] == "failed":
                print(f"[harness] {phase_name} validation FAILED")
                fail_actions = validation.get("actions", [])

                # Check for block_proceed
                if any(a.get("block_proceed") for a in fail_actions):
                    print(f"[harness] BLOCKED: {phase_name} failure blocks workflow")
                    break

                # Check for escalate
                if any(a.get("escalate") for a in fail_actions):
                    print(f"[harness] ESCALATE: {phase_name} requires commander intervention")
                    # In real impl, would notify via Telegram
                    break

            # Check for fallback
            validation = self.validate_phase(phase_name, result)
            fail_actions = validation.get("actions", [])
            fallback = next((a.get("fallback") for a in fail_actions if "fallback" in a), None)
            if fallback:
                print(f"[harness] Fallback: proceeding to {fallback}")

        # Generate final report
        end_time = datetime.now().isoformat()
        self.state["end_time"] = end_time
        self.state["results"] = results

        summary = self.generate_report()
        return summary

    def generate_report(self) -> Dict:
        """Generate workflow execution report"""
        summary = {
            "workflow": self.state["workflow"],
            "start_time": self.state["start_time"],
            "end_time": self.state["end_time"],
            "task": self.state.get("task", ""),
            "total_phases": len(self.state["phase_status"]),
            "completed": sum(1 for s in self.state["phase_status"].values() if s == "completed"),
            "failed": sum(1 for s in self.state["phase_status"].values() if s == "failed"),
            "phases": self.state["phase_status"],
            "errors": self.state.get("errors", [])
        }

        # Save report
        report_path = REPORTS_DIR / f"harness-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

        with open(report_path, 'w') as f:
            f.write("# Harness Execution Report\n\n")
            f.write(f"**Workflow:** {summary['workflow']}\n")
            f.write(f"**Start:** {summary['start_time']}\n")
            f.write(f"**End:** {summary['end_time']}\n")
            f.write(f"**Task:** {summary['task'][:200]}...\n\n")
            f.write(f"## Phase Status\n\n")
            f.write("| Phase | Status |\n")
            f.write("|-------|--------|\n")
            for phase, status in summary['phases'].items():
                emoji = "✅" if status == "completed" else "❌"
                f.write(f"| {phase} | {emoji} {status} |\n")
            f.write(f"\n**Total:** {summary['completed']}/{summary['total_phases']} completed\n")

        summary["report_path"] = str(report_path)
        print(f"[harness] Report saved to: {report_path}")

        return summary


def main():
    """CLI entry point"""
    if len(sys.argv) < 2:
        print("Usage: python harness_controller.py <task> [phase1,phase2,...]")
        print("  task       - Task description")
        print("  phases     - Optional comma-separated list of phases to run")
        sys.exit(1)

    task = sys.argv[1]
    phases = None

    if len(sys.argv) > 2:
        phases = [p.strip() for p in sys.argv[2].split(",")]

    controller = HarnessController()
    result = controller.run_workflow(task, phases)

    print("\n" + "=" * 50)
    print("WORKFLOW COMPLETE")
    print("=" * 50)
    print(f"Completed: {result['completed']}/{result['total_phases']}")
    print(f"Failed: {result['failed']}/{result['total_phases']}")
    print(f"Report: {result.get('report_path', 'N/A')}")

    sys.exit(0 if result['failed'] == 0 else 1)


if __name__ == "__main__":
    main()