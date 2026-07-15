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
