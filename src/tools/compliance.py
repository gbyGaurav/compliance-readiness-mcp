"""
Compliance analysis, document ingestion, suggestions, and requirement re-check tools.
"""

from typing import Dict, Any, Optional, List
from pathlib import Path

from src.config import (
    COMPANY_X_DATA_DIR,
    COMPANY_Y_DATA_DIR,
    TOP_K_RETRIEVAL,
)
from src.database.db import db_manager
from src.database.models import ComplianceFinding
from src.rag.vector_store import vector_store
from src.llm.evaluator import evaluator
from src.tools.pdf_generator import generate_gap_report_pdf


# Requirement to policy category mapping for requirement-specific retrieval
REQUIREMENT_POLICY_MAPPING = {
    "CONSUS-DATA-001": "Data Handling Policy",
    "CONSUS-ENC-001": "Encryption Policy",
    "CONSUS-IAM-001": "Access Control Policy",
    "CONSUS-IR-001": "Incident Response Policy",
    "CONSUS-LOG-001": "Audit Logging Policy",
    "CONSUS-VULN-001": "Vulnerability Management Policy",
    "CONSUS-CUI-001": "CUI Handling Policy",
}

# Suggestions and policy clause knowledge base for representative requirements
COMPLIANCE_KNOWLEDGE_BASE = {
    "CONSUS-DATA-001": {
        "title": "US-Only Data Residency & Boundary Control",
        "responsible_team": "Infrastructure Team",
        "suggested_clauses": [
            "All customer training data, model checkpoints, inference prompts, and output vectors must reside exclusively within FedRAMP High or AWS GovCloud (US) regions.",
            "Cross-border replication, multi-region fallback outside CONUS (Continental US), or remote access from non-US IP addresses is strictly prohibited.",
        ],
        "actionable_steps": [
            "Update Data Handling / Cloud Infrastructure Policy to mandate AWS GovCloud (US) / Azure Government exclusively.",
            "Remove any fallback to commercial multi-region global clouds.",
            "Explicitly prohibit cross-border data transfer or non-US replication.",
        ],
    },
    "CONSUS-IAM-001": {
        "title": "US-Person Only Access Control & Phishing-Resistant MFA",
        "responsible_team": "Security Team",
        "suggested_clauses": [
            "Access to defense AI workloads and CUI data environments is restricted strictly to verified U.S. persons (U.S. citizens or lawful permanent residents).",
            "Privileged access requires phishing-resistant hardware token MFA (FIDO2 / WebAuthn) and formal quarterly (90-day) entitlement re-certification.",
        ],
        "actionable_steps": [
            "Amend Access Control Policy to specify mandatory U.S. Person citizenship verification.",
            "Specify FIDO2 / WebAuthn phishing-resistant MFA tokens for all privileged AI infrastructure roles.",
            "Establish mandatory 90-day periodic access review cycles.",
        ],
    },
    "CONSUS-LOG-001": {
        "title": "Immutable Audit Logging & 365-Day Retention",
        "responsible_team": "Security Team",
        "suggested_clauses": [
            "All system authentication events, API calls, inference queries, and administrative modifications must be written to append-only immutable storage (AWS S3 Object Lock in Compliance mode or WORM storage).",
            "Audit logs must be retained for a minimum period of 365 days (1 year) with tamper-evident cryptographic hashes and real-time SIEM synchronization.",
        ],
        "actionable_steps": [
            "Extend audit log retention policy from 90/180 days to minimum 365 days.",
            "Mandate Write-Once-Read-Many (WORM) storage or AWS S3 Object Lock in Compliance mode.",
            "Require continuous real-time log forwarding to centralized SIEM.",
        ],
    },
    "CONSUS-ENC-001": {
        "title": "FIPS 140-2 Validated Encryption in Transit & at Rest",
        "responsible_team": "Security Team",
        "suggested_clauses": [
            "All data in transit must be protected using TLS 1.3 with FIPS 140-2 validated cryptographic modules.",
            "All data at rest, including training datasets and model weights, must be encrypted using AES-256 with customer-managed keys rotated annually.",
        ],
        "actionable_steps": [
            "Specify FIPS 140-2 module validation for all cryptographic endpoints.",
            "Enforce AES-256 encryption at rest with annual key rotation.",
        ],
    },
    "CONSUS-IR-001": {
        "title": "72-Hour Defense Incident Response Reporting",
        "responsible_team": "Security Team",
        "suggested_clauses": [
            "Any cybersecurity incident impacting systems processing CUI or defense AI pipelines must be reported to the DoD Cyber Crime Center (DC3) and Consus Operations within 72 hours of discovery.",
            "Chain-of-custody and digital forensic images of impacted containers or instances must be preserved for 90 days following containment.",
        ],
        "actionable_steps": [
            "Incorporate mandatory 72-hour notification SLA into Incident Response Playbook.",
            "Establish forensic data preservation protocols matching DFARS 252.204-7012.",
        ],
    },
    "CONSUS-VULN-001": {
        "title": "Vulnerability Remediation & Continuous Container Scanning",
        "responsible_team": "Security Team",
        "suggested_clauses": [
            "Critical vulnerabilities (CVSS >= 9.0) must be remediated or mitigated within 14 days of discovery; High vulnerabilities within 30 days.",
            "All AI container images, Python wheels, and foundation models must pass automated scanning in CI/CD before deployment.",
        ],
        "actionable_steps": [
            "Define explicit 14-day SLA for Critical vulnerabilities and 30-day for High.",
            "Implement mandatory container and dependency scanning in CI/CD.",
        ],
    },
    "CONSUS-CUI-001": {
        "title": "Controlled Unclassified Information (CUI) Handling & Sanitization",
        "responsible_team": "Compliance Team",
        "suggested_clauses": [
            "All Controlled Unclassified Information (CUI) processed by AI systems must display standard CUI banners and markings.",
            "Disposal of digital media or virtual storage containing CUI must strictly adhere to NIST SP 800-88 Rev. 1 cryptographic sanitization.",
        ],
        "actionable_steps": [
            "Adopt NIST SP 800-88 Rev. 1 sanitization standards.",
            "Mandate CUI classification banners across AI interfaces and artifacts.",
        ],
    },
}


