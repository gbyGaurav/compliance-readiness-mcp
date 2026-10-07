"""
Remediation task management tools for Consus Compliance Operations MCP.
"""

from typing import Dict, Any, Optional
from src.database.db import db_manager
from src.database.models import ComplianceTask


# Team mapping based on requirement category
TEAM_ROUTING = {
    "CONSUS-DATA-001": "Infrastructure Team",
    "CONSUS-IAM-001": "Security Team",
    "CONSUS-LOG-001": "Security Team",
    "CONSUS-ENC-001": "Security Team",
    "CONSUS-IR-001": "Security Team",
    "CONSUS-VULN-001": "Security Team",
    "CONSUS-CUI-001": "Compliance Team",
}


def get_team_for_requirement(requirement_id: str, category: Optional[str] = None) -> str:
    """Returns the responsible team for a requirement with category-aware fallback."""
    req_upper = (requirement_id or "").upper().strip()
    if req_upper in TEAM_ROUTING:
        return TEAM_ROUTING[req_upper]
    if category:
        cat_lower = category.lower()
        if any(w in cat_lower for w in ("data", "infra", "cloud", "residency", "storage")):
            return "Infrastructure Team"
        if any(w in cat_lower for w in ("compliance", "cui", "governance", "legal", "regulatory")):
            return "Compliance Team"
        if "it" in cat_lower:
            return "IT Team"
    return "Security Team"


def run_create_compliance_task(
    requirement_id: str,
    finding: str,
    severity: str,
    recommended_action: str,
    company_id: str = "company_x",
) -> Dict[str, Any]:
    """
    Creates a remediation task for a PARTIAL or MISMATCH finding.
    Strict validation rule: Findings with status MATCH will NOT create remediation tasks.
    Newly created tasks always start as OPEN and are automatically assigned to the correct team.
    If a task already exists for this requirement, it is reopened to OPEN (if not already OPEN)
    and updated with the latest finding details.
    """
    from src.database.db import normalize_company_id

    cid = normalize_company_id(company_id)
    req_clean = requirement_id.strip().upper()

    # Verify current finding status
    existing_findings = {f.requirement_id.upper(): f for f in db_manager.get_findings(cid)}
    if req_clean in existing_findings:
        status = existing_findings[req_clean].status
        if status == "MATCH":
            return {
                "error": f"Cannot create remediation task: Requirement {requirement_id} has status MATCH. Only PARTIAL and MISMATCH findings generate remediation tasks.",
                "requirement_id": requirement_id,
                "current_status": "MATCH",
            }

    req = db_manager.get_requirement(requirement_id)
    req_title = req.title if req else requirement_id
    assigned_team = get_team_for_requirement(req_clean, req.category if req else None)
    priority = severity.upper() if severity else "HIGH"
    title = f"Remediate Compliance Gap: {req_title}"
    description = f"Finding: {finding}\nRecommended Action: {recommended_action}"

    # Check if a task already exists for this requirement
    existing_task = db_manager.get_task_by_requirement(req_clean, cid)
    if existing_task:
        # Prevent duplicate tasks. If task was marked RESOLVED in a previous cycle
        # but finding is now PARTIAL/MISMATCH, reopen it to OPEN and clear resolution notes.
        needs_update = False
        new_status = existing_task.status
        if existing_task.status != "OPEN":
            new_status = "OPEN"
            needs_update = True

        if existing_task.assigned_team != assigned_team:
            needs_update = True

        if existing_task.priority != priority:
            needs_update = True

        if needs_update or existing_task.description != description:
            updated = db_manager.update_task(
                task_id=existing_task.task_id,
                status=new_status,
                assigned_team=assigned_team,
                clear_notes=(new_status == "OPEN"),
                title=title,
                description=description,
                priority=priority,
            )
            if updated:
                existing_task = updated

        return {
            "task_id": existing_task.task_id,
            "requirement_id": existing_task.requirement_id,
            "title": existing_task.title,
            "description": existing_task.description,
            "assigned_team": existing_task.assigned_team,
            "priority": existing_task.priority,
            "status": existing_task.status,
            "message": f"Task already exists for requirement {requirement_id}." if not needs_update else f"Reopened remediation task {existing_task.task_id} as OPEN.",
        }

    # Generate next deterministic task_id
    existing_tasks = db_manager.get_all_tasks(cid)
    max_num = 0
    for t in existing_tasks:
        try:
            num = int(t.task_id.split("-")[-1])
            if num > max_num:
                max_num = num
        except (ValueError, IndexError):
            pass
    task_num = max_num + 1

    if cid == "company_x":
        task_id = f"TASK-{task_num:03d}"
    else:
        prefix = cid.upper().replace("COMPANY_", "")
        task_id = f"TASK-{prefix}-{task_num:03d}"

    task = ComplianceTask(
        task_id=task_id,
        requirement_id=req_clean,
        company_id=cid,
        title=title,
        description=description,
        assigned_team=assigned_team,
        priority=priority,
        status="OPEN",
    )

    saved_task = db_manager.create_task(task)
    return {
        "task_id": saved_task.task_id,
        "requirement_id": saved_task.requirement_id,
        "title": saved_task.title,
        "description": saved_task.description,
        "assigned_team": saved_task.assigned_team,
        "priority": saved_task.priority,
        "status": saved_task.status,
    }


