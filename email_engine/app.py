# -*- coding: utf-8 -*-
"""
app.py — Email Engine v2.0 Entry Point
=======================================
Khởi động Desktop GUI.

Usage:
    python app.py
"""
import sys
import os
from pathlib import Path

# ── Ensure core/ is importable ────────────────────────────────
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "core"))

# ── Windows: fix UTF-8 console output ─────────────────────────
if sys.platform == "win32":
    import io
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Check dependencies ─────────────────────────────────────────
def _check_deps():
    missing = []
    for pkg, imp in [
        ("customtkinter", "customtkinter"),
        ("pandas",        "pandas"),
        ("openpyxl",      "openpyxl"),
        ("pyarrow",       "pyarrow"),
    ]:
        try:
            __import__(imp)
        except ImportError:
            missing.append(pkg)
    return missing

missing = _check_deps()
if missing:
    print("=" * 60)
    print("  Missing dependencies. Run:")
    print(f"    pip install {' '.join(missing)}")
    print("  Or:")
    print("    pip install -r requirements.txt")
    print("=" * 60)
    sys.exit(1)

# ── Launch ────────────────────────────────────────────────────
from gui.app_window import AppWindow


def main():
    app = AppWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