def explain_policy_and_requirement(
    requirement_id: str,
    status: str,
    matched_policy: str,
    reasoning: str,
    missing_elements: List[str],
    company_name: str = "Company",
) -> Dict[str, str]:
    """
    Generates short, human-friendly interpretations for executive compliance cards:
    - What the company's policy currently means
    - What the representative Consus requirement requires
    - Identified gap
    - Recommended remediation action
    """
    st = (status or "").upper()
    req_id = (requirement_id or "").upper().strip()

    consus_meaning = f"Mandatory compliance control baseline for {req_id}."
    policy_meaning = reasoning or f"{company_name}'s {matched_policy} was evaluated."
    gap = ", ".join(missing_elements) if missing_elements else ("None" if st == "MATCH" else "Identified control deficiency.")
    rec_action = "Review and adapt internal security policy to satisfy requirement."

    if req_id == "CONSUS-DATA-001":
        consus_meaning = "The relevant workload, backups, models, and embeddings must remain strictly within an authorized US sovereign boundary (AWS GovCloud / Azure Government) with an explicit prohibition on cross-border data replication."
        if st == "MISMATCH":
            policy_meaning = f"{company_name}'s {matched_policy} currently permits data replication across global cloud regions or international availability zones without US sovereign boundary enforcement."
            gap = "Cross-border data replication is not prohibited, and US sovereign boundary isolation is missing."
            rec_action = "Update Data Handling Policy to restrict workloads to US sovereign cloud (AWS GovCloud / Azure Government) and strictly ban cross-border replication."
        elif st == "PARTIAL":
            policy_meaning = f"{company_name}'s {matched_policy} discusses cloud hosting and storage retention, but lacks an explicit US sovereign boundary commitment and cross-border transit ban."
            gap = "Missing explicit US sovereign boundary mandate and cross-border replication ban."
            rec_action = "Explicitly specify US sovereign cloud boundary and ban cross-border transit in Data Handling Policy."
        else:
            policy_meaning = f"{company_name}'s {matched_policy} strictly confines all workload data to US sovereign cloud environments (AWS GovCloud / Azure Government) and strictly prohibits cross-border data replication."
            gap = "None. Workload data is confined to US sovereign cloud."
            rec_action = "None required."

    elif req_id == "CONSUS-ENC-001":
        consus_meaning = "All data in transit must be protected using TLS 1.2+ (or FIPS 140-2 validated cryptography) and all data at rest must use AES-256 encryption with managed key rotation."
        if st == "MISMATCH":
            policy_meaning = f"{company_name}'s {matched_policy} does not document mandatory cryptographic encryption standards for data at rest or in transit."
            gap = "Lacks mandatory AES-256 at-rest and TLS 1.2+ in-transit encryption standards."
            rec_action = "Establish cryptographic standards mandating AES-256 at rest, TLS 1.2+ in transit, and annual KMS key rotation."
        elif st == "PARTIAL":
            policy_meaning = f"{company_name}'s {matched_policy} references encryption, but does not fully confirm both AES-256 at rest and TLS 1.2+ in transit with annual key rotation."
            gap = "Incomplete cryptographic specifications or missing key rotation schedule."
            rec_action = "Update encryption policy to mandate AES-256, TLS 1.2+, and KMS annual key rotation."
        else:
            policy_meaning = f"{company_name}'s {matched_policy} enforces AES-256 encryption at rest, TLS 1.2+ in transit, and KMS key management with annual rotation."
            gap = "None. Cryptographic controls satisfy Consus standards."
            rec_action = "None required."

    elif req_id == "CONSUS-IAM-001":
        consus_meaning = "Access to sensitive systems requires granular role-based access control (RBAC), least privilege, phishing-resistant MFA (FIDO2/hardware tokens), and restriction to verified U.S. persons."
        if st == "MISMATCH":
            policy_meaning = f"{company_name}'s {matched_policy} does not enforce RBAC, lacks phishing-resistant MFA, and permits shared or unverified international credentials."
            gap = "Lacks RBAC enforcement, phishing-resistant MFA, and US-person access restriction."
            rec_action = "Enforce granular RBAC, least privilege, FIDO2 hardware MFA, and US-person verification."
        elif st == "PARTIAL":
            policy_meaning = f"{company_name}'s {matched_policy} enforces basic role-based access and password/SMS MFA, but does not require U.S. person citizenship verification or phishing-resistant hardware token MFA."
            gap = "No U.S. person citizenship verification and relies on basic SMS/app MFA rather than phishing-resistant hardware tokens."
            rec_action = "Amend Access Control Policy to mandate verified U.S. person access and phishing-resistant FIDO2 hardware tokens."
        else:
            policy_meaning = f"{company_name}'s {matched_policy} enforces granular RBAC, least privilege, mandatory U.S. person citizenship verification, phishing-resistant hardware token MFA, and quarterly access reviews."
            gap = "None. Identity and access management controls fully align."
            rec_action = "None required."

    elif req_id == "CONSUS-IR-001":
        consus_meaning = "Cybersecurity incidents impacting sensitive workloads must have a mandatory 72-hour reporting SLA to defense authorities and Consus, with 90-day forensic container snapshot preservation."
        if st == "MISMATCH":
            policy_meaning = f"{company_name}'s {matched_policy} does not document incident containment procedures or reporting SLAs."
            gap = "No documented incident response timelines or reporting obligations."
            rec_action = "Create an incident response playbook with mandatory 72-hour reporting SLA."
        elif st == "PARTIAL":
            policy_meaning = f"{company_name}'s {matched_policy} outlines incident response procedures, but lacks a strict 72-hour reporting SLA and 90-day forensic container snapshot preservation."
            gap = "Missing 72-hour external reporting SLA and 90-day forensic data preservation."
            rec_action = "Update Incident Response Policy to include a 72-hour notification SLA and 90-day forensic preservation."
        else:
            policy_meaning = f"{company_name}'s {matched_policy} enforces a formal 72-hour incident notification SLA to defense authorities and Consus, with 90-day forensic container snapshot preservation."
            gap = "None. Incident response procedures meet defense standards."
            rec_action = "None required."

    elif req_id == "CONSUS-LOG-001":
        consus_meaning = "All system authentication, API calls, inference queries, and administrative events must be written to append-only immutable storage (WORM / S3 Object Lock) and retained for at least 365 days."
        if st == "MISMATCH":
            policy_meaning = f"{company_name}'s {matched_policy} specifies only short audit log retention (e.g. 90-180 days) and uses standard mutable storage without immutability protection."
            gap = "Log retention is less than 365 days and logs are stored in mutable storage without WORM protection."
            rec_action = "Extend log retention to 365 days and mandate append-only immutable storage (WORM / S3 Object Lock in Compliance mode)."
        elif st == "PARTIAL":
            policy_meaning = f"{company_name}'s {matched_policy} maintains audit logging and SIEM forwarding, but does not guarantee 365-day retention or append-only WORM immutability."
            gap = "Lacks full 365-day retention or immutable storage protection."
            rec_action = "Update Audit Logging Policy to enforce 365-day retention and WORM immutable storage."
        else:
            policy_meaning = f"{company_name}'s {matched_policy} writes all authentication, API, and inference telemetry to append-only immutable storage (WORM / S3 Object Lock) with 365-day retention and SIEM synchronization."
            gap = "None. Audit logging and immutability controls fully satisfy Consus standards."
            rec_action = "None required."

    return {
        "policy_meaning": policy_meaning,
        "consus_meaning": consus_meaning,
        "gap": gap,
        "recommended_action": rec_action,
    }


