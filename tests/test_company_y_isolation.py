"""
Dedicated tests for Company Y strict RAG isolation, versioning, and baseline compliance accuracy.
"""

import pytest
from pathlib import Path

from src.config import COMPANY_Y_DATA_DIR, COMPANY_X_DATA_DIR
from src.database.db import db_manager
from src.database.seed import seed_requirements
from src.rag.vector_store import vector_store
from src.tools.compliance import run_analyze_compliance


@pytest.fixture(autouse=True)
def setup_test_db():
    seed_requirements()
    # Ingest baseline for both companies
    vector_store.ingest_directory(COMPANY_X_DATA_DIR, company_id="company_x")
    vector_store.ingest_directory(COMPANY_Y_DATA_DIR, company_id="company_y")


def test_company_y_baseline_contains_only_five_active_documents():
    """
    Verifies that Company Y baseline contains ONLY the 5 active documents,
    and all removed documents have is_active = 0 in SQLite and 0 active chunks in memory.
    """
    expected_filenames = {
        "01_data_handling_policy.txt",
        "02_encryption_policy.docx",
        "03_access_control_policy.pdf",
        "04_incident_response_policy.md",
        "05_audit_logging_policy.docx",
    }

    active_docs = db_manager.get_active_documents("company_y")
    active_filenames = {d.filename for d in active_docs}
    assert active_filenames == expected_filenames, f"Active docs mismatch: {active_filenames} vs {expected_filenames}"
    assert len(active_docs) == 5

    # Confirm in-memory active chunks count matches exactly 5 baseline documents
    chunks = vector_store.company_chunks.get("company_y", [])
    assert len(chunks) == 5
    for c in chunks:
        assert c.company_id == "company_y"
        assert c.is_active is True
        assert c.version == 1

    # Check that removed documents are marked inactive in SQLite
    all_docs = db_manager.get_all_documents("company_y")
    inactive_docs = [d for d in all_docs if not d.is_active]
    for d in inactive_docs:
        assert d.filename not in expected_filenames


def test_company_y_retrieval_isolation_and_no_leakage():
    """
    Verifies that Company Y RAG retrieval NEVER retrieves:
    1. Company X documents
    2. Old or removed Company Y documents
    3. Remediated v2 documents before remediation is performed
    4. Hardcoded Company X identifiers (e.g. CX-POL)
    """
    reqs = db_manager.get_all_requirements()
    assert len(reqs) == 5

    for req in reqs:
        query = f"{req.title} {req.description} {' '.join(req.mandatory_controls)}"
        retrieved = vector_store.search(query, top_k=3, company_id="company_y")
        assert len(retrieved) > 0

        for chunk in retrieved:
            # Multi-company isolation
            assert chunk["company_id"] == "company_y"
            assert "company_x" not in chunk["document_id"]
            # Active and baseline version checks
            assert chunk["is_active"] is True
            assert chunk["version"] == 1
            assert not chunk["document_id"].endswith("-v2")
            # Evidence source filename must be one of the 5 baseline documents
            matched_prefix = chunk["document_id"].replace("company_y-", "")
            assert any(matched_prefix in f for f in [
                "01_data_handling_policy",
                "02_encryption_policy",
                "03_access_control_policy",
                "04_incident_response_policy",
                "05_audit_logging_policy",
            ])
            # No Company X identifiers leaked in retrieved text
            assert "CX-POL" not in chunk["text"]


def test_company_y_baseline_evaluation_accuracy():
    """
    Verifies that baseline evaluation of Company Y against the 5 baseline documents produces:
    - Data Boundary: MISMATCH
    - Encryption: MATCH
    - Access Control: PARTIAL
    - Incident Response: MATCH
    - Audit Logging: MISMATCH
    Summary: MATCH = 2, PARTIAL = 1, MISMATCH = 2.
    And all reasoning dynamically references policies without hardcoded CX-POL identifiers.
    """
    analysis = run_analyze_compliance(company_id="company_y")
    assert analysis["company_id"] == "company_y"

    summary = analysis["summary"]
    assert summary["match"] == 2, f"Expected 2 MATCH, got {summary['match']}"
    assert summary["partial"] == 1, f"Expected 1 PARTIAL, got {summary['partial']}"
    assert summary["mismatch"] == 2, f"Expected 2 MISMATCH, got {summary['mismatch']}"
    assert summary["total_requirements"] == 5

    findings_map = {f["requirement_id"]: f for f in analysis["findings"]}
    assert findings_map["CONSUS-DATA-001"]["status"] == "MISMATCH"
    assert findings_map["CONSUS-ENC-001"]["status"] == "MATCH"
    assert findings_map["CONSUS-IAM-001"]["status"] == "PARTIAL"
    assert findings_map["CONSUS-IR-001"]["status"] == "MATCH"
    assert findings_map["CONSUS-LOG-001"]["status"] == "MISMATCH"

    # Confirm no hardcoded CX-POL strings in reasoning
    for req_id, finding in findings_map.items():
        assert "CX-POL" not in finding["reasoning"], f"Found CX-POL in {req_id} reasoning: {finding['reasoning']}"


