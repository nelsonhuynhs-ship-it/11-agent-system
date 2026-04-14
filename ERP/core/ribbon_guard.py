"""
ribbon_guard.py — preserve CustomUI ribbon across openpyxl saves
=================================================================
`openpyxl.save()` silently strips `customUI/customUI14.xml` from .xlsm files.
This helper re-injects the ribbon XML after any save so tabs Pricing/Operations
don't disappear.

Usage:
    from ERP.core.ribbon_guard import save_preserving_ribbon

    save_preserving_ribbon(wb, erp_file)      # instead of wb.save(erp_file)

Under the hood delegates to `customui_utils.ensure_customui()` which lives at:
    D:/OneDrive/NelsonData/erp/customui_utils.py
"""
from __future__ import annotations

import importlib.util
import os
import sys
from typing import Final

# Fallback paths to both customui_utils.py and CustomUI_v14.xml
_CANDIDATE_CUSTOMUI_DIRS: Final = [
    r"D:\OneDrive\NelsonData\erp",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "OneDrive", "NelsonData", "erp"),
]


def _locate(filename: str) -> str | None:
    for d in _CANDIDATE_CUSTOMUI_DIRS:
        p = os.path.join(d, filename)
        if os.path.exists(p):
            return os.path.abspath(p)
    return None


def _load_ensure_customui():
    util_path = _locate("customui_utils.py")
    if not util_path:
        return None
    spec = importlib.util.spec_from_file_location("customui_utils", util_path)
    if not spec or not spec.loader:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "ensure_customui", None)


def save_preserving_ribbon(wb, erp_file: str, xml_path: str | None = None) -> dict:
    """
    Save workbook, then re-inject ribbon XML.

    Returns dict from ensure_customui (or {"skipped": reason}).
    """
    wb.save(erp_file)
    return reinject_ribbon(erp_file, xml_path=xml_path)


def reinject_ribbon(erp_file: str, xml_path: str | None = None) -> dict:
    """Re-inject customUI XML without saving (use after wb.save() done elsewhere)."""
    ensure = _load_ensure_customui()
    if ensure is None:
        return {"skipped": "customui_utils.py not found"}
    xml = xml_path or _locate("CustomUI_v14.xml")
    if not xml:
        return {"skipped": "CustomUI_v14.xml not found"}
    return ensure(erp_file, xml)


if __name__ == "__main__":
    # CLI: python ERP/core/ribbon_guard.py <xlsm>
    if len(sys.argv) < 2:
        print("Usage: python ribbon_guard.py <path/to/ERP_Master_v14.xlsm>")
        sys.exit(1)
    print("Re-inject result:", reinject_ribbon(sys.argv[1]))