def ensure_vector_store_initialized(company_id: str = "company_x"):
    """Ensures baseline policies are loaded into the vector store for the requested company."""
    from src.database.db import normalize_company_id
    from src.rag.vector_store import resolve_company_data_directory

    cid = normalize_company_id(company_id)
    if cid not in vector_store.company_chunks or not vector_store.company_chunks[cid]:
        active_docs = db_manager.get_active_documents(cid)
        if active_docs:
            vector_store.rebuild_index_from_active_documents(cid)
            return

        cand = resolve_company_data_directory(cid)
        if cand.exists() and cand.is_dir():
            vector_store.ingest_directory(cand, company_id=cid)


def run_scan_company_documents(
    company_name_or_id: str,
    path_str: Optional[str] = None,
    is_updated: bool = False,
) -> Dict[str, Any]:
    """
    Discovers and inspects policy documents (.pdf, .docx, .txt, .md) for a company.
    Does NOT require the user to provide raw Windows file paths.
    """
    from src.database.db import normalize_company_id
    from src.rag.vector_store import resolve_company_data_directory, resolve_policy_metadata

    cid = normalize_company_id(company_name_or_id)
    company_record = db_manager.find_or_create_company(company_name_or_id)
    company_name = company_record["name"]

    if path_str:
        from src.config import PROJECT_ROOT
        scan_dir = Path(path_str)
        if not scan_dir.exists() and not scan_dir.is_absolute():
            scan_dir = PROJECT_ROOT / path_str
    else:
        scan_dir = resolve_company_data_directory(cid, is_updated=is_updated)

    if not scan_dir.exists():
        scan_dir.mkdir(parents=True, exist_ok=True)
        return {
            "success": True,
            "company_id": cid,
            "company_name": company_name,
            "documents_found_count": 0,
            "documents": [],
            "message": f"Created workspace folder for {company_name}. Please place policy documents (.pdf, .docx, .txt, .md) to scan.",
        }

    supported_extensions = ["*.md", "*.txt", "*.pdf", "*.docx"]
    found_files = []
    for ext in supported_extensions:
        found_files.extend(scan_dir.glob(ext))

    present_files = sorted(set(f for f in found_files if f.is_file()))

    docs_info = []
    for f in present_files:
        cat_name, ver, doc_type = resolve_policy_metadata(f)
        size_kb = round(f.stat().st_size / 1024, 1)
        docs_info.append({
            "filename": f.name,
            "policy_category": cat_name,
            "version": ver,
            "format": doc_type.upper(),
            "size_kb": size_kb,
            "status": "Ready to store" if not is_updated else "Updated version ready to store",
        })

    return {
        "success": True,
        "company_id": cid,
        "company_name": company_name,
        "documents_found_count": len(docs_info),
        "documents": docs_info,
        "message": (
            f"Found {len(docs_info)} policy document(s) for {company_name}. Ready to store in vector database."
            if docs_info
            else f"Workspace directory for {company_name} is active. 0 policy documents detected. Please place policy documents (.pdf, .docx, .txt, .md) to scan and store."
        ),
    }


