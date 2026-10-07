"""
CLI script to seed representative Consus requirements into SQLite.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.seed import seed_requirements


if __name__ == "__main__":
    seed_requirements()
