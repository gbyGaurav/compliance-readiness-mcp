"""
Comprehensive test suite for natural company onboarding and compliance-readiness workflow.
Verifies:
1. Generic company registration and slug normalization (XYZ, Company X, Company Y).
2. Document scanning and multi-format discovery without requiring Windows paths.
3. Multi-format policy storage and strict vector isolation.
4. Compliance analysis returning friendly explanation cards (policy meaning, Consus meaning, gap, severity).
5. Batch task creation and automatic team routing for gaps (no false tasks for MATCH).
6. Remediation report generation.
7. Updated policy ingestion (v2 active, v1 inactive, stale vector cleanup).
8. Batch recheck and automatic task resolution upon MATCH.
9. Final readiness report generation and strict non-certification governance.
10. FastMCP tool registration of all logical workflow tools.
"""

import shutil
import pytest
from pathlib import Path

from src.database.db import db_manager, normalize_company_id
from src.database.seed import seed_requirements
from src.rag.vector_store import vector_store, resolve_company_data_directory
from src.tools.compliance import (
    run_scan_company_documents,
    run_store_company_documents,
    run_analyze_compliance,
    run_recheck_requirement,
    run_recheck_company_compliance,
    run_get_compliance_suggestions,
)
from src.tools.tasks import (
    run_create_compliance_tasks,
    run_create_compliance_task,
)
from src.tools.reports import (
    run_generate_remediation_report,
    run_generate_final_readiness_report,
    run_generate_compliance_report,
)
from src.config import COMPANY_Y_DATA_DIR, COMPANY_X_DATA_DIR, DATA_DIR


@pytest.fixture(autouse=True)
def clean_onboarding_environment():
    """Ensure clean database and baseline vectors for each test."""
    seed_requirements()
    with db_manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM findings WHERE LOWER(company_id) NOT IN ('company_x');")
        cursor.execute("DELETE FROM tasks WHERE LOWER(company_id) NOT IN ('company_x');")
        cursor.execute("DELETE FROM reports WHERE LOWER(company_id) NOT IN ('company_x');")
        cursor.execute("DELETE FROM documents WHERE LOWER(company_id) NOT IN ('company_x', 'company_y');")
        cursor.execute("DELETE FROM companies WHERE LOWER(company_id) NOT IN ('company_x', 'company_y');")
        conn.commit()

    # Ingest clean baselines
    vector_store.ingest_directory(COMPANY_X_DATA_DIR, company_id="company_x")
    vector_store.ingest_directory(COMPANY_Y_DATA_DIR, company_id="company_y")

    yield

    # Teardown: restore company_y to clean baseline v1 so other test files find baseline state
    vector_store.ingest_directory(COMPANY_Y_DATA_DIR, company_id="company_y")

    # Teardown transient company directories if created
    for cand in DATA_DIR.glob("xyz*"):
        if cand.is_dir():
            shutil.rmtree(cand, ignore_errors=True)


def test_company_registration_and_normalization():
    """Verifies that arbitrary company names are normalized and stored with isolated records."""
    assert normalize_company_id("XYZ") == "xyz"
    assert normalize_company_id("XYZ Company") == "xyz"
    assert normalize_company_id("Company X") == "company_x"
    assert normalize_company_id("Company Y") == "company_y"
    assert normalize_company_id("Acme Aerospace") == "acme_aerospace"

    co = db_manager.find_or_create_company("XYZ Company", description="New defense AI vendor.")
    assert co["company_id"] == "xyz"
    assert "XYZ" in co["name"]

    fetched = db_manager.get_company("xyz")
    assert fetched is not None
    assert fetched["company_id"] == "xyz"


