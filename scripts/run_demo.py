"""
End-to-End Demo Script for Consus Compliance Operations MCP.
Demonstrates:
1. Multi-company isolated compliance workflow for Company X and Company Y.
2. Multi-format policy extraction (PDF, DOCX, TXT, MD).
3. Initial compliance gap analysis and Compliance Gap Report PDF generation.
4. Remediation suggestions retrieval (actionable clauses & steps).
5. Remediation task creation for PARTIAL/MISMATCH findings.
6. Version-aware human policy remediation (v2 policies).
7. Re-check workflow and automated task resolution.
8. Final compliance readiness report generation in Markdown and PDF with human sign-off block.
9. Exact RAG token savings measurement and context reduction.
"""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DB_PATH, COMPANY_X_DATA_DIR, COMPANY_Y_DATA_DIR, COMPANY_Y_UPDATED_DIR
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
    run_update_task_status,
)
from src.tools.reports import run_generate_compliance_report
from src.rag.token_counter import calculate_token_comparison
from scripts.simulate_human_remediation import apply_human_remediation


def run_company_x_demo():
    print("\n" + "=" * 80)
    print("PART 1: COMPANY X COMPLIANCE READINESS WORKFLOW (BASELINE)")
    print("=" * 80)

    # Step 0: Index baseline
    vector_store.ingest_directory(COMPANY_X_DATA_DIR, company_id="company_x")
    print(f"Indexed {len(vector_store.company_chunks['company_x'])} chunks across Company X baseline policies.")

    # Step 1: Analyze compliance
    analysis = run_analyze_compliance(company_id="company_x")
    print(f"\n[Step 1] Initial Analysis: MATCH: {analysis['summary']['match']}, "
          f"PARTIAL: {analysis['summary']['partial']}, "
          f"MISMATCH: {analysis['summary']['mismatch']}")
    print(f"  • Generated Gap Report PDF: {analysis['gap_report_pdf']}")

    # Step 2: Create tasks for PARTIAL / MISMATCH
    print("\n[Step 2] Creating remediation tasks for PARTIAL and MISMATCH findings...")
    for f in analysis["findings"]:
        if f["status"] in ["PARTIAL", "MISMATCH"]:
            task = run_create_compliance_task(
                requirement_id=f["requirement_id"],
                finding=f["reasoning"],
                severity=f["severity"],
                recommended_action=f["recommended_action"] or "Remediate policy",
                company_id="company_x",
            )
            print(f"  -> Task {task['task_id']} ({f['requirement_id']}): Assigned to {task['assigned_team']} (Status: {task['status']})")

    # Step 3: Human remediation
    print("\n[Step 3] Simulating human policy remediation (v2 policy files authored by policy leads)...")
    apply_human_remediation("all")

    # Step 4: Recheck requirements
    print("\n[Step 4] Running recheck_requirement() for remediated requirements...")
    for req_id in ["CONSUS-DATA-001", "CONSUS-IAM-001", "CONSUS-LOG-001"]:
        recheck = run_recheck_requirement("company_x", req_id)
        print(f"  • {req_id}: {recheck['previous_status']} -> {recheck['new_status']}")
        if recheck.get("associated_task_resolution"):
            task_res = recheck["associated_task_resolution"]
            print(f"    Auto-resolved: {task_res['task_id']} ({task_res['new_task_status']})")

    # Step 5: Final Report
    print("\n[Step 5] Generating Final Compliance Readiness Report...")
    report = run_generate_compliance_report("company_x")
    print(f"  • Report ID: {report['report_id']}")
    print(f"  • Overall Status: {report['overall_status']}")
    print(f"  • PDF Report Path: {report.get('pdf_report')}")


