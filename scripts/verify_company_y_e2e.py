"""
End-to-end simulation of the conversational Company Y onboarding & compliance-readiness workflow.
Exercises:
1. "Company Y has arrived. Scan their policy documents." -> scan_company_documents
2. "Store them." -> store_company_documents
3. "Compare Company Y with Consus." -> analyze_compliance
4. "Create the tasks." -> create_compliance_tasks
5. "Generate the remediation report." -> generate_remediation_report
6. "Store the updated documents." -> store_company_documents(is_updated=True)
7. "Recheck Company Y." -> recheck_company_compliance
8. "Generate the final readiness report." -> generate_final_readiness_report
"""

import json
from src.database.seed import seed_requirements
from src.database.db import db_manager
from src.rag.vector_store import vector_store
from src.tools.compliance import (
    run_scan_company_documents,
    run_store_company_documents,
    run_analyze_compliance,
    run_recheck_company_compliance,
)
from src.tools.tasks import run_create_compliance_tasks
from src.tools.reports import (
    run_generate_remediation_report,
    run_generate_final_readiness_report,
)


def run_e2e_flow():
    print("=" * 80)
    print("CONSUS COMPLIANCE OPERATIONS — COMPANY Y END-TO-END WORKFLOW")
    print("=" * 80)

    # Clean setup for demonstration
    seed_requirements()
    with db_manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM findings WHERE LOWER(company_id) = 'company_y';")
        cursor.execute("DELETE FROM tasks WHERE LOWER(company_id) = 'company_y';")
        cursor.execute("DELETE FROM reports WHERE LOWER(company_id) = 'company_y';")
        conn.commit()

    # STEP 1: Scan Documents
    print("\n[STEP 1] USER: 'Company Y has joined. Here are their policy documents.'")
    scan = run_scan_company_documents("Company Y")
    print(f"CLAUDE/MCP: Found {scan['documents_found_count']} policy documents for {scan['company_name']}:")
    for doc in scan["documents"]:
        print(f"  - {doc['filename']} ({doc['format']}) -> Detected: {doc['policy_category']} (v{doc['version']})")

    # STEP 2: Store Documents
    print("\n[STEP 2] USER: 'Store them.'")
    store = run_store_company_documents("Company Y")
    print(f"CLAUDE/MCP: {store['message']} (Active chunks: {store['active_chunks']})")

    # STEP 3: Compare with Consus
    print("\n[STEP 3] USER: 'Compare Company Y with Consus.'")
    comp = run_analyze_compliance("Company Y")
    summary = comp["summary"]
    print(f"CLAUDE/MCP: Compliance Summary for {comp['company_name']}:")
    print(f"  Total Requirements: {summary['total_requirements']}")
    print(f"  MATCH: {summary['match']}")
    print(f"  PARTIAL: {summary['partial']}")
    print(f"  MISMATCH: {summary['mismatch']}")
    print("\nFindings Detail:")
    for f in comp["findings"]:
        print(f"  [{f['status']}] {f['requirement_id']}: {f['requirement_title']}")
        print(f"    - Policy: {f['matched_policy']}")
        print(f"    - Policy Meaning: {f['policy_meaning']}")
        print(f"    - Consus Meaning: {f['consus_meaning']}")
        print(f"    - Gap: {f['gap']}")
        print(f"    - Severity: {f['severity']}")

    # STEP 4: Create Tasks
    print("\n[STEP 4] USER: 'Create the tasks.'")
    tasks_res = run_create_compliance_tasks("Company Y")
    print(f"CLAUDE/MCP: {tasks_res['message']}")
    for t in tasks_res["tasks"]:
        print(f"  - {t['task_id']} | Req: {t['requirement_id']} | Team: {t['assigned_team']} | Severity: {t['severity']} | Status: {t['status']}")

    # STEP 5: Remediation Report
    print("\n[STEP 5] CLAUDE: Generating remediation report...")
    rem_rep = run_generate_remediation_report("Company Y")
    print(f"  Report ID: {rem_rep['report_id']} | Status: {rem_rep['overall_status']}")
    print(f"  Open Tasks: {rem_rep['summary']['open_tasks']} | Guidance: {rem_rep['next_step']}")

    # STEP 6: Human Remediation & Store Updated Policies
    print("\n[STEP 6] USER: 'Here are Company Y's updated policies. Store them.'")
    store_up = run_store_company_documents("Company Y", is_updated=True)
    print(f"CLAUDE/MCP: {store_up['message']}")
    for d in store_up["documents"]:
        if d["version"] > 1:
            print(f"  - {d['filename']} (v{d['version']}) -> Status: {d['status']} ({d['chunk_count']} chunks)")

    # STEP 7: Recheck
    print("\n[STEP 7] USER: 'Recheck Company Y.'")
    recheck = run_recheck_company_compliance("Company Y")
    print(f"CLAUDE/MCP: {recheck['message']}")
    print(f"  MATCH: {recheck['match_count']} | PARTIAL: {recheck['partial_count']} | MISMATCH: {recheck['mismatch_count']}")
    print(f"  Tasks Auto-Resolved: {recheck['tasks_resolved_count']}")

    # STEP 8: Final Readiness Report
    print("\n[STEP 8] USER: 'Generate the final readiness report.'")
    final = run_generate_final_readiness_report("Company Y")
    print(f"CLAUDE/MCP: Overall Readiness Status: {final['overall_status']}")
    print(f"  Requirements Evaluated: {final['summary']['total_requirements']}")
    print(f"  MATCH: {final['summary']['match']} | PARTIAL: {final['summary']['partial']} | MISMATCH: {final['summary']['mismatch']}")
    print(f"  Unresolved Tasks: {final['summary']['unresolved_tasks']}")
    print(f"  Remediation Status: {final['remediation_status']}")
    print(f"  Next Step: {final['next_step']}")

    print("\n" + "=" * 80)
    print("COMPANY Y WORKFLOW SIMULATION COMPLETED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    run_e2e_flow()
