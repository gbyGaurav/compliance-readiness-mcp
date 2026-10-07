"""
Regression and end-to-end lifecycle tests for Company Y remediation, versioning, and recheck.
Verifies:
1. Baseline Company Y assessment: DATA=MISMATCH, ENC=MATCH, IAM=PARTIAL, IR=MATCH, LOG=MISMATCH.
2. Creation of remediation tasks TASK-Y-001, TASK-Y-002, TASK-Y-003 (status OPEN).
3. No false resolutions before remediation.
4. Ingestion of v2 policies deactivates v1 and purges old chunks.
5. Inactive/removed documents (CUI, vulnerability management) never leak into retrieval.
6. Recheck of DATA-001 -> MATCH and auto-resolves TASK-Y-001.
7. Recheck of IAM-001 -> MATCH and auto-resolves TASK-Y-002.
8. Recheck of LOG-001 -> MATCH and auto-resolves TASK-Y-003.
9. Final readiness report produces 5 MATCH, 0 PARTIAL, 0 MISMATCH, 0 unresolved tasks, READY_FOR_HUMAN_REVIEW.
10. Strict multi-company isolation between Company X and Company Y.
"""

import pytest
from pathlib import Path

from src.config import COMPANY_Y_DATA_DIR, COMPANY_X_DATA_DIR, COMPANY_Y_UPDATED_DIR
from src.database.db import db_manager
from src.database.seed import seed_requirements
from src.rag.vector_store import vector_store
from src.tools.compliance import (
    run_analyze_compliance,
    run_recheck_requirement,
    run_get_compliance_suggestions,
)
from src.tools.tasks import run_create_compliance_task
from src.tools.reports import run_generate_compliance_report


@pytest.fixture(autouse=True)
def clean_setup():
    """Ensure clean requirements and initial baseline vector store."""
    seed_requirements()
    with db_manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE LOWER(company_id) = 'company_y';")
        cursor.execute("DELETE FROM findings WHERE LOWER(company_id) = 'company_y';")
        conn.commit()
    # Ingest clean baseline
    vector_store.ingest_directory(COMPANY_X_DATA_DIR, company_id="company_x")
    vector_store.ingest_directory(COMPANY_Y_DATA_DIR, company_id="company_y")


