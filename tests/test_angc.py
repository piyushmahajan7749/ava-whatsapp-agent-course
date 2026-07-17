"""Unit tests for the ANGC assistant: routing, DB, auth (no LLM calls)."""

import os

import pytest

os.environ.setdefault("DIRECTOR_PHONE_NUMBERS", "919999900000")

from ai_companion.modules.angc import db, team
from ai_companion.settings import settings


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ANGC_DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    yield


# ---------------------------------------------------------------------------
# team.py
# ---------------------------------------------------------------------------

def test_employee_phones_normalized():
    assert team.EMPLOYEES["Sandhya"]["phone"] == "919109128734"
    assert team.EMPLOYEES["Ramu"]["phone"] == "919475455555"
    assert team.EMPLOYEES["Nikhil Uikey"]["phone"] == "917509002010"


def test_director_detection(monkeypatch):
    monkeypatch.setattr(settings, "DIRECTOR_PHONE_NUMBERS", "98260 12345, 917000000001")
    assert team.is_director("919826012345")
    assert team.is_director("917000000001")
    assert not team.is_director("919109128734")


def test_employee_by_phone():
    assert team.employee_by_phone("919109128734") == "Sandhya"
    assert team.employee_by_phone("9475455555") == "Ramu"
    assert team.employee_by_phone("911111111111") is None


def test_mention_extraction_sample_message():
    text = "Central park hotel capital subsidy case machi  singh ji case update .\n@~Sandhya"
    assert team.extract_mention(text) == "Sandhya"


def test_mention_variants():
    assert team.extract_mention("@Ramu isko dekh lo") == "Ramu"
    assert team.extract_mention("please handle @~Nikhil Uikey") == "Nikhil Uikey"
    assert team.extract_mention("koi mention nahi hai") is None


def test_resolve_employee_name():
    assert team.resolve_employee_name("sandhya dangi") == "Sandhya"
    assert team.resolve_employee_name("Uikey") == "Nikhil Uikey"
    assert team.resolve_employee_name("unknown person") is None
    assert team.resolve_employee_name(None) is None


def test_pick_assignee_mention_beats_default():
    assert team.pick_assignee("Work Pendency Reminder", None) == "Nikhil Uikey"
    assert team.pick_assignee("Client Management", None) == "Sandhya"
    assert team.pick_assignee("Client Management", "Ramu") == "Ramu"
    # unknown category falls back to default category's eligibility
    assert team.pick_assignee("Nonsense", None) == "Sandhya"


def test_every_category_default_is_valid():
    for category, eligible in team.CATEGORIES.items():
        assert eligible, category
        for name in eligible:
            assert name in team.EMPLOYEES


# ---------------------------------------------------------------------------
# db.py
# ---------------------------------------------------------------------------

def test_seeded_users():
    staff = db.list_staff()
    assert {u["name"] for u in staff} == {"Sandhya", "Ramu", "Nikhil Uikey"}
    admin = db.get_user_by_email(settings.ANGC_ADMIN_EMAIL)
    assert admin and admin["role"] == "admin" and admin["full_name"] == "Nikhil Gupta"


def test_login_and_password_change():
    user = db.check_login("cspangcgroup@gmail.com", settings.ANGC_DEFAULT_PASSWORD)
    assert user and user["name"] == "Sandhya"
    assert db.check_login("cspangcgroup@gmail.com", "wrong") is None
    db.set_password(user["id"], "newpass123")
    assert db.check_login("cspangcgroup@gmail.com", "newpass123")
    assert db.check_login("cspangcgroup@gmail.com", settings.ANGC_DEFAULT_PASSWORD) is None


def test_task_lifecycle():
    task = db.create_task(
        assignee_name="Sandhya",
        category="Client Management",
        title="Central Park Hotel capital subsidy — Machi Singh ji case update",
        message="Central park hotel capital subsidy case machi singh ji case update .\n@~Sandhya",
    )
    assert task["status"] == "pending"
    assert task["assignee_name"] == "Sandhya"
    assert task["assignee_phone"] == "919109128734"

    db.update_task_status(task["id"], "in_progress")
    db.update_task_status(task["id"], "done")
    done = db.get_task(task["id"])
    assert done["status"] == "done" and done["completed_at"]

    with pytest.raises(ValueError):
        db.update_task_status(task["id"], "bogus")
    with pytest.raises(ValueError):
        db.create_task("Nobody", "Expenses", "x", "y")


