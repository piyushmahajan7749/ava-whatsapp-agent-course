"""ANGC task dashboard — server-rendered pages, no frontend build needed.

- Staff (Sandhya / Ramu / Nikhil Uikey): see and update their own tasks.
- Admin (Nikhil Gupta): summary dashboard + every employee's task list.
"""

import html
import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ai_companion.interfaces.dashboard.auth import (
    COOKIE_NAME,
    SESSION_TTL_SECONDS,
    create_session_token,
    current_user,
)
from ai_companion.modules.angc import db

logger = logging.getLogger(__name__)

dashboard_router = APIRouter()

STATUS_LABELS = {"pending": "Pending", "in_progress": "In Progress", "done": "Done"}
STATUS_COLORS = {"pending": "#b45309", "in_progress": "#1d4ed8", "done": "#15803d"}
STATUS_BG = {"pending": "#fef3c7", "in_progress": "#dbeafe", "done": "#dcfce7"}

_BASE_CSS = """
* { box-sizing: border-box; margin: 0; }
body { font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; background: #f1f5f9; color: #0f172a; }
a { color: #1d4ed8; text-decoration: none; }
.topbar { background: #0f172a; color: #fff; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.topbar .brand { font-weight: 700; font-size: 17px; }
.topbar .brand span { color: #fbbf24; }
.topbar a { color: #cbd5e1; margin-left: 14px; font-size: 14px; }
.wrap { max-width: 1000px; margin: 24px auto; padding: 0 16px; }
h1 { font-size: 22px; margin-bottom: 4px; }
h2 { font-size: 17px; margin: 22px 0 10px; }
.sub { color: #64748b; font-size: 14px; margin-bottom: 18px; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; }
.card { background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 1px 3px rgba(15,23,42,.08); }
.card .name { font-weight: 700; }
.card .row { display: flex; justify-content: space-between; font-size: 14px; margin-top: 8px; color: #475569; }
.card .big { font-size: 26px; font-weight: 700; margin-top: 6px; }
.task { background: #fff; border-radius: 12px; padding: 14px 16px; box-shadow: 0 1px 3px rgba(15,23,42,.08); margin-bottom: 12px; }
.task .head { display: flex; justify-content: space-between; gap: 10px; align-items: baseline; flex-wrap: wrap; }
.task .title { font-weight: 700; font-size: 15px; }
.task .msg { color: #475569; font-size: 14px; margin: 8px 0; white-space: pre-wrap; }
.task .meta { color: #94a3b8; font-size: 12.5px; }
.chip { display: inline-block; border-radius: 999px; padding: 3px 10px; font-size: 12px; font-weight: 600; }
.tag { background: #ede9fe; color: #6d28d9; }
form.inline { display: inline; }
button.act { border: 0; border-radius: 8px; padding: 7px 12px; font-size: 13px; font-weight: 600; cursor: pointer; margin-right: 6px; margin-top: 8px; }
.b-start { background: #dbeafe; color: #1d4ed8; }
.b-done { background: #dcfce7; color: #15803d; }
.b-reopen { background: #f1f5f9; color: #475569; }
.b-del { background: #fee2e2; color: #b91c1c; }
.login-box { max-width: 380px; margin: 60px auto; background: #fff; border-radius: 14px; padding: 28px; box-shadow: 0 4px 16px rgba(15,23,42,.1); }
.login-box h1 { text-align: center; margin-bottom: 4px; }
.login-box .sub { text-align: center; }
label { display: block; font-size: 13.5px; font-weight: 600; margin: 12px 0 4px; }
input { width: 100%; padding: 10px 12px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14.5px; }
button.primary { width: 100%; margin-top: 18px; background: #0f172a; color: #fff; border: 0; border-radius: 8px; padding: 12px; font-size: 15px; font-weight: 600; cursor: pointer; }
.error { background: #fee2e2; color: #b91c1c; border-radius: 8px; padding: 10px 12px; font-size: 14px; margin-top: 12px; }
.ok { background: #dcfce7; color: #15803d; border-radius: 8px; padding: 10px 12px; font-size: 14px; margin-top: 12px; }
.filters { margin-bottom: 14px; font-size: 14px; }
.filters a { margin-right: 12px; color: #64748b; }
.filters a.on { color: #0f172a; font-weight: 700; border-bottom: 2px solid #fbbf24; }
.empty { color: #94a3b8; text-align: center; padding: 30px 0; }
"""


def _esc(value) -> str:
    return html.escape(str(value or ""))


