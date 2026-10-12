"""Settings, read from the environment (and a .env file, via python-dotenv)."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
DB_PATH = os.environ.get("DB_PATH", os.path.join(DATA_DIR, "app.db"))
SAMPLES_DIR = os.path.join(BASE_DIR, "app", "samples")
FRONTEND_DIST = os.environ.get("FRONTEND_DIST", os.path.join(BASE_DIR, "..", "frontend", "dist"))

CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]

ENGINE_WORKERS = _int("ENGINE_WORKERS", max(1, min(4, os.cpu_count() or 1)))
CHECK_TIMEOUT = _int("CHECK_TIMEOUT", 60)

MAX_UPLOAD_BYTES = _int("MAX_UPLOAD_MB", 15) * 1024 * 1024
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_LINES = 40

RATE_READ = _int("RATE_READ_PER_10MIN", 40)
RATE_CHECK = _int("RATE_CHECK_PER_10MIN", 200)
RATE_AUTH = _int("RATE_AUTH_PER_10MIN", 20)
RATE_SHARE = _int("RATE_SHARE_PER_HOUR", 30)

CACHE_TTL = _int("CACHE_TTL_SECONDS", 3600)
CACHE_SIZE = _int("CACHE_SIZE", 64)

SESSION_DAYS = _int("SESSION_DAYS", 30)
AI_HINTS = os.environ.get("AI_HINTS", "1").strip() not in ("0", "false", "no")
