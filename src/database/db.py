"""
SQLite persistence layer for Consus Compliance Operations MCP.
"""

import sqlite3
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.config import DB_PATH
from src.database.models import (
    ComplianceRequirement,
    ComplianceFinding,
    ComplianceTask,
    ComplianceReport,
    CompanyDocument,
    AssessmentHistory,
    ComplianceSuggestion,
)


def normalize_company_id(name_or_id: str) -> str:
    """
    Normalizes a company name or identifier into a canonical, consistent company_id slug.
    Examples:
      - 'XYZ' -> 'xyz'
      - 'XYZ Company' -> 'xyz'
      - 'Company X' -> 'company_x'
      - 'Company Y' -> 'company_y'
      - 'company_x' -> 'company_x'
      - 'company_y' -> 'company_y'
      - 'Acme Corp' -> 'acme_corp'
    """
    if not name_or_id:
        return "company_x"
    raw = name_or_id.strip()
    lower = raw.lower().replace("-", "_").replace(" ", "_")

    if lower in ("company_x", "company_y"):
        return lower
    if lower.startswith("company_") and len(lower) == 9:  # e.g. company_a ... company_z
        return lower
    if lower.endswith("_company"):
        lower = lower[:-8]
    elif lower.startswith("company_"):
        candidate = lower[8:]
        if candidate in ("x", "y"):
            return f"company_{candidate}"
        return candidate

    clean = re.sub(r"[^a-zA-Z0-9_]", "", lower)
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean or "default_company"


