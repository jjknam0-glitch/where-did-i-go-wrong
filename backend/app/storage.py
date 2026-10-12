"""SQLite storage: optional accounts, synced profiles, share links, opt-in corrections.

Photos are never stored on the server. Accounts are optional (13+) and only
hold what the features need: an email, a password hash, the plan, and the
student's mistake profile/history (without photos).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time

from . import config

_init_lock = threading.Lock()
_initialized = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    pw_hash BLOB NOT NULL,
    salt BLOB NOT NULL,
    plan TEXT NOT NULL DEFAULT 'free',
    corrections_opt_in INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS user_data (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS shares (
    id TEXT PRIMARY KEY,
    secret_hash TEXT NOT NULL,
    snapshot TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original TEXT NOT NULL,
    corrected TEXT NOT NULL,
    line_type TEXT,
    created_at REAL NOT NULL
);
"""


class StorageError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _connect() -> sqlite3.Connection:
    global _initialized
    if not _initialized:
        with _init_lock:
            if not _initialized:
                os.makedirs(os.path.dirname(os.path.abspath(config.DB_PATH)), exist_ok=True)
                conn = sqlite3.connect(config.DB_PATH)
                conn.executescript(SCHEMA)
                conn.execute("PRAGMA journal_mode=WAL")
                conn.commit()
                conn.close()
                _initialized = True
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def reset_for_tests():
    global _initialized
    _initialized = False


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[A-Za-z]{2,}$")


def contains_image_data(obj, depth=0) -> bool:
    """True if any string looks like embedded image data (photos never leave the device)."""
    if depth > 30:
        return True
    if isinstance(obj, str):
        return obj.startswith("data:image") or len(obj) > 20_000
    if isinstance(obj, dict):
        return any(contains_image_data(v, depth + 1) for v in obj.values())
    if isinstance(obj, list):
        return any(contains_image_data(v, depth + 1) for v in obj)
    return False


def _dump(obj, limit: int) -> str:
    try:
        s = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError):
        raise StorageError("Invalid data")
    if len(s.encode()) > limit:
        raise StorageError("Data is too large", 413)
    if contains_image_data(obj):
        raise StorageError("Photos can't be uploaded here")
    return s


# --------------------------------------------------------------------------
# accounts
# --------------------------------------------------------------------------

def _hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)


def create_user(email: str, password: str, corrections_opt_in: bool = False) -> int:
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise StorageError("Enter a valid email address")
    if not password or len(password) < 8:
        raise StorageError("Use a password with at least 8 characters")
    if len(password) > 200:
        raise StorageError("Password is too long")
    salt = secrets.token_bytes(16)
    pw = _hash_password(password, salt)
    with _connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO users (email, pw_hash, salt, corrections_opt_in, created_at) VALUES (?,?,?,?,?)",
                (email, pw, salt, int(bool(corrections_opt_in)), time.time()))
        except sqlite3.IntegrityError:
            raise StorageError("An account with that email already exists", 409)
        return int(cur.lastrowid)


def verify_user(email: str, password: str) -> int:
    email = (email or "").strip().lower()
    with _connect() as conn:
        row = conn.execute("SELECT id, pw_hash, salt FROM users WHERE email = ?", (email,)).fetchone()
    if row is None:
        # Spend the same time as a real check so emails can't be probed by timing.
        _hash_password(password or "", b"0" * 16)
        raise StorageError("Wrong email or password", 401)
    if not hmac.compare_digest(_hash_password(password or "", row["salt"]), row["pw_hash"]):
        raise StorageError("Wrong email or password", 401)
    return int(row["id"])


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (time.time(),))
        conn.execute("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?,?,?)",
                     (_sha(token), user_id, time.time() + config.SESSION_DAYS * 86400))
    return token


def user_for_token(token: str | None) -> dict | None:
    if not token:
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT u.id, u.email, u.plan, u.corrections_opt_in, u.created_at FROM sessions s "
            "JOIN users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.expires_at > ?",
            (_sha(token), time.time())).fetchone()
    if row is None:
        return None
    return {"id": row["id"], "email": row["email"], "plan": row["plan"],
            "corrections_opt_in": bool(row["corrections_opt_in"]), "created_at": row["created_at"]}


def delete_session(token: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_sha(token),))


def delete_user(user_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM user_data WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def update_user(user_id: int, plan: str | None = None, corrections_opt_in: bool | None = None) -> None:
    with _connect() as conn:
        if plan is not None:
            if plan not in ("free", "plus", "family"):
                raise StorageError("Unknown plan")
            conn.execute("UPDATE users SET plan = ? WHERE id = ?", (plan, user_id))
        if corrections_opt_in is not None:
            conn.execute("UPDATE users SET corrections_opt_in = ? WHERE id = ?",
                         (int(bool(corrections_opt_in)), user_id))


def get_user_data(user_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT data, updated_at FROM user_data WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        return None
    return {"data": json.loads(row["data"]), "updated_at": row["updated_at"]}


def put_user_data(user_id: int, data: dict) -> float:
    s = _dump(data, config.MAX_JSON_BYTES)
    now = time.time()
    with _connect() as conn:
        conn.execute("INSERT INTO user_data (user_id, data, updated_at) VALUES (?,?,?) "
                     "ON CONFLICT(user_id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
                     (user_id, s, now))
    return now


# --------------------------------------------------------------------------
# parent / tutor share links
# --------------------------------------------------------------------------

SHARE_LIMIT = 200_000


def create_share(snapshot: dict) -> tuple[str, str]:
    s = _dump(snapshot, SHARE_LIMIT)
    share_id = secrets.token_urlsafe(9)
    secret = secrets.token_urlsafe(24)
    now = time.time()
    with _connect() as conn:
        conn.execute("INSERT INTO shares (id, secret_hash, snapshot, created_at, updated_at) VALUES (?,?,?,?,?)",
                     (share_id, _sha(secret), s, now, now))
    return share_id, secret


def get_share(share_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT snapshot, updated_at FROM shares WHERE id = ?", (share_id,)).fetchone()
    if row is None:
        return None
    return {"snapshot": json.loads(row["snapshot"]), "updated_at": row["updated_at"]}


def _check_secret(conn, share_id: str, secret: str) -> None:
    row = conn.execute("SELECT secret_hash FROM shares WHERE id = ?", (share_id,)).fetchone()
    if row is None:
        raise StorageError("This share link doesn't exist", 404)
    if not secret or not hmac.compare_digest(row["secret_hash"], _sha(secret)):
        raise StorageError("Not allowed", 403)


def update_share(share_id: str, secret: str, snapshot: dict) -> None:
    s = _dump(snapshot, SHARE_LIMIT)
    with _connect() as conn:
        _check_secret(conn, share_id, secret)
        conn.execute("UPDATE shares SET snapshot = ?, updated_at = ? WHERE id = ?", (s, time.time(), share_id))


def delete_share(share_id: str, secret: str) -> None:
    with _connect() as conn:
        _check_secret(conn, share_id, secret)
        conn.execute("DELETE FROM shares WHERE id = ?", (share_id,))


# --------------------------------------------------------------------------
# opt-in transcription corrections
# --------------------------------------------------------------------------

def add_correction(original: str, corrected: str, line_type: str | None) -> None:
    original, corrected = (original or "")[:300], (corrected or "")[:300]
    if not corrected or original == corrected:
        return
    with _connect() as conn:
        conn.execute("INSERT INTO corrections (original, corrected, line_type, created_at) VALUES (?,?,?,?)",
                     (original, corrected, (line_type or "")[:20], time.time()))
