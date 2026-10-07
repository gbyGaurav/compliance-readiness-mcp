"""
Tests for exact token count measurement and context window savings.
"""

from src.rag.vector_store import ComplianceVectorStore
from src.rag.token_counter import count_tokens, calculate_token_comparison
from src.config import COMPANY_X_DATA_DIR


def test_token_savings_measurement_on_actual_data():
    store = ComplianceVectorStore()
    store.ingest_directory(COMPANY_X_DATA_DIR, company_id="company_x")

    full_repo_text = store.get_full_policy_text()
    retrieved_chunks = store.search("US-Only sovereign boundary GovCloud data isolation", top_k=3)
    retrieved_text = "\n\n".join(c["text"] for c in retrieved_chunks)

    metrics = calculate_token_comparison(full_repo_text, retrieved_text)

    # Validate that tokens are non-zero, measured accurately, and show significant reduction
    assert metrics["full_document_tokens"] > 3000
    assert metrics["retrieved_chunks_tokens"] < metrics["full_document_tokens"]
    assert metrics["tokens_saved"] > 2500
    assert metrics["reduction_percentage"] > 75.0
    print(f"\nToken Savings: {metrics['reduction_percentage']}% reduction ({metrics['tokens_saved']} tokens saved)")
