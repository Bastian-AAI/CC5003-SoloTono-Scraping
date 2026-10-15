"""Configuration settings for SoloTono."""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env from project root or scraper directory
root_env = BASE_DIR.parent / ".env"
scraper_env = BASE_DIR / ".env"
if root_env.exists():
    load_dotenv(root_env)
elif scraper_env.exists():
    load_dotenv(scraper_env)

# Database configuration: defaults to local PostgreSQL container, fallback to SQLite if needed
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/solotono")

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
MATCH_FUZZY_THRESHOLD = float(os.getenv("MATCH_FUZZY_THRESHOLD", "0.90"))
MATCH_PENDING_THRESHOLD = float(os.getenv("MATCH_PENDING_THRESHOLD", "0.60"))
AUTO_CREATE_CANONICAL = os.getenv("AUTO_CREATE_CANONICAL", "true").lower() in ("true", "1", "yes")

