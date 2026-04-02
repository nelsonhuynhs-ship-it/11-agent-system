# -*- coding: utf-8 -*-
"""
architecture_rules.py — Blueprint Definitions & Scoring Weights
================================================================
Defines the target architecture for Nelson Freight Platform.
All audit modules reference these rules as the source of truth.
"""
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = os.environ.get(
    "NELSON_BASE_DIR",
    r"D:\NELSON\2. Areas\PricingSystem\Engine_test"
)
API_DIR       = os.path.join(BASE_DIR, "api")
BOT_DIR       = os.path.join(BASE_DIR, "TelegramBot")
WEBAPP_DIR    = os.path.join(BASE_DIR, "webapp")
ERP_DIR       = os.path.join(BASE_DIR, "ERP")
PRICING_DIR   = os.path.join(BASE_DIR, "Pricing_Engine")
EMAIL_DIR     = os.environ.get("NELSON_EMAIL_DIR", r"D:\NELSON\email_engine")
INTEGRATION   = os.path.join(BASE_DIR, "Integration")


class Severity(Enum):
    CRITICAL = "CRITICAL"
    HIGH     = "HIGH"
    MEDIUM   = "MEDIUM"
    LOW      = "LOW"


@dataclass
class Finding:
    """A single audit finding."""
    rule_id:     str
    layer:       str
    severity:    Severity
    title:       str
    detail:      str
    file_path:   Optional[str] = None
    line_number: Optional[int] = None
    suggestion:  str = ""


@dataclass
class LayerScore:
    """Score for a single architecture layer."""
    name:       str
    weight:     float
    score:      float = 10.0  # start perfect, deduct per finding
    findings:   list = field(default_factory=list)
    max_score:  float = 10.0

    def deduct(self, points: float, finding: Finding):
        self.score = max(0, self.score - points)
        self.findings.append(finding)

    @property
    def weighted_score(self) -> float:
        return self.score * self.weight


# ── Blueprint Layer Definitions ───────────────────────────────────────────────

LAYER_WEIGHTS = {
    "Data Layer":        0.20,
    "API Layer":         0.20,
    "Service Layer":     0.15,
    "Client Isolation":  0.15,
    "Event System":      0.15,
    "Security":          0.15,
}


def create_layers() -> dict[str, LayerScore]:
    """Create fresh LayerScore objects for a new audit run."""
    return {
        name: LayerScore(name=name, weight=weight)
        for name, weight in LAYER_WEIGHTS.items()
    }


def compute_total_score(layers: dict[str, LayerScore]) -> float:
    """Compute weighted total architecture score (0-10)."""
    total = sum(ls.weighted_score for ls in layers.values())
    return round(total, 1)


# ── Deduction Rules ──────────────────────────────────────────────────────────
# Defines how much to deduct per violation type

DEDUCTION_MAP = {
    # Data Layer violations
    "json_as_database":           (2.0, Severity.CRITICAL, "Data Layer"),
    "no_data_access_layer":       (1.5, Severity.CRITICAL, "Data Layer"),
    "direct_parquet_outside_dal": (1.0, Severity.HIGH,     "Data Layer"),
    "multiple_writers_no_lock":   (1.5, Severity.CRITICAL, "Data Layer"),
    "hardcoded_data_path":        (0.5, Severity.MEDIUM,   "Data Layer"),

    # API Layer violations
    "monolith_server":            (1.5, Severity.HIGH,     "API Layer"),
    "file_too_large":             (0.5, Severity.MEDIUM,   "API Layer"),
    "no_error_handler":           (0.5, Severity.MEDIUM,   "API Layer"),
    "inline_import":              (0.3, Severity.LOW,      "API Layer"),
    "no_input_validation":        (0.5, Severity.MEDIUM,   "API Layer"),

    # Service Layer violations
    "cross_service_db_access":    (1.0, Severity.HIGH,     "Service Layer"),
    "god_function":               (0.5, Severity.MEDIUM,   "Service Layer"),
    "circular_dependency":        (1.0, Severity.HIGH,     "Service Layer"),
    "missing_service_boundary":   (0.5, Severity.MEDIUM,   "Service Layer"),

    # Client Isolation violations
    "client_reads_file":          (1.5, Severity.CRITICAL, "Client Isolation"),
    "client_has_business_logic":  (1.0, Severity.HIGH,     "Client Isolation"),
    "bot_bypasses_api":           (2.0, Severity.CRITICAL, "Client Isolation"),
    "erp_direct_file_access":     (1.0, Severity.HIGH,     "Client Isolation"),

    # Event System violations
    "no_event_sourcing":          (1.0, Severity.HIGH,     "Event System"),
    "mutable_state_overwrite":    (1.5, Severity.CRITICAL, "Event System"),
    "no_background_workers":      (0.5, Severity.MEDIUM,   "Event System"),
    "missing_event_table":        (1.0, Severity.HIGH,     "Event System"),

    # Security violations
    "no_authentication":          (2.0, Severity.CRITICAL, "Security"),
    "endpoint_no_auth":           (0.5, Severity.HIGH,     "Security"),
    "hardcoded_secret":           (1.5, Severity.CRITICAL, "Security"),
    "no_rbac":                    (1.0, Severity.HIGH,     "Security"),
    "no_rate_limiting":           (0.3, Severity.MEDIUM,   "Security"),
}


