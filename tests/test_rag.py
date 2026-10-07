"""
Unit tests for RAG ingestion, vector retrieval, and token counting.
"""

import pytest
from pathlib import Path

from src.config import COMPANY_X_DATA_DIR
from src.rag.chunker import chunk_markdown_document
from src.rag.vector_store import ComplianceVectorStore
from src.rag.token_counter import count_tokens, calculate_token_comparison


def test_chunk_markdown_document():
    sample_md = """# Sample Security Policy
## 1. Authentication
All users must provide multi-factor authentication credentials.
## 2. Encryption
All disks must use AES-256 bit encryption.
"""
    chunks = chunk_markdown_document(
        markdown_text=sample_md,
        document_id="test-doc",
        policy_name="Sample Policy",
        target_tokens=100,
        overlap_tokens=10,
    )
    assert len(chunks) >= 2
    assert chunks[0].policy_name == "Sample Policy"
    assert chunks[0].token_count > 0


def test_token_counter_and_savings():
    full_doc = "This is a detailed corporate security policy with extensive descriptions. " * 30
    chunk = "This is a detailed corporate security policy snippet."
    comp = calculate_token_comparison(full_doc, chunk)

    assert comp["full_document_tokens"] > comp["retrieved_chunks_tokens"]
    assert comp["tokens_saved"] > 0
    assert comp["reduction_percentage"] > 50.0


def test_vector_store_ingestion_and_search():
    store = ComplianceVectorStore()
    store.ingest_directory(COMPANY_X_DATA_DIR, company_id="test_co")

    assert len(store.chunks) > 10
    results = store.search("encryption aes-256 tls", top_k=3)
    assert len(results) == 3
    # Top result should be from Encryption Policy
    assert any("encryption" in r["policy_name"].lower() for r in results)