def test_list_and_stats():
    sandhya_task = db.create_task("Sandhya", "WhatsApp Message", "Msg task", "raw")
    db.create_task("Ramu", "Expenses", "Diesel expense", "raw2")
    db.update_task_status(sandhya_task["id"], "done")

    sandhya = db.get_user_by_name("Sandhya")
    assert [t["id"] for t in db.list_tasks(assignee_id=sandhya["id"])] == [sandhya_task["id"]]
    assert len(db.list_tasks(status="pending")) == 1

    stats = db.summary_stats()
    assert stats["totals"] == {"pending": 1, "in_progress": 0, "in_review": 0, "done": 1}
    by_name = {e["name"]: e for e in stats["per_employee"]}
    assert by_name["Sandhya"]["done_today"] == 1
    assert by_name["Ramu"]["pending"] == 1
    assert by_name["Nikhil Uikey"]["total"] == 0


def test_update_task_fields_and_delete():
    task = db.create_task("Sandhya", "Financial Management", "BS payment correct 2 lakh", "raw")
    ramu = db.get_user_by_name("Ramu")
    updated = db.update_task_fields(
        task["id"], title="Ayush bhai se payment collect", message="new msg",
        assignee_id=ramu["id"], status="hacked", bogus="x",
    )
    assert updated["title"] == "Ayush bhai se payment collect"
    assert updated["assignee_name"] == "Ramu"
    assert updated["status"] == "pending"  # status/bogus not editable via fields

    assert db.delete_task(task["id"]) is True
    assert db.get_task(task["id"]) is None
    assert db.delete_task(task["id"]) is False


def test_director_edit_delete_regexes():
    from ai_companion.modules.angc.task_intake import _DIR_DELETE_RE, _DIR_EDIT_RE

    m = _DIR_EDIT_RE.match("Edit task 3 - Ayush bhai se payment collect karni hai..2 lakh")
    assert m and (m.group(1) or m.group(3)) == "3"
    assert "Ayush bhai" in (m.group(2) or m.group(4))
    m = _DIR_EDIT_RE.match("task 5 update karo - naya detail @Ramu")
    assert m and (m.group(1) or m.group(3)) == "5"
    m = _DIR_EDIT_RE.match("update task #7: kal tak")
    assert m and (m.group(1) or m.group(3)) == "7"

    assert _DIR_DELETE_RE.match("delete task 3")
    assert _DIR_DELETE_RE.match("Task 4 cancel karo")
    assert _DIR_DELETE_RE.match("task #9 hata do")
    assert not _DIR_DELETE_RE.match("cancel task 3 ka payment follow up")  # new task, not delete
    assert not _DIR_EDIT_RE.match("Central park hotel case update .\n@~Sandhya")


# ---------------------------------------------------------------------------
# dashboard auth
# ---------------------------------------------------------------------------

def test_session_tokens():
    from ai_companion.interfaces.dashboard import auth

    token = auth.create_session_token(42)
    assert auth.verify_session_token(token) == 42
    assert auth.verify_session_token(token + "x") is None
    assert auth.verify_session_token("1.2.3") is None
    assert auth.verify_session_token(None) is None


def test_employee_role_flow():
    emp = db.create_user("Rahul", "Rahul Sharma", "rahul@angcgroup.com", "98260 99999", "secret123")
    assert emp["role"] == "employee" and emp["phone"] == "919826099999"
    assert db.check_login("rahul@angcgroup.com", "secret123")
    assert emp["name"] in [u["name"] for u in db.list_staff()]

    # dynamic roster: mentions/phone/assignment resolve for the new employee
    assert team.resolve_employee_name("rahul") == "Rahul"
    assert team.employee_by_phone("919826099999") == "Rahul"
    assert team.extract_mention("yeh kaam @Rahul ko do") == "Rahul"
    assert team.pick_assignee("Client Management", "Rahul") == "Rahul"

    task = db.create_task("Rahul", "Staff Task", "Test task", "raw msg")
    assert task["assignee_name"] == "Rahul"

    # employee edits own task fields
    updated = db.update_task_fields(task["id"], title="Edited title", due_date="2026-07-20")
    assert updated["title"] == "Edited title" and updated["due_date"] == "2026-07-20"


# ---------------------------------------------------------------------------
# notes
# ---------------------------------------------------------------------------

