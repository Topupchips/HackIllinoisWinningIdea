"""
API configuration - customize via environment variables.
Enables extensibility without code changes.
"""
import os

# Auth (optional): set API_KEY to require X-API-Key header
API_KEY = os.environ.get("API_KEY", "")

# Rate limiting: max requests per window per client
RATE_LIMIT_REQUESTS = int(os.environ.get("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW_SEC = int(os.environ.get("RATE_LIMIT_WINDOW_SEC", "60"))

# CORS: comma-separated origins, or "*" for all
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",") if os.environ.get("CORS_ORIGINS") else ["*"]

# PubChem timeout
PUBCHEM_TIMEOUT = int(os.environ.get("PUBCHEM_TIMEOUT", "15"))
