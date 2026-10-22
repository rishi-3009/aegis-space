"""Vercel entry point. Vercel's FastAPI support routes every request to the app in this file."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.main import app  # noqa: E402,F401
