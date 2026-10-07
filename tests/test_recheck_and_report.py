"""
Integration tests for human policy remediation, requirement re-check auto-resolution, and readiness report generation.
"""

import pytest
from pathlib import Path

from src.config import COMPANY_X_DATA_DIR, UPDATED_DATA_DIR, COMPANY_X_UPDATED_DIR
from src.database.db import db_manager
from src.database.seed import seed_requirements
from src.rag.vector_store import vector_store
from src.tools.compliance import run_analyze_compliance, run_recheck_requirement
from src.tools.tasks import run_create_compliance_task
from src.tools.reports import run_generate_compliance_report


@pytest.fixture(autouse=True)
def setup_environment():
    # Clear tables for clean test isolation
    with db_manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM findings;")
        cursor.execute("DELETE FROM tasks;")
        cursor.execute("DELETE FROM reports;")
        conn.commit()
    seed_requirements()
    vector_store.ingest_directory(COMPANY_X_DATA_DIR, company_id="company_x")


def test_full_remediation_and_recheck_flow():
    # 1. Initial scan
    analysis = run_analyze_compliance(company_id="company_x")
    findings = {f["requirement_id"]: f for f in analysis["findings"]}

    assert findings["CONSUS-DATA-001"]["status"] == "MISMATCH"
    assert findings["CONSUS-IAM-001"]["status"] == "PARTIAL"
    assert findings["CONSUS-LOG-001"]["status"] == "PARTIAL"
    assert findings["CONSUS-ENC-001"]["status"] == "MATCH"
    assert findings["CONSUS-IR-001"]["status"] == "MATCH"

    # 2. Create tasks for all PARTIAL and MISMATCH findings
    task1 = run_create_compliance_task(
        requirement_id="CONSUS-DATA-001",
        finding=findings["CONSUS-DATA-001"]["reasoning"],
        severity=findings["CONSUS-DATA-001"]["severity"],
        recommended_action=findings["CONSUS-DATA-001"]["recommended_action"],
        company_id="company_x",
    )
    task2 = run_create_compliance_task(
        requirement_id="CONSUS-IAM-001",
        finding=findings["CONSUS-IAM-001"]["reasoning"],
        severity=findings["CONSUS-IAM-001"]["severity"],
        recommended_action=findings["CONSUS-IAM-001"]["recommended_action"],
        company_id="company_x",
    )
    task3 = run_create_compliance_task(
        requirement_id="CONSUS-LOG-001",
        finding=findings["CONSUS-LOG-001"]["reasoning"],
        severity=findings["CONSUS-LOG-001"]["severity"],
        recommended_action=findings["CONSUS-LOG-001"]["recommended_action"],
        company_id="company_x",
    )

    assert task1["status"] == "OPEN"
    assert task2["status"] == "OPEN"
    assert task3["status"] == "OPEN"

    # 3. Re-check each requirement (run_recheck_requirement ingests/reindexes updated policies from data/updated)
    recheck_data = run_recheck_requirement("company_x", "CONSUS-DATA-001")
    assert recheck_data["previous_status"] == "MISMATCH"
    assert recheck_data["new_status"] == "MATCH"

    recheck_iam = run_recheck_requirement("company_x", "CONSUS-IAM-001")
    assert recheck_iam["previous_status"] == "PARTIAL"
    assert recheck_iam["new_status"] == "MATCH"

    recheck_log = run_recheck_requirement("company_x", "CONSUS-LOG-001")
    assert recheck_log["previous_status"] == "PARTIAL"
    assert recheck_log["new_status"] == "MATCH"

    # 4. Verify tasks auto-resolved ONLY after re-check returned MATCH
    resolved_t1 = db_manager.get_task(task1["task_id"])
    resolved_t2 = db_manager.get_task(task2["task_id"])
    resolved_t3 = db_manager.get_task(task3["task_id"])

    assert resolved_t1.status == "RESOLVED"
    assert resolved_t2.status == "RESOLVED"
    assert resolved_t3.status == "RESOLVED"
    assert "Auto-resolved" in resolved_t1.resolution_notes
    assert "Auto-resolved" in resolved_t2.resolution_notes
    assert "Auto-resolved" in resolved_t3.resolution_notes

    # 5. Generate final report and verify READY_FOR_HUMAN_REVIEW
    final_report = run_generate_compliance_report(company_id="company_x")
    assert final_report["overall_status"] == "READY_FOR_HUMAN_REVIEW"
    assert final_report["summary"]["match"] == 5
    assert final_report["summary"]["partial"] == 0
    assert final_report["summary"]["mismatch"] == 0
    assert final_report["summary"]["resolved_tasks"] == 3
    assert final_report["summary"]["unresolved_tasks"] == 0
    assert "READY FOR HUMAN REVIEW" in final_report["markdown_report"]


def test_report_generation_states():
    # When tasks are unresolved or partials exist
    initial_report = run_generate_compliance_report(company_id="company_x")
    assert "REMEDIATION REQUIRED" in initial_report["markdown_report"]
    assert "Human-in-the-Loop Governance Notice" in initial_report["markdown_report"]