def test_notes_crud():
    task = db.create_task("Sandhya", "Client Management", "Note test task", "raw")
    admin = db.get_user_by_email(settings.ANGC_ADMIN_EMAIL)
    sandhya = db.get_user_by_name("Sandhya")

    n1 = db.add_note(task["id"], admin["id"], "Sir ne bola urgent hai")
    n2 = db.add_note(task["id"], sandhya["id"], "Kar diya hai, confirm pending")
    assert n1["author_name"] == "NG Sir" and n2["author_name"] == "Sandhya"

    notes = db.list_notes(task["id"])
    assert [n["id"] for n in notes] == [n1["id"], n2["id"]]  # chronological

    # task's note_count reflects both, updated_at bumped
    fetched = db.get_task(task["id"])
    assert fetched["note_count"] == 2
    assert fetched["updated_at"] >= task["updated_at"]

    assert db.delete_note(n1["id"]) is True
    assert len(db.list_notes(task["id"])) == 1
    assert db.get_task(task["id"])["note_count"] == 1
    assert db.delete_note(999999) is False


def test_notes_cascade_on_task_delete():
    task = db.create_task("Ramu", "Expenses", "To be deleted", "raw")
    ramu = db.get_user_by_name("Ramu")
    db.add_note(task["id"], ramu["id"], "note before delete")
    assert db.delete_task(task["id"]) is True
    assert db.list_notes(task["id"]) == []


# ---------------------------------------------------------------------------
# dashboard: new task + notes + overdue (via TestClient)
# ---------------------------------------------------------------------------

def test_dashboard_new_task_and_notes_and_overdue():
    from fastapi.testclient import TestClient
    from ai_companion.interfaces.whatsapp.webhook_endpoint import app

    with TestClient(app) as c:
        # employee creates a task for themself (no assignee_id control)
        c.post("/login", data={"email": "cspangcgroup@gmail.com", "password": settings.ANGC_DEFAULT_PASSWORD})

        # GET /tasks/new must render the form, not get shadowed by GET /tasks/{task_id}
        get_r = c.get("/tasks/new")
        assert get_r.status_code == 200 and "New Task" in get_r.text and "Create task" in get_r.text

        r = c.post(
            "/tasks/new",
            data={"title": "Self-created task", "message": "details", "category": "WhatsApp Message",
                  "due_date": "2020-01-01"},
            follow_redirects=True,
        )
        assert r.status_code == 200 and "Self-created task" in r.text
        sandhya = db.get_user_by_name("Sandhya")
        tasks = db.list_tasks(assignee_id=sandhya["id"])
        new_task = next(t for t in tasks if t["title"] == "Self-created task")
        assert new_task["assignee_name"] == "Sandhya"  # can't self-assign to someone else
        assert new_task["due_date"] == "2020-01-01"

        # overdue task shows a warning marker on the board
        board_page = c.get("/dashboard").text
        assert "⚠️" in board_page and "overdue" in board_page

        # add + view a note
        r2 = c.post(f"/tasks/{new_task['id']}/notes", data={"body": "Reminder set"}, follow_redirects=True)
        assert "Reminder set" in r2.text and "Notes (1)" in r2.text

        # employee cannot touch another employee's task
        ramu_task = db.create_task("Ramu", "Expenses", "Ramu only", "raw")
        r3 = c.post(f"/tasks/{ramu_task['id']}/notes", data={"body": "sneaky"}, follow_redirects=False)
        assert r3.status_code == 303
        assert db.list_notes(ramu_task["id"]) == []

    with TestClient(app) as a:
        # admin can create a task and assign it to anyone
        a.post("/login", data={"email": settings.ANGC_ADMIN_EMAIL, "password": settings.ANGC_DEFAULT_PASSWORD})
        ramu = db.get_user_by_name("Ramu")
        r4 = a.post(
            "/tasks/new",
            data={"title": "Admin assigned", "message": "m", "category": "Vehicle Management",
                  "due_date": "", "assignee_id": str(ramu["id"])},
            follow_redirects=True,
        )
        assert r4.status_code == 200
        assigned = next(t for t in db.list_tasks(assignee_id=ramu["id"]) if t["title"] == "Admin assigned")
        assert assigned["assignee_name"] == "Ramu" and assigned["assigned_by"] == "NG Sir"


# ---------------------------------------------------------------------------
# calendar feed
# ---------------------------------------------------------------------------

