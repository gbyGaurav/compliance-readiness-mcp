"""
Unit tests for compliance task creation, assignment, and status lifecycle.
"""

import pytest
from src.database.db import db_manager
from src.database.models import ComplianceFinding
from src.tools.tasks import (
    run_create_compliance_task,
    run_create_compliance_tasks,
    run_assign_compliance_task,
    run_update_task_status,
)
from src.tools.reports import run_generate_remediation_report


@pytest.fixture(autouse=True)
def setup_clean_db():
    # Setup test DB tables
    db_manager._init_db()
    with db_manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM findings WHERE LOWER(company_id) IN ('test', 'company_test', 'regression', 'company_regression', 'stale', 'company_stale', 'dedup', 'company_dedup');")
        cursor.execute("DELETE FROM tasks WHERE LOWER(company_id) IN ('test', 'company_test', 'regression', 'company_regression', 'stale', 'company_stale', 'dedup', 'company_dedup');")
        conn.commit()


def test_match_finding_does_not_create_task():
    # Save a MATCH finding
    finding = ComplianceFinding(
        requirement_id="TEST-MATCH-001",
        requirement_title="Test Match Requirement",
        category="Testing",
        status="MATCH",
        matched_policy="Test Policy",
        relevant_policy_chunks=[],
        reasoning="All controls satisfied.",
        missing_elements=[],
        severity="LOW",
    )
    db_manager.save_finding("company_test", finding)

    result = run_create_compliance_task(
        requirement_id="TEST-MATCH-001",
        finding="All controls satisfied",
        severity="LOW",
        recommended_action="None",
        company_id="company_test",
    )

    assert "error" in result
    assert "Cannot create remediation task" in result["error"]


def test_mismatch_creates_task_and_assignment_lifecycle():
    # Save a MISMATCH finding
    finding = ComplianceFinding(
        requirement_id="TEST-MISMATCH-001",
        requirement_title="Test Mismatch Requirement",
        category="Testing",
        status="MISMATCH",
        matched_policy="Test Policy",
        relevant_policy_chunks=[],
        reasoning="Critical gap found.",
        missing_elements=["Control A"],
        severity="CRITICAL",
    )
    db_manager.save_finding("company_test", finding)

    # 1. Create task
    task = run_create_compliance_task(
        requirement_id="TEST-MISMATCH-001",
        finding="Critical gap found.",
        severity="CRITICAL",
        recommended_action="Remediate control A immediately.",
        company_id="company_test",
    )
    assert "task_id" in task
    assert task["status"] == "OPEN"
    assert task["priority"] == "CRITICAL"
    task_id = task["task_id"]

    # 2. Assign task
    assign_res = run_assign_compliance_task(task_id, "Infrastructure Team")
    assert assign_res["assigned_team"] == "Infrastructure Team"

    # 3. Update task status to IN_PROGRESS
    status_res1 = run_update_task_status(task_id, "IN_PROGRESS", notes="Assigned to sprint.")
    assert status_res1["status"] == "IN_PROGRESS"

    # 4. Update task status to RESOLVED
    status_res2 = run_update_task_status(task_id, "RESOLVED", notes="Policy updated.")
    assert status_res2["status"] == "RESOLVED"

    # 5. Invalid status rejection
    invalid_res = run_update_task_status(task_id, "INVALID_STATE")
    assert "error" in invalid_res


def test_batch_task_creation_returns_task_ids_and_open_status():
    """
    Regression test:
    create_compliance_tasks must return actual created task IDs, assign correct teams,
    start as OPEN, and remediation report must report 4 open and 0 resolved tasks.
    """
    # Create test findings: 1 MATCH, 4 PARTIAL
    findings_data = [
        ("CONSUS-DATA-001", "PARTIAL", "Infrastructure gap.", "Infrastructure Team"),
        ("CONSUS-ENC-001", "MATCH", "Encryption satisfied.", "Security Team"),
        ("CONSUS-IAM-001", "PARTIAL", "IAM gap.", "Security Team"),
        ("CONSUS-IR-001", "PARTIAL", "Incident response gap.", "Security Team"),
        ("CONSUS-LOG-001", "PARTIAL", "Logging gap.", "Security Team"),
    ]
    for req_id, st, reason, _ in findings_data:
        db_manager.save_finding(
            "company_regression",
            ComplianceFinding(
                requirement_id=req_id,
                requirement_title=req_id,
                category="Regression Testing",
                status=st,
                matched_policy="Policy",
                relevant_policy_chunks=[],
                reasoning=reason,
                missing_elements=[],
                severity="HIGH",
            ),
        )

    # 1. Run batch creation
    res = run_create_compliance_tasks("company_regression")
    assert res["tasks_created_count"] == 4
    assert res["skipped_match_count"] == 1
    assert res["open_tasks_count"] == 4

    # 2. Assert tasks list is populated with IDs and OPEN statuses
    assert len(res["tasks"]) == 4
    for t in res["tasks"]:
        assert t["task_id"].startswith("TASK-REGRESSION-")
        assert t["status"] == "OPEN"
        assert t["assigned_team"] in ("Infrastructure Team", "Security Team", "Compliance Team")

    tasks_by_req = {t["requirement_id"]: t for t in res["tasks"]}
    assert tasks_by_req["CONSUS-DATA-001"]["assigned_team"] == "Infrastructure Team"
    assert tasks_by_req["CONSUS-IAM-001"]["assigned_team"] == "Security Team"

    # 3. Verify remediation report reflects real database state
    report = run_generate_remediation_report("company_regression")
    assert report["summary"]["open_tasks"] == 4
    assert report["summary"]["resolved_tasks"] == 0
    assert len(report["open_tasks"]) == 4