def run_store_company_documents(
    company_name_or_id: str = "company_x",
    path_str: Optional[str] = None,
    is_updated: bool = False,
) -> Dict[str, Any]:
    """
    Extracts text, parses metadata, generates embeddings, stores chunks in vector store,
    registers active documents in SQLite, and synchronizes active retrieval for any company.
    """
    from src.database.db import normalize_company_id
    from src.rag.vector_store import resolve_company_data_directory
    from src.config import PROJECT_ROOT

    cid = normalize_company_id(company_name_or_id)
    company_record = db_manager.find_or_create_company(company_name_or_id)
    company_name = company_record["name"]

    if path_str:
        target_path = Path(path_str)
        if not target_path.exists() and not target_path.is_absolute():
            target_path = PROJECT_ROOT / path_str
    else:
        target_path = resolve_company_data_directory(cid, is_updated=is_updated)

    if not target_path.exists():
        return {
            "success": False,
            "error": f"Path '{path_str or str(target_path)}' does not exist.",
            "company_id": cid,
            "documents_ingested_count": 0,
            "documents": [],
            "total_active_chunks": 0,
        }

    is_up = is_updated or ("updated" in str(target_path).lower())
    if is_up:
        vector_store.ingest_updated_policies(
            updated_directories=[target_path] if target_path.is_dir() else None,
            company_id=cid,
        )
        ingested_docs = db_manager.get_active_documents(cid)
    else:
        if target_path.is_file():
            doc = vector_store.ingest_file(file_path=target_path, company_id=cid)
            ingested_docs = [doc]
        else:
            ingested_docs = vector_store.ingest_directory(directory_path=target_path, company_id=cid)

    active_chunk_count = len(vector_store.company_chunks.get(cid, []))

    return {
        "success": True,
        "company_id": cid,
        "company_name": company_name,
        "documents_ingested_count": len(ingested_docs),
        "stored_documents_count": len(ingested_docs),
        "documents": [
            {
                "doc_id": d.doc_id,
                "filename": d.filename,
                "document_type": d.document_type,
                "policy_category": d.policy_category,
                "version": d.version,
                "chunk_count": d.chunk_count,
                "status": "ACTIVE" if d.is_active else "HISTORICAL",
            }
            for d in ingested_docs
        ],
        "total_active_chunks": active_chunk_count,
        "active_chunks": active_chunk_count,
        "message": f"Successfully stored {len(ingested_docs)} document(s) for {company_name}. Vector index updated and isolated.",
    }


