"""
Data models for Consus Compliance Operations MCP.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class Company(BaseModel):
    company_id: str
    name: str
    description: Optional[str] = None
    created_at: Optional[str] = None


class ComplianceRequirement(BaseModel):
    requirement_id: str
    title: str
    category: str
    severity: str
    description: str
    mandatory_controls: List[str]
    verification_criteria: List[str]


class ComplianceFinding(BaseModel):
    requirement_id: str
    requirement_title: str
    category: str
    status: str  # MATCH, PARTIAL, MISMATCH
    matched_policy: str
    relevant_policy_chunks: List[Dict[str, Any]]
    reasoning: str
    missing_elements: List[str]
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    recommended_action: Optional[str] = None


class ComplianceTask(BaseModel):
    task_id: str
    requirement_id: str
    company_id: str = "company_x"
    title: str
    description: str
    assigned_team: str  # Security Team, Compliance Team, Infrastructure Team, IT Team
    priority: str       # CRITICAL, HIGH, MEDIUM, LOW
    status: str         # OPEN, IN_PROGRESS, WAITING_FOR_EVIDENCE, RESOLVED, REJECTED
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    resolution_notes: Optional[str] = None


class ComplianceReport(BaseModel):
    report_id: str
    company_id: str
    generated_at: str
    total_requirements: int
    match_count: int
    partial_count: int
    mismatch_count: int
    resolved_tasks: int
    unresolved_tasks: int
    overall_status: str  # READY_FOR_HUMAN_REVIEW or REMEDIATION_REQUIRED
    markdown_content: str
    pdf_path: Optional[str] = None


class CompanyDocument(BaseModel):
    doc_id: str
    company_id: str
    filename: str
    file_path: str
    document_type: str  # pdf, docx, txt, md
    policy_category: str
    version: int = 1
    is_active: bool = True
    uploaded_at: Optional[str] = None
    chunk_count: int = 0


class AssessmentHistory(BaseModel):
    history_id: str
    company_id: str
    requirement_id: str
    status: str  # MATCH, PARTIAL, MISMATCH
    matched_policy: Optional[str] = None
    reasoning: Optional[str] = None
    timestamp: str


class ComplianceSuggestion(BaseModel):
    suggestion_id: str
    company_id: str
    requirement_id: str
    requirement_title: str
    current_status: str
    severity: str
    gap_summary: str
    recommended_action: str
    suggested_clauses: List[str]
    responsible_team: str
