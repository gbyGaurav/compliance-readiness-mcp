"""
Consus Compliance Operations MCP Server.
Exposes tools, resources, and prompts for multi-company, version-aware AI compliance readiness workflows.
"""

from typing import Optional, Dict, Any
from mcp.server.fastmcp import FastMCP

from src.config import COMPANY_X_DATA_DIR
from src.database.seed import seed_requirements
from src.database.db import db_manager, normalize_company_id
from src.rag.vector_store import vector_store
from src.tools.compliance import (
    run_analyze_compliance,
    run_recheck_requirement,
    run_recheck_company_compliance,
    run_get_compliance_suggestions,
    run_ingest_company_documents,
    run_scan_company_documents,
    run_store_company_documents,
)
from src.tools.tasks import (
    run_create_compliance_task,
    run_create_compliance_tasks,
    run_assign_compliance_task,
    run_update_task_status,
)
from src.tools.reports import (
    run_generate_compliance_report,
    run_generate_remediation_report,
    run_generate_final_readiness_report,
)

# Initialize FastMCP Server with executive instructions
mcp = FastMCP(
    "Consus Compliance Operations",
    instructions=(
        "You are the Consus Compliance Operations AI Assistant. "
        "Consus is a real YC startup building compliant AI infrastructure for aerospace & defense workloads. "
        "Your role is to orchestrate internal compliance pre-assessments for customer policies against representative Consus requirements. "
        "\n"
        "STANDARD ONBOARDING WORKFLOW FOR ANY COMPANY (XYZ, Company X, Company Y, etc.):\n"
        "Step 1: REGISTER the company first using `register_company(company_name=...)`. This creates the isolated tenant workspace.\n"
        "Step 2: SCAN policy documents using `scan_company_documents(company_id=...)`. Reports detected files, formats, and categories (even if 0 files).\n"
        "Step 3: STORE policy documents using `store_company_documents(company_id=...)` once the user approves.\n"
        "Step 4: ANALYZE compliance using `analyze_compliance(company_id=...)` to compare against Consus requirements and generate the gap report.\n"
        "Step 5: SUGGESTIONS & TASKS: Review suggestions via `get_compliance_suggestions` and create tasks via `create_compliance_tasks`.\n"
        "Step 6: HUMAN REMEDIATION: The customer's human security/infrastructure teams update the policy documents.\n"
        "Step 7: STORE UPDATED: Re-index updated policies via `store_company_documents(company_id=...)`.\n"
        "Step 8: RECHECK: Re-evaluate compliance via `recheck_company_compliance(company_id=...)` to automatically resolve tasks.\n"
        "Step 9: READINESS REPORT: Generate final report via `generate_final_readiness_report(company_id=...)`.\n"
        "\n"
        "STRICT GUIDELINES:\n"
        "1. Never jump directly to `ingest_company_documents` for a new company. Always call `register_company` first, then `scan_company_documents`.\n"
        "2. Do NOT ask the user for Windows file paths. The system automatically locates data/<company_id>.\n"
        "3. Responses must be short, point-wise, human-friendly, and non-technical by default.\n"
        "4. Never fabricate certification or claim regulatory approval. Conclude with 'READY FOR HUMAN REVIEW'."
    ),
)


def initialize_server():
    """Initializes SQLite seed data and indexes baseline policy documents."""
    seed_requirements()
    if not vector_store.chunks:
        vector_store.ingest_directory(COMPANY_X_DATA_DIR, company_id="company_x")


# Run initialization on module load
initialize_server()


def _resolve_company_name_or_id(
    company_id: Optional[str] = None,
    company_name: Optional[str] = None,
    default: str = "company_x",
) -> str:
    """Gracefully resolves target company whether passed as company_id or company_name."""
    if company_name and (not company_id or company_id == default):
        return company_name.strip()
    if company_id:
        return company_id.strip()
    if company_name:
        return company_name.strip()
    return default


# ============================================================================
# MCP TOOLS
# ============================================================================