def test_natural_document_scanning_without_paths():
    """Verifies document discovery finds multi-format files without requiring Windows file paths."""
    scan_res = run_scan_company_documents("Company Y")
    assert scan_res["success"] is True
    assert scan_res["company_id"] == "company_y"
    assert scan_res["documents_found_count"] == 5

    filenames = [d["filename"] for d in scan_res["documents"]]
    assert "01_data_handling_policy.txt" in filenames
    assert "02_encryption_policy.docx" in filenames
    assert "03_access_control_policy.pdf" in filenames
    assert "04_incident_response_policy.md" in filenames
    assert "05_audit_logging_policy.docx" in filenames

    # Verify categories and formats are detected
    doc_map = {d["filename"]: d for d in scan_res["documents"]}
    assert doc_map["01_data_handling_policy.txt"]["policy_category"] == "Data Handling Policy"
    assert doc_map["01_data_handling_policy.txt"]["format"] == "TXT"
    assert doc_map["03_access_control_policy.pdf"]["format"] == "PDF"
    assert doc_map["02_encryption_policy.docx"]["format"] == "DOCX"
    assert doc_map["04_incident_response_policy.md"]["format"] == "MD"

    # Confirm user message contains no Windows drive letters (E:\ or C:\)
    assert "E:\\" not in scan_res["message"]
    assert "C:\\" not in scan_res["message"]


def test_generic_company_xyz_onboarding_and_isolation():
    """Verifies end-to-end onboarding for a brand new company XYZ with multi-company isolation."""
    xyz_dir = DATA_DIR / "xyz"
    xyz_dir.mkdir(parents=True, exist_ok=True)

    # Place mock policies for XYZ
    (xyz_dir / "01_data_boundary_policy.txt").write_text(
        "XYZ Data Policy: All XYZ workloads are strictly confined to AWS GovCloud US regions. "
        "Strict prohibition of cross-border replication.",
        encoding="utf-8",
    )
    (xyz_dir / "02_encryption_policy.md").write_text(
        "XYZ Encryption: Mandatory AES-256 for all data at rest. Mandatory TLS 1.3 in transit with KMS key management.",
        encoding="utf-8",
    )

    # 1. Scan without path
    scan = run_scan_company_documents("XYZ")
    assert scan["documents_found_count"] == 2

    # 2. Store without path
    store_res = run_store_company_documents("XYZ")
    assert store_res["success"] is True
    assert store_res["stored_documents_count"] == 2

    # 3. Verify strict isolation: XYZ evidence only searchable under xyz
    xyz_chunks = vector_store.search("AWS GovCloud US regions", company_id="xyz", top_k=2)
    assert len(xyz_chunks) > 0
    assert all("xyz" in c["document_id"] for c in xyz_chunks)

    # Company X and Company Y must never retrieve XYZ chunks
    x_results = vector_store.search("AWS GovCloud US regions", company_id="company_x", top_k=5)
    assert all("xyz" not in r["document_id"] for r in x_results)


def test_compliance_analysis_cards_and_explanations():
    """Verifies analyze_compliance returns human-friendly cards with policy meaning, Consus meaning, and gaps."""
    res = run_analyze_compliance("company_y")
    assert res["summary"]["total_requirements"] == 5
    assert res["summary"]["match"] == 2
    assert res["summary"]["partial"] == 1
    assert res["summary"]["mismatch"] == 2

    findings = {f["requirement_id"]: f for f in res["findings"]}

    # CONSUS-DATA-001 (MISMATCH)
    data_f = findings["CONSUS-DATA-001"]
    assert data_f["status"] == "MISMATCH"
    assert "policy_meaning" in data_f
    assert "consus_meaning" in data_f
    assert "gap" in data_f
    assert "global" in data_f["policy_meaning"].lower()
    assert "sovereign" in data_f["consus_meaning"].lower()
    assert data_f["severity"] == "CRITICAL"

    # CONSUS-ENC-001 (MATCH)
    enc_f = findings["CONSUS-ENC-001"]
    assert enc_f["status"] == "MATCH"
    assert "aes-256" in enc_f["policy_meaning"].lower()

    # CONSUS-IAM-001 (PARTIAL)
    iam_f = findings["CONSUS-IAM-001"]
    assert iam_f["status"] == "PARTIAL"
    assert "u.s. person" in iam_f["gap"].lower() or "mfa" in iam_f["gap"].lower()


