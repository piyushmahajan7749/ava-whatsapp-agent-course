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

TASK_STATUSES = ("pending", "in_progress", "in_review", "done")
TASK_PRIORITIES = ("normal", "urgent")


def _db_path() -> str:
    return settings.ANGC_DB_PATH


def _connect() -> sqlite3.Connection:
    path = _db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    if settings.ANGC_SQLITE_WAL:
        try:
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

_PW_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_password(length: int = 10) -> str:
    """Random password (unambiguous alphabet, no lookalike chars)."""
    return "".join(secrets.choice(_PW_ALPHABET) for _ in range(length))


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
            CREATE TABLE IF NOT EXISTS task_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                author_id INTEGER NOT NULL REFERENCES users(id),
                body TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_notes_task ON task_notes(task_id);
            CREATE TABLE IF NOT EXISTS job_runs (
                run_key TEXT PRIMARY KEY,
                ran_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS recurring_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assignee_id INTEGER NOT NULL REFERENCES users(id),
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'normal',
                recurrence TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_by TEXT NOT NULL DEFAULT 'NG Sir',
                last_run_date TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        _migrate_calendar_token(conn)
        _migrate_task_priority(conn)
        _seed_users(conn)


def _migrate_calendar_token(conn: sqlite3.Connection) -> None:
    """Add users.calendar_token if missing (older DBs created before the
    calendar-feed feature). CREATE TABLE IF NOT EXISTS above won't add columns
    to an already-existing table, so this runs an explicit ALTER once."""
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    if "calendar_token" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN calendar_token TEXT")
        logger.info("[angc.db] migrated: added users.calendar_token")


def _migrate_task_priority(conn: sqlite3.Connection) -> None:
    """Add tasks.priority ('normal'|'urgent') for DBs predating priorities."""
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
    if "priority" not in cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN priority TEXT NOT NULL DEFAULT 'normal'")
        logger.info("[angc.db] migrated: added tasks.priority")


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
        rows = conn.execute("SELECT * FROM users WHERE role != 'admin' ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def create_user(name: str, full_name: str, email: str, phone: str, password: str, role: str = "employee") -> dict:
    """Create a dashboard user (admin adds employees). Phone is normalized digits."""
    digits = "".join(c for c in (phone or "") if c.isdigit())
    if len(digits) == 10:
        digits = "91" + digits
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO users (name, full_name, email, phone, role, password_hash, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name.strip(), full_name.strip() or name.strip(), email.strip().lower(), digits,
             role, hash_password(password), _utcnow()),
        )
        user_id = cur.lastrowid
    user = get_user_by_id(user_id)
    assert user is not None
    return user


def set_password(user_id: int, new_password: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(new_password), user_id))


def check_login(email: str, password: str) -> dict | None:
    user = get_user_by_email(email)
    if user and verify_password(password, user["password_hash"]):
        return user
    return None


# ---------------------------------------------------------------------------
# Calendar feed tokens
# ---------------------------------------------------------------------------

def get_or_create_calendar_token(user_id: int) -> str:
    """Lazily assign a private token for this user's .ics feed URL."""
    user = get_user_by_id(user_id)
    if user and user.get("calendar_token"):
        return user["calendar_token"]
    token = secrets.token_urlsafe(24)
    with _connect() as conn:
        conn.execute("UPDATE users SET calendar_token=? WHERE id=?", (token, user_id))
    return token


def regenerate_calendar_token(user_id: int) -> str:
    """Invalidate the old feed URL (e.g. if it leaked) and issue a new one."""
    token = secrets.token_urlsafe(24)
    with _connect() as conn:
        conn.execute("UPDATE users SET calendar_token=? WHERE id=?", (token, user_id))
    return token


def get_user_by_calendar_token(token: str) -> dict | None:
    if not token:
        return None
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE calendar_token=?", (token,)).fetchone()
        return dict(row) if row else None


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
    priority: str = "normal",
) -> dict:
    assignee = get_user_by_name(assignee_name)
    if not assignee:
        raise ValueError(f"Unknown assignee: {assignee_name}")
    if priority not in TASK_PRIORITIES:
        priority = "normal"
    now = _utcnow()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (assignee_id, category, title, message, status, assigned_by, due_date, priority, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)",
            (assignee["id"], category, title, message, assigned_by, due_date, priority, now, now),
        )
        task_id = cur.lastrowid
    task = get_task(task_id)
    assert task is not None
    return task


