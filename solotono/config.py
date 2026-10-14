"""Configuration settings for SoloTono."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Database configuration: defaults to local SQLite, easily switchable to PostgreSQL via env var
# e.g. postgresql://user:password@localhost:5432/solotono
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/solotono.db")

# Scraping settings
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "15"))
HTTP_RETRIES = int(os.getenv("HTTP_RETRIES", "3"))
HTTP_PROXY = os.getenv("HTTP_PROXY", None)
HTTPS_PROXY = os.getenv("HTTPS_PROXY", None)

USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
)

# Product Matching thresholds
MATCH_EXACT_BOOST = 1.0
MATCH_FUZZY_THRESHOLD = float(os.getenv("MATCH_FUZZY_THRESHOLD", "0.85"))
MATCH_PENDING_THRESHOLD = float(os.getenv("MATCH_PENDING_THRESHOLD", "0.60"))
