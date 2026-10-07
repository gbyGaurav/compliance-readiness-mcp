"""
Unit tests for multi-format document text extraction, chunking, and versioned ingestion.
"""

import pytest
from pathlib import Path

from src.config import COMPANY_Y_DATA_DIR, COMPANY_Y_UPDATED_DIR
from src.rag.extractor import extract_text_from_file
from src.rag.vector_store import ComplianceVectorStore, resolve_policy_metadata
from src.database.db import db_manager


def test_multi_format_text_extraction():
    # 1. PDF extraction
    pdf_path = COMPANY_Y_DATA_DIR / "03_access_control_policy.pdf"
    assert pdf_path.exists(), "PDF file must exist"
    pdf_text = extract_text_from_file(pdf_path)
    assert len(pdf_text) > 50
    assert "Access Control" in pdf_text or "multi-factor" in pdf_text

    # 2. DOCX extraction
    docx_path = COMPANY_Y_DATA_DIR / "02_encryption_policy.docx"
    assert docx_path.exists(), "DOCX file must exist"
    docx_text = extract_text_from_file(docx_path)
    assert len(docx_text) > 50
    assert "Encryption" in docx_text or "AES-256" in docx_text

    # 3. TXT extraction
    txt_path = COMPANY_Y_DATA_DIR / "01_data_handling_policy.txt"
    assert txt_path.exists(), "TXT file must exist"
    txt_text = extract_text_from_file(txt_path)
    assert "Data Handling" in txt_text
    assert "global regions" in txt_text

    # 4. MD extraction
    md_path = COMPANY_Y_DATA_DIR / "04_incident_response_policy.md"
    assert md_path.exists(), "MD file must exist"
    md_text = extract_text_from_file(md_path)
    assert "Incident Response" in md_text
    assert "48 hours" in md_text


def test_metadata_resolution():
    pol_name, ver, doc_type = resolve_policy_metadata(Path("data_boundary_policy_v2.pdf"))
    assert pol_name == "Data Handling Policy"
    assert ver == 2
    assert doc_type == "pdf"

    pol_name, ver, doc_type = resolve_policy_metadata(Path("access_control_policy.docx"))
    assert pol_name == "Access Control Policy"
    assert ver == 1
    assert doc_type == "docx"


def test_vector_store_multi_format_ingestion_and_versioning():
    store = ComplianceVectorStore()
    company_id = "test_ingestion_co"

    # Ingest baseline v1 TXT
    txt_v1 = COMPANY_Y_DATA_DIR / "01_data_handling_policy.txt"
    doc1 = store.ingest_file(txt_v1, company_id=company_id)
    assert doc1.document_type == "txt"
    assert doc1.version == 1
    assert len(store.company_chunks[company_id]) > 0

    # Search v1 returns commercial / multi-region text
    res_v1 = store.search("cloud hosting global regions", company_id=company_id, top_k=2)
    assert len(res_v1) > 0
    assert any("global" in r["text"].lower() or "regions" in r["text"].lower() for r in res_v1)

    # Ingest remediated v2 PDF
    pdf_v2 = COMPANY_Y_UPDATED_DIR / "data_boundary_policy_v2.pdf"
    doc2 = store.ingest_file(pdf_v2, company_id=company_id)
    assert doc2.version == 2
    assert doc2.document_type == "pdf"

    # Search now returns GovCloud / CONUS text
    res_v2 = store.search("govcloud fedramp conus", company_id=company_id, top_k=2)
    assert len(res_v2) > 0
    assert any("govcloud" in r["text"].lower() or "conus" in r["text"].lower() for r in res_v2)