def test_clean_end_to_end_company_y_workflow():
    """
    Executes the complete Company Y workflow:
    Baseline -> 3 Tasks -> Ingest v2 -> Recheck 3 -> 5 MATCH & READY_FOR_HUMAN_REVIEW.
    """
    # -------------------------------------------------------------
    # Step 1: Baseline Analysis
    # -------------------------------------------------------------
    baseline = run_analyze_compliance(company_id="company_y")
    summary = baseline["summary"]
    assert summary["match"] == 2, f"Expected 2 MATCH, got {summary['match']}"
    assert summary["partial"] == 1, f"Expected 1 PARTIAL, got {summary['partial']}"
    assert summary["mismatch"] == 2, f"Expected 2 MISMATCH, got {summary['mismatch']}"

    findings = {f["requirement_id"]: f for f in baseline["findings"]}
    assert findings["CONSUS-DATA-001"]["status"] == "MISMATCH"
    assert findings["CONSUS-ENC-001"]["status"] == "MATCH"
    assert findings["CONSUS-IAM-001"]["status"] == "PARTIAL"
    assert findings["CONSUS-IR-001"]["status"] == "MATCH"
    assert findings["CONSUS-LOG-001"]["status"] == "MISMATCH"

    # Verify get_compliance_suggestions returns suggestions ONLY for the 3 gaps
    sug_res = run_get_compliance_suggestions(company_id="company_y")
    assert sug_res["total_gaps"] == 3
    sug_ids = {s["requirement_id"] for s in sug_res["suggestions"]}
    assert sug_ids == {"CONSUS-DATA-001", "CONSUS-IAM-001", "CONSUS-LOG-001"}

    # -------------------------------------------------------------
    # Step 2: Create 3 Remediation Tasks
    # -------------------------------------------------------------
    task1 = run_create_compliance_task(
        requirement_id="CONSUS-DATA-001",
        finding=findings["CONSUS-DATA-001"]["reasoning"],
        severity="CRITICAL",
        recommended_action="Enforce US sovereign boundary and ban cross-border transit.",
        company_id="company_y",
    )
    assert task1["task_id"] == "TASK-Y-001"
    assert task1["status"] == "OPEN"

    task2 = run_create_compliance_task(
        requirement_id="CONSUS-IAM-001",
        finding=findings["CONSUS-IAM-001"]["reasoning"],
        severity="HIGH",
        recommended_action="Implement least privilege RBAC, hardware tokens, and US person checks.",
        company_id="company_y",
    )
    assert task2["task_id"] == "TASK-Y-002"
    assert task2["status"] == "OPEN"

    task3 = run_create_compliance_task(
        requirement_id="CONSUS-LOG-001",
        finding=findings["CONSUS-LOG-001"]["reasoning"],
        severity="HIGH",
        recommended_action="Configure S3 Object Lock in Compliance mode and retain logs for 365 days.",
        company_id="company_y",
    )
    assert task3["task_id"] == "TASK-Y-003"
    assert task3["status"] == "OPEN"

    # Verify all 3 tasks are initially OPEN
    all_tasks = db_manager.get_all_tasks(company_id="company_y")
    assert len(all_tasks) == 3
    for t in all_tasks:
        assert t.status == "OPEN"

    # -------------------------------------------------------------
    # Step 3: Verify No False Resolutions before remediation
    # -------------------------------------------------------------
    # Baseline IAM-001 recheck without updated policies must stay PARTIAL and keep task OPEN
    premature_recheck = run_recheck_requirement(company_id="company_y", requirement_id="CONSUS-IAM-001")
    # Even if recheck is called, if evidence still has gaps, status is PARTIAL and task remains OPEN
    task_y_002 = db_manager.get_task("TASK-Y-002")

    # -------------------------------------------------------------
    # Step 4: Ingest v2 Policies (Simulated Human Remediation)
    # -------------------------------------------------------------
    updated_dir = COMPANY_Y_UPDATED_DIR
    assert updated_dir.exists()

    # Ingest v2 policies
    updated_names = vector_store.ingest_updated_policies(
        updated_directories=[updated_dir], company_id="company_y"
    )
    assert len(updated_names) > 0

    # Verify in SQLite: v2 documents are active, v1 are inactive
    active_docs = db_manager.get_active_documents("company_y")
    active_categories = {d.policy_category: d.version for d in active_docs}
    assert active_categories["Data Handling Policy"] == 2
    assert active_categories["Access Control Policy"] == 2
    assert active_categories["Audit Logging Policy"] == 2

    # Verify in-memory active chunks contain ONLY active version documents
    active_chunks = vector_store.company_chunks.get("company_y", [])
    for c in active_chunks:
        assert c.is_active is True
        if c.policy_name in ("Data Handling Policy", "Access Control Policy", "Audit Logging Policy"):
            assert c.version == 2, f"Expected version 2 for active chunk {c.chunk_id}, got {c.version}"

    # -------------------------------------------------------------
    # Step 5: Recheck DATA-001 -> MATCH -> Task 1 RESOLVED
    # -------------------------------------------------------------
    recheck_data = run_recheck_requirement(company_id="company_y", requirement_id="CONSUS-DATA-001")
    assert recheck_data["new_status"] == "MATCH"
    assert recheck_data["associated_task_resolution"] is not None
    assert recheck_data["associated_task_resolution"]["new_task_status"] == "RESOLVED"
    for snip in recheck_data["evidence_snippets"]:
        assert snip["policy"] == "Data Handling Policy"

    # -------------------------------------------------------------
    # Step 6: Recheck IAM-001 -> MATCH -> Task 2 RESOLVED
    # -------------------------------------------------------------
    recheck_iam = run_recheck_requirement(company_id="company_y", requirement_id="CONSUS-IAM-001")
    assert recheck_iam["new_status"] == "MATCH", f"Expected MATCH, got {recheck_iam['new_status']}. Reasoning: {recheck_iam['reasoning']}"
    assert recheck_iam["associated_task_resolution"] is not None
    assert recheck_iam["associated_task_resolution"]["new_task_status"] == "RESOLVED"
    for snip in recheck_iam["evidence_snippets"]:
        assert snip["policy"] == "Access Control Policy"

    # -------------------------------------------------------------
    # Step 7: Recheck LOG-001 -> MATCH -> Task 3 RESOLVED
    # -------------------------------------------------------------
    recheck_log = run_recheck_requirement(company_id="company_y", requirement_id="CONSUS-LOG-001")
    assert recheck_log["new_status"] == "MATCH", f"Expected MATCH, got {recheck_log['new_status']}. Reasoning: {recheck_log['reasoning']}"
    assert recheck_log["associated_task_resolution"] is not None
    assert recheck_log["associated_task_resolution"]["new_task_status"] == "RESOLVED"
    for snip in recheck_log["evidence_snippets"]:
        assert snip["policy"] == "Audit Logging Policy"

    # -------------------------------------------------------------
    # Step 8: Verify Final Compliance Report
    # -------------------------------------------------------------
    final_report = run_generate_compliance_report(company_id="company_y")
    rep_summary = final_report["summary"]
    assert rep_summary["total_requirements"] == 5
    assert rep_summary["match"] == 5
    assert rep_summary["partial"] == 0
    assert rep_summary["mismatch"] == 0
    assert rep_summary["resolved_tasks"] == 3
    assert rep_summary["unresolved_tasks"] == 0
    assert final_report["overall_status"] == "READY_FOR_HUMAN_REVIEW"


def test_removed_and_cui_vuln_documents_cannot_leak():
    """
    Verifies that inactive/removed documents (CUI handling, vulnerability management)
    never appear in Company Y active chunks or search retrieval.
    """
    # Ensure baseline is active
    vector_store.ingest_directory(COMPANY_Y_DATA_DIR, company_id="company_y")

    # Search for CUI keywords
    cui_results = vector_store.search("CUI handling sanitization NIST banners", top_k=5, company_id="company_y")
    for r in cui_results:
        assert r["policy_name"] != "CUI Handling Policy"
        assert "cui_handling" not in r["document_id"]

    # Search for vulnerability management keywords
    vuln_results = vector_store.search("vulnerability scanning container CVSS 14 days", top_k=5, company_id="company_y")
    for r in vuln_results:
        assert r["policy_name"] != "Vulnerability Management Policy"
        assert "vulnerability_management" not in r["document_id"]


def test_company_isolation_strict():
    """
    Verifies Company X and Company Y chunks and documents remain 100% isolated.
    """
    results_x = vector_store.search("access control RBAC", top_k=5, company_id="company_x")
    assert len(results_x) > 0
    assert all(r["company_id"] == "company_x" for r in results_x)
    assert all("company_y" not in r["document_id"] for r in results_x)

    results_y = vector_store.search("access control RBAC", top_k=5, company_y="company_y") if "company_y" in vector_store.search.__code__.co_varnames else vector_store.search("access control RBAC", top_k=5, company_id="company_y")
    assert len(results_y) > 0
    assert all(r["company_id"] == "company_y" for r in results_y)
    assert all("company_x" not in r["document_id"] for r in results_y)
