"""
Test proving Company Y RAG index rebuild mechanism from SQLite WHERE is_active=1
strictly retains only the 5 active v1 documents and purges all stale/superseded chunks.
"""

import pytest
from src.database.db import db_manager
from src.rag.vector_store import vector_store


def test_company_y_rebuild_returns_only_active_v1_documents():
    """
    Validates that:
    1. SQLite documents table has exactly 5 active documents for Company Y.
    2. rebuild_index_from_active_documents('company_y') purges any stale chunks
       and rebuilds the index strictly from the 5 active v1 documents.
    3. Any retrieval query against Company Y returns ONLY chunks from the 5 active v1 documents.
    """
    company_id = "company_y"

    # 1. Verify SQLite active documents state
    active_docs = db_manager.get_active_documents(company_id)
    assert len(active_docs) == 5, f"Expected 5 active documents, found {len(active_docs)}"

    expected_doc_ids = {
        "company_y-01_data_handling_policy",
        "company_y-02_encryption_policy",
        "company_y-03_access_control_policy",
        "company_y-04_incident_response_policy",
        "company_y-05_audit_logging_policy",
    }
    actual_doc_ids = {d.doc_id for d in active_docs}
    assert actual_doc_ids == expected_doc_ids, f"Active doc_ids mismatch: {actual_doc_ids} vs {expected_doc_ids}"

    # Confirm all 5 active documents in DB are version 1
    for d in active_docs:
        assert d.version == 1
        assert d.is_active is True

    # 2. Rebuild the index from active documents
    rebuilt_chunks = vector_store.rebuild_index_from_active_documents(company_id)
    assert len(rebuilt_chunks) == 5, f"Expected 5 active chunks for 5 documents, got {len(rebuilt_chunks)}"

    # Confirm in-memory active chunks belong strictly to the 5 active documents
    in_memory_chunks = vector_store.company_chunks.get(company_id, [])
    assert len(in_memory_chunks) == 5
    for chunk in in_memory_chunks:
        assert chunk.company_id == company_id
        assert chunk.is_active is True
        assert chunk.version == 1
        assert chunk.document_id in expected_doc_ids
        assert not chunk.document_id.endswith("_v2")
        assert not chunk.document_id.endswith("-v2")

    # 3. Test multiple retrieval queries (broad and specific)
    test_queries = [
        "access control role-based least privilege MFA",
        "audit logging 365 days retention WORM immutable",
        "US sovereign data boundary FedRAMP GovCloud",
        "encryption AES-256 TLS KMS key rotation",
        "incident response containment notification SLA",
        "security policies and compliance",
        "CUI handling sanitization NIST",
        "vulnerability management container scanning",
    ]

    for query in test_queries:
        results = vector_store.search(query=query, top_k=5, company_id=company_id)
        assert len(results) > 0, f"Expected retrieval results for query '{query}'"

        for r in results:
            # Must strictly belong to company_y
            assert r["company_id"] == company_id
            # Must strictly be active and version 1
            assert r["is_active"] is True
            assert r["version"] == 1
            # Must strictly come from one of the 5 active baseline documents
            assert r["document_id"] in expected_doc_ids
            # Stale/superseded documents must NEVER appear
            assert "v2" not in r["document_id"]
            assert "cui_handling" not in r["document_id"]
            assert "vulnerability_management" not in r["document_id"]
            assert "company_x" not in r["document_id"]