def run_create_compliance_tasks(
    company_name_or_id: str = "company_x",
) -> Dict[str, Any]:
    """
    Batch creates remediation tasks for all PARTIAL and MISMATCH findings for a company.
    Strictly validates that MATCH findings do NOT create tasks.
    Automatically assigns tasks to responsible teams and generates an initial remediation report.
    Returns all created task IDs, titles, assigned teams, and OPEN statuses.
    """
    from src.database.db import normalize_company_id

    cid = normalize_company_id(company_name_or_id)
    company_record = db_manager.find_or_create_company(company_name_or_id)
    company_name = company_record["name"]

    findings = db_manager.get_findings(cid)
    if not findings:
        from src.tools.compliance import run_analyze_compliance
        run_analyze_compliance(company_id=cid)
        findings = db_manager.get_findings(cid)

    active_tasks = []
    skipped_matches = []

    for f in findings:
        st = (f.status or "").upper()
        if st == "MATCH":
            skipped_matches.append(f.requirement_id)
            continue
        if st in ("PARTIAL", "MISMATCH"):
            task_res = run_create_compliance_task(
                requirement_id=f.requirement_id,
                finding=f.reasoning,
                severity=f.severity,
                recommended_action=f.recommended_action or f"Update internal policies to address missing {f.requirement_title} controls.",
                company_id=cid,
            )
            if "error" not in task_res and "task_id" in task_res:
                task_obj = db_manager.get_task(task_res["task_id"])
                if task_obj:
                    active_tasks.append(task_obj)

    all_tasks = db_manager.get_all_tasks(cid)
    open_tasks = [t for t in all_tasks if t.status == "OPEN"]

    remediation_summary = {
        "company": company_name,
        "company_id": cid,
        "overall_status": "REMEDIATION_REQUIRED",
        "open_tasks_count": len(open_tasks),
        "tasks": [
            {
                "task_id": t.task_id,
                "requirement_id": t.requirement_id,
                "requirement_title": db_manager.get_requirement(t.requirement_id).title if db_manager.get_requirement(t.requirement_id) else t.requirement_id,
                "assigned_team": t.assigned_team,
                "severity": t.priority,
                "status": t.status,
                "problem": t.description.split("Finding: ")[-1].split("\nRecommended Action:")[0].strip() if "Finding: " in t.description else t.description,
                "recommended_action": t.description.split("Recommended Action: ")[-1].strip() if "Recommended Action: " in t.description else "",
            }
            for t in active_tasks
        ],
    }

    return {
        "company_id": cid,
        "company_name": company_name,
        "tasks_created_count": len(active_tasks),
        "skipped_match_count": len(skipped_matches),
        "open_tasks_count": len(open_tasks),
        "tasks": [
            {
                "task_id": t.task_id,
                "requirement_id": t.requirement_id,
                "title": t.title,
                "assigned_team": t.assigned_team,
                "severity": t.priority,
                "status": t.status,
                "description": t.description,
            }
            for t in active_tasks
        ],
        "remediation_report_summary": remediation_summary,
        "message": f"{len(active_tasks)} remediation task(s) created and assigned to responsible teams. Remediation report generated.",
    }


def run_assign_compliance_task(
    task_id: str,
    assigned_team: str,
) -> Dict[str, Any]:
    """
    Assigns a remediation task to a specific Company X team.
    Allowed teams: Security Team, Compliance Team, Infrastructure Team, IT Team.
    """
    valid_teams = ["Security Team", "Compliance Team", "Infrastructure Team", "IT Team"]
    matched_team = None
    for vt in valid_teams:
        if vt.lower() == assigned_team.strip().lower():
            matched_team = vt
            break

    if not matched_team:
        matched_team = assigned_team.strip()

    updated = db_manager.update_task(task_id=task_id, assigned_team=matched_team)
    if not updated:
        return {"error": f"Task {task_id} not found."}

    return {
        "task_id": updated.task_id,
        "requirement_id": updated.requirement_id,
        "title": updated.title,
        "assigned_team": updated.assigned_team,
        "priority": updated.priority,
        "status": updated.status,
    }


def run_update_task_status(
    task_id: str,
    status: str,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Updates the remediation status of a compliance task.
    Allowed statuses: OPEN, IN_PROGRESS, WAITING_FOR_EVIDENCE, RESOLVED, REJECTED.
    """
    valid_statuses = ["OPEN", "IN_PROGRESS", "WAITING_FOR_EVIDENCE", "RESOLVED", "REJECTED"]
    clean_status = status.strip().upper()
    if clean_status not in valid_statuses:
        return {
            "error": f"Invalid status '{status}'. Must be one of: {', '.join(valid_statuses)}",
        }

    updated = db_manager.update_task(task_id=task_id, status=clean_status, resolution_notes=notes)
    if not updated:
        return {"error": f"Task {task_id} not found."}

    return {
        "task_id": updated.task_id,
        "requirement_id": updated.requirement_id,
        "title": updated.title,
        "status": updated.status,
        "assigned_team": updated.assigned_team,
        "resolution_notes": updated.resolution_notes,
    }
