"""SQLite store for ANGC tasks and dashboard users.

Synchronous sqlite3 (call via asyncio.to_thread from async webhook code;
FastAPI sync endpoints run in a threadpool). One connection per call keeps
things simple and thread-safe; WAL mode keeps concurrent reads cheap.
"""

import hashlib
import hmac
import logging
import secrets
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

from ai_companion.modules.angc.team import EMPLOYEES
from ai_companion.settings import settings

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

TASK_STATUSES = ("pending", "in_progress", "done")


def _db_path() -> str:
    return settings.ANGC_DB_PATH


def _connect() -> sqlite3.Connection:
    path = _db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        # WAL is unreliable on network mounts (Azure Files/SMB); fall back to
        # the default journal there — single replica, so plain locking is fine.
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        pass
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_ist_label(utc_iso: str | None) -> str:
    """'2026-07-11T09:30:00Z' -> '11 Jul 2026, 03:00 PM' (IST) for display."""
    if not utc_iso:
        return ""
    try:
        dt = datetime.strptime(utc_iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return dt.astimezone(IST).strftime("%d %b %Y, %I:%M %p")
    except ValueError:
        return utc_iso


# ---------------------------------------------------------------------------
# Passwords (stdlib pbkdf2 — no extra deps)
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000)
    return f"pbkdf2:200000:{salt}:{digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, expected = stored.split(":")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(digest.hex(), expected)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Schema + seed
# ---------------------------------------------------------------------------

def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                phone TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT 'staff',
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assignee_id INTEGER NOT NULL REFERENCES users(id),
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                assigned_by TEXT NOT NULL DEFAULT 'NG Sir',
                due_date TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee_id, status);
            """
        )
        _seed_users(conn)


def _seed_users(conn: sqlite3.Connection) -> None:
    """Create the three assistants + admin on first run. Default passwords come
    from ANGC_DEFAULT_PASSWORD (change them via the dashboard after first login)."""
    existing = {r["email"] for r in conn.execute("SELECT email FROM users")}
    default_pw = settings.ANGC_DEFAULT_PASSWORD
    now = _utcnow()

    for key, emp in EMPLOYEES.items():
        if emp["email"] not in existing:
            conn.execute(
                "INSERT INTO users (name, full_name, email, phone, role, password_hash, created_at)"
                " VALUES (?, ?, ?, ?, 'staff', ?, ?)",
                (key, emp["full_name"], emp["email"], emp["phone"], hash_password(default_pw), now),
            )
            logger.info("[angc.db] seeded staff user %s <%s>", key, emp["email"])

    admin_email = settings.ANGC_ADMIN_EMAIL
    if admin_email not in existing:
        conn.execute(
            "INSERT INTO users (name, full_name, email, phone, role, password_hash, created_at)"
            " VALUES ('NG Sir', 'Nikhil Gupta', ?, '', 'admin', ?, ?)",
            (admin_email, hash_password(default_pw), now),
        )
        logger.info("[angc.db] seeded admin user Nikhil Gupta <%s>", admin_email)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def get_user_by_email(email: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE lower(email)=lower(?)", (email.strip(),)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_user_by_name(name: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE name=?", (name,)).fetchone()
        return dict(row) if row else None


def list_staff() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM users WHERE role='staff' ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def set_password(user_id: int, new_password: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(new_password), user_id))


def check_login(email: str, password: str) -> dict | None:
    user = get_user_by_email(email)
    if user and verify_password(password, user["password_hash"]):
        return user
    return None


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def create_task(
    assignee_name: str,
    category: str,
    title: str,
    message: str,
    assigned_by: str = "NG Sir",
    due_date: str | None = None,
) -> dict:
    assignee = get_user_by_name(assignee_name)
    if not assignee:
        raise ValueError(f"Unknown assignee: {assignee_name}")
    now = _utcnow()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (assignee_id, category, title, message, status, assigned_by, due_date, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?)",
            (assignee["id"], category, title, message, assigned_by, due_date, now, now),
        )
        task_id = cur.lastrowid
    task = get_task(task_id)
    assert task is not None
    return task


def get_task(task_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT t.*, u.name AS assignee_name, u.full_name AS assignee_full_name, u.phone AS assignee_phone"
            " FROM tasks t JOIN users u ON u.id = t.assignee_id WHERE t.id=?",
            (task_id,),
        ).fetchone()
        return dict(row) if row else None


def list_tasks(
    assignee_id: int | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[dict]:
    query = (
        "SELECT t.*, u.name AS assignee_name, u.full_name AS assignee_full_name"
        " FROM tasks t JOIN users u ON u.id = t.assignee_id WHERE 1=1"
    )
    params: list = []
    if assignee_id is not None:
        query += " AND t.assignee_id=?"
        params.append(assignee_id)
    if status:
        query += " AND t.status=?"
        params.append(status)
    query += " ORDER BY t.id DESC LIMIT ?"
    params.append(limit)
    with _connect() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def update_task_status(task_id: int, status: str) -> dict | None:
    if status not in TASK_STATUSES:
        raise ValueError(f"Invalid status: {status}")
    now = _utcnow()
    completed_at = now if status == "done" else None
    with _connect() as conn:
        conn.execute(
            "UPDATE tasks SET status=?, updated_at=?, completed_at=? WHERE id=?",
            (status, now, completed_at, task_id),
        )
    return get_task(task_id)


def summary_stats() -> dict:
    """Per-employee and overall counts for the admin dashboard / director queries."""
    today_utc_start = (
        datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
        .astimezone(timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    with _connect() as conn:
        per_employee = []
        for staff in conn.execute("SELECT * FROM users WHERE role='staff' ORDER BY id").fetchall():
            counts = {s: 0 for s in TASK_STATUSES}
            for row in conn.execute(
                "SELECT status, COUNT(*) AS n FROM tasks WHERE assignee_id=? GROUP BY status", (staff["id"],)
            ):
                counts[row["status"]] = row["n"]
            done_today = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE assignee_id=? AND status='done' AND completed_at>=?",
                (staff["id"], today_utc_start),
            ).fetchone()[0]
            new_today = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE assignee_id=? AND created_at>=?",
                (staff["id"], today_utc_start),
            ).fetchone()[0]
            per_employee.append(
                {
                    "id": staff["id"],
                    "name": staff["name"],
                    "full_name": staff["full_name"],
                    "pending": counts["pending"],
                    "in_progress": counts["in_progress"],
                    "done": counts["done"],
                    "done_today": done_today,
                    "new_today": new_today,
                    "total": sum(counts.values()),
                }
            )
        totals = {s: 0 for s in TASK_STATUSES}
        for row in conn.execute("SELECT status, COUNT(*) AS n FROM tasks GROUP BY status"):
            totals[row["status"]] = row["n"]
        return {"per_employee": per_employee, "totals": totals}