def _page(title: str, body: str, user: dict | None = None) -> HTMLResponse:
    nav = ""
    if user:
        admin_link = '<a href="/dashboard">Dashboard</a>' if user["role"] == "admin" else '<a href="/dashboard">My Tasks</a>'
        nav = (
            f'<div>{admin_link}<a href="/password">Password</a><a href="/logout">Logout</a></div>'
        )
    html_doc = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)} — ANGC</title><style>{_BASE_CSS}</style>
</head><body>
<div class="topbar"><div class="brand">ANGC <span>Task Assistant</span></div>{nav}</div>
<div class="wrap">{body}</div>
</body></html>"""
    return HTMLResponse(html_doc)


def _status_chip(status: str) -> str:
    return (
        f'<span class="chip" style="background:{STATUS_BG[status]};color:{STATUS_COLORS[status]}">'
        f"{STATUS_LABELS[status]}</span>"
    )


def _task_card(task: dict, can_update: bool, show_assignee: bool = False, can_delete: bool = False) -> str:
    buttons = ""
    if can_update:
        if task["status"] == "pending":
            buttons += _status_button(task["id"], "in_progress", "Start", "b-start")
            buttons += _status_button(task["id"], "done", "Mark Done", "b-done")
        elif task["status"] == "in_progress":
            buttons += _status_button(task["id"], "done", "Mark Done", "b-done")
        else:
            buttons += _status_button(task["id"], "pending", "Reopen", "b-reopen")
    if can_delete:
        buttons += (
            f'<form class="inline" method="post" action="/tasks/{task["id"]}/delete" '
            f'onsubmit="return confirm(\'Delete task #{task["id"]}?\')">'
            f'<button class="act b-del" type="submit">Delete</button></form>'
        )

    assignee_line = f" · 👤 {_esc(task['assignee_name'])}" if show_assignee else ""
    due_line = f" · 📅 Due {_esc(task['due_date'])}" if task.get("due_date") else ""
    return f"""<div class="task">
  <div class="head">
    <span class="title">#{task['id']} {_esc(task['title'])}</span>
    {_status_chip(task['status'])}
  </div>
  <div class="msg">{_esc(task['message'])}</div>
  <div class="meta"><span class="chip tag">{_esc(task['category'])}</span>
    &nbsp;🕐 {_esc(db.to_ist_label(task['created_at']))}{assignee_line}{due_line}</div>
  {buttons}
</div>"""


def _status_button(task_id: int, status: str, label: str, css: str) -> str:
    return (
        f'<form class="inline" method="post" action="/tasks/{task_id}/status">'
        f'<input type="hidden" name="status" value="{status}">'
        f'<button class="act {css}" type="submit">{label}</button></form>'
    )


def _filter_bar(base: str, active: str) -> str:
    links = []
    for key, label in [("", "All"), ("pending", "Pending"), ("in_progress", "In Progress"), ("done", "Done")]:
        href = base if not key else f"{base}?status={key}"
        cls = "on" if key == active else ""
        links.append(f'<a class="{cls}" href="{href}">{label}</a>')
    return f'<div class="filters">{"".join(links)}</div>'


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@dashboard_router.get("/", include_in_schema=False)
def root(request: Request):
    return RedirectResponse("/dashboard" if current_user(request) else "/login")


@dashboard_router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = ""):
    if current_user(request):
        return RedirectResponse("/dashboard")
    error_html = '<div class="error">Email ya password galat hai.</div>' if error else ""
    body = f"""<div class="login-box">
  <h1>ANGC Login</h1>
  <div class="sub">Task Assistant Dashboard</div>
  <form method="post" action="/login">
    <label>Email</label><input type="email" name="email" required autofocus>
    <label>Password</label><input type="password" name="password" required>
    {error_html}
    <button class="primary" type="submit">Sign in</button>
  </form>
</div>"""
    return _page("Login", body)


@dashboard_router.post("/login")
def login_submit(email: str = Form(...), password: str = Form(...)):
    user = db.check_login(email, password)
    if not user:
        return RedirectResponse("/login?error=1", status_code=303)
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie(
        COOKIE_NAME,
        create_session_token(user["id"]),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
    )
    return response


@dashboard_router.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


@dashboard_router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, status: str = ""):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login")

    if user["role"] == "admin":
        return _admin_dashboard(user)

    tasks = db.list_tasks(assignee_id=user["id"], status=status or None)
    cards = "".join(_task_card(t, can_update=True) for t in tasks) or '<div class="empty">Koi task nahi hai 🎉</div>'
    body = f"""<h1>Namaste, {_esc(user['name'])} ji 🙏</h1>