def apply_deduction(
    layers: dict[str, LayerScore],
    violation_type: str,
    title: str,
    detail: str,
    file_path: str = None,
    line_number: int = None,
    suggestion: str = "",
) -> Finding:
    """Apply a deduction from the DEDUCTION_MAP to the appropriate layer."""
    if violation_type not in DEDUCTION_MAP:
        raise ValueError(f"Unknown violation type: {violation_type}")

    points, severity, layer_name = DEDUCTION_MAP[violation_type]
    finding = Finding(
        rule_id=violation_type,
        layer=layer_name,
        severity=severity,
        title=title,
        detail=detail,
        file_path=file_path,
        line_number=line_number,
        suggestion=suggestion,
    )
    layers[layer_name].deduct(points, finding)
    return finding


# ── Target Architecture Patterns ─────────────────────────────────────────────
# Used by drift_detector to identify violations

# Patterns that should NOT appear in client-side code
FORBIDDEN_IN_CLIENTS = {
    "bot": [
        r'pd\.read_parquet\(',
        r'open\(["\'].*\.json["\']',
        r'json\.load\(',
        r'openpyxl\.load_workbook\(',
        r'shipment_state\.json',
        r'quotes\.json',
        r'outlook_dataset\.json',
    ],
    "webapp": [
        r'fs\.readFile',
        r'require\(["\']fs["\']\)',
        r'\.json["\'].*readFile',
    ],
    "erp_scripts": [
        r'pd\.read_parquet\(',  # Should go via API
    ],
}

# Files that constitute "JSON as database" anti-pattern
JSON_DATABASE_FILES = [
    "quotes.json",
    "shipment_state.json",
    "outlook_dataset.json",
    "sync_state.json",
]

# Maximum acceptable file sizes (lines)
MAX_FILE_LINES = {
    "default": 500,
    "server.py": 300,      # After split, each router < 300
    "bot_v5.py": 2000,     # After refactor
    "audit_engine.py": 400,
}

# Hardcoded paths that should be environment variables
HARDCODED_PATH_PATTERNS = [
    r'["\']D:\\\\NELSON\\\\',
    r'["\']D:/NELSON/',
    r"[\"']D:\\NELSON\\",
    r'Path\(r["\']D:\\\\',
    r'Path\(r["\']D:/',
]

# Expected target structure after full migration
TARGET_API_STRUCTURE = {
    "app.py":                "Entry point + middleware mount",
    "routers/rate_router.py":     "Rate endpoints",
    "routers/quote_router.py":    "Quote endpoints",
    "routers/shipment_router.py": "Shipment endpoints",
    "routers/email_router.py":    "Email event endpoints",
    "routers/intelligence_router.py": "Intelligence endpoints",
    "routers/dashboard_router.py":    "Dashboard endpoints",
    "routers/auth_router.py":    "Auth endpoints",
    "routers/erp_router.py":     "ERP integration endpoints",
    "services/data_access.py":   "Data access layer",
    "services/event_bus.py":     "Event publishing",
}
