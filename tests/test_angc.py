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