_NOTE_COUNT_SQL = "(SELECT COUNT(*) FROM task_notes n WHERE n.task_id = t.id) AS note_count"


def get_task(task_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            f"SELECT t.*, u.name AS assignee_name, u.full_name AS assignee_full_name, u.phone AS assignee_phone,"
            f" {_NOTE_COUNT_SQL}"
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
        f"SELECT t.*, u.name AS assignee_name, u.full_name AS assignee_full_name, {_NOTE_COUNT_SQL}"
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


_EDITABLE_FIELDS = {"title", "message", "category", "assignee_id", "due_date", "priority"}


def update_task_fields(task_id: int, **fields) -> dict | None:
    """Update task fields (title/message/category/assignee_id/due_date/priority)."""
    updates = {k: v for k, v in fields.items() if k in _EDITABLE_FIELDS}
    if "priority" in updates and updates["priority"] not in TASK_PRIORITIES:
        del updates["priority"]
    if not updates:
        return get_task(task_id)
    updates["updated_at"] = _utcnow()
    set_clause = ", ".join(f"{k}=?" for k in updates)
    with _connect() as conn:
        conn.execute(f"UPDATE tasks SET {set_clause} WHERE id=?", (*updates.values(), task_id))
    return get_task(task_id)


def delete_task(task_id: int) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        return cur.rowcount > 0


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


def add_note(task_id: int, author_id: int, body: str) -> dict:
    now = _utcnow()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO task_notes (task_id, author_id, body, created_at) VALUES (?, ?, ?, ?)",
            (task_id, author_id, body.strip(), now),
        )
        note_id = cur.lastrowid
        conn.execute("UPDATE tasks SET updated_at=? WHERE id=?", (now, task_id))
    with _connect() as conn:
        row = conn.execute(
            "SELECT n.*, u.name AS author_name FROM task_notes n"
            " JOIN users u ON u.id = n.author_id WHERE n.id=?",
            (note_id,),
        ).fetchone()
        return dict(row)