<div class="sub">Aapke tasks — NG Sir dwara assigned</div>
{_filter_bar('/dashboard', status)}
{cards}"""
    return _page("My Tasks", body, user)


def _admin_dashboard(user: dict) -> HTMLResponse:
    stats = db.summary_stats()
    totals = stats["totals"]
    emp_cards = ""
    for emp in stats["per_employee"]:
        emp_cards += f"""<div class="card">
  <div class="name"><a href="/admin/employee/{emp['id']}">{_esc(emp['name'])}</a></div>
  <div class="sub" style="margin:0">{_esc(emp['full_name'])}</div>
  <div class="big">{emp['pending'] + emp['in_progress']}<span style="font-size:13px;color:#94a3b8"> open</span></div>
  <div class="row"><span>⏳ Pending</span><b>{emp['pending']}</b></div>
  <div class="row"><span>🔄 In progress</span><b>{emp['in_progress']}</b></div>
  <div class="row"><span>✅ Done today</span><b>{emp['done_today']}</b></div>
  <div class="row"><span>🆕 New today</span><b>{emp['new_today']}</b></div>
</div>"""

    recent = db.list_tasks(limit=15)
    recent_html = "".join(
        _task_card(t, can_update=True, show_assignee=True, can_delete=True) for t in recent
    ) or '<div class="empty">Abhi koi task nahi.</div>'

    body = f"""<h1>Namaste, Nikhil Gupta Sir 🙏</h1>
<div class="sub">ANGC team task overview — {totals['pending']} pending · {totals['in_progress']} in progress · {totals['done']} done</div>
<div class="cards">{emp_cards}</div>
<h2>Recent tasks</h2>
{recent_html}"""
    return _page("Admin Dashboard", body, user)


@dashboard_router.get("/admin/employee/{employee_id}", response_class=HTMLResponse)
def employee_tasks(request: Request, employee_id: int, status: str = ""):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role"] != "admin":
        return RedirectResponse("/dashboard")

    employee = db.get_user_by_id(employee_id)
    if not employee or employee["role"] != "staff":
        return _page("Not found", '<div class="empty">Employee nahi mila.</div>', user)

    tasks = db.list_tasks(assignee_id=employee_id, status=status or None)
    cards = "".join(
        _task_card(t, can_update=True, can_delete=True) for t in tasks
    ) or '<div class="empty">Koi task nahi hai.</div>'
    body = f"""<h1>{_esc(employee['name'])} — {_esc(employee['full_name'])}</h1>
<div class="sub">{_esc(employee['email'])} · {_esc(employee['phone'])} · <a href="/dashboard">← back to dashboard</a></div>
{_filter_bar(f'/admin/employee/{employee_id}', status)}
{cards}"""
    return _page(f"{employee['name']} tasks", body, user)


@dashboard_router.post("/tasks/{task_id}/status")
def change_status(request: Request, task_id: int, status: str = Form(...)):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    task = db.get_task(task_id)
    if not task:
        return RedirectResponse("/dashboard", status_code=303)
    # Staff can only touch their own tasks; admin can touch all.
    if user["role"] != "admin" and task["assignee_id"] != user["id"]:
        return RedirectResponse("/dashboard", status_code=303)
    if status in db.TASK_STATUSES:
        db.update_task_status(task_id, status)
    referer = request.headers.get("referer") or "/dashboard"
    return RedirectResponse(referer, status_code=303)


@dashboard_router.post("/tasks/{task_id}/delete")
def delete_task_route(request: Request, task_id: int):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] != "admin":
        return RedirectResponse("/dashboard", status_code=303)
    db.delete_task(task_id)
    referer = request.headers.get("referer") or "/dashboard"
    return RedirectResponse(referer, status_code=303)


@dashboard_router.get("/password", response_class=HTMLResponse)
def password_page(request: Request, ok: str = "", error: str = ""):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login")
    note = ""
    if ok:
        note = '<div class="ok">Password badal diya gaya ✅</div>'
    elif error:
        note = '<div class="error">Current password galat hai ya naya password 6 akshar se chhota hai.</div>'
    body = f"""<div class="login-box">
  <h1>Change Password</h1>
  <div class="sub">{_esc(user['email'])}</div>
  <form method="post" action="/password">
    <label>Current password</label><input type="password" name="current" required>
    <label>New password (min 6)</label><input type="password" name="new" required minlength="6">
    {note}
    <button class="primary" type="submit">Update</button>
  </form>
</div>"""
    return _page("Change Password", body, user)


@dashboard_router.post("/password")
def password_submit(request: Request, current: str = Form(...), new: str = Form(...)):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if len(new) < 6 or not db.verify_password(current, user["password_hash"]):
        return RedirectResponse("/password?error=1", status_code=303)
    db.set_password(user["id"], new)
    return RedirectResponse("/password?ok=1", status_code=303)
