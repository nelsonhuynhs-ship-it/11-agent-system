"""Verify core Python modules import cleanly."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

try:
    from ERP.core.active_jobs_cols import COL, HDR_ROW, DATA_START, STAGE_NAMES
    from ERP.core.ribbon_guard import save_preserving_ribbon  # noqa: F401
    from ERP.jobs.email_builder import build_mailto_link, load_rules  # noqa: F401
except Exception as ex:  # pragma: no cover
    print(f"[FAIL] import error: {ex}")
    sys.exit(1)

print(f"  COL keys       : {len(COL)}")
print(f"  HDR_ROW        : {HDR_ROW}")
print(f"  DATA_START     : {DATA_START}")
print(f"  STAGE_NAMES    : {len(STAGE_NAMES)} stages")
print("IMPORTS: OK")
sys.exit(0)
