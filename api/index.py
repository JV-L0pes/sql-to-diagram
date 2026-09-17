"""Vercel Python Function entrypoint.

Vercel's Python runtime auto-detects functions only under a top-level
`api/` directory (relative to the project's Root Directory). Our FastAPI
app actually lives at `apps/api/src/main.py` (see Task 7's DDD-style
monorepo layout), so this thin adapter puts `apps/api` on `sys.path` and
re-exports the real ASGI `app` object from there, without moving or
duplicating any application code.
"""

import sys
from pathlib import Path

_APPS_API_DIR = Path(__file__).resolve().parent.parent / "apps" / "api"
if str(_APPS_API_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_API_DIR))

from src.main import app  # noqa: E402
