"""
Unit tests for compliance evaluation (MATCH, PARTIAL, MISMATCH).
"""

import pytest
from src.database.models import ComplianceRequirement
from src.llm.evaluator import ComplianceEvaluator


@pytest.fixture
def evaluator():
    return ComplianceEvaluator(provider="fallback")


def test_encryption_evaluates_to_match(evaluator):
    req = ComplianceRequirement(
        requirement_id="CONSUS-ENC-001",
        title="Cryptographic Protection",
        category="Cryptography",
        severity="High",
        description="FIPS 140-2 validated encryption",
        mandatory_controls=["AES-256 at rest", "TLS 1.2+ in transit", "KMS key management"],
        verification_criteria=["Check AES-256 and TLS"],
    )
    mock_chunks = [
        {
            "policy_name": "Encryption Policy",
            "section_title": "2. Encryption at Rest",
            "text": "Databases are encrypted using AES-256 keys managed in cloud KMS.",
        },
        {
            "policy_name": "Encryption Policy",
            "section_title": "3. Encryption in Transit",
            "text": "All transport protocols enforce TLS 1.2 or TLS 1.3.",
        },
    ]
    finding = evaluator.evaluate(req, mock_chunks)
    assert finding.status == "MATCH"
    assert finding.severity == "LOW"
    assert len(finding.missing_elements) == 0


def test_global_cloud_evaluates_to_mismatch(evaluator):
    req = ComplianceRequirement(
        requirement_id="CONSUS-DATA-001",
        title="US-Only Boundary",
        category="Data Boundary",
        severity="Critical",
        description="Data must remain within US sovereign boundary",
        mandatory_controls=["No cross-border replication"],
        verification_criteria=["US sovereign check"],
    )
    mock_chunks = [
        {
            "policy_name": "Data Handling Policy",
            "section_title": "3. Cloud Backup Policy",
            "text": "Global replication permitted across international availability zones.",
        }
    ]
    finding = evaluator.evaluate(req, mock_chunks)
    assert finding.status == "MISMATCH"
    assert finding.severity == "CRITICAL"
    assert len(finding.missing_elements) > 0


def test_incomplete_access_evaluates_to_partial(evaluator):
    req = ComplianceRequirement(
        requirement_id="CONSUS-IAM-001",
        title="Role-Based Access Control",
        category="IAM",
        severity="High",
        description="Granular RBAC and US-Person verification required",
        mandatory_controls=["Granular RBAC", "US-Person verification"],
        verification_criteria=["RBAC verification"],
    )
    mock_chunks = [
        {
            "policy_name": "Access Control Policy",
            "section_title": "4. Limitations",
            "text": "Fine-grained Role-Based Access Control is not fully implemented and elevated administrator privileges are shared.",
        }
    ]
    finding = evaluator.evaluate(req, mock_chunks)
    assert finding.status == "PARTIAL"
    assert finding.severity == "HIGH"
    assert len(finding.missing_elements) > 0


def test_get_compliance_suggestions_excludes_match_requirements():
    """
    Regression test: Verifies that get_compliance_suggestions strictly excludes requirements
    that evaluated to MATCH, and produces suggestions ONLY for PARTIAL and MISMATCH findings.
    """
    from src.database.db import db_manager
    from src.database.models import ComplianceFinding
    from src.tools.compliance import run_get_compliance_suggestions

    test_co = "test_suggestions_filter_co"

    # Clean test findings
    with db_manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM findings WHERE company_id = ?;", (test_co,))
        conn.commit()

    # Save mock findings: 2 MATCH, 1 PARTIAL, 2 MISMATCH
    mock_findings = [
        ComplianceFinding(
            requirement_id="CONSUS-DATA-001",
            requirement_title="US-Only Data Residency",
            category="Data Boundary",
            status="MISMATCH",
            matched_policy="Data Policy",
            relevant_policy_chunks=[],
            reasoning="Global replication enabled.",
            missing_elements=["US-only boundary"],
            severity="CRITICAL",
        ),
        ComplianceFinding(
            requirement_id="CONSUS-ENC-001",
            requirement_title="Cryptographic Protection",
            category="Cryptography",
            status="MATCH",
            matched_policy="Encryption Policy",
            relevant_policy_chunks=[],
            reasoning="AES-256 and TLS 1.2+ verified.",
            missing_elements=[],
            severity="LOW",
        ),
        ComplianceFinding(
            requirement_id="CONSUS-IAM-001",
            requirement_title="Identity and Access Control",
            category="IAM",
            status="PARTIAL",
            matched_policy="Access Policy",
            relevant_policy_chunks=[],
            reasoning="Lacks granular RBAC.",
            missing_elements=["Granular RBAC"],
            severity="HIGH",
        ),
        ComplianceFinding(
            requirement_id="CONSUS-IR-001",
            requirement_title="Incident Response",
            category="Incident Response",
            status="MATCH",
            matched_policy="IR Policy",
            relevant_policy_chunks=[],
            reasoning="Incident plan and 48-hour SLA confirmed.",
            missing_elements=[],
            severity="LOW",
        ),
        ComplianceFinding(
            requirement_id="CONSUS-LOG-001",
            requirement_title="Audit Logging",
            category="Audit Logging",
            status="MISMATCH",
            matched_policy="Log Policy",
            relevant_policy_chunks=[],
            reasoning="90-day retention and no WORM storage.",
            missing_elements=["365-day retention", "WORM storage"],
            severity="HIGH",
        ),
    ]

    for f in mock_findings:
        db_manager.save_finding(test_co, f)

    # 1. Fetch suggestions for all requirements
    res = run_get_compliance_suggestions(company_id=test_co)
    assert res["total_gaps"] == 3

    suggested_req_ids = {s["requirement_id"] for s in res["suggestions"]}
    assert suggested_req_ids == {"CONSUS-DATA-001", "CONSUS-IAM-001", "CONSUS-LOG-001"}

    # Prove that MATCH requirements are NEVER in suggestions
    assert "CONSUS-ENC-001" not in suggested_req_ids
    assert "CONSUS-IR-001" not in suggested_req_ids

    # 2. Querying specific MATCH requirement directly must return 0 gaps
    direct_ir = run_get_compliance_suggestions(company_id=test_co, requirement_id="CONSUS-IR-001")
    assert direct_ir["total_gaps"] == 0
    assert len(direct_ir["suggestions"]) == 0

    direct_enc = run_get_compliance_suggestions(company_id=test_co, requirement_id="CONSUS-ENC-001")
    assert direct_enc["total_gaps"] == 0
    assert len(direct_enc["suggestions"]) == 0

    # 3. Querying specific gap returns exactly that gap
    direct_data = run_get_compliance_suggestions(company_id=test_co, requirement_id="CONSUS-DATA-001")
    assert direct_data["total_gaps"] == 1
    assert direct_data["suggestions"][0]["requirement_id"] == "CONSUS-DATA-001"
    assert direct_data["suggestions"][0]["current_status"] == "MISMATCH"

