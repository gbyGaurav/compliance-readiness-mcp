"""
In-memory & local vector store supporting semantic search, dynamic policy updates,
multi-format extraction (PDF, DOCX, TXT, MD), and strict multi-company isolation.
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from src.rag.chunker import chunk_markdown_document, PolicyChunk
from src.rag.embeddings import LocalEmbeddingEngine
from src.rag.extractor import extract_text_from_file
from src.config import TOP_K_RETRIEVAL
from src.database.db import db_manager
from src.database.models import CompanyDocument


def resolve_policy_metadata(file_path: Path) -> Tuple[str, int, str]:
    """
    Infers policy category, version, and document type from a file path.
    """
    stem = file_path.stem.lower()
    ext = file_path.suffix.lower().lstrip(".")
    
    # Extract version if present (e.g. _v2, -v2, _v3)
    version = 1
    v_match = re.search(r"[-_]v(\d+)", stem)
    if v_match:
        version = int(v_match.group(1))

    policy_mapping = {
        "data_boundary": "Data Handling Policy",
        "data_handling": "Data Handling Policy",
        "access_control": "Access Control Policy",
        "iam": "Access Control Policy",
        "audit_logging": "Audit Logging Policy",
        "logging": "Audit Logging Policy",
        "encryption": "Encryption Policy",
        "incident_response": "Incident Response Policy",
        "vulnerability": "Vulnerability Management Policy",
        "security": "Information Security Policy",
        "cui": "CUI Handling Policy",
    }

    matched_name = None
    for key, pol_name in policy_mapping.items():
        if key in stem:
            matched_name = pol_name
            break

    if not matched_name:
        clean = re.sub(r"[-_]v\d+", "", stem).replace("_", " ").replace("-", " ").title()
        matched_name = clean if "Policy" in clean else f"{clean} Policy"

    return matched_name, version, ext


def resolve_company_data_directory(company_id: str, is_updated: bool = False) -> Path:
    """
    Automatically resolves the policy storage directory on disk for any company.
    Eliminates the need for end users or clients to provide raw Windows paths.
    Checks candidate directories for company_x, company_y, xyz, or any custom tenant.
    """
    from src.config import (
        DATA_DIR,
        COMPANY_X_DATA_DIR,
        COMPANY_Y_DATA_DIR,
        COMPANY_X_UPDATED_DIR,
        COMPANY_Y_UPDATED_DIR,
        UPDATED_DATA_DIR,
    )
    from src.database.db import normalize_company_id

    cid = normalize_company_id(company_id)
    candidates: List[Path] = []

    if is_updated:
        if cid == "company_x":
            candidates.extend([COMPANY_X_UPDATED_DIR, UPDATED_DATA_DIR])
        elif cid == "company_y":
            candidates.extend([
                COMPANY_Y_UPDATED_DIR,
                DATA_DIR / "company_y" / "updated",
                DATA_DIR / "company_y_v1" / "updated",
            ])
        else:
            candidates.extend([
                DATA_DIR / cid / "updated",
                DATA_DIR / f"{cid}_v1" / "updated",
                DATA_DIR / f"company_{cid}" / "updated",
                DATA_DIR / f"company_{cid}_v1" / "updated",
                DATA_DIR / "updated",
            ])
    else:
        if cid == "company_x":
            candidates.append(COMPANY_X_DATA_DIR)
        elif cid == "company_y":
            candidates.append(COMPANY_Y_DATA_DIR)
        else:
            candidates.extend([
                DATA_DIR / cid,
                DATA_DIR / f"{cid}_v1",
                DATA_DIR / f"company_{cid}",
                DATA_DIR / f"company_{cid}_v1",
            ])

    # 1. Prefer existing directory that contains supported policy files
    supported_exts = ("*.pdf", "*.docx", "*.txt", "*.md")
    for cand in candidates:
        if cand.exists() and cand.is_dir():
            has_files = any(list(cand.glob(ext)) for ext in supported_exts)
            if has_files:
                return cand

    # 2. Return first existing candidate directory
    for cand in candidates:
        if cand.exists() and cand.is_dir():
            return cand

    # 3. Fallback: default company directory under DATA_DIR
    fallback = (DATA_DIR / cid / "updated") if is_updated else (DATA_DIR / cid)
    return fallback


class ComplianceVectorStore:
    def __init__(self):
        # Multi-company isolated structures: company_id -> data
        self.company_chunks: Dict[str, List[PolicyChunk]] = {}
        self.company_archived_chunks: Dict[str, List[PolicyChunk]] = {}
        self.company_matrices: Dict[str, Optional[np.ndarray]] = {}
        self.company_engines: Dict[str, LocalEmbeddingEngine] = {}
        self.company_raw_docs: Dict[str, Dict[str, str]] = {}
        self.current_company_id: str = "company_x"

    @property
    def chunks(self) -> List[PolicyChunk]:
        """Provides backward-compatible access to current company's active chunks."""
        if self.current_company_id in self.company_chunks:
            return self.company_chunks[self.current_company_id]
        if self.company_chunks:
            return list(self.company_chunks.values())[0]
        return []

    @chunks.setter
    def chunks(self, val: List[PolicyChunk]):
        self.company_chunks[self.current_company_id] = val

    @property
    def embeddings_matrix(self) -> Optional[np.ndarray]:
        return self.company_matrices.get(self.current_company_id, None)

    @embeddings_matrix.setter
    def embeddings_matrix(self, val: Optional[np.ndarray]):
        self.company_matrices[self.current_company_id] = val

    @property
    def embedding_engine(self) -> LocalEmbeddingEngine:
        if self.current_company_id not in self.company_engines:
            self.company_engines[self.current_company_id] = LocalEmbeddingEngine()
        return self.company_engines[self.current_company_id]

    @property
    def raw_documents(self) -> Dict[str, str]:
        if self.current_company_id not in self.company_raw_docs:
            self.company_raw_docs[self.current_company_id] = {}
        return self.company_raw_docs[self.current_company_id]

    def _get_engine(self, company_id: str) -> LocalEmbeddingEngine:
        if company_id not in self.company_engines:
            self.company_engines[company_id] = LocalEmbeddingEngine()
        return self.company_engines[company_id]

    def ingest_file(
        self,
        file_path: Path,
        company_id: str = "company_x",
        version: Optional[int] = None,
        policy_name: Optional[str] = None,
    ) -> CompanyDocument:
        """
        Extracts, chunks, embeds, and records a single document (.pdf, .docx, .txt, .md).
        Guarantees version-aware replacement of older chunks in the vector search index.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        extracted_text = extract_text_from_file(path)
        inferred_name, detected_ver, doc_type = resolve_policy_metadata(path)
        final_policy_name = policy_name or inferred_name
        final_ver = version if version is not None else detected_ver

        doc_id = f"{company_id}-{path.stem}"

        # Initialize company storage
        if company_id not in self.company_chunks:
            self.company_chunks[company_id] = []
        if company_id not in self.company_raw_docs:
            self.company_raw_docs[company_id] = {}
        if company_id not in self.company_archived_chunks:
            self.company_archived_chunks[company_id] = []

        self.company_raw_docs[company_id][final_policy_name] = extracted_text

        # Archive prior active chunks for this policy in this company's index
        active_chunks = []
        for c in self.company_chunks[company_id]:
            if c.policy_name.lower() == final_policy_name.lower():
                c.is_active = False
                self.company_archived_chunks[company_id].append(c)
            else:
                active_chunks.append(c)
        self.company_chunks[company_id] = active_chunks

        # Chunk the extracted document with company_id, version, and is_active=True
        new_chunks = chunk_markdown_document(
            markdown_text=extracted_text,
            document_id=doc_id,
            policy_name=final_policy_name,
            company_id=company_id,
            version=final_ver,
            is_active=True,
        )
        self.company_chunks[company_id].extend(new_chunks)

        # Register document in database
        doc_record = CompanyDocument(
            doc_id=doc_id,
            company_id=company_id,
            filename=path.name,
            file_path=str(path),
            document_type=doc_type,
            policy_category=final_policy_name,
            version=final_ver,
            is_active=True,
            chunk_count=len(new_chunks),
        )
        db_manager.register_document(doc_record)

        self._rebuild_index(company_id=company_id)
        self.current_company_id = company_id
        return doc_record

    def ingest_directory(self, directory_path: Path, company_id: str = "company_x") -> List[CompanyDocument]:
        """
        Reads all supported documents (.md, .txt, .pdf, .docx) directly from directory,
        chunks them, synchronizes active documents in SQLite, and builds company-isolated vector index.
        Guarantees that deleted/removed documents leave NO active chunks in this company's search index.
        """
        dir_p = Path(directory_path)
        if not dir_p.exists():
            raise FileNotFoundError(f"Directory {dir_p} does not exist.")

        self.current_company_id = company_id
        if company_id not in self.company_chunks:
            self.company_chunks[company_id] = []
        if company_id not in self.company_raw_docs:
            self.company_raw_docs[company_id] = {}
        if company_id not in self.company_archived_chunks:
            self.company_archived_chunks[company_id] = []

        supported_extensions = ["*.md", "*.txt", "*.pdf", "*.docx"]
        all_files = []
        for ext in supported_extensions:
            all_files.extend(dir_p.glob(ext))

        # Only files directly in this directory (exclude subdirectories like updated)
        present_files = sorted(set(f for f in all_files if f.is_file()))
        active_filenames = [f.name for f in present_files]

        # 1. Sync SQLite documents: deactivate any documents no longer present in directory
        db_manager.sync_active_documents(company_id=company_id, active_filenames=active_filenames)

        # 2. Archive any previous in-memory chunks that are being reset
        for c in self.company_chunks[company_id]:
            c.is_active = False
            self.company_archived_chunks[company_id].append(c)

        # 3. Reset active company chunks and raw docs so only present files are active
        self.company_chunks[company_id] = []
        self.company_raw_docs[company_id] = {}

        # 4. Ingest present files
        ingested_docs: List[CompanyDocument] = []
        for file_path in present_files:
            doc = self.ingest_file(file_path=file_path, company_id=company_id)
            ingested_docs.append(doc)

        return ingested_docs

    def update_policy(self, file_path: Path, policy_name: str, company_id: str = "company_x"):
        """
        Simulates human remediation: updates or replaces an existing policy with a remediated version.
        """
        self.ingest_file(
            file_path=file_path,
            company_id=company_id,
            policy_name=policy_name,
        )

    def ingest_updated_policies(
        self,
        updated_directories: Optional[List[Path]] = None,
        company_id: str = "company_x",
    ) -> List[str]:
        """
        Scans for human-remediated policy documents in candidate directories,
        and re-indexes them into the company vector store.
        """
        if updated_directories is None:
            resolved_up_dir = resolve_company_data_directory(company_id, is_updated=True)
            from src.config import DATA_DIR
            cid = company_id.lower()
            candidate_dirs = [resolved_up_dir, DATA_DIR / cid / "updated", DATA_DIR / f"{cid}_v1" / "updated"]
        else:
            candidate_dirs = updated_directories

        updated_policy_names = []
        seen_files = set()

        for u_dir in candidate_dirs:
            dir_path = Path(u_dir)
            if not dir_path.exists():
                continue
            supported_extensions = ["*.md", "*.txt", "*.pdf", "*.docx"]
            cand_files = []
            for ext in supported_extensions:
                cand_files.extend(dir_path.glob(ext))

            for file_path in sorted(set(cand_files)):
                if file_path.name in seen_files:
                    continue
                seen_files.add(file_path.name)

                matched_name, _, _ = resolve_policy_metadata(file_path)
                self.ingest_file(
                    file_path=file_path,
                    company_id=company_id,
                    policy_name=matched_name,
                )
                updated_policy_names.append(matched_name)

        # Ensure active search index is cleanly synchronized with active SQLite documents
        self.rebuild_index_from_active_documents(company_id=company_id)
        return updated_policy_names

    def _resolve_document_file_path(self, file_path_str: str, filename: str, company_id: str) -> Optional[Path]:
        """
        Safely resolves document path on disk by checking exact path, workspace root,
        or company-specific candidate directories.
        """
        from src.config import PROJECT_ROOT, DATA_DIR

        # 1. Direct path check
        p = Path(file_path_str)
        if p.exists() and p.is_file():
            return p

        # 2. Check under PROJECT_ROOT
        p2 = PROJECT_ROOT / file_path_str
        if p2.exists() and p2.is_file():
            return p2

        # 3. Check known directories
        candidates = [
            DATA_DIR / f"{company_id}_v1" / filename,
            DATA_DIR / company_id / filename,
            DATA_DIR / f"{company_id}_v1" / "updated" / filename,
            DATA_DIR / company_id / "updated" / filename,
            DATA_DIR / "updated" / filename,
            DATA_DIR / filename,
        ]
        for c in candidates:
            if c.exists() and c.is_file():
                return c

        # 4. Search recursively in DATA_DIR
        for m in DATA_DIR.rglob(filename):
            if m.is_file():
                return m

        return None

    def rebuild_index_from_active_documents(self, company_id: Optional[str] = None) -> List[PolicyChunk]:
        """
        Rebuilds the vector index from documents WHERE is_active=1 in SQLite,
        strictly filtered by company_id, and purges all stale/superseded chunks.
        """
        cid = (company_id or self.current_company_id).lower()
        active_docs = db_manager.get_active_documents(cid)
        active_doc_ids = {d.doc_id for d in active_docs}

        # Archive any previous in-memory chunks that are no longer active in SQLite
        archived_chunks = self.company_archived_chunks.setdefault(cid, [])
        for c in self.company_chunks.get(cid, []):
            if getattr(c, "document_id", "") not in active_doc_ids:
                c.is_active = False
                archived_chunks.append(c)

        fresh_chunks: List[PolicyChunk] = []
        raw_docs: Dict[str, str] = {}

        for doc in active_docs:
            file_path = self._resolve_document_file_path(doc.file_path, doc.filename, cid)
            if file_path and file_path.exists():
                try:
                    text = extract_text_from_file(file_path)
                    raw_docs[doc.policy_category] = text
                    chunks = chunk_markdown_document(
                        markdown_text=text,
                        document_id=doc.doc_id,
                        policy_name=doc.policy_category,
                        company_id=cid,
                        version=doc.version,
                        is_active=True,
                    )
                    fresh_chunks.extend(chunks)
                except Exception:
                    existing = [
                        c for c in self.company_chunks.get(cid, [])
                        if getattr(c, "document_id", "") == doc.doc_id and getattr(c, "is_active", True)
                    ]
                    fresh_chunks.extend(existing)
            else:
                existing = [
                    c for c in self.company_chunks.get(cid, [])
                    if getattr(c, "document_id", "") == doc.doc_id and getattr(c, "is_active", True)
                ]
                fresh_chunks.extend(existing)

        self.company_chunks[cid] = fresh_chunks
        self.company_raw_docs[cid] = raw_docs

        if fresh_chunks:
            engine = self._get_engine(cid)
            corpus = [c.text for c in fresh_chunks]
            self.company_matrices[cid] = engine.fit_and_embed(corpus)
        else:
            self.company_matrices[cid] = None

        return fresh_chunks

    def _rebuild_index(self, company_id: Optional[str] = None):
        cid = (company_id or self.current_company_id).lower()
        active_docs = db_manager.get_active_documents(cid)
        if active_docs:
            self.rebuild_index_from_active_documents(cid)
            return

        # Fallback if no documents registered in DB yet
        active_chunks = [
            c for c in self.company_chunks.get(cid, [])
            if getattr(c, "is_active", True) and getattr(c, "company_id", cid).lower() == cid
        ]
        self.company_chunks[cid] = active_chunks
        if not active_chunks:
            self.company_matrices[cid] = None
            return

        engine = self._get_engine(cid)
        corpus = [c.text for c in active_chunks]
        self.company_matrices[cid] = engine.fit_and_embed(corpus)

    def search(
        self,
        query: str,
        top_k: int = TOP_K_RETRIEVAL,
        policy_filter: Optional[str] = None,
        company_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Performs semantic similarity retrieval strictly within the specified company's active index.
        Guarantees strict multi-company isolation and version filtering:
        Company Y never sees Company X chunks or inactive/superseded chunks.
        """
        cid = (company_id or self.current_company_id).lower()
        if cid not in self.company_chunks or not self.company_chunks[cid]:
            active_docs = db_manager.get_active_documents(cid)
            if active_docs:
                self.rebuild_index_from_active_documents(cid)

        chunks = self.company_chunks.get(cid, [])
        matrix = self.company_matrices.get(cid, None)

        if not chunks or matrix is None:
            return []

        engine = self._get_engine(cid)
        query_vec = engine.embed_query(query)
        # Cosine similarity because embeddings are L2 normalized
        scores = np.dot(matrix, query_vec)

        # Apply strict metadata filtering:
        # 1. company_id match (case-insensitive)
        # 2. is_active must be True
        # 3. optional policy_filter
        candidate_indices = []
        for idx, chunk in enumerate(chunks):
            if getattr(chunk, "company_id", cid).lower() != cid:
                continue
            if not getattr(chunk, "is_active", True):
                continue
            if policy_filter:
                if policy_filter.lower() in chunk.policy_name.lower():
                    candidate_indices.append(idx)
            else:
                candidate_indices.append(idx)

        if not candidate_indices:
            return []

        candidate_indices.sort(key=lambda idx: scores[idx], reverse=True)
        top_indices = candidate_indices[:top_k]

        results = []
        for idx in top_indices:
            chunk = chunks[idx]
            results.append({
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "company_id": getattr(chunk, "company_id", cid).lower(),
                "version": getattr(chunk, "version", 1),
                "is_active": getattr(chunk, "is_active", True),
                "policy_name": chunk.policy_name,
                "section_title": chunk.section_title,
                "text": chunk.text,
                "token_count": chunk.token_count,
                "similarity_score": round(float(scores[idx]), 4),
            })
        return results

    def get_full_policy_text(
        self, policy_name: Optional[str] = None, company_id: Optional[str] = None
    ) -> str:
        """
        Returns full concatenated document text for comparison / token analysis.
        """
        cid = company_id or self.current_company_id
        raw_docs = self.company_raw_docs.get(cid, {})

        if policy_name:
            for name, text in raw_docs.items():
                if policy_name.lower() in name.lower():
                    return text
            return ""
        return "\n\n---\n\n".join(raw_docs.values())


# Global singleton store instance for easy server lifecycle integration
vector_store = ComplianceVectorStore()
