"""
Unit tests for PDF report generation tools.
"""

import pytest
from pathlib import Path

from src.tools.pdf_generator import generate_gap_report_pdf, generate_final_report_pdf
from src.config import REPORTS_DIR


def test_gap_report_pdf_generation():
    test_findings = [
        {
            "requirement_id": "CONSUS-DATA-001",
            "requirement_title": "US-Only Data Residency",
            "status": "MISMATCH",
            "severity": "CRITICAL",
            "matched_policy": "Data Handling Policy",
            "reasoning": "Commercial multi-region cloud without FedRAMP boundary.",
            "missing_elements": ["US GovCloud", "Strict CONUS boundary"],
            "recommended_action": "Migrate cloud workloads to AWS GovCloud.",
        },
        {
            "requirement_id": "CONSUS-IAM-001",
            "requirement_title": "Identity and Access Control",
            "status": "PARTIAL",
            "severity": "HIGH",
            "matched_policy": "Access Control Policy",
            "reasoning": "Missing phishing-resistant MFA tokens.",
            "missing_elements": ["FIDO2 WebAuthn"],
            "recommended_action": "Mandate hardware security keys.",
        },
    ]
    summary = {
        "total_requirements": 2,
        "match": 0,
        "partial": 1,
        "mismatch": 1,
    }

    out_pdf = generate_gap_report_pdf("test_company", test_findings, summary)
    p = Path(out_pdf)
    assert p.exists()
    assert p.is_file()
    assert p.suffix == ".pdf"
    assert p.stat().st_size > 500


def test_final_report_pdf_generation():
    report_data = {
        "report_id": "REP-TEST-001",
        "overall_status": "READY_FOR_HUMAN_REVIEW",
        "summary": {
            "total_requirements": 5,
            "match": 5,
            "partial": 0,
            "mismatch": 0,
            "resolved_tasks": 3,
            "unresolved_tasks": 0,
        },
        "findings": [
            {
                "requirement_id": "CONSUS-DATA-001",
                "status": "MATCH",
                "matched_policy": "Sovereign US Data Boundary Policy v2",
                "reasoning": "AWS GovCloud verified.",
            },
            {
                "requirement_id": "CONSUS-IAM-001",
                "status": "MATCH",
                "matched_policy": "Access Control Policy v2",
                "reasoning": "US-person and FIDO2 MFA verified.",
            },
        ],
    }

    out_pdf = generate_final_report_pdf("test_company", report_data)
    p = Path(out_pdf)
    assert p.exists()
    assert p.is_file()
    assert p.suffix == ".pdf"
    assert p.stat().st_size > 500