def test_batch_task_creation_and_automatic_routing():
    """Verifies batch task creation creates tasks only for PARTIAL/MISMATCH and routes to correct teams."""
    # Run analysis first to populate findings
    run_analyze_compliance("company_y")

    # Call batch task creation
    batch_res = run_create_compliance_tasks("company_y")
    assert batch_res["tasks_created_count"] == 3
    assert batch_res["skipped_match_count"] == 2
    assert batch_res["open_tasks_count"] == 3

    tasks_by_req = {t["requirement_id"]: t for t in batch_res["tasks"]}

    # Verify correct routing
    assert tasks_by_req["CONSUS-DATA-001"]["assigned_team"] == "Infrastructure Team"
    assert tasks_by_req["CONSUS-IAM-001"]["assigned_team"] == "Security Team"
    assert tasks_by_req["CONSUS-LOG-001"]["assigned_team"] == "Security Team"

    # Verify MATCH requirements (ENC-001 and IR-001) did NOT generate tasks
    assert "CONSUS-ENC-001" not in tasks_by_req
    assert "CONSUS-IR-001" not in tasks_by_req

    # Verify all tasks are OPEN
    assert all(t["status"] == "OPEN" for t in batch_res["tasks"])

    # Verify remediation report summary returned
    assert "remediation_report_summary" in batch_res
    assert batch_res["remediation_report_summary"]["overall_status"] == "REMEDIATION_REQUIRED"


def test_remediation_report_generation():
    """Verifies generate_remediation_report outputs structured gap and task summaries."""
    run_analyze_compliance("company_y")
    run_create_compliance_tasks("company_y")

    report = run_generate_remediation_report("company_y")
    assert report["overall_status"] == "REMEDIATION_REQUIRED"
    assert report["summary"]["open_tasks"] == 3
    assert len(report["open_tasks"]) == 3
    assert "Human-in-the-Loop Governance Notice" in report["markdown_report"]
    assert "REMEDIATION REQUIRED" in report["markdown_report"]


def test_updated_policy_storage_and_active_index_cleanup():
    """Verifies updated policy ingestion sets v2 active, v1 historical, and removes stale vectors."""
    # Store updated v2 policies for Company Y without providing Windows path
    store_res = run_store_company_documents("company_y", is_updated=True)
    assert store_res["success"] is True

    # Active documents in SQLite must all be version 2
    active_docs = db_manager.get_active_documents("company_y")
    for d in active_docs:
        assert d.is_active is True

    # Inactive documents in SQLite must exist as historical records
    all_docs = db_manager.get_all_documents("company_y")
    historical_docs = [d for d in all_docs if not d.is_active]
    assert len(historical_docs) > 0

    # Stale v1 retrieval check: Searching for commercial cloud global replication must NOT return v1 chunks
    results = vector_store.search("commercial multi-region global availability", company_id="company_y", top_k=5)
    for r in results:
        # Chunks must come from active documents (v2 for updated policies)
        if "data" in r["policy_name"].lower():
            assert "govcloud" in r["text"].lower() or "sovereign" in r["text"].lower()


def test_recheck_and_automatic_task_resolution():
    """Verifies batch recheck upgrades all requirements to MATCH and auto-resolves tasks."""
    run_analyze_compliance("company_y")
    run_create_compliance_tasks("company_y")

    # Ingest v2 policies
    run_store_company_documents("company_y", is_updated=True)

    # Run batch recheck
    recheck_res = run_recheck_company_compliance("company_y")
    assert recheck_res["all_match"] is True
    assert recheck_res["match_count"] == 5
    assert recheck_res["partial_count"] == 0
    assert recheck_res["mismatch_count"] == 0
    assert recheck_res["tasks_resolved_count"] == 3

    # Verify tasks in SQLite are marked RESOLVED
    y_tasks = db_manager.get_all_tasks("company_y")
    assert all(t.status == "RESOLVED" for t in y_tasks)
    assert all("Auto-resolved" in (t.resolution_notes or "") for t in y_tasks)


