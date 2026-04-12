"""Unit test for refresh-v14 normalize_container_types helper.

Tests the 45'HQ → 45HQ collapse that prevents pivot column collision.
Also verifies the legacy ERP.core.refresh module is fully deprecated.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

REFRESH_V14 = Path("D:/OneDrive/NelsonData/erp/refresh-v14.py")

# Add repo root for ERP.core.refresh import in deprecation tests
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_refresh_module():
    """Import refresh-v14.py as a module.

    refresh-v14.py has top-level side effects (loads parquet + PUC xlsx). To
    avoid triggering those heavy loads during unit tests, we extract just the
    helper function via AST surgery instead of exec'ing the whole script.
    This keeps the test hermetic and fast (~50ms vs ~3-5s full load).
    """
    if not REFRESH_V14.exists():
        pytest.skip(f"refresh-v14.py not found at {REFRESH_V14}")

    import ast
    import types

    source = REFRESH_V14.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Pull only the import statements + normalize_container_types function
    wanted_fn = "normalize_container_types"
    kept_nodes = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            kept_nodes.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name == wanted_fn:
            kept_nodes.append(node)
            break

    if not any(isinstance(n, ast.FunctionDef) and n.name == wanted_fn for n in kept_nodes):
        pytest.skip(f"{wanted_fn} not found in refresh-v14.py")

    minimal = ast.Module(body=kept_nodes, type_ignores=[])
    ast.fix_missing_locations(minimal)
    code = compile(minimal, str(REFRESH_V14), "exec")

    module = types.ModuleType("_refresh_v14_helpers_only")
    try:
        exec(code, module.__dict__)
    except Exception as e:
        pytest.skip(f"refresh-v14 helper extraction failed: {e}")

    return module


@pytest.fixture(scope="module")
def refresh_v14():
    return _load_refresh_module()


# ---------------------------------------------------------------------------
# normalize_container_types
# ---------------------------------------------------------------------------
def test_normalize_collapses_45hq_variants(refresh_v14):
    """Core bug fix: "45'HQ" → "45HQ" so pivot sees one container column."""
    df = pd.DataFrame({"Container_Type": ["45'HQ", "45HQ", "40HQ", "20GP"]})
    out = refresh_v14.normalize_container_types(df)
    assert (out["Container_Type"] == "45HQ").sum() == 2
    assert "45'HQ" not in out["Container_Type"].values
    assert set(out["Container_Type"]) == {"45HQ", "40HQ", "20GP"}


def test_normalize_preserves_non_matching_values(refresh_v14):
    df = pd.DataFrame({"Container_Type": ["40HQ", "20GP", "40NOR", "45HQ"]})
    out = refresh_v14.normalize_container_types(df)
    assert list(out["Container_Type"]) == ["40HQ", "20GP", "40NOR", "45HQ"]


def test_normalize_returns_copy_not_view(refresh_v14):
    """Safety: helper must not mutate caller's DataFrame in place."""
    df = pd.DataFrame({"Container_Type": ["45'HQ", "45HQ"]})
    out = refresh_v14.normalize_container_types(df)
    df.loc[0, "Container_Type"] = "SHOULD_NOT_PROPAGATE"
    assert "45HQ" in out["Container_Type"].values
    assert "SHOULD_NOT_PROPAGATE" not in out["Container_Type"].values


def test_normalize_handles_missing_column(refresh_v14):
    """No-op on DataFrames that don't have a Container_Type column."""
    df = pd.DataFrame({"Other_Col": [1, 2, 3]})
    out = refresh_v14.normalize_container_types(df)
    assert "Container_Type" not in out.columns
    assert len(out) == 3


def test_normalize_preserves_other_columns(refresh_v14):
    """Other columns pass through unchanged."""
    df = pd.DataFrame({
        "Container_Type": ["45'HQ", "40HQ"],
        "POL": ["HCM", "HPH"],
        "Amount": [1500, 2500],
    })
    out = refresh_v14.normalize_container_types(df)
    assert list(out["POL"]) == ["HCM", "HPH"]
    assert list(out["Amount"]) == [1500, 2500]
    assert list(out["Container_Type"]) == ["45HQ", "40HQ"]


# ---------------------------------------------------------------------------
# Legacy ERP.core.refresh deprecation
# ---------------------------------------------------------------------------
def test_legacy_refresh_data_raises():
    """Calling legacy refresh_data must fail loudly with RuntimeError."""
    from ERP.core import refresh as legacy
    with pytest.raises(RuntimeError, match="dead code"):
        legacy.refresh_data()


def test_legacy_load_and_process_parquet_raises():
    from ERP.core import refresh as legacy
    with pytest.raises(RuntimeError, match="dead code"):
        legacy.load_and_process_parquet()


def test_legacy_main_raises():
    from ERP.core import refresh as legacy
    with pytest.raises(RuntimeError, match="dead code"):
        legacy.main()
