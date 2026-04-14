"""test_email_builder.py — booking email builder v2.0 tests.

Covers build_subject, build_email_body, build_mailto_link with real booking_rules.json.
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import unquote, urlparse, parse_qs

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "ERP" / "jobs"))
from email_builder import (
    build_email_body,
    build_mailto_link,
    build_subject,
    load_rules,
)

RULES_FILE = str(
    Path(__file__).parent.parent / "ERP" / "carrier_rules" / "booking_rules.json"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rules():
    return load_rules(RULES_FILE)


def _hph_dry_job(**overrides) -> dict:
    j = {
        "Customer_Name": "NAFOODS", "POL": "HPH", "POD": "USLGB",
        "Place": "LOS ANGELES, CA", "Carrier": "ONE",
        "Container_Type": "40HQ", "Quantity": 2,
        "Contract_No": "SHA0005N25",
        "Group_Rate": "990132 – S1 Group SOC Big 4",
    }
    j.update(overrides)
    return j


def _hcm_reefer_job(**overrides) -> dict:
    j = {
        "Customer_Name": "NAFOODS", "POL": "HCM", "POD": "USLAX",
        "Place": "LOS ANGELES, CA", "Carrier": "ONE",
        "Container_Type": "40RF", "Quantity": 1,
        "Contract_No": "SHA0005N25",
    }
    j.update(overrides)
    return j


# ---------------------------------------------------------------------------
# build_subject tests
# ---------------------------------------------------------------------------

class TestBuildSubject:

    def test_hph_dry_subject_structure(self, rules: dict):
        job = _hph_dry_job()
        subject = build_subject(job, rules)
        assert "NAFOODS BOOKING" in subject
        assert "HPH" in subject
        assert "LOS ANGELES" in subject.upper() or "USLGB" in subject
        assert "40HC" in subject  # 40HQ displays as 40HC per container_display
        assert "ONE" in subject
        assert "NELSON" in subject

    def test_hcm_reefer_subject_structure(self, rules: dict):
        job = _hcm_reefer_job()
        subject = build_subject(job, rules)
        assert "NAFOODS BOOKING" in subject
        assert "40RF" in subject
        assert "ONE" in subject

    def test_cma_payment_term_subject(self, rules: dict):
        job = {
            "Customer_Name": "TRAN ANH", "POL": "HCM", "POD": "USNYC",
            "Place": "NEW YORK, NY", "Carrier": "CMA",
            "Container_Type": "40GP", "Quantity": 1,
            "Contract_No": "CMA-SCFI-2026",
        }
        subject = build_subject(job, rules)
        assert "TRAN ANH BOOKING" in subject
        assert "CMA" in subject

    def test_place_equals_pod_no_via_duplication(self, rules: dict):
        """When Place == POD, subject must use 'POL-POD' not 'POL-POD VIA POD'."""
        job = _hph_dry_job(Place="USLGB", POD="USLGB")
        subject = build_subject(job, rules)
        # VIA should NOT appear since place == pod
        assert "VIA" not in subject, (
            f"Subject duplicated VIA when place==pod: {subject}"
        )
        assert "HPH-USLGB" in subject

    def test_quantity_appears_in_subject(self, rules: dict):
        job = _hph_dry_job(Quantity=3)
        subject = build_subject(job, rules)
        assert "3X" in subject

    def test_sender_in_subject(self, rules: dict):
        job = _hph_dry_job()
        subject = build_subject(job, rules)
        assert "NELSON" in subject


# ---------------------------------------------------------------------------
# build_email_body tests
# ---------------------------------------------------------------------------

class TestBuildEmailBody:

    def test_reefer_shows_temperature_line(self, rules: dict):
        job = _hcm_reefer_job()
        body = build_email_body(job, rules)
        assert "REEFER" in body.upper()
        assert "-18" in body or "Temperature" in body

    def test_dry_does_not_show_reefer_line(self, rules: dict):
        job = _hph_dry_job()
        body = build_email_body(job, rules)
        assert "REEFER CONTAINER" not in body

    def test_hph_does_not_show_mt_pickup(self, rules: dict):
        """HPH pol_config.show_mt_pickup=false → no MT pickup line."""
        job = _hph_dry_job()
        body = build_email_body(job, rules)
        assert "MT pick up" not in body

    def test_hcm_shows_mt_pickup(self, rules: dict):
        """HCM pol_config.show_mt_pickup=true → MT pickup line present."""
        job = _hcm_reefer_job()
        body = build_email_body(job, rules)
        assert "MT pick up" in body

    def test_cma_payment_term_in_body(self, rules: dict):
        """CMA carrier_specific_rules → payment_term line present."""
        job = {
            "Customer_Name": "TRAN ANH", "POL": "HCM", "POD": "USNYC",
            "Place": "NEW YORK, NY", "Carrier": "CMA",
            "Container_Type": "40GP", "Quantity": 1,
        }
        body = build_email_body(job, rules)
        assert "payment" in body.lower() or "Payment" in body

    def test_one_carrier_no_payment_term(self, rules: dict):
        """ONE carrier has no carrier_specific_rules → no payment_term."""
        job = _hph_dry_job()
        body = build_email_body(job, rules)
        assert "payment_term" not in body.lower()

    def test_body_contains_pol_pod(self, rules: dict):
        job = _hph_dry_job()
        body = build_email_body(job, rules)
        assert "HAI PHONG" in body or "HPH" in body
        assert "USLGB" in body

    def test_body_contains_volume(self, rules: dict):
        job = _hph_dry_job(Quantity=2)
        body = build_email_body(job, rules)
        assert "2X40HC" in body

    def test_greeting_present(self, rules: dict):
        job = _hph_dry_job()
        body = build_email_body(job, rules)
        assert "Dear" in body

    def test_closing_present(self, rules: dict):
        job = _hph_dry_job()
        body = build_email_body(job, rules)
        assert "regards" in body.lower()

    def test_contract_displayed(self, rules: dict):
        job = _hph_dry_job(Contract_No="SHA0005N25")
        body = build_email_body(job, rules)
        assert "SHA0005N25" in body

    def test_reefer_contract_prefixed(self, rules: dict):
        """Reefer contract_display template = 'REEFER {contract}'."""
        job = _hcm_reefer_job(Contract_No="RFC2026")
        body = build_email_body(job, rules)
        assert "REEFER RFC2026" in body


# ---------------------------------------------------------------------------
# build_mailto_link tests
# ---------------------------------------------------------------------------

class TestBuildMailtoLink:

    def test_starts_with_mailto(self, rules: dict):
        job = _hph_dry_job()
        link = build_mailto_link(job, rules=rules)
        assert link.startswith("mailto:")

    def test_contains_subject_param(self, rules: dict):
        job = _hph_dry_job()
        link = build_mailto_link(job, rules=rules)
        assert "subject=" in link

    def test_contains_body_param(self, rules: dict):
        job = _hph_dry_job()
        link = build_mailto_link(job, rules=rules)
        assert "body=" in link

    def test_url_encoding_applied(self, rules: dict):
        """Spaces must be percent-encoded in the mailto URL."""
        job = _hph_dry_job()
        link = build_mailto_link(job, rules=rules)
        # Raw spaces must not appear in subject/body params (% encoding)
        after_question = link.split("?", 1)[1] if "?" in link else link
        # Decoded must contain content; raw must be encoded
        assert " " not in after_question.split("subject=")[1].split("&")[0], (
            "Subject not URL-encoded (contains raw space)"
        )

    def test_custom_to_email(self, rules: dict):
        job = _hph_dry_job()
        link = build_mailto_link(job, rules=rules, to_email="custom@test.com")
        assert "mailto:custom@test.com" in link

    def test_cost_data_fills_missing_contract(self, rules: dict):
        """cost_data provides Contract when job_data doesn't have Contract_No."""
        job = _hph_dry_job(Contract_No="")
        cost = {"Contract": "INJECTED_CONTRACT", "Group_Rate": ""}
        link = build_mailto_link(job, cost_data=cost, rules=rules)
        assert "INJECTED_CONTRACT" in unquote(link)

    def test_job_data_contract_takes_precedence(self, rules: dict):
        """job_data.Contract_No takes precedence over cost_data.Contract."""
        job = _hph_dry_job(Contract_No="ORIGINAL")
        cost = {"Contract": "SHOULD_NOT_APPEAR", "Group_Rate": ""}
        link = build_mailto_link(job, cost_data=cost, rules=rules)
        decoded = unquote(link)
        assert "ORIGINAL" in decoded
        assert "SHOULD_NOT_APPEAR" not in decoded