def test_calendar_token_lifecycle():
    sandhya = db.get_user_by_name("Sandhya")
    token1 = db.get_or_create_calendar_token(sandhya["id"])
    token1_again = db.get_or_create_calendar_token(sandhya["id"])
    assert token1 == token1_again  # stable once created

    assert db.get_user_by_calendar_token(token1)["name"] == "Sandhya"
    assert db.get_user_by_calendar_token("bogus-token") is None

    token2 = db.regenerate_calendar_token(sandhya["id"])
    assert token2 != token1
    assert db.get_user_by_calendar_token(token1) is None  # old one dead
    assert db.get_user_by_calendar_token(token2)["name"] == "Sandhya"


def test_ics_build_basic_and_escaping():
    from ai_companion.modules.angc import ics

    tasks = [
        {
            "id": 1, "title": "Call, Ayush; re: payment\nfollow-up", "assignee_name": "Sandhya",
            "assigned_by": "NG Sir", "category": "Client Management", "status": "pending",
            "due_date": "2026-07-20", "message": "Details with a comma, and a backslash \\ here",
        },
        {
            "id": 2, "title": "No due date task", "assignee_name": "Ramu", "assigned_by": "NG Sir",
            "category": "Expenses", "status": "done", "due_date": None, "message": "skip me",
        },
    ]
    out = ics.build_ics(tasks, "Test Calendar")
    assert out.startswith("BEGIN:VCALENDAR\r\n")
    assert out.rstrip().endswith("END:VCALENDAR")
    assert "BEGIN:VEVENT" in out and out.count("BEGIN:VEVENT") == 1  # undated task skipped
    assert "UID:task-1@" in out
    assert "DTSTART;VALUE=DATE:20260720" in out
    # Unfold RFC 5545 line folds (CRLF + space) before checking content substrings.
    unfolded = out.replace("\r\n ", "")
    assert "Call\\, Ayush\\; re: payment\\nfollow-up" in unfolded
    assert "a comma\\, and a backslash \\\\ here" in unfolded
    assert "X-WR-CALNAME:Test Calendar" in out


def test_ics_overdue_marker():
    from ai_companion.modules.angc import ics

    tasks = [{
        "id": 5, "title": "Overdue thing", "assignee_name": "Ramu", "assigned_by": "NG Sir",
        "category": "Expenses", "status": "pending", "due_date": "2000-01-01", "message": "",
    }]
    out = ics.build_ics(tasks, "Test")
    assert "⚠️" in out


# ---------------------------------------------------------------------------
# priority + due-date inference + proof-of-completion
# ---------------------------------------------------------------------------

def test_priority_field_create_edit_and_migration():
    task = db.create_task("Sandhya", "Client Management", "Prio task", "raw", priority="urgent")
    assert task["priority"] == "urgent"
    assert db.create_task("Ramu", "Expenses", "Normal task", "raw")["priority"] == "normal"
    # invalid priority coerces to normal
    assert db.create_task("Ramu", "Expenses", "Bad prio", "raw", priority="wtf")["priority"] == "normal"

    updated = db.update_task_fields(task["id"], priority="normal")
    assert updated["priority"] == "normal"
    # invalid priority via edit is ignored, not written
    kept = db.update_task_fields(task["id"], priority="bogus")
    assert kept["priority"] == "normal"


def test_urgency_detection_and_due_inference(monkeypatch):
    from ai_companion.modules.angc import task_intake

    # deterministic backstop upgrades to urgent even if LLM omits it
    monkeypatch.setattr(task_intake, "extract_task", lambda text: {
        "intent": "TASK", "task_id": None, "title": "Ayush payment",
        "category": "Financial Management", "assignee": "Sandhya",
        "due_date": None, "priority": "urgent",
    })
    # avoid real WhatsApp + director notify
    monkeypatch.setattr(task_intake, "_notify_assignee", lambda task: False)

    reply = task_intake.handle_director_message("Ayush se payment urgent collect karo @Sandhya")
    assert "URGENT" in reply
    # urgent + no explicit date => due today (IST)
    from ai_companion.modules.angc.db import IST
    from datetime import datetime
    today = datetime.now(IST).strftime("%Y-%m-%d")
    sandhya = db.get_user_by_name("Sandhya")
    latest = db.list_tasks(assignee_id=sandhya["id"])[0]
    assert latest["priority"] == "urgent" and latest["due_date"] == today


def test_urgent_regex_backstop():
    from ai_companion.modules.angc.task_intake import _URGENT_RE
    for s in ["ye kaam jaldi karo", "URGENT: call client", "🔴 abhi karo", "asap bhejo"]:
        assert _URGENT_RE.search(s), s
    assert not _URGENT_RE.search("normal follow up kal karna")


