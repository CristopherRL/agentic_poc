"""
Vercel serverless function entry point for FastAPI application.
"""
import sys
from pathlib import Path

# Add backend directory to Python path (we're already in backend, so use current dir)
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from src.app.main import app

# Export the ASGI application for Vercel
# Vercel expects a handler named 'app' or 'handler'
handler = app

