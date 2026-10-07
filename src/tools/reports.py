"""
Compliance report generation tool for Consus Compliance Operations MCP.
Generates comprehensive Markdown readiness report and PDF readiness report with sign-off block.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from src.database.db import db_manager, normalize_company_id
from src.database.models import ComplianceReport
from src.tools.pdf_generator import generate_final_report_pdf, generate_gap_report_pdf


def run_generate_remediation_report(company_name_or_id: str = "company_x") -> Dict[str, Any]:
    """
    Generates a concise remediation report summarizing open tasks and policy gaps.
    """
    cid = normalize_company_id(company_name_or_id)
    co_info = db_manager.get_company(cid)
    company_name = co_info["name"] if co_info else f"Company {cid.upper()}"

    requirements = db_manager.get_all_requirements()
    findings = {f.requirement_id: f for f in db_manager.get_findings(cid)}
    all_tasks = db_manager.get_all_tasks(cid)
    open_tasks = [t for t in all_tasks if t.status == "OPEN"]
    resolved_tasks = [t for t in all_tasks if t.status == "RESOLVED"]

    match_count = sum(1 for f in findings.values() if f.status == "MATCH")
    partial_count = sum(1 for f in findings.values() if f.status == "PARTIAL")
    mismatch_count = sum(1 for f in findings.values() if f.status == "MISMATCH")

    assessment_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    report_id = f"REM-{cid.upper()}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    task_lines = []
    task_items = []
    for t in open_tasks:
        req = db_manager.get_requirement(t.requirement_id)
        req_title = req.title if req else t.requirement_id
        prob = t.description.split("Finding: ")[-1].split("\nRecommended Action:")[0].strip() if "Finding: " in t.description else t.description
        act = t.description.split("Recommended Action: ")[-1].strip() if "Recommended Action: " in t.description else "Update policy controls."
        task_lines.append(
            f"### Task {t.task_id} — {t.assigned_team}\n"
            f"- **Requirement:** {t.requirement_id}: {req_title}\n"
            f"- **Severity:** {t.priority}\n"
            f"- **Identified Problem:** {prob}\n"
            f"- **Remediation Action:** {act}\n"
            f"- **Status:** {t.status}\n"
        )
        task_items.append({
            "task_id": t.task_id,
            "requirement_id": t.requirement_id,
            "requirement_title": req_title,
            "assigned_team": t.assigned_team,
            "severity": t.priority,
            "status": t.status,
            "problem": prob,
            "remediation_action": act,
        })

    tasks_block = "\n".join(task_lines) if task_lines else "No open remediation tasks.\n"

    md_content = f"""# Compliance Remediation & Gap Report

**Company:** {company_name}  
**Assessment:** Consus Representative Compliance Gap Assessment (Prototype)  
**Report ID:** `{report_id}`  
**Assessment Date:** {assessment_date}  
**Overall Status:** **REMEDIATION REQUIRED**

---

## Compliance Summary

- **Total Requirements Evaluated:** {len(requirements)}
- **MATCH:** {match_count}
- **PARTIAL:** {partial_count}
- **MISMATCH:** {mismatch_count}
- **Open Remediation Tasks:** {len(open_tasks)}
- **Resolved Tasks:** {len(resolved_tasks)}

---

## Open Remediation Tasks

{tasks_block}

---