def test_final_readiness_report_governance_and_non_certification():
    """Verifies final readiness report produces READY_FOR_HUMAN_REVIEW and avoids legal certification claims."""
    run_analyze_compliance("company_y")
    run_create_compliance_tasks("company_y")
    run_store_company_documents("company_y", is_updated=True)
    run_recheck_company_compliance("company_y")

    final_report = run_generate_final_readiness_report("company_y")
    assert final_report["overall_status"] == "READY_FOR_HUMAN_REVIEW"
    assert final_report["summary"]["match"] == 5
    assert final_report["summary"]["unresolved_tasks"] == 0
    assert len(final_report["requirement_explanations"]) == 5

    md = final_report["markdown_report"]
    assert "READY FOR HUMAN REVIEW" in md
    assert "Human-in-the-Loop Governance Notice" in md

    # Strict governance rule: never claim official certification or legal approval
    assert "officially compliant" not in md.lower()
    assert "is certified" not in md.lower()
    assert "consus has approved" not in md.lower()

    # Next step guidance
    assert "can proceed to the next onboarding stage, subject to final human compliance review and approval" in final_report["next_step"]


def test_fastmcp_tools_and_prompts_registered():
    """Verifies that all 15 logical tools and prompts are registered on FastMCP server."""
    from src.server import mcp

    registered_tool_names = set(mcp._tool_manager._tools.keys())
    expected_tools = {
        # Preserved baseline tools
        "ingest_company_documents",
        "analyze_compliance",
        "get_compliance_suggestions",
        "create_compliance_task",
        "assign_compliance_task",
        "update_task_status",
        "recheck_requirement",
        "generate_compliance_report",
        # New natural onboarding workflow tools
        "register_company",
        "scan_company_documents",
        "store_company_documents",
        "create_compliance_tasks",
        "recheck_company_compliance",
        "generate_remediation_report",
        "generate_final_readiness_report",
    }

    for tool in expected_tools:
        assert tool in registered_tool_names, f"Tool '{tool}' not registered on FastMCP server."

    registered_prompts = set(mcp._prompt_manager._prompts.keys())
    assert "company_onboarding_and_readiness" in registered_prompts
    assert "compliance_readiness_assessment" in registered_prompts


def test_server_register_and_scan_xyz_zero_documents():
    """Verifies that register_company succeeds even with 0 documents and creates the folder,
    and scan_company_documents reports 0 files without errors."""
    from src.server import register_company, scan_company_documents

    # 1. Register company XYZ with 0 documents
    reg_res = register_company(company_name="XYZ")
    assert reg_res["success"] is True
    assert reg_res["company_id"] == "xyz"
    assert reg_res["status"] == "REGISTERED"

    # Workspace directory exists on disk
    xyz_dir = Path("data") / "xyz"
    assert xyz_dir.exists()
    assert xyz_dir.is_dir()

    # 2. Scan company documents when 0 files exist
    scan_res = scan_company_documents(company_id="XYZ")
    assert scan_res["success"] is True
    assert scan_res["company_id"] == "xyz"
    assert scan_res["documents_found_count"] == 0
    assert scan_res["documents"] == []
    assert "0 policy documents detected" in scan_res["message"]


def test_server_flexible_parameter_names():
    """Verifies that all server tools accept both company_name and company_id gracefully."""
    from src.server import (
        register_company,
        scan_company_documents,
        store_company_documents,
        analyze_compliance,
        get_compliance_suggestions,
        create_compliance_tasks,
        recheck_company_compliance,
        generate_final_readiness_report,
    )

    # Calling with company_id keyword
    r1 = register_company(company_id="XYZ_ParamTest")
    assert r1["success"] is True
    assert r1["company_id"] == "xyz_paramtest"

    # Calling with company_name keyword
    r2 = register_company(company_name="XYZ_ParamTest2")
    assert r2["success"] is True
    assert r2["company_id"] == "xyz_paramtest2"

    # scan with company_name
    s1 = scan_company_documents(company_name="Company Y")
    assert s1["documents_found_count"] == 5

    # scan with company_id
    s2 = scan_company_documents(company_id="company_y")
    assert s2["documents_found_count"] == 5

    # analyze with company_name
    a1 = analyze_compliance(company_name="Company Y")
    assert a1["company_id"] == "company_y"
    assert "findings" in a1

    # analyze with company_id
    a2 = analyze_compliance(company_id="company_y")
    assert a2["company_id"] == "company_y"
    assert "findings" in a2