@mcp.tool()
def register_company(
    company_name: Optional[str] = None,
    company_id: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    PRIMARY ONBOARDING STEP 1: Register a new customer company into the compliance platform.
    Call this FIRST whenever onboarding a new company (e.g. 'XYZ', 'Company Y', etc.).
    Automatically creates the isolated tenant workspace directory (data/<company_id>) and database record.
    Succeeds independently even if no policy documents exist on disk yet.
    """
    target = _resolve_company_name_or_id(company_id=company_id, company_name=company_name, default="company_x")
    co = db_manager.find_or_create_company(target, description=description)
    cid = co["company_id"]
    from src.rag.vector_store import resolve_company_data_directory
    folder = resolve_company_data_directory(cid)
    folder.mkdir(parents=True, exist_ok=True)
    file_count = len([f for f in folder.glob("*.*") if f.is_file()])
    return {
        "success": True,
        "status": "REGISTERED",
        "company_id": cid,
        "name": co["name"],
        "description": co.get("description"),
        "workspace_directory": str(folder),
        "documents_present": file_count,
        "message": f"Successfully registered company '{co['name']}' (ID: {cid}). Workspace directory established. Ready to scan company documents.",
    }


@mcp.tool()
def scan_company_documents(
    company_id: str = "company_x",
    company_name: Optional[str] = None,
    path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    PRIMARY ONBOARDING STEP 2: Scan and discover policy documents for a company.
    Inspects policy files (.pdf, .docx, .txt, .md) in the company's workspace without requiring Windows paths.
    Reports detected filenames, policy categories, versions, formats, and file counts (even if 0 files).
    """
    target = _resolve_company_name_or_id(company_id=company_id, company_name=company_name, default="company_x")
    return run_scan_company_documents(company_name_or_id=target, path_str=path)


@mcp.tool()
def store_company_documents(
    company_id: str = "company_x",
    company_name: Optional[str] = None,
    path: Optional[str] = None,
    is_updated: bool = False,
) -> Dict[str, Any]:
    """
    PRIMARY ONBOARDING STEP 3: Store and index scanned policy documents into the vector store and database.
    Extracts text, creates chunks, computes embeddings, and activates documents for compliance analysis.
    Set is_updated=True when storing updated/remediated v2 policies for re-check.
    Only call this after scanning, when the user confirms storing the policy documents.
    """
    target = _resolve_company_name_or_id(company_id=company_id, company_name=company_name, default="company_x")
    return run_store_company_documents(company_name_or_id=target, path_str=path, is_updated=is_updated)


@mcp.tool()
def ingest_company_documents(
    company_id: str = "company_x",
    company_name: Optional[str] = None,
    path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    [Direct Ingestion] Ingest customer policy documents into the company-isolated vector store.
    Note: For standard company onboarding, prefer using 'register_company' first, then 'scan_company_documents' and 'store_company_documents'.
    """
    target = _resolve_company_name_or_id(company_id=company_id, company_name=company_name, default="company_x")
    return run_ingest_company_documents(company_id=target, path_str=path)


@mcp.tool()
def analyze_compliance(
    company_id: str = "company_x",
    company_name: Optional[str] = None,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """
    PRIMARY ONBOARDING STEP 4: Analyze internal security policies against representative Consus compliance requirements using RAG.
    
    Retrieves top relevant evidence chunks for each requirement, evaluates alignment (MATCH, PARTIAL, MISMATCH),
    and automatically generates a Compliance Gap Report PDF.
    
    Responses are formatted point-wise with key findings, evidence policies, and missing elements.
    """
    target = _resolve_company_name_or_id(company_id=company_id, company_name=company_name, default="company_x")
    return run_analyze_compliance(company_id=target, category=category)


@mcp.tool()
def get_compliance_suggestions(
    company_id: str = "company_x",
    company_name: Optional[str] = None,
    requirement_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Provide actionable remediation suggestions and recommended policy clauses for PARTIAL or MISMATCH findings.
    
    Returns specific policy clauses and step-by-step guidance for human security and compliance officers.
    Does NOT modify customer documents automatically; human-in-the-loop remediation is preserved.
    """
    target = _resolve_company_name_or_id(company_id=company_id, company_name=company_name, default="company_x")
    return run_get_compliance_suggestions(company_id=target, requirement_id=requirement_id)


@mcp.tool()
def create_compliance_task(
    requirement_id: str,
    finding: str,
    severity: str,
    recommended_action: str,
    company_id: str = "company_x",
    company_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a remediation task for a PARTIAL or MISMATCH compliance finding.
    
    Strict validation rule: Findings with status MATCH will NOT create remediation tasks.
    Creates a tracked task with priority, assigned team, and initial status 'OPEN'.
    """
    target = _resolve_company_name_or_id(company_id=company_id, company_name=company_name, default="company_x")
    return run_create_compliance_task(
        requirement_id=requirement_id,
        finding=finding,
        severity=severity,
        recommended_action=recommended_action,
        company_id=target,
    )


@mcp.tool()
def create_compliance_tasks(
    company_id: str = "company_x",
    company_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    PRIMARY ONBOARDING STEP 5: Batch create remediation tasks for all PARTIAL and MISMATCH findings for a company.
    
    Strict validation rule: Requirements with status MATCH will NOT generate tasks.
    Automatically routes each gap to the appropriate team (Infrastructure, Security, Compliance)
    and produces an initial remediation report.
    """
    target = _resolve_company_name_or_id(company_id=company_id, company_name=company_name, default="company_x")
    return run_create_compliance_tasks(company_name_or_id=target)


@mcp.tool()
def assign_compliance_task(
    task_id: str,
    assigned_team: str,
) -> Dict[str, Any]:
    """
    Assign an open compliance remediation task to a specific team.
    
    Eligible teams:
    - 'Security Team'
    - 'Compliance Team'
    - 'Infrastructure Team'
    - 'IT Team'
    """
    return run_assign_compliance_task(task_id=task_id, assigned_team=assigned_team)


@mcp.tool()
def update_task_status(
    task_id: str,
    status: str,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update the operational lifecycle status of an existing compliance task.
    
    Allowed statuses:
    - 'OPEN'
    - 'IN_PROGRESS'
    - 'WAITING_FOR_EVIDENCE'
    - 'RESOLVED'
    - 'REJECTED'
    """
    return run_update_task_status(task_id=task_id, status=status, notes=notes)


@mcp.tool()
def recheck_requirement(
    company_id: str = "company_x",
    requirement_id: str = "",
    company_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Re-evaluate a single compliance requirement against updated company policy evidence using RAG.
    
    Use this after company human teams update internal policies or provide remediation evidence.
    If the requirement status becomes MATCH, this tool automatically resolves the associated task.
    """
    target = _resolve_company_name_or_id(company_id=company_id, company_name=company_name, default="company_x")
    return run_recheck_requirement(company_id=target, requirement_id=requirement_id)


@mcp.tool()
def recheck_company_compliance(
    company_id: str = "company_x",
    company_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    PRIMARY ONBOARDING STEP 7/8: Re-evaluate all compliance requirements for a company against active updated policy evidence.
    
    Automatically resolves associated remediation tasks for all requirements that reach MATCH.
    Returns previous vs new status breakdown and remaining open tasks.
    """
    target = _resolve_company_name_or_id(company_id=company_id, company_name=company_name, default="company_x")
    return run_recheck_company_compliance(company_name_or_id=target)


@mcp.tool()
def generate_remediation_report(
    company_id: str = "company_x",
    company_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a focused compliance remediation report summarizing all open tasks,
    assigned teams, gap descriptions, and actionable steps for human remediation.
    """
    target = _resolve_company_name_or_id(company_id=company_id, company_name=company_name, default="company_x")
    return run_generate_remediation_report(company_name_or_id=target)


@mcp.tool()
def generate_final_readiness_report(
    company_id: str = "company_x",
    company_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    PRIMARY ONBOARDING FINAL STEP: Generate the comprehensive final compliance readiness assessment report.
    
    Explains active customer policies against representative Consus requirements,
    summarizes task resolution history, and issues overall readiness status
    ('READY_FOR_HUMAN_REVIEW' or 'REMEDIATION_REQUIRED').
    Includes human governance sign-off blocks. Does NOT grant legal certification.
    """
    target = _resolve_company_name_or_id(company_id=company_id, company_name=company_name, default="company_x")
    return run_generate_final_readiness_report(company_name_or_id=target)


@mcp.tool()
def generate_compliance_report(
    company_id: str = "company_x",
    company_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate the compliance assessment report in Markdown and PDF formats.
    
    Summarizes all assessed requirements, current status breakdown (MATCH / PARTIAL / MISMATCH),
    evidence policies, and task resolution state.
    Produces overall status: 'READY_FOR_HUMAN_REVIEW' or 'REMEDIATION_REQUIRED'.
    Includes human governance sign-off fields. Does NOT grant legal certification.
    """
    target = _resolve_company_name_or_id(company_id=company_id, company_name=company_name, default="company_x")
    return run_generate_compliance_report(company_id=target)


# ============================================================================
# MCP RESOURCES
# ============================================================================

@mcp.resource("consus://requirements")
def get_consus_requirements() -> str:
    """
    Read-only catalog of representative Consus compliance requirements for prototype evaluation.
    """
    reqs = db_manager.get_all_requirements()
    lines = [
        "# Representative Consus Requirements Catalog (Prototype)",
        "",
        "> Notice: Representative compliance controls based on public defense/ITAR AI standards.",
        "",
    ]
    for r in reqs:
        lines.append(f"### {r.requirement_id}: {r.title}")
        lines.append(f"- **Category:** {r.category}")
        lines.append(f"- **Severity:** {r.severity}")
        lines.append(f"- **Description:** {r.description}")
        lines.append(f"- **Mandatory Controls:** {', '.join(r.mandatory_controls)}")
        lines.append("")
    return "\n".join(lines)


# ============================================================================
# MCP PROMPTS
# ============================================================================

@mcp.prompt("company_onboarding_and_readiness")
def company_onboarding_and_readiness(company_name: str = "XYZ") -> str:
    """
    Natural conversational onboarding prompt guiding Claude through the end-to-end workflow:
    Register -> Scan -> Store -> Compare -> Tasks -> Remediate -> Recheck -> Final Readiness.
    """
    return f"""You are orchestrating compliance onboarding for {company_name}:
1. Register company first: Call `register_company(company_name='{company_name}')` to create the isolated tenant workspace.
2. Scan company documents: Call `scan_company_documents(company_id='{company_name}')` to detect policy files.
3. Confirm findings to user: report detected filenames and categories.
4. Upon approval ("Store them"): Call `store_company_documents(company_id='{company_name}')`.
5. Upon request ("Compare with Consus"): Call `analyze_compliance(company_id='{company_name}')`. Present friendly point-wise cards with policy meaning, Consus requirement meaning, gap, and severity.
6. Upon request ("Create the tasks"): Call `create_compliance_tasks(company_id='{company_name}')`. Show assigned teams and short remediation actions.
7. After human teams update policies ("Store updated documents"): Call `store_company_documents(company_id='{company_name}')`.
8. Upon request ("Recheck" / "Compare again"): Call `recheck_company_compliance(company_id='{company_name}')`.
9. When all requirements MATCH: Call `generate_final_readiness_report(company_id='{company_name}')`. Conclude with: 'READY FOR HUMAN REVIEW: {company_name} can proceed to the next onboarding stage, subject to human review and approval.'
"""


@mcp.prompt("compliance_readiness_assessment")
def compliance_readiness_assessment(company_name: str = "Company X", company_id: str = "company_x") -> str:
    """
    Prompt template guiding an LLM through the full end-to-end Consus compliance readiness workflow.
    """
    return f"""Please perform a complete Consus compliance readiness assessment for {company_name} (ID: {company_id}):
1. Scan & Store: Call `scan_company_documents(company_id='{company_id}')` then `store_company_documents(company_id='{company_id}')`.
2. Gap Analysis: Call `analyze_compliance(company_id='{company_id}')` to discover gaps and generate the Gap Report PDF.
3. Review gap suggestions: `get_compliance_suggestions(company_id='{company_id}')`.
4. Task Creation: Call `create_compliance_tasks(company_id='{company_id}')` to generate and route remediation tasks.
5. Recheck after human policy update: Call `recheck_company_compliance(company_id='{company_id}')`.
6. Final Report: Call `generate_final_readiness_report(company_id='{company_id}')` to generate the Final Markdown & PDF readiness summary.
7. Present a short, point-wise, executive summary ready for human compliance sign-off.
"""


def main():
    """Runs the Consus Compliance Operations MCP server using stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
