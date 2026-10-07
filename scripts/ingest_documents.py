"""
CLI script to ingest and index Company X policy documents into the RAG vector store.
Supports baseline policy ingestion and optional updated policy ingestion.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import COMPANY_X_DATA_DIR
from src.rag.vector_store import vector_store


if __name__ == "__main__":
    include_updated = "--updated" in sys.argv or "--all" in sys.argv
    print(f"Ingesting baseline policy documents from {COMPANY_X_DATA_DIR}...")
    vector_store.ingest_directory(COMPANY_X_DATA_DIR, company_id="company_x")
    print(f"Indexed {len(vector_store.chunks)} baseline chunks across {len(vector_store.raw_documents)} policies.")

    if include_updated:
        print("Ingesting human-remediated policy documents...")
        updated = vector_store.ingest_updated_policies(company_id="company_x")
        print(f"Re-indexed updated policies: {updated}")
        print(f"Total chunks in vector store: {len(vector_store.chunks)}")
