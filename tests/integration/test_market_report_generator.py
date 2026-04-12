"""Integration smoke test: generate a DOCX end-to-end with mocked inputs."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

docx = pytest.importorskip("docx")

from Pricing_Engine.market_report.report_generator import generate_weekly_report
from Pricing_Engine.market_report.schemas import Catalyst, CostingItem


def test_generate_weekly_report_smoke(tmp_path: Path):
    """Build a report with mocked costing + catalysts; verify DOCX written."""
    mock_costing = [
        CostingItem(
            lane="WC", carrier="ONE", rate_type="FIX", container="40HC",
            price=1835.0, valid_from=date(2026, 4, 1), valid_to=date(2026, 4, 8),
            is_pudong_best=True, spread_vs_lane_avg=-50.0,
        ),
        CostingItem(
            lane="WC", carrier="WHL", rate_type="FIX", container="40HC",
            price=2000.0, valid_from=date(2026, 4, 1), valid_to=date(2026, 4, 7),
            is_pudong_best=True, spread_vs_lane_avg=115.0,
        ),
        CostingItem(
            lane="EC", carrier="YML", rate_type="FIX", container="40HC",
            price=2723.0, valid_from=date(2026, 4, 1), valid_to=date(2026, 4, 12),
            is_pudong_best=True, spread_vs_lane_avg=-100.0,
        ),
        CostingItem(
            lane="GULF", carrier="CMA", rate_type="FIX", container="40HC",
            price=3000.0, valid_from=date(2026, 4, 1), valid_to=date(2026, 4, 15),
            is_pudong_best=True, spread_vs_lane_avg=0.0,
        ),
    ]
    mock_catalysts = [
        Catalyst(
            source="CarrierNotice",
            category="surcharge",
            headline="HPL EFS $320/40HC from 23-Mar",
            body="Hapag-Lloyd announces emergency fuel surcharge on TP non-FMC lanes.",
            impact_direction="UP",
            impact_magnitude="MED",
            affected_lanes=["WC", "EC"],
            affected_carriers=["HPL"],
            effective_date=date(2026, 3, 23),
            confidence=0.9,
            ingested_at=datetime.now(),
        )
    ]

    out = tmp_path / "report-2026-W14-predict-2026-W15.docx"
    result = generate_weekly_report(
        prev_week="2026-W14",
        next_week="2026-W15",
        output_path=out,
        override_catalysts=mock_catalysts,
        override_costing=mock_costing,
    )
    assert result.exists(), f"DOCX not created at {result}"
    assert result.stat().st_size > 2000, "DOCX suspiciously small"

    # Open and spot-check the content structure
    doc = docx.Document(str(result))
    all_text = "\n".join(p.text for p in doc.paragraphs)
    assert "BÁO CÁO THỊ TRƯỜNG TUẦN" in all_text
    assert "I. COSTING" in all_text
    assert "II. CAPACITY" in all_text
    assert "III. CHALLENGE & CHANCE" in all_text
    assert "IV. FORECAST TUẦN 2026-W15" in all_text
    assert "V. BACKTEST TUẦN 2026-W14" in all_text
    # Content from mocks
    assert "ONE" in all_text
    assert "HPL EFS" in all_text