def test_staff_done_with_completion_note():
    from ai_companion.modules.angc import task_intake

    task = db.create_task("Sandhya", "Client Management", "Note-on-done", "raw")
    reply = task_intake.handle_staff_message("919109128734", f"done {task['id']} client ne confirm kar diya")
    assert "complete" in reply.lower()
    notes = db.list_notes(task["id"])
    assert len(notes) == 1 and "client ne confirm" in notes[0]["body"]
    assert db.get_task(task["id"])["status"] == "done"

    # plain "done N" with no note adds no note
    task2 = db.create_task("Sandhya", "Client Management", "No-note", "raw")
    task_intake.handle_staff_message("919109128734", f"done {task2['id']}")
    assert db.list_notes(task2["id"]) == []


def test_ics_urgent_priority():
    from ai_companion.modules.angc import ics

    tasks = [{
        "id": 9, "title": "Urgent thing", "assignee_name": "Ramu", "assigned_by": "NG Sir",
        "category": "Expenses", "status": "pending", "due_date": "2030-01-01", "message": "",
        "priority": "urgent",
    }]
    out = ics.build_ics(tasks, "Test")
    assert "🔴" in out and "PRIORITY:1" in out


def test_calendar_feed_url_uses_https_behind_proxy(monkeypatch):
    """Azure Container Apps terminates TLS and proxies over http — the feed URL
    we show must still be https:// or calendar apps refuse to subscribe."""
    from fastapi.testclient import TestClient
    from ai_companion.interfaces.whatsapp.webhook_endpoint import app

    monkeypatch.setattr(settings, "ANGC_DASHBOARD_URL", None)
    with TestClient(app) as c:
        c.post("/login", data={"email": "cspangcgroup@gmail.com", "password": settings.ANGC_DEFAULT_PASSWORD})
        page = c.get("/calendar", headers={"X-Forwarded-Proto": "https"}).text
        assert 'value="https://' in page
        assert 'value="http://' not in page
        assert "webcal://" in page

        # ANGC_DASHBOARD_URL, when set, wins over request headers
        monkeypatch.setattr(settings, "ANGC_DASHBOARD_URL", "https://tasks.angcgroup.com")
        page2 = c.get("/calendar").text
        assert 'value="https://tasks.angcgroup.com/calendar/' in page2


def test_dashboard_calendar_feed_scoping_and_auth():
    from fastapi.testclient import TestClient
    from ai_companion.interfaces.whatsapp.webhook_endpoint import app

    with_due = db.create_task("Sandhya", "Client Management", "Sandhya dated task", "raw", due_date="2026-08-01")
    db.create_task("Ramu", "Expenses", "Ramu dated task", "raw", due_date="2026-08-02")

    with TestClient(app) as c:
        # must be logged in to see the settings page
        assert c.get("/calendar", follow_redirects=False).status_code in (303, 307)

        c.post("/login", data={"email": "cspangcgroup@gmail.com", "password": settings.ANGC_DEFAULT_PASSWORD})
        page = c.get("/calendar").text
        assert "Calendar Feed" in page and ".ics" in page and "sirf aapke tasks" in page

        sandhya = db.get_user_by_name("Sandhya")
        token = db.get_or_create_calendar_token(sandhya["id"])

        # feed itself needs NO auth/cookies (calendar apps can't send session cookies)
        anon = TestClient(app)
        feed = anon.get(f"/calendar/{token}.ics")
        assert feed.status_code == 200
        assert feed.headers["content-type"].startswith("text/calendar")
        assert "Sandhya dated task" in feed.text
        assert "Ramu dated task" not in feed.text  # employee feed = own tasks only

        # bad token -> 404
        assert anon.get("/calendar/not-a-real-token.ics").status_code == 404

        # regenerate invalidates the old link
        c.post("/calendar/regenerate")
        assert anon.get(f"/calendar/{token}.ics").status_code == 404

    with TestClient(app) as a:
        a.post("/login", data={"email": settings.ANGC_ADMIN_EMAIL, "password": settings.ANGC_DEFAULT_PASSWORD})
        admin = db.get_user_by_email(settings.ANGC_ADMIN_EMAIL)
        admin_token = db.get_or_create_calendar_token(admin["id"])
        admin_feed = TestClient(app).get(f"/calendar/{admin_token}.ics")
        assert "Sandhya dated task" in admin_feed.text and "Ramu dated task" in admin_feed.text
