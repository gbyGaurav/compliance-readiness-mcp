"""
Unit and integration tests for strict multi-company isolation and Company Y compliance lifecycle.
"""

import pytest
from pathlib import Path

from src.config import COMPANY_X_DATA_DIR, COMPANY_Y_DATA_DIR, COMPANY_Y_UPDATED_DIR
from src.database.db import db_manager
from src.database.seed import seed_requirements
from src.rag.vector_store import vector_store
from src.tools.compliance import (
    run_analyze_compliance,
    run_recheck_requirement,
    run_get_compliance_suggestions,
    run_ingest_company_documents,
)
from src.tools.tasks import (
    run_create_compliance_task,
    run_assign_compliance_task,
)
from src.tools.reports import run_generate_compliance_report


@pytest.fixture(autouse=True)
def setup_test_environment():
    with db_manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM findings WHERE company_id = 'company_y';")
        cursor.execute("DELETE FROM tasks WHERE company_id = 'company_y';")
        cursor.execute("DELETE FROM reports WHERE company_id = 'company_y';")
        conn.commit()
    seed_requirements()
    # Ingest baseline documents for both companies
    vector_store.ingest_directory(COMPANY_X_DATA_DIR, company_id="company_x")
    vector_store.ingest_directory(COMPANY_Y_DATA_DIR, company_id="company_y")


def test_strict_multi_company_isolation():
    """
    Verifies that Company Y queries NEVER return Company X chunks,
    and Company X queries NEVER return Company Y chunks.
    """
    # Company X chunks must only contain Company X documents
    chunks_x = vector_store.company_chunks.get("company_x", [])
    assert all("company_x" in c.document_id for c in chunks_x)

    # Company Y chunks must only contain Company Y documents
    chunks_y = vector_store.company_chunks.get("company_y", [])
    assert all("company_y" in c.document_id for c in chunks_y)

    # Search isolated to company_y
    results_y = vector_store.search("data residency infrastructure", company_id="company_y", top_k=5)
    assert len(results_y) > 0
    for r in results_y:
        assert "company_y" in r["document_id"]
        assert "company_x" not in r["document_id"]

    # Search isolated to company_x
    results_x = vector_store.search("data residency infrastructure", company_id="company_x", top_k=5)
    assert len(results_x) > 0
    for r in results_x:
        assert "company_x" in r["document_id"]
        assert "company_y" not in r["document_id"]


def test_company_y_full_compliance_lifecycle():
    """
    Tests the complete Company Y workflow:
    1. Ingestion of multi-format documents (.pdf, .docx, .txt, .md)
    2. Initial compliance analysis -> gaps identified & Gap Report PDF generated
    3. Retrieval of remediation suggestions
    4. Task creation for gaps
    5. Ingestion of remediated v2 documents
    6. Recheck requirements -> upgrade to MATCH & tasks auto-resolved
    7. Final readiness report -> READY_FOR_HUMAN_REVIEW + Final PDF generated
    """
    company_id = "company_y"

    # 1. Analyze baseline compliance
    analysis = run_analyze_compliance(company_id=company_id)
    assert analysis["company_id"] == company_id
    summary = analysis["summary"]
    assert summary["mismatch"] == 2
    assert summary["partial"] == 1
    assert summary["match"] == 2
    assert "gap_report_pdf" in analysis
    assert Path(analysis["gap_report_pdf"]).exists()

    # Verify specific initial findings
    findings = {f["requirement_id"]: f for f in analysis["findings"]}
    assert findings["CONSUS-DATA-001"]["status"] == "MISMATCH"
    assert findings["CONSUS-ENC-001"]["status"] == "MATCH"
    assert findings["CONSUS-IAM-001"]["status"] == "PARTIAL"
    assert findings["CONSUS-IR-001"]["status"] == "MATCH"
    assert findings["CONSUS-LOG-001"]["status"] == "MISMATCH"

    # 2. Suggestions tool
    suggestions_resp = run_get_compliance_suggestions(company_id=company_id)
    assert suggestions_resp["total_gaps"] >= 3
    sugg_map = {s["requirement_id"]: s for s in suggestions_resp["suggestions"]}
    assert "CONSUS-DATA-001" in sugg_map
    assert len(sugg_map["CONSUS-DATA-001"]["recommended_policy_clauses"]) > 0

    # 3. Create remediation tasks for gaps
    task_data = run_create_compliance_task(
        requirement_id="CONSUS-DATA-001",
        finding="Cloud hosting permits commercial multi-region and EU transit.",
        severity="CRITICAL",
        recommended_action="Migrate to FedRAMP High / AWS GovCloud US.",
        company_id=company_id,
    )
    assert task_data["status"] == "OPEN"
    assert "TASK-Y-" in task_data["task_id"]

    task_iam = run_create_compliance_task(
        requirement_id="CONSUS-IAM-001",
        finding="No US-person requirement and SMS MFA used.",
        severity="HIGH",
        recommended_action="Enforce US-person verification and FIDO2 MFA.",
        company_id=company_id,
    )
    assert task_iam["status"] == "OPEN"

    task_log = run_create_compliance_task(
        requirement_id="CONSUS-LOG-001",
        finding="90-day mutable log retention.",
        severity="HIGH",
        recommended_action="Enforce 365-day immutable WORM log storage.",
        company_id=company_id,
    )
    assert task_log["status"] == "OPEN"

    # 4. Ingest remediated v2 documents
    ingest_result = run_ingest_company_documents(company_id=company_id, path_str=str(COMPANY_Y_UPDATED_DIR))
    assert ingest_result["success"] is True
    assert ingest_result["documents_ingested_count"] >= 3

    # 5. Recheck requirement CONSUS-DATA-001
    recheck_data = run_recheck_requirement(company_id=company_id, requirement_id="CONSUS-DATA-001")
    assert recheck_data["new_status"] == "MATCH"
    assert recheck_data["associated_task_resolution"] is not None
    assert recheck_data["associated_task_resolution"]["new_task_status"] == "RESOLVED"

    # Recheck CONSUS-IAM-001
    recheck_iam = run_recheck_requirement(company_id=company_id, requirement_id="CONSUS-IAM-001")
    assert recheck_iam["new_status"] == "MATCH"
    assert recheck_iam["associated_task_resolution"]["new_task_status"] == "RESOLVED"

    # Recheck CONSUS-LOG-001
    recheck_log = run_recheck_requirement(company_id=company_id, requirement_id="CONSUS-LOG-001")
    assert recheck_log["new_status"] == "MATCH"
    assert recheck_log["associated_task_resolution"]["new_task_status"] == "RESOLVED"

    # 6. Generate final compliance readiness report
    final_report = run_generate_compliance_report(company_id=company_id)
    assert final_report["overall_status"] == "READY_FOR_HUMAN_REVIEW"
    assert final_report["summary"]["mismatch"] == 0
    assert final_report["summary"]["partial"] == 0
    assert final_report["summary"]["match"] == final_report["summary"]["total_requirements"]
    assert final_report["summary"]["unresolved_tasks"] == 0
    assert "pdf_report" in final_report
    assert Path(final_report["pdf_report"]).exists()
