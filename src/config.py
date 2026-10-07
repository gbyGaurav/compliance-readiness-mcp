"""
Configuration settings for Consus Compliance Operations MCP.
"""

import os
from pathlib import Path

# Base Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
COMPANY_X_DATA_DIR = DATA_DIR / "company_x"
COMPANY_X_UPDATED_DIR = DATA_DIR / "company_x" / "updated"
COMPANY_Y_DATA_DIR = (DATA_DIR / "company_y") if (DATA_DIR / "company_y").exists() else (DATA_DIR / "company_y_v1")
COMPANY_Y_UPDATED_DIR = (COMPANY_Y_DATA_DIR / "updated") if (COMPANY_Y_DATA_DIR / "updated").exists() else (DATA_DIR / "company_y" / "updated")
UPDATED_DATA_DIR = DATA_DIR / "updated"
CONSUS_REQ_DATA_DIR = DATA_DIR / "consus_requirements"
REPORTS_DIR = DATA_DIR / "reports"
DB_PATH = DATA_DIR / "consus_compliance.db"
CHROMA_PERSIST_DIR = DATA_DIR / "chroma_db"

# RAG Configuration
# Target: Chunk size ~400-600 tokens, Overlap ~50-100 tokens, Top-K: 3-5
CHUNK_SIZE_TOKENS = int(os.getenv("CHUNK_SIZE_TOKENS", "450"))
CHUNK_OVERLAP_TOKENS = int(os.getenv("CHUNK_OVERLAP_TOKENS", "60"))
TOP_K_RETRIEVAL = int(os.getenv("TOP_K_RETRIEVAL", "4"))

# LLM Configuration
# Options: 'ollama', 'fallback'
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "fallback").lower()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