def test_reopen_stale_resolved_task_when_gap_detected():
    """
    Regression test:
    If a task was previously marked RESOLVED in an earlier run, but a new assessment
    finds the requirement is still PARTIAL or MISMATCH, create_compliance_tasks
    must reopen the task to OPEN and not leave it as RESOLVED.
    """
    # 1. Simulate an old task marked RESOLVED in SQLite
    from src.database.models import ComplianceTask
    old_task = ComplianceTask(
        task_id="TASK-STALE-001",
        company_id="company_stale",
        requirement_id="CONSUS-IAM-001",
        title="Remediate Compliance Gap: IAM",
        description="Finding: Old gap\nRecommended Action: Fix IAM",
        assigned_team="Security Team",
        priority="HIGH",
        status="RESOLVED",
        resolution_notes="Previously resolved in older test run.",
    )
    db_manager.create_task(old_task)

    # 2. Add current finding showing requirement is PARTIAL
    db_manager.save_finding(
        "company_stale",
        ComplianceFinding(
            requirement_id="CONSUS-IAM-001",
            requirement_title="Granular RBAC",
            category="Access Control",
            status="PARTIAL",
            matched_policy="Access Policy",
            relevant_policy_chunks=[],
            reasoning="Current policy still missing MFA.",
            missing_elements=["MFA"],
            severity="HIGH",
        ),
    )

    # 3. Call batch creation
    res = run_create_compliance_tasks("company_stale")
    assert res["tasks_created_count"] == 1
    assert len(res["tasks"]) == 1
    task_out = res["tasks"][0]
    assert task_out["task_id"] == "TASK-STALE-001"
    assert task_out["status"] == "OPEN"

    # Verify database state
    db_task = db_manager.get_task("TASK-STALE-001")
    assert db_task.status == "OPEN"
    assert db_task.resolution_notes is None

    # Verify remediation report
    report = run_generate_remediation_report("company_stale")
    assert report["summary"]["open_tasks"] == 1
    assert report["summary"]["resolved_tasks"] == 0


def test_prevent_duplicate_tasks_for_same_company_and_requirement():
    """
    Regression test:
    Prevent duplicate tasks for the same company and requirement.
    Subsequent calls must reuse and update the existing task without creating a second row.
    """
    db_manager.save_finding(
        "company_dedup",
        ComplianceFinding(
            requirement_id="CONSUS-DATA-001",
            requirement_title="Data Boundary",
            category="Data",
            status="MISMATCH",
            matched_policy="Policy",
            relevant_policy_chunks=[],
            reasoning="Gap 1",
            missing_elements=[],
            severity="HIGH",
        ),
    )

    res1 = run_create_compliance_task(
        requirement_id="CONSUS-DATA-001",
        finding="Gap 1",
        severity="HIGH",
        recommended_action="Action 1",
        company_id="company_dedup",
    )
    task_id1 = res1["task_id"]

    res2 = run_create_compliance_task(
        requirement_id="CONSUS-DATA-001",
        finding="Gap 2",
        severity="CRITICAL",
        recommended_action="Action 2",
        company_id="company_dedup",
    )
    task_id2 = res2["task_id"]

    assert task_id1 == task_id2

    # Assert exactly 1 task exists in database
    all_tasks = db_manager.get_all_tasks("company_dedup")
    assert len(all_tasks) == 1
    assert all_tasks[0].task_id == task_id1
    assert all_tasks[0].priority == "CRITICAL"