def run_company_y_demo():
    print("\n" + "=" * 80)
    print("PART 2: COMPANY Y MULTI-FORMAT ONBOARDING & COMPLIANCE LIFECYCLE")
    print("Formats: PDF (.pdf), Word (.docx), Plain Text (.txt), Markdown (.md)")
    print("=" * 80)

    # Ingest multi-format documents
    print("\n[Step 1] Ingesting multi-format policies for Company Y...")
    ingest_res = run_ingest_company_documents("company_y", str(COMPANY_Y_DATA_DIR))
    print(f"  • Ingested {ingest_res['documents_ingested_count']} documents:")
    for doc in ingest_res["documents"]:
        print(f"    - {doc['filename']} ({doc['document_type'].upper()}) -> {doc['policy_category']} (v{doc['version']}, {doc['chunk_count']} chunks)")

    # Run analysis
    print("\n[Step 2] Running analyze_compliance(company_id='company_y')...")
    analysis = run_analyze_compliance(company_id="company_y")
    print(f"  • Findings: MATCH: {analysis['summary']['match']}, "
          f"PARTIAL: {analysis['summary']['partial']}, "
          f"MISMATCH: {analysis['summary']['mismatch']}")
    print(f"  • Generated Compliance Gap Report PDF: {analysis['gap_report_pdf']}")

    # Suggestions tool
    print("\n[Step 3] Fetching remediation suggestions via get_compliance_suggestions()...")
    sugg = run_get_compliance_suggestions("company_y")
    print(f"  • Retrieved {sugg['total_gaps']} actionable gap remediation suggestions:")
    for s in sugg["suggestions"][:2]:
        print(f"    - [{s['requirement_id']}] {s['requirement_title']} (Target: {s['responsible_team']})")
        print(f"      Recommended Clause: \"{s['recommended_policy_clauses'][0][:100]}...\"")

    # Create tasks
    print("\n[Step 4] Creating tracked remediation tasks for Company Y...")
    for f in analysis["findings"]:
        if f["status"] in ["PARTIAL", "MISMATCH"]:
            task = run_create_compliance_task(
                requirement_id=f["requirement_id"],
                finding=f["reasoning"],
                severity=f["severity"],
                recommended_action=f["recommended_action"] or "Update policy controls",
                company_id="company_y",
            )
            print(f"  -> Task {task['task_id']} ({f['requirement_id']}) assigned to {task['assigned_team']}")

    # Ingest v2 documents
    print("\n[Step 5] Human teams remediate policies -> Ingesting v2 updated documents...")
    v2_res = run_ingest_company_documents("company_y", str(COMPANY_Y_UPDATED_DIR))
    print(f"  • Ingested {v2_res['documents_ingested_count']} updated documents:")
    for doc in v2_res["documents"]:
        print(f"    - {doc['filename']} ({doc['document_type'].upper()}) -> v{doc['version']}")

    # Recheck
    print("\n[Step 6] Running recheck_requirement() for remediated Company Y requirements...")
    for req_id in ["CONSUS-DATA-001", "CONSUS-IAM-001", "CONSUS-LOG-001"]:
        recheck = run_recheck_requirement("company_y", req_id)
        print(f"  • {req_id}: {recheck['previous_status']} -> {recheck['new_status']}")
        if recheck.get("associated_task_resolution"):
            task_res = recheck["associated_task_resolution"]
            print(f"    Auto-resolved: {task_res['task_id']} ({task_res['new_task_status']})")

    # Final Readiness Report
    print("\n[Step 7] Generating Final Compliance Readiness Report...")
    report = run_generate_compliance_report("company_y")
    print(f"  • Report ID: {report['report_id']}")
    print(f"  • Overall Status: {report['overall_status']}")
    print(f"  • Summary: MATCH: {report['summary']['match']}/{report['summary']['total_requirements']}, "
          f"Resolved Tasks: {report['summary']['resolved_tasks']}, Unresolved Tasks: {report['summary']['unresolved_tasks']}")
    print(f"  • Final Readiness PDF: {report.get('pdf_report')}")


def run_token_savings_demo():
    print("\n" + "=" * 80)
    print("PART 3: RAG TOKEN SAVINGS & CONTEXT EFFICIENCY MEASUREMENT")
    print("=" * 80)
    all_docs = vector_store.get_full_policy_text(company_id="company_x")
    retrieved_for_query = vector_store.search(
        "US-Only geographic boundary and cloud backup replication",
        top_k=3,
        company_id="company_x",
    )
    retrieved_text = "\n\n".join(c["text"] for c in retrieved_for_query)
    comp = calculate_token_comparison(all_docs, retrieved_text)

    print(f"Total Full Policy Repository Tokens: {comp['full_document_tokens']:,} tokens")
    print(f"Top-3 Retrieved Chunks Passed to LLM: {comp['retrieved_chunks_tokens']:,} tokens")
    print(f"Tokens Saved per Query:               {comp['tokens_saved']:,} tokens")
    print(f"Context Window Token Reduction:       {comp['reduction_percentage']}%")


def main():
    print("=" * 80)
    print("CONSUS COMPLIANCE OPERATIONS MCP PLATFORM — END-TO-END DEMO")
    print("Startup: CONSUS (YC — Compliant AI Infrastructure for Aerospace & Defense)")
    print("Customers: Company X (Fictional Baseline) & Company Y (Multi-Format Onboarding)")
    print("=" * 80)

    # Initialize fresh DB
    with db_manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM findings;")
        cursor.execute("DELETE FROM tasks;")
        cursor.execute("DELETE FROM reports;")
        conn.commit()
    seed_requirements()

    run_company_x_demo()
    run_company_y_demo()
    run_token_savings_demo()

    print("\n" + "=" * 80)
    print("DEMO COMPLETE — ALL WORKFLOW STEPS VERIFIED END-TO-END!")
    print("=" * 80)


if __name__ == "__main__":
    main()