def run_ingest_company_documents(company_id: str = "company_x", path_str: Optional[str] = None) -> Dict[str, Any]:
    """
    Ingests policy documents (.pdf, .docx, .txt, .md) into the company vector store.
    Backward-compatible wrapper for run_store_company_documents.
    """
    return run_store_company_documents(company_name_or_id=company_id, path_str=path_str)


def run_analyze_compliance(
    company_id: str = "company_x",
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyzes internal company policies against representative Consus requirements using RAG.
    Generates a Compliance Gap Report PDF and provides point-wise, human-friendly findings.
    """
    from src.database.db import normalize_company_id

    cid = normalize_company_id(company_id)
    company_record = db_manager.find_or_create_company(company_id)
    company_name = company_record["name"]

    ensure_vector_store_initialized(company_id=cid)
    requirements = db_manager.get_all_requirements(category=category)

    if not requirements:
        return {
            "error": "No requirements found. Please ensure requirement catalog is seeded.",
            "company_id": cid,
            "company_name": company_name,
            "findings": [],
        }

    findings_list: List[Dict[str, Any]] = []
    match_count = 0
    partial_count = 0
    mismatch_count = 0

    for req in requirements:
        # Strict company-isolated and requirement-specific RAG search
        target_policy = REQUIREMENT_POLICY_MAPPING.get(req.requirement_id)
        search_query = f"{req.title} {req.description} {' '.join(req.mandatory_controls)}"
        retrieved_chunks = vector_store.search(
            search_query, top_k=TOP_K_RETRIEVAL, company_id=cid, policy_filter=target_policy
        )
        if not retrieved_chunks and target_policy:
            retrieved_chunks = vector_store.search(
                search_query, top_k=TOP_K_RETRIEVAL, company_id=cid
            )

        # Semantic evaluation
        finding = evaluator.evaluate(req, retrieved_chunks)
        db_manager.save_finding(cid, finding)

        if finding.status == "MATCH":
            match_count += 1
        elif finding.status == "PARTIAL":
            partial_count += 1
        elif finding.status == "MISMATCH":
            mismatch_count += 1

        explanations = explain_policy_and_requirement(
            requirement_id=finding.requirement_id,
            status=finding.status,
            matched_policy=finding.matched_policy,
            reasoning=finding.reasoning,
            missing_elements=finding.missing_elements,
            company_name=company_name,
        )

        findings_list.append({
            "requirement_id": finding.requirement_id,
            "requirement_title": finding.requirement_title,
            "category": finding.category,
            "status": finding.status,
            "matched_policy": finding.matched_policy,
            "policy_meaning": explanations["policy_meaning"],
            "consus_meaning": explanations["consus_meaning"],
            "gap": explanations["gap"],
            "severity": finding.severity,
            "recommended_action": finding.recommended_action or explanations["recommended_action"],
            "evidence_chunk_count": len(finding.relevant_policy_chunks),
            "evidence_snippets": [
                {
                    "policy": c["policy_name"],
                    "section": c["section_title"],
                    "similarity": c.get("similarity_score"),
                    "snippet": c["text"][:220] + "..." if len(c["text"]) > 220 else c["text"]
                }
                for c in finding.relevant_policy_chunks
            ],
            "reasoning": finding.reasoning,
            "missing_elements": finding.missing_elements,
        })

    summary = {
        "total_requirements": len(requirements),
        "match": match_count,
        "partial": partial_count,
        "mismatch": mismatch_count,
    }

    # Automatically generate Compliance Gap Report PDF
    pdf_path = None
    try:
        pdf_path = generate_gap_report_pdf(
            company_id=cid,
            findings=findings_list,
            summary=summary,
        )
    except Exception as e:
        pdf_path = f"PDF Generation note: {str(e)}"

    return {
        "company_id": cid,
        "company_name": company_name,
        "summary": summary,
        "findings": findings_list,
        "gap_report_pdf": pdf_path,
        "status_overview": f"Compliance Analysis Completed: {match_count} MATCH, {partial_count} PARTIAL, {mismatch_count} MISMATCH.",
    }


def run_get_compliance_suggestions(
    company_id: str = "company_x",
    requirement_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Provides actionable suggestions and recommended policy clauses for PARTIAL or MISMATCH findings.
    Uses stored findings from the current compliance assessment.
    Does NOT modify company documents directly; preserves human-in-the-loop remediation.
    """
    cid = company_id.strip().lower() if company_id else "company_x"
    findings = db_manager.get_findings(cid)

    # If no findings exist in database, run current compliance analysis first
    if not findings:
        run_analyze_compliance(company_id=cid)
        findings = db_manager.get_findings(cid)

    if requirement_id:
        req_target = requirement_id.strip().upper()
        findings = [f for f in findings if f.requirement_id.strip().upper() == req_target]

    suggestions = []
    for f in findings:
        status = (f.status or "").strip().upper()
        # Strictly exclude any requirement evaluated as MATCH from gap suggestions
        if status == "MATCH":
            continue
        # Suggestions apply exclusively to PARTIAL and MISMATCH findings
        if status not in ("PARTIAL", "MISMATCH"):
            continue

        req_info = COMPLIANCE_KNOWLEDGE_BASE.get(f.requirement_id, {})
        suggested_clauses = req_info.get("suggested_clauses", [
            f"The company shall formally document and implement mandatory controls for {f.requirement_title}."
        ])
        actionable_steps = req_info.get("actionable_steps", [
            f.recommended_action or f"Update internal policies to address missing elements: {', '.join(f.missing_elements)}"
        ])
        responsible_team = req_info.get("responsible_team", "Security Team")

        suggestions.append({
            "requirement_id": f.requirement_id,
            "requirement_title": f.requirement_title,
            "current_status": f.status,
            "severity": f.severity,
            "gap_summary": f.reasoning,
            "missing_elements": f.missing_elements,
            "responsible_team": responsible_team,
            "actionable_steps": actionable_steps,
            "recommended_policy_clauses": suggested_clauses,
        })

    return {
        "company_id": cid,
        "total_gaps": len(suggestions),
        "suggestions": suggestions,
        "guidance_note": (
            "These suggestions provide template language and action steps for human compliance officers. "
            "Please review, adapt, and update your internal policy documents before uploading them for re-check."
        ),
    }


def run_recheck_requirement(
    company_id: str,
    requirement_id: str,
) -> Dict[str, Any]:
    """
    Re-runs RAG retrieval and evaluation for a specific requirement after human policy updates.
    If the requirement status becomes MATCH, automatically resolves the associated task.
    """
    cid = (company_id or "company_x").strip().lower()
    ensure_vector_store_initialized(company_id=cid)
    # Ingest / re-index human-remediated policy documents before re-checking
    vector_store.ingest_updated_policies(company_id=cid)

    req = db_manager.get_requirement(requirement_id)
    if not req:
        return {"error": f"Requirement {requirement_id} not found."}

    # Fetch previous finding
    existing_findings = {f.requirement_id: f for f in db_manager.get_findings(cid)}
    prev_status = existing_findings[requirement_id].status if requirement_id in existing_findings else "UNKNOWN"

    # Re-run company-isolated and requirement-specific RAG search with updated vector index
    target_policy = REQUIREMENT_POLICY_MAPPING.get(req.requirement_id)
    search_query = f"{req.title} {req.description} {' '.join(req.mandatory_controls)}"
    retrieved_chunks = vector_store.search(
        search_query, top_k=TOP_K_RETRIEVAL, company_id=cid, policy_filter=target_policy
    )
    if not retrieved_chunks and target_policy:
        retrieved_chunks = vector_store.search(
            search_query, top_k=TOP_K_RETRIEVAL, company_id=cid
        )

    # Re-evaluate
    new_finding = evaluator.evaluate(req, retrieved_chunks)
    db_manager.save_finding(cid, new_finding)

    # Check for associated task and auto-resolve strictly if MATCH
    associated_task = db_manager.get_task_by_requirement(requirement_id, cid)
    task_update_info = None

    if associated_task and new_finding.status == "MATCH":
        updated_task = db_manager.update_task(
            task_id=associated_task.task_id,
            status="RESOLVED",
            resolution_notes=f"Auto-resolved: Requirement re-check confirmed MATCH based on updated policy evidence. Reasoning: {new_finding.reasoning}",
        )
        task_update_info = {
            "task_id": updated_task.task_id,
            "previous_task_status": associated_task.status,
            "new_task_status": updated_task.status,
            "resolution_notes": updated_task.resolution_notes,
        }
    elif associated_task and new_finding.status in ("PARTIAL", "MISMATCH"):
        if associated_task.status == "RESOLVED":
            # Finding has gap; ensure task is not erroneously left RESOLVED
            db_manager.update_task(
                task_id=associated_task.task_id,
                status="OPEN",
                clear_notes=True,
            )

    co = db_manager.get_company(cid)
    cname = co["name"] if co else cid.upper()
    explanations = explain_policy_and_requirement(
        requirement_id=new_finding.requirement_id,
        status=new_finding.status,
        matched_policy=new_finding.matched_policy,
        reasoning=new_finding.reasoning,
        missing_elements=new_finding.missing_elements,
        company_name=cname,
    )

    return {
        "company_id": cid,
        "requirement_id": req.requirement_id,
        "requirement_title": req.title,
        "previous_status": prev_status,
        "new_status": new_finding.status,
        "matched_policy": new_finding.matched_policy,
        "policy_meaning": explanations["policy_meaning"],
        "consus_meaning": explanations["consus_meaning"],
        "gap": explanations["gap"],
        "severity": new_finding.severity,
        "evidence_snippets": [
            {
                "policy": c["policy_name"],
                "section": c["section_title"],
                "similarity": c.get("similarity_score"),
                "snippet": c["text"][:220] + "..." if len(c["text"]) > 220 else c["text"]
            }
            for c in new_finding.relevant_policy_chunks
        ],
        "reasoning": new_finding.reasoning,
        "missing_elements": new_finding.missing_elements,
        "associated_task_resolution": task_update_info,
    }


def run_recheck_company_compliance(company_name_or_id: str = "company_x") -> Dict[str, Any]:
    """
    Rechecks all compliance requirements for a company against active updated policies.
    Automatically resolves associated tasks when requirements upgrade to MATCH.
    """
    from src.database.db import normalize_company_id

    cid = normalize_company_id(company_name_or_id)
    ensure_vector_store_initialized(company_id=cid)
    vector_store.ingest_updated_policies(company_id=cid)

    all_reqs = db_manager.get_all_requirements()
    co = db_manager.get_company(cid)
    company_name = co["name"] if co else cid.upper()

    rechecked_results = []
    tasks_resolved_list = []
    match_count = 0
    partial_count = 0
    mismatch_count = 0

    for req in all_reqs:
        res = run_recheck_requirement(company_id=cid, requirement_id=req.requirement_id)
        new_status = res.get("new_status", "UNKNOWN")
        if new_status == "MATCH":
            match_count += 1
        elif new_status == "PARTIAL":
            partial_count += 1
        elif new_status == "MISMATCH":
            mismatch_count += 1

        if res.get("associated_task_resolution"):
            tasks_resolved_list.append(res["associated_task_resolution"])

        rechecked_results.append({
            "requirement_id": req.requirement_id,
            "requirement_title": req.title,
            "previous_status": res.get("previous_status"),
            "new_status": new_status,
            "matched_policy": res.get("matched_policy"),
            "policy_meaning": res.get("policy_meaning"),
            "consus_meaning": res.get("consus_meaning"),
            "gap": res.get("gap"),
            "reasoning": res.get("reasoning"),
            "task_resolved": bool(res.get("associated_task_resolution")),
        })

    all_match = (match_count == len(all_reqs))

    return {
        "company_id": cid,
        "company_name": company_name,
        "rechecked_count": len(rechecked_results),
        "match_count": match_count,
        "partial_count": partial_count,
        "mismatch_count": mismatch_count,
        "tasks_resolved_count": len(tasks_resolved_list),
        "tasks_resolved": tasks_resolved_list,
        "rechecked_requirements": rechecked_results,
        "all_match": all_match,
        "remediation_status": (
            "All previously identified remediation tasks have been resolved after rechecking the updated policies."
            if all_match
            else f"Recheck completed: {match_count} MATCH, {partial_count} PARTIAL, {mismatch_count} MISMATCH."
        ),
        "message": (
            f"All {len(all_reqs)} requirements now MATCH for {company_name}. All remediation tasks resolved."
            if all_match
            else f"Recheck completed for {company_name}: {match_count} MATCH, {partial_count} PARTIAL, {mismatch_count} MISMATCH."
        ),
    }