class DatabaseManager:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Companies table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                company_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL
            );
            """)

            # Requirements table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS requirements (
                requirement_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                severity TEXT NOT NULL,
                description TEXT NOT NULL,
                mandatory_controls TEXT NOT NULL,
                verification_criteria TEXT NOT NULL
            );
            """)

            # Findings table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS findings (
                finding_id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id TEXT NOT NULL,
                requirement_id TEXT NOT NULL,
                requirement_title TEXT NOT NULL,
                category TEXT NOT NULL,
                status TEXT NOT NULL,
                matched_policy TEXT NOT NULL,
                evidence_chunks TEXT NOT NULL,
                reasoning TEXT NOT NULL,
                missing_elements TEXT NOT NULL,
                severity TEXT NOT NULL,
                recommended_action TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(company_id, requirement_id)
            );
            """)

            # Tasks table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL,
                requirement_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                assigned_team TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                resolution_notes TEXT
            );
            """)

            cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_company_req
            ON tasks (LOWER(company_id), UPPER(requirement_id));
            """)

            # Reports table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                report_id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                total_requirements INTEGER NOT NULL,
                match_count INTEGER NOT NULL,
                partial_count INTEGER NOT NULL,
                mismatch_count INTEGER NOT NULL,
                resolved_tasks INTEGER NOT NULL,
                unresolved_tasks INTEGER NOT NULL,
                overall_status TEXT NOT NULL,
                markdown_content TEXT NOT NULL,
                pdf_path TEXT
            );
            """)

            # Ensure pdf_path column exists in existing database
            try:
                cursor.execute("ALTER TABLE reports ADD COLUMN pdf_path TEXT;")
            except sqlite3.OperationalError:
                pass

            # Documents table (version-aware, multi-company)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                document_type TEXT NOT NULL,
                policy_category TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                is_active INTEGER NOT NULL DEFAULT 1,
                uploaded_at TEXT NOT NULL,
                chunk_count INTEGER NOT NULL DEFAULT 0
            );
            """)

            # Assessment History table (tracks every evaluation/recheck over time)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS assessment_history (
                history_id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL,
                requirement_id TEXT NOT NULL,
                status TEXT NOT NULL,
                matched_policy TEXT,
                reasoning TEXT,
                timestamp TEXT NOT NULL
            );
            """)

            # Seed default Company X if not exists
            cursor.execute("""
            INSERT OR IGNORE INTO companies (company_id, name, description, created_at)
            VALUES (?, ?, ?, ?);
            """, (
                "company_x",
                "Company X (Fictional Customer)",
                "Fictional aerospace & defense AI customer evaluating compliance before onboarding to Consus.",
                datetime.now(timezone.utc).isoformat(),
            ))

            # Seed Company Y if not exists
            cursor.execute("""
            INSERT OR IGNORE INTO companies (company_id, name, description, created_at)
            VALUES (?, ?, ?, ?);
            """, (
                "company_y",
                "Company Y (New Customer)",
                "Prospective aerospace AI contractor undergoing Consus compliance gap analysis and multi-format document onboarding.",
                datetime.now(timezone.utc).isoformat(),
            ))

            conn.commit()

    # --- Requirement Operations ---
    def upsert_requirement(self, req: ComplianceRequirement):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO requirements (
                requirement_id, title, category, severity, description, mandatory_controls, verification_criteria
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                req.requirement_id,
                req.title,
                req.category,
                req.severity,
                req.description,
                json.dumps(req.mandatory_controls),
                json.dumps(req.verification_criteria),
            ))
            conn.commit()

    def get_all_requirements(self, category: Optional[str] = None) -> List[ComplianceRequirement]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if category:
                cursor.execute("SELECT * FROM requirements WHERE LOWER(category) = LOWER(?);", (category,))
            else:
                cursor.execute("SELECT * FROM requirements ORDER BY requirement_id;")
            rows = cursor.fetchall()
            return [
                ComplianceRequirement(
                    requirement_id=row["requirement_id"],
                    title=row["title"],
                    category=row["category"],
                    severity=row["severity"],
                    description=row["description"],
                    mandatory_controls=json.loads(row["mandatory_controls"]),
                    verification_criteria=json.loads(row["verification_criteria"]),
                )
                for row in rows
            ]

    def get_requirement(self, requirement_id: str) -> Optional[ComplianceRequirement]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM requirements WHERE requirement_id = ?;", (requirement_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return ComplianceRequirement(
                requirement_id=row["requirement_id"],
                title=row["title"],
                category=row["category"],
                severity=row["severity"],
                description=row["description"],
                mandatory_controls=json.loads(row["mandatory_controls"]),
                verification_criteria=json.loads(row["verification_criteria"]),
            )

    # --- Findings Operations ---
    def save_finding(self, company_id: str, finding: ComplianceFinding):
        cid = normalize_company_id(company_id)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute("""
            INSERT OR REPLACE INTO findings (
                company_id, requirement_id, requirement_title, category, status,
                matched_policy, evidence_chunks, reasoning, missing_elements, severity,
                recommended_action, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                cid,
                finding.requirement_id,
                finding.requirement_title,
                finding.category,
                finding.status,
                finding.matched_policy,
                json.dumps(finding.relevant_policy_chunks),
                finding.reasoning,
                json.dumps(finding.missing_elements),
                finding.severity,
                finding.recommended_action,
                now,
            ))
            conn.commit()

        # Record into immutable assessment history audit log
        self.record_assessment_history(
            company_id=cid,
            requirement_id=finding.requirement_id,
            status=finding.status,
            matched_policy=finding.matched_policy,
            reasoning=finding.reasoning,
        )

    def get_findings(self, company_id: str = "company_x") -> List[ComplianceFinding]:
        cid = normalize_company_id(company_id)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM findings WHERE LOWER(company_id) = LOWER(?) ORDER BY requirement_id;", (cid,))
            rows = cursor.fetchall()
            return [
                ComplianceFinding(
                    requirement_id=row["requirement_id"],
                    requirement_title=row["requirement_title"],
                    category=row["category"],
                    status=row["status"],
                    matched_policy=row["matched_policy"],
                    relevant_policy_chunks=json.loads(row["evidence_chunks"]),
                    reasoning=row["reasoning"],
                    missing_elements=json.loads(row["missing_elements"]),
                    severity=row["severity"],
                    recommended_action=row["recommended_action"],
                )
                for row in rows
            ]

    # --- Task Operations ---
    def create_task(self, task: ComplianceTask) -> ComplianceTask:
        cid = task.company_id.strip().lower() if task.company_id else "company_x"
        req_id = task.requirement_id.strip().upper() if task.requirement_id else ""
        task.company_id = cid
        task.requirement_id = req_id

        # Deduplicate: if a task already exists for this (company, requirement), reuse and update its record
        existing = self.get_task_by_requirement(req_id, cid)
        if existing and existing.task_id != task.task_id:
            updated = self.update_task(
                task_id=existing.task_id,
                status=task.status,
                assigned_team=task.assigned_team,
                resolution_notes=task.resolution_notes,
                clear_notes=(task.resolution_notes is None and task.status == "OPEN"),
                title=task.title,
                description=task.description,
                priority=task.priority,
            )
            return updated if updated else existing

        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            created_at = task.created_at or now
            updated_at = task.updated_at or now
            cursor.execute("""
            INSERT OR REPLACE INTO tasks (
                task_id, company_id, requirement_id, title, description,
                assigned_team, priority, status, created_at, updated_at, resolution_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                task.task_id,
                task.company_id,
                task.requirement_id,
                task.title,
                task.description,
                task.assigned_team,
                task.priority,
                task.status,
                created_at,
                updated_at,
                task.resolution_notes,
            ))
            conn.commit()
            task.created_at = created_at
            task.updated_at = updated_at
            return task

    def get_task(self, task_id: str) -> Optional[ComplianceTask]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE task_id = ?;", (task_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return ComplianceTask(
                task_id=row["task_id"],
                company_id=row["company_id"],
                requirement_id=row["requirement_id"],
                title=row["title"],
                description=row["description"],
                assigned_team=row["assigned_team"],
                priority=row["priority"],
                status=row["status"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                resolution_notes=row["resolution_notes"],
            )

    def get_task_by_requirement(self, requirement_id: str, company_id: str = "company_x") -> Optional[ComplianceTask]:
        cid = normalize_company_id(company_id)
        req_id = requirement_id.strip().upper() if requirement_id else ""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM tasks WHERE LOWER(requirement_id) = LOWER(?) AND LOWER(company_id) = LOWER(?) ORDER BY created_at DESC;",
                (req_id, cid),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return ComplianceTask(
                task_id=row["task_id"],
                company_id=row["company_id"],
                requirement_id=row["requirement_id"],
                title=row["title"],
                description=row["description"],
                assigned_team=row["assigned_team"],
                priority=row["priority"],
                status=row["status"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                resolution_notes=row["resolution_notes"],
            )

    def get_all_tasks(self, company_id: str = "company_x") -> List[ComplianceTask]:
        cid = normalize_company_id(company_id)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE LOWER(company_id) = LOWER(?) ORDER BY task_id;", (cid,))
            rows = cursor.fetchall()
            return [
                ComplianceTask(
                    task_id=row["task_id"],
                    company_id=row["company_id"],
                    requirement_id=row["requirement_id"],
                    title=row["title"],
                    description=row["description"],
                    assigned_team=row["assigned_team"],
                    priority=row["priority"],
                    status=row["status"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    resolution_notes=row["resolution_notes"],
                )
                for row in rows
            ]

    def update_task(
        self,
        task_id: str,
        status: Optional[str] = None,
        assigned_team: Optional[str] = None,
        resolution_notes: Optional[str] = None,
        clear_notes: bool = False,
        title: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> Optional[ComplianceTask]:
        task = self.get_task(task_id)
        if not task:
            return None

        now = datetime.now(timezone.utc).isoformat()
        if status:
            task.status = status.upper()
        if assigned_team:
            task.assigned_team = assigned_team
        if clear_notes:
            task.resolution_notes = None
        elif resolution_notes is not None:
            task.resolution_notes = resolution_notes
        if title:
            task.title = title
        if description:
            task.description = description
        if priority:
            task.priority = priority.upper()
        task.updated_at = now

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE tasks SET
                assigned_team = ?,
                status = ?,
                updated_at = ?,
                resolution_notes = ?,
                title = ?,
                description = ?,
                priority = ?
            WHERE task_id = ?;
            """, (
                task.assigned_team,
                task.status,
                task.updated_at,
                task.resolution_notes,
                task.title,
                task.description,
                task.priority,
                task_id,
            ))
            conn.commit()

        return task

    # --- Report Operations ---
    def save_report(self, report: ComplianceReport):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO reports (
                report_id, company_id, generated_at, total_requirements,
                match_count, partial_count, mismatch_count,
                resolved_tasks, unresolved_tasks, overall_status, markdown_content, pdf_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                report.report_id,
                report.company_id,
                report.generated_at,
                report.total_requirements,
                report.match_count,
                report.partial_count,
                report.mismatch_count,
                report.resolved_tasks,
                report.unresolved_tasks,
                report.overall_status,
                report.markdown_content,
                report.pdf_path,
            ))
            conn.commit()

    def get_latest_report(self, company_id: str = "company_x") -> Optional[ComplianceReport]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM reports WHERE company_id = ? ORDER BY generated_at DESC LIMIT 1;", (company_id,))
            row = cursor.fetchone()
            if not row:
                return None
            keys = row.keys()
            return ComplianceReport(
                report_id=row["report_id"],
                company_id=row["company_id"],
                generated_at=row["generated_at"],
                total_requirements=row["total_requirements"],
                match_count=row["match_count"],
                partial_count=row["partial_count"],
                mismatch_count=row["mismatch_count"],
                resolved_tasks=row["resolved_tasks"],
                unresolved_tasks=row["unresolved_tasks"],
                overall_status=row["overall_status"],
                markdown_content=row["markdown_content"],
                pdf_path=row["pdf_path"] if "pdf_path" in keys else None,
            )

    # --- Company Operations ---
    def register_company(self, company_id: str, name: str, description: Optional[str] = None):
        cid = normalize_company_id(company_id)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO companies (company_id, name, description, created_at)
            VALUES (?, ?, ?, ?);
            """, (
                cid,
                name,
                description or f"Customer {name}",
                datetime.now(timezone.utc).isoformat(),
            ))
            conn.commit()

    def get_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        cid = normalize_company_id(company_id)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM companies WHERE LOWER(company_id) = LOWER(?);", (cid,))
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row)

    def find_company(self, name_or_id: str) -> Optional[Dict[str, Any]]:
        """Finds existing company by normalized ID, exact name, or partial match."""
        cid = normalize_company_id(name_or_id)
        found = self.get_company(cid)
        if found:
            return found
        clean_term = name_or_id.strip().lower()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Exact match on company_id or name
            cursor.execute(
                "SELECT * FROM companies WHERE LOWER(company_id) = ? OR LOWER(name) = ?;",
                (clean_term, clean_term),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            # 2. Substring match on name only if clean_term has >= 4 characters
            if len(clean_term) >= 4:
                cursor.execute(
                    "SELECT * FROM companies WHERE LOWER(name) LIKE ?;",
                    (f"%{clean_term}%",),
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)
        return None

    def find_or_create_company(self, name_or_id: str, description: Optional[str] = None) -> Dict[str, Any]:
        """Finds an existing company or automatically registers it with a canonical ID."""
        cid = normalize_company_id(name_or_id)
        existing = self.get_company(cid)
        if existing:
            return existing
        clean_name = name_or_id.strip().lower()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM companies WHERE LOWER(name) = ?;", (clean_name,))
            row = cursor.fetchone()
            if row:
                return dict(row)

        raw_name = name_or_id.strip()
        if raw_name.lower() in (cid, cid.replace("_", "")):
            display_name = f"{cid.upper()} Company" if len(cid) <= 4 else cid.replace("_", " ").title()
        else:
            display_name = raw_name
        self.register_company(company_id=cid, name=display_name, description=description)
        return self.get_company(cid)

    def get_all_companies(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM companies ORDER BY created_at ASC;")
            return [dict(r) for r in cursor.fetchall()]

    # --- Document Operations (Version-Aware) ---
    def register_document(self, doc: CompanyDocument) -> CompanyDocument:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            uploaded_at = doc.uploaded_at or now

            # If this is an active newer version, deactivate prior versions in the same category
            if doc.is_active:
                cursor.execute("""
                UPDATE documents SET is_active = 0
                WHERE company_id = ? AND policy_category = ? AND doc_id != ?;
                """, (doc.company_id, doc.policy_category, doc.doc_id))

            cursor.execute("""
            INSERT OR REPLACE INTO documents (
                doc_id, company_id, filename, file_path, document_type,
                policy_category, version, is_active, uploaded_at, chunk_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                doc.doc_id,
                doc.company_id,
                doc.filename,
                doc.file_path,
                doc.document_type,
                doc.policy_category,
                doc.version,
                1 if doc.is_active else 0,
                uploaded_at,
                doc.chunk_count,
            ))
            conn.commit()
        return doc

    def sync_active_documents(self, company_id: str, active_filenames: List[str]):
        """
        Marks documents not in active_filenames as is_active = 0 for this company.
        Preserves history/records in SQLite while ensuring only currently present files are active.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if not active_filenames:
                cursor.execute("UPDATE documents SET is_active = 0 WHERE company_id = ?;", (company_id,))
            else:
                placeholders = ",".join("?" for _ in active_filenames)
                cursor.execute(
                    f"UPDATE documents SET is_active = 0 WHERE company_id = ? AND filename NOT IN ({placeholders});",
                    [company_id] + list(active_filenames),
                )
            conn.commit()

    def get_active_documents(self, company_id: str) -> List[CompanyDocument]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM documents WHERE LOWER(company_id) = LOWER(?) AND is_active = 1 ORDER BY policy_category, version DESC;",
                (company_id,),
            )
            rows = cursor.fetchall()
            return [
                CompanyDocument(
                    doc_id=r["doc_id"],
                    company_id=r["company_id"],
                    filename=r["filename"],
                    file_path=r["file_path"],
                    document_type=r["document_type"],
                    policy_category=r["policy_category"],
                    version=r["version"],
                    is_active=bool(r["is_active"]),
                    uploaded_at=r["uploaded_at"],
                    chunk_count=r["chunk_count"],
                )
                for r in rows
            ]

    def get_all_documents(self, company_id: str) -> List[CompanyDocument]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM documents WHERE company_id = ? ORDER BY policy_category, version ASC;",
                (company_id,),
            )
            rows = cursor.fetchall()
            return [
                CompanyDocument(
                    doc_id=r["doc_id"],
                    company_id=r["company_id"],
                    filename=r["filename"],
                    file_path=r["file_path"],
                    document_type=r["document_type"],
                    policy_category=r["policy_category"],
                    version=r["version"],
                    is_active=bool(r["is_active"]),
                    uploaded_at=r["uploaded_at"],
                    chunk_count=r["chunk_count"],
                )
                for r in rows
            ]

    # --- Assessment History Operations ---
    def record_assessment_history(
        self,
        company_id: str,
        requirement_id: str,
        status: str,
        matched_policy: Optional[str] = None,
        reasoning: Optional[str] = None,
    ) -> AssessmentHistory:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            history_id = f"HIST-{company_id}-{requirement_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')[:18]}"
            cursor.execute("""
            INSERT INTO assessment_history (
                history_id, company_id, requirement_id, status, matched_policy, reasoning, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                history_id,
                company_id,
                requirement_id,
                status,
                matched_policy or "",
                reasoning or "",
                now,
            ))
            conn.commit()
            return AssessmentHistory(
                history_id=history_id,
                company_id=company_id,
                requirement_id=requirement_id,
                status=status,
                matched_policy=matched_policy,
                reasoning=reasoning,
                timestamp=now,
            )

    def get_assessment_history(
        self, company_id: str, requirement_id: Optional[str] = None
    ) -> List[AssessmentHistory]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if requirement_id:
                cursor.execute(
                    "SELECT * FROM assessment_history WHERE company_id = ? AND requirement_id = ? ORDER BY timestamp ASC;",
                    (company_id, requirement_id),
                )
            else:
                cursor.execute(
                    "SELECT * FROM assessment_history WHERE company_id = ? ORDER BY timestamp ASC;",
                    (company_id,),
                )
            rows = cursor.fetchall()
            return [
                AssessmentHistory(
                    history_id=r["history_id"],
                    company_id=r["company_id"],
                    requirement_id=r["requirement_id"],
                    status=r["status"],
                    matched_policy=r["matched_policy"],
                    reasoning=r["reasoning"],
                    timestamp=r["timestamp"],
                )
                for r in rows
            ]


# Global database manager singleton
db_manager = DatabaseManager()
