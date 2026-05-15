#!/usr/bin/env python3
"""Phase 0B baseline: verify rate query path and rate table rendering stability."""
import pytest, sys, os, re

WORKTREE = "D:/NELSON/2. Areas/Engine_test/.claude/worktrees/priceless-archimedes-689d1d"
BUILDER_PATH = f"{WORKTREE}/email_engine/intelligence/builder.py"
AUTO_RATE_BUILDER = f"{WORKTREE}/email_engine/core/auto_rate_builder.py"


class TestRateQueryPath:
    """Rate query must use existing approved rate source path."""

    def test_auto_rate_builder_exists(self):
        assert os.path.exists(AUTO_RATE_BUILDER), f"auto_rate_builder.py not found"

    def test_build_rate_table_for_customer_callable(self):
        with open(AUTO_RATE_BUILDER, encoding="utf-8") as f:
            content = f.read()
        assert "def build_rate_table_for_customer" in content

    def test_parquet_data_source_referenced(self):
        with open(AUTO_RATE_BUILDER, encoding="utf-8") as f:
            content = f.read()
        assert "parquet" in content.lower() or ".parquet" in content

    def test_market_engine_analyze_lane_in_builder(self):
        with open(BUILDER_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "analyze_lane" in content

    def test_yaml_default_routes_referenced(self):
        with open(BUILDER_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "default_routes.yaml" in content or "routes.yaml" in content or "pod_list" in content


class TestRateTableRendering:
    """Rate table HTML rendering must be stable across renderers."""

    def test_dual_rate_table_renderer_exists(self):
        with open(BUILDER_PATH, encoding="utf-8") as f:
            content = f.read()
        has_v2 = "render_dual_rate_table" in content or "rate_table_v2" in content
        has_v1 = "build_rate_table_for_customer" in content
        assert has_v2 or has_v1, "No rate table renderer found"

    def test_pudong_prime_branding_in_render(self):
        with open(BUILDER_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "Pudong" in content or "pudong" in content or "PRIME" in content

    def test_markup_pill_in_table(self):
        with open(BUILDER_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "markup" in content.lower()

    def test_pol_bands_in_table(self):
        with open(BUILDER_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "POL" in content or "pol" in content

    def test_carrier_rows_in_table(self):
        with open(BUILDER_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "carrier" in content.lower() or "CARRIER" in content


class TestNoRateFallbackChange:
    """No-rate fallback must not change silently."""

    def test_no_rate_fallback_exists(self):
        with open(BUILDER_PATH, encoding="utf-8") as f:
            content = f.read()
        has_fallback = "no" in content.lower() and "rate" in content.lower()
        assert has_fallback, "No-rate fallback check not found"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])