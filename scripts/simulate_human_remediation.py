"""
Simulates human remediation by updating Company X policy documents with v2 versions.
This represents an authorized human security officer from Company X reviewing findings
and publishing updated policy controls.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import COMPANY_X_UPDATED_DIR
from src.rag.vector_store import vector_store


def apply_human_remediation(policy_target: str = "all"):
    """
    Updates the vector store with human-authored v2 policies from data/updated and data/company_x/updated.
    """
    updated_policies = vector_store.ingest_updated_policies(company_id="company_x")
    for pol_name in updated_policies:
        print(f"[Human Remediation] Ingested and indexed updated policy: '{pol_name}'")
    return updated_policies


if __name__ == "__main__":
    apply_human_remediation("all")
    print("All human policy remediations successfully applied to vector store.")