> [!IMPORTANT]
> **Human-in-the-Loop Governance Notice:**  
> This remediation report provides automated technical guidance only.  
> Policies must be reviewed, authored, and approved by human compliance and engineering officers.
"""

    return {
        "report_id": report_id,
        "company_id": cid,
        "company_name": company_name,
        "assessment_date": assessment_date,
        "overall_status": "REMEDIATION_REQUIRED",
        "summary": {
            "total_requirements": len(requirements),
            "match": match_count,
            "partial": partial_count,
            "mismatch": mismatch_count,
            "open_tasks": len(open_tasks),
            "resolved_tasks": len(resolved_tasks),
        },
        "open_tasks": task_items,
        "markdown_report": md_content,
        "next_step": "Teams should remediate policy clauses and upload updated documents for re-check.",
    }


def run_generate_final_readiness_report(company_name_or_id: str = "company_x") -> Dict[str, Any]:
    """
    Generates the final compliance readiness assessment report in Markdown and PDF formats.
    Provides detailed requirement breakdown, explains policy meaning vs Consus controls,
    and calculates readiness status (READY_FOR_HUMAN_REVIEW or REMEDIATION_REQUIRED).
    """
    from src.tools.compliance import explain_policy_and_requirement

    cid = normalize_company_id(company_name_or_id)
    co_info = db_manager.get_company(cid)
    company_name = co_info["name"] if co_info else f"Company {cid.upper()}"

    requirements = db_manager.get_all_requirements()
    findings = {f.requirement_id: f for f in db_manager.get_findings(cid)}
    tasks = {t.requirement_id: t for t in db_manager.get_all_tasks(cid)}

    match_count = 0
    partial_count = 0
    mismatch_count = 0

    table_rows = []
    findings_summary_list = []
    requirement_explanations = []

    for req in requirements:
        finding = findings.get(req.requirement_id)
        status = finding.status if finding else "UNASSESSED"
        evidence = finding.matched_policy if finding else "None"
        reasoning = finding.reasoning if finding else "Not yet evaluated."

        task = tasks.get(req.requirement_id)
        task_str = "None"
        if task:
            task_str = f"{task.task_id} ({task.status})"

        if status == "MATCH":
            match_count += 1
        elif status == "PARTIAL":
            partial_count += 1
        elif status == "MISMATCH":
            mismatch_count += 1

        explanations = explain_policy_and_requirement(
            requirement_id=req.requirement_id,
            status=status,
            matched_policy=evidence,
            reasoning=reasoning,
            missing_elements=finding.missing_elements if finding else [],
            company_name=company_name,
        )

        table_rows.append(
            f"| {req.requirement_id}: {req.title} | **{status}** | {evidence} | {task_str} |"
        )
        findings_summary_list.append({
            "requirement_id": req.requirement_id,
            "title": req.title,
            "status": status,
            "matched_policy": evidence,
            "reasoning": reasoning,
        })
        requirement_explanations.append({
            "requirement_id": req.requirement_id,
            "requirement_title": req.title,
            "status": status,
            "matched_policy": evidence,
            "policy_meaning": explanations["policy_meaning"],
            "consus_meaning": explanations["consus_meaning"],
            "why_matched_or_gap": (
                "Policy evidence satisfies all mandatory controls."
                if status == "MATCH"
                else explanations["gap"]
            ),
        })

    all_tasks = db_manager.get_all_tasks(cid)
    resolved_tasks = sum(1 for t in all_tasks if t.status == "RESOLVED")
    unresolved_tasks = len(all_tasks) - resolved_tasks

    if match_count == len(requirements) and unresolved_tasks == 0:
        overall_status = "READY_FOR_HUMAN_REVIEW"
    else:
        overall_status = "REMEDIATION_REQUIRED"

    assessment_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    report_id = f"REP-{cid.upper()}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    # Detailed requirement explanation block
    req_explanation_lines = []
    for r in requirement_explanations:
        req_explanation_lines.append(
            f"### {r['requirement_id']}: {r['requirement_title']}\n"
            f"- **Status:** **{r['status']}**\n"
            f"- **Active Policy:** {r['matched_policy']}\n"
            f"- **What {company_name}'s Policy Means:** {r['policy_meaning']}\n"
            f"- **What Representative Consus Requirement Means:** {r['consus_meaning']}\n"
            f"- **Evaluation Detail:** {r['why_matched_or_gap']}\n"
        )

    explanation_block = "\n".join(req_explanation_lines)

    # Remediation Status section
    if unresolved_tasks == 0 and resolved_tasks > 0:
        remediation_status_text = "All previously identified remediation tasks have been resolved after rechecking the updated policies."
    elif unresolved_tasks == 0 and resolved_tasks == 0:
        remediation_status_text = "All baseline requirements evaluated to MATCH on initial assessment. No remediation tasks required."
    else:
        remediation_status_text = f"{unresolved_tasks} open remediation task(s) remaining. Policy remediation and re-check required."

    md_content = f"""# Consus Readiness Assessment Report

