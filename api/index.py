"""Vercel serverless entry point for MasterSales FastAPI app."""
import os
import sys

# Vercel runs from the project root, but we need to make sure
# all our module imports resolve correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# On Vercel, use /tmp for SQLite since the filesystem is read-only elsewhere
if os.environ.get("VERCEL"):
    os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/mastersales.db")

from app import app  # noqa: E402, F401