def list_notes(task_id: int) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT n.*, u.name AS author_name FROM task_notes n"
            " JOIN users u ON u.id = n.author_id WHERE n.task_id=? ORDER BY n.id ASC",
            (task_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_note(note_id: int) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM task_notes WHERE id=?", (note_id,))
        return cur.rowcount > 0


def summary_stats() -> dict:
    """Per-employee and overall counts for the admin dashboard / director queries."""
    today_utc_start = (
        datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
        .astimezone(timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    with _connect() as conn:
        per_employee = []
        for staff in conn.execute("SELECT * FROM users WHERE role != 'admin' ORDER BY id").fetchall():
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
                    "in_review": counts["in_review"],
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


# ---------------------------------------------------------------------------
# Scheduler support — idempotent job ledger + recurring tasks
# ---------------------------------------------------------------------------

def claim_job(run_key: str) -> bool:
    """Atomically claim a job run. Returns True the first time a run_key is
    seen, False on any repeat — so a scheduled job fires exactly once even if
    the loop wakes twice, the app restarts, or two replicas race."""
    try:
        with _connect() as conn:
            conn.execute("INSERT INTO job_runs (run_key, ran_at) VALUES (?, ?)", (run_key, _utcnow()))
        return True
    except sqlite3.IntegrityError:
        return False


def tasks_in_date_range(start: str, end: str, assignee_id: int | None = None) -> list[dict]:
    """Tasks with a due_date in [start, end] (inclusive, 'YYYY-MM-DD'), for the
    calendar month view. Scoped to one assignee when given."""
    q = (
        f"SELECT t.*, u.name AS assignee_name, u.full_name AS assignee_full_name, {_NOTE_COUNT_SQL}"
        " FROM tasks t JOIN users u ON u.id = t.assignee_id"
        " WHERE t.due_date IS NOT NULL AND t.due_date != '' AND t.due_date >= ? AND t.due_date <= ?"
    )
    params: list = [start, end]
    if assignee_id is not None:
        q += " AND t.assignee_id = ?"
        params.append(assignee_id)
    q += " ORDER BY t.due_date ASC, t.priority DESC, t.id ASC"
    with _connect() as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def upcoming_tasks(days: int = 14, assignee_id: int | None = None) -> list[dict]:
    """Open tasks due from today through the next `days` days."""
    today = datetime.now(IST).date()
    end = today + timedelta(days=days)
    rows = tasks_in_date_range(today.isoformat(), end.isoformat(), assignee_id)
    return [r for r in rows if r["status"] != "done"]


def open_tasks_with_due() -> list[dict]:
    """All not-done tasks that have a due date (for reminder/escalation sweeps)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT t.*, u.name AS assignee_name, u.full_name AS assignee_full_name, u.phone AS assignee_phone"
            " FROM tasks t JOIN users u ON u.id = t.assignee_id"
            " WHERE t.status != 'done' AND t.due_date IS NOT NULL AND t.due_date != ''"
            " ORDER BY t.due_date ASC",
        ).fetchall()
        return [dict(r) for r in rows]


def director_daily_snapshot() -> dict:
    """Counts for the morning/evening digest (IST day boundaries)."""
    today = datetime.now(IST).date()
    start_utc = datetime(today.year, today.month, today.day, tzinfo=IST).astimezone(timezone.utc)
    s = start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    stats = summary_stats()
    with _connect() as conn:
        done_today = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status='done' AND completed_at>=?", (s,)
        ).fetchone()[0]
        new_today = conn.execute("SELECT COUNT(*) FROM tasks WHERE created_at>=?", (s,)).fetchone()[0]
    overdue = sum(1 for t in open_tasks_with_due() if t["due_date"] < str(today))
    totals = stats["totals"]
    return {
        "open": totals["pending"] + totals["in_progress"] + totals["in_review"],
        "pending": totals["pending"],
        "in_progress": totals["in_progress"],
        "in_review": totals["in_review"],
        "overdue": overdue,
        "done_today": done_today,
        "new_today": new_today,
        "per_employee": stats["per_employee"],
    }


# ---------------------------------------------------------------------------
# Recurring tasks
# ---------------------------------------------------------------------------

def create_recurring(assignee_name: str, category: str, title: str, message: str,
                     recurrence: str, priority: str = "normal", created_by: str = "NG Sir") -> dict:
    assignee = get_user_by_name(assignee_name)
    if not assignee:
        raise ValueError(f"Unknown assignee: {assignee_name}")
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO recurring_tasks (assignee_id, category, title, message, priority, recurrence, created_by, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (assignee["id"], category, title, message,
             priority if priority in TASK_PRIORITIES else "normal", recurrence, created_by, _utcnow()),
        )
        rid = cur.lastrowid
    return get_recurring(rid)


def get_recurring(rid: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT r.*, u.name AS assignee_name, u.full_name AS assignee_full_name"
            " FROM recurring_tasks r JOIN users u ON u.id = r.assignee_id WHERE r.id=?",
            (rid,),
        ).fetchone()
        return dict(row) if row else None


def list_recurring(active_only: bool = False) -> list[dict]:
    q = ("SELECT r.*, u.name AS assignee_name, u.full_name AS assignee_full_name"
         " FROM recurring_tasks r JOIN users u ON u.id = r.assignee_id")
    if active_only:
        q += " WHERE r.active = 1"
    q += " ORDER BY r.id DESC"
    with _connect() as conn:
        return [dict(r) for r in conn.execute(q).fetchall()]


def set_recurring_active(rid: int, active: bool) -> None:
    with _connect() as conn:
        conn.execute("UPDATE recurring_tasks SET active=? WHERE id=?", (1 if active else 0, rid))


def delete_recurring(rid: int) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM recurring_tasks WHERE id=?", (rid,))
        return cur.rowcount > 0


def mark_recurring_run(rid: int, day: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE recurring_tasks SET last_run_date=? WHERE id=?", (day, rid))


def _parse_utc(iso: str | None):
    if not iso:
        return None
    try:
        return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _fmt_duration(hours: float | None) -> str:
    if hours is None:
        return "—"
    if hours < 1:
        return f"{int(round(hours * 60))}m"
    if hours < 48:
        return f"{hours:.1f}h"
    return f"{hours / 24:.1f}d"


def analytics_stats() -> dict:
    """Performance metrics per employee + a created-vs-completed daily trend.

    - completion_rate: done / total assigned
    - avg_turnaround_h: mean (completed_at - created_at) over done tasks, hours
    - on_time_rate: among done tasks that HAD a due date, fraction finished on/before it
    - overdue_now: open tasks past due
    - avg_open_age_h: mean age of currently-open tasks, hours
    """
    now = datetime.now(timezone.utc)
    today_ist = datetime.now(IST).date()
    with _connect() as conn:
        per_employee = []
        for staff in conn.execute("SELECT * FROM users WHERE role != 'admin' ORDER BY id").fetchall():
            rows = [dict(r) for r in conn.execute("SELECT * FROM tasks WHERE assignee_id=?", (staff["id"],))]
            total = len(rows)
            done = [r for r in rows if r["status"] == "done"]
            open_rows = [r for r in rows if r["status"] != "done"]

            turnarounds = []
            for r in done:
                c, d = _parse_utc(r["created_at"]), _parse_utc(r["completed_at"])
                if c and d and d >= c:
                    turnarounds.append((d - c).total_seconds() / 3600)
            avg_turnaround = sum(turnarounds) / len(turnarounds) if turnarounds else None

            with_due = [r for r in done if r.get("due_date") and r.get("completed_at")]
            on_time = 0
            for r in with_due:
                comp = _parse_utc(r["completed_at"])
                comp_ist = comp.astimezone(IST).date() if comp else None
                if comp_ist and str(comp_ist) <= r["due_date"]:
                    on_time += 1
            on_time_rate = (on_time / len(with_due)) if with_due else None

            overdue_now = sum(
                1 for r in open_rows if r.get("due_date") and r["due_date"] < str(today_ist)
            )
            open_ages = [
                (now - _parse_utc(r["created_at"])).total_seconds() / 3600
                for r in open_rows if _parse_utc(r["created_at"])
            ]
            avg_open_age = sum(open_ages) / len(open_ages) if open_ages else None

            per_employee.append({
                "id": staff["id"],
                "name": staff["name"],
                "full_name": staff["full_name"],
                "total": total,
                "done": len(done),
                "open": len(open_rows),
                "completion_rate": (len(done) / total) if total else 0.0,
                "avg_turnaround_h": avg_turnaround,
                "avg_turnaround_label": _fmt_duration(avg_turnaround),
                "on_time_rate": on_time_rate,
                "overdue_now": overdue_now,
                "avg_open_age_h": avg_open_age,
                "avg_open_age_label": _fmt_duration(avg_open_age),
            })

        # 14-day created-vs-completed trend (IST days).
        trend = []
        for i in range(13, -1, -1):
            day = today_ist - timedelta(days=i)
            start_utc = datetime(day.year, day.month, day.day, tzinfo=IST).astimezone(timezone.utc)
            end_utc = start_utc + timedelta(days=1)
            s, e = start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"), end_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            created = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE created_at>=? AND created_at<?", (s, e)
            ).fetchone()[0]
            completed = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE completed_at>=? AND completed_at<?", (s, e)
            ).fetchone()[0]
            trend.append({"date": str(day), "label": day.strftime("%d %b"), "created": created, "completed": completed})

        team = {
            "total": sum(e["total"] for e in per_employee),
            "done": sum(e["done"] for e in per_employee),
            "open": sum(e["open"] for e in per_employee),
            "overdue_now": sum(e["overdue_now"] for e in per_employee),
        }
        team["completion_rate"] = (team["done"] / team["total"]) if team["total"] else 0.0
        all_turnarounds = [e["avg_turnaround_h"] for e in per_employee if e["avg_turnaround_h"] is not None]
        team["avg_turnaround_label"] = _fmt_duration(
            sum(all_turnarounds) / len(all_turnarounds) if all_turnarounds else None
        )
        return {"per_employee": per_employee, "team": team, "trend": trend}