**Company:** {company_name}  
**Assessment:** Consus Representative Compliance Readiness Assessment (Prototype)  
**Report ID:** `{report_id}`  
**Assessment Date:** {assessment_date}  

---

## Executive Summary

| Metric | Count |
|---|---|
| **Requirements Evaluated** | {len(requirements)} |
| **MATCH** | {match_count} |
| **PARTIAL** | {partial_count} |
| **MISMATCH** | {mismatch_count} |
| **Resolved Tasks** | {resolved_tasks} |
| **Unresolved Tasks** | {unresolved_tasks} |

---

## Requirement Assessment Results

| Requirement | Status | Evidence Policy | Remediation Task |
|---|---|---|---|
{chr(10).join(table_rows)}

---

## Detailed Requirement Analysis

{explanation_block}

---

## Remediation Status

{remediation_status_text}

---

## Overall Readiness Status

# **{overall_status.replace('_', ' ')}**

**Next Step:**  
{company_name} can proceed to the next onboarding stage, subject to final human compliance review and approval.

---

> [!IMPORTANT]
> **Human-in-the-Loop Governance Notice:**  
> This readiness report is an automated prototype pre-assessment for evaluation purposes only.  
> - It does NOT constitute legal certification, regulatory sign-off, or official Consus platform authorization.  
> - Final approval must be explicitly reviewed and certified by an authorized human compliance officer from {company_name} before production deployment.
"""

    summary_dict = {
        "total_requirements": len(requirements),
        "match": match_count,
        "partial": partial_count,
        "mismatch": mismatch_count,
        "resolved_tasks": resolved_tasks,
        "unresolved_tasks": unresolved_tasks,
    }

    # Generate PDF report
    pdf_path = None
    try:
        pdf_path = generate_final_report_pdf(
            company_id=cid,
            report_data={
                "report_id": report_id,
                "generated_at": assessment_date,
                "overall_status": overall_status,
                "summary": summary_dict,
                "findings": findings_summary_list,
            },
        )
    except Exception as e:
        pdf_path = f"PDF Generation Note: {str(e)}"

    report_record = ComplianceReport(
        report_id=report_id,
        company_id=cid,
        generated_at=assessment_date,
        total_requirements=len(requirements),
        match_count=match_count,
        partial_count=partial_count,
        mismatch_count=mismatch_count,
        resolved_tasks=resolved_tasks,
        unresolved_tasks=unresolved_tasks,
        overall_status=overall_status,
        markdown_content=md_content,
        pdf_path=pdf_path if isinstance(pdf_path, str) and pdf_path.endswith(".pdf") else None,
    )
    db_manager.save_report(report_record)

    return {
        "report_id": report_id,
        "company_id": cid,
        "company_name": company_name,
        "generated_at": assessment_date,
        "overall_status": overall_status,
        "summary": summary_dict,
        "requirement_explanations": requirement_explanations,
        "remediation_status": remediation_status_text,
        "markdown_report": md_content,
        "pdf_report": pdf_path,
        "next_step": f"{company_name} can proceed to the next onboarding stage, subject to final human compliance review and approval.",
    }


def run_generate_compliance_report(company_id: str = "company_x") -> Dict[str, Any]:
    """
    Generates the final compliance readiness report in Markdown and PDF formats.
    Backward-compatible entry point for run_generate_final_readiness_report.
    """
    return run_generate_final_readiness_report(company_name_or_id=company_id)