def test_company_x_and_company_y_mutual_isolation():
    """
    Verifies that Company X and Company Y indices remain strictly isolated concurrently.
    """
    res_x = vector_store.search("data residency sovereign", top_k=3, company_id="company_x")
    assert all(r["company_id"] == "company_x" for r in res_x)
    assert all("company_y" not in r["document_id"] for r in res_x)

    res_y = vector_store.search("data residency sovereign", top_k=3, company_id="company_y")
    assert all(r["company_id"] == "company_y" for r in res_y)
    assert all("company_x" not in r["document_id"] for r in res_y)


def test_company_y_baseline_suggestions_exact_consistency():
    """
    Regression test: Verifies that get_compliance_suggestions uses the exact findings
    from analyze_compliance. Since baseline assessment has:
      - DATA-001 -> MISMATCH
      - ENC-001 -> MATCH
      - IAM-001 -> PARTIAL
      - IR-001 -> MATCH
      - LOG-001 -> MISMATCH
    get_compliance_suggestions MUST return suggestions ONLY for DATA-001, IAM-001, LOG-001 (exactly 3 gaps),
    and Incident Response / Encryption must NEVER appear in suggestions.
    """
    from src.tools.compliance import run_get_compliance_suggestions

    # 1. Run baseline analysis
    analysis = run_analyze_compliance(company_id="company_y")
    summary = analysis["summary"]
    assert summary["match"] == 2
    assert summary["partial"] == 1
    assert summary["mismatch"] == 2

    findings_map = {f["requirement_id"]: f["status"] for f in analysis["findings"]}
    assert findings_map["CONSUS-DATA-001"] == "MISMATCH"
    assert findings_map["CONSUS-ENC-001"] == "MATCH"
    assert findings_map["CONSUS-IAM-001"] == "PARTIAL"
    assert findings_map["CONSUS-IR-001"] == "MATCH"
    assert findings_map["CONSUS-LOG-001"] == "MISMATCH"

    # 2. Get compliance suggestions for Company Y
    suggestions_res = run_get_compliance_suggestions(company_id="company_y")
    assert suggestions_res["total_gaps"] == 3

    suggested_ids = {s["requirement_id"] for s in suggestions_res["suggestions"]}
    assert suggested_ids == {"CONSUS-DATA-001", "CONSUS-IAM-001", "CONSUS-LOG-001"}

    # Neither MATCH requirement must appear in gap suggestions
    assert "CONSUS-ENC-001" not in suggested_ids
    assert "CONSUS-IR-001" not in suggested_ids

    # Each suggestion reflects the exact finding status
    for s in suggestions_res["suggestions"]:
        assert s["current_status"] in ("PARTIAL", "MISMATCH")
        assert s["current_status"] == findings_map[s["requirement_id"]]

    # 3. Direct queries for MATCH requirements return 0 suggestions
    ir_sugg = run_get_compliance_suggestions(company_id="company_y", requirement_id="CONSUS-IR-001")
    assert ir_sugg["total_gaps"] == 0
    assert len(ir_sugg["suggestions"]) == 0

    enc_sugg = run_get_compliance_suggestions(company_id="company_y", requirement_id="CONSUS-ENC-001")
    assert enc_sugg["total_gaps"] == 0
    assert len(enc_sugg["suggestions"]) == 0

    # 4. Direct query for gap returns 1 suggestion
    data_sugg = run_get_compliance_suggestions(company_id="company_y", requirement_id="CONSUS-DATA-001")
    assert data_sugg["total_gaps"] == 1
    assert data_sugg["suggestions"][0]["requirement_id"] == "CONSUS-DATA-001"
    assert data_sugg["suggestions"][0]["current_status"] == "MISMATCH"

