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
# Status colors validated (CVD ΔE > 25, contrast ≥ 3:1 on light surface);
# chips always pair color with a text label + dot, never color alone.
STATUS_COLORS = {"pending": "#b45309", "in_progress": "#1d4ed8", "done": "#15803d"}
STATUS_BG = {"pending": "#fef3c7", "in_progress": "#dbeafe", "done": "#dcfce7"}

# Fixed identity colors per employee (never reassigned).
AVATAR_COLORS = {"Sandhya": "#6d28d9", "Ramu": "#0f766e", "Nikhil Uikey": "#be185d"}
_AVATAR_FALLBACK = "#334155"

_BASE_CSS = """
:root {
  --navy-900: #0b1220; --navy-800: #111d36; --navy-700: #1a2b4d;
  --gold: #d4a537; --gold-soft: #f6d98a; --gold-dark: #a87f24;
  --bg: #f2f4f8; --surface: #ffffff; --line: #e5e9f0;
  --ink: #16213a; --ink-2: #4b5875; --ink-3: #8d99b5;
  --shadow-sm: 0 1px 2px rgba(11,18,32,.05), 0 2px 8px rgba(11,18,32,.05);
  --shadow-md: 0 2px 6px rgba(11,18,32,.06), 0 10px 28px rgba(11,18,32,.09);
  --r-lg: 16px; --r-md: 12px; --r-sm: 9px;
}
* { box-sizing: border-box; margin: 0; }
html { -webkit-text-size-adjust: 100%; }
body {
  font-family: 'Plus Jakarta Sans', -apple-system, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg); color: var(--ink); line-height: 1.5;
  min-height: 100vh; display: flex; flex-direction: column;
}
a { color: var(--navy-700); text-decoration: none; }

/* ---- top bar ---- */
.topbar {
  background: linear-gradient(120deg, var(--navy-900) 0%, var(--navy-800) 55%, var(--navy-700) 100%);
  color: #fff; padding: 14px clamp(16px, 4vw, 32px);
  display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap;
  border-bottom: 3px solid var(--gold);
}
.brand { display: flex; align-items: center; gap: 11px; }
.brand .mark {
  width: 38px; height: 38px; border-radius: 11px; flex: none;
  background: linear-gradient(135deg, var(--gold-soft), var(--gold) 60%, var(--gold-dark));
  color: var(--navy-900); font-weight: 800; font-size: 19px;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 2px 8px rgba(212,165,55,.4);
}
.brand .t1 { font-weight: 800; font-size: 16.5px; letter-spacing: .02em; }
.brand .t2 { font-size: 11.5px; color: #9fb0d0; letter-spacing: .14em; text-transform: uppercase; margin-top: 1px; }
.nav { display: flex; align-items: center; gap: 4px; }
.nav a {
  color: #c6d2e8; font-size: 13.5px; font-weight: 600;
  padding: 7px 12px; border-radius: 8px; transition: background .15s, color .15s;
}
.nav a:hover { background: rgba(255,255,255,.09); color: #fff; }
.nav .me {
  display: flex; align-items: center; gap: 8px; margin-left: 10px; padding: 5px 12px 5px 6px;
  background: rgba(255,255,255,.07); border: 1px solid rgba(255,255,255,.12); border-radius: 999px;
}
.nav .me .av { width: 26px; height: 26px; font-size: 11px; }
.nav .me span { font-size: 12.5px; font-weight: 700; color: #e8edf7; }

/* ---- layout ---- */
.wrap { width: 100%; max-width: 1040px; margin: 0 auto; padding: clamp(18px, 3.5vw, 32px) 16px 48px; }
h1 { font-size: clamp(20px, 3vw, 25px); font-weight: 800; letter-spacing: -.01em; }
h2 { font-size: 16px; font-weight: 800; margin: 30px 0 12px; display: flex; align-items: center; gap: 8px; }
h2::after { content: ""; flex: 1; height: 1px; background: var(--line); }
.sub { color: var(--ink-2); font-size: 14px; margin: 3px 0 20px; }

/* ---- avatar ---- */
.av {
  width: 40px; height: 40px; border-radius: 50%; flex: none;
  color: #fff; font-weight: 800; font-size: 14.5px;
  display: inline-flex; align-items: center; justify-content: center;
}

/* ---- KPI tiles ---- */
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 22px; }
.kpi {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-md);
  padding: 14px 16px; box-shadow: var(--shadow-sm);
}
.kpi .k-label { font-size: 11.5px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--ink-3); display: flex; align-items: center; gap: 6px; }
.kpi .k-dot { width: 8px; height: 8px; border-radius: 50%; }
.kpi .k-num { font-size: 30px; font-weight: 800; letter-spacing: -.02em; margin-top: 4px; font-variant-numeric: tabular-nums; }

/* ---- employee cards ---- */
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 14px; }
.card {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-lg);
  padding: 18px; box-shadow: var(--shadow-sm); transition: box-shadow .18s, transform .18s;
  display: block; color: var(--ink);
}
a.card:hover { box-shadow: var(--shadow-md); transform: translateY(-2px); }
.card .head { display: flex; align-items: center; gap: 12px; }
.card .name { font-weight: 800; font-size: 15.5px; }
.card .full { color: var(--ink-3); font-size: 12.5px; }
.card .open-n { margin-left: auto; text-align: right; }
.card .open-n b { font-size: 26px; font-weight: 800; font-variant-numeric: tabular-nums; }
.card .open-n span { display: block; font-size: 10.5px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--ink-3); }
.meter { margin: 14px 0 4px; }
.meter .bar { height: 7px; border-radius: 99px; background: #e9edf4; overflow: hidden; }
.meter .fill { height: 100%; border-radius: 99px; background: linear-gradient(90deg, var(--gold-soft), var(--gold)); }
.meter .cap { font-size: 11.5px; color: var(--ink-3); margin-top: 5px; font-weight: 600; }
.card .stats { display: flex; gap: 6px; margin-top: 12px; flex-wrap: wrap; }
.mini {
  flex: 1; min-width: 70px; text-align: center; padding: 7px 4px;
  background: var(--bg); border-radius: var(--r-sm);
}
.mini b { display: block; font-size: 16px; font-weight: 800; font-variant-numeric: tabular-nums; }
.mini span { font-size: 10.5px; color: var(--ink-3); font-weight: 700; }

/* ---- filter pills ---- */
.filters { display: inline-flex; gap: 4px; background: #e7ebf2; padding: 4px; border-radius: 999px; margin-bottom: 18px; flex-wrap: wrap; }
.filters a {
  padding: 7px 15px; border-radius: 999px; font-size: 13px; font-weight: 700; color: var(--ink-2);
  transition: background .15s, color .15s;
}
.filters a:hover { color: var(--ink); }
.filters a.on { background: var(--navy-800); color: #fff; box-shadow: var(--shadow-sm); }

/* ---- task cards ---- */
.task {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-md);
  padding: 15px 18px; box-shadow: var(--shadow-sm); margin-bottom: 12px;
  border-left: 4px solid var(--line); transition: box-shadow .18s;
}
.task:hover { box-shadow: var(--shadow-md); }
.task.s-pending { border-left-color: #f59e0b; }
.task.s-in_progress { border-left-color: #3b82f6; }
.task.s-done { border-left-color: #22c55e; }
.task .head { display: flex; justify-content: space-between; gap: 10px; align-items: flex-start; flex-wrap: wrap; }
.task .tid { color: var(--ink-3); font-weight: 700; margin-right: 2px; }
.task .title { font-weight: 800; font-size: 15px; letter-spacing: -.005em; }
.task .msg {
  color: var(--ink-2); font-size: 13.5px; margin: 9px 0 10px; white-space: pre-wrap;
  background: var(--bg); border-radius: var(--r-sm); padding: 9px 12px;
  border-left: 3px solid var(--gold-soft);
}
.task .meta { color: var(--ink-3); font-size: 12.5px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.task .btns { margin-top: 11px; display: flex; gap: 8px; flex-wrap: wrap; }

/* ---- chips ---- */
.chip {
  display: inline-flex; align-items: center; gap: 6px;
  border-radius: 999px; padding: 3.5px 11px; font-size: 12px; font-weight: 700; white-space: nowrap;
}
.chip .dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.tag { background: #efe9fb; color: #5b21b6; }

/* ---- buttons ---- */
form.inline { display: inline; }
button.act {
  border: 1px solid transparent; border-radius: 999px; padding: 7px 15px;
  font-size: 12.5px; font-weight: 700; cursor: pointer; font-family: inherit;
  transition: filter .15s, transform .1s;
}
button.act:hover { filter: brightness(.95); }
button.act:active { transform: scale(.97); }
.b-start { background: #e3edfd; color: #1d4ed8; border-color: #c9dcfb; }
.b-done { background: #ddf5e4; color: #15803d; border-color: #bfeacd; }
.b-reopen { background: #eef1f6; color: #4b5875; border-color: #dde3ec; }
.b-del { background: #fde8e8; color: #b91c1c; border-color: #f8d0d0; }

/* ---- auth / narrow pages ---- */
body.page-auth {
  background:
    radial-gradient(900px 500px at 85% -10%, rgba(212,165,55,.16), transparent 60%),
    radial-gradient(700px 500px at -10% 110%, rgba(26,43,77,.5), transparent 55%),
    linear-gradient(150deg, var(--navy-900), var(--navy-800) 70%, var(--navy-700));
}
.auth-wrap { flex: 1; display: flex; align-items: center; justify-content: center; padding: 32px 16px; }
.login-box {
  width: 100%; max-width: 392px; background: var(--surface); border-radius: 20px;
  padding: 34px 30px 30px; box-shadow: 0 24px 70px rgba(4,8,18,.45);
}
.login-box .mark {
  width: 52px; height: 52px; border-radius: 15px; margin: 0 auto 14px;
  background: linear-gradient(135deg, var(--gold-soft), var(--gold) 60%, var(--gold-dark));
  color: var(--navy-900); font-weight: 800; font-size: 26px;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 6px 18px rgba(212,165,55,.45);
}
.login-box h1 { text-align: center; font-size: 21px; }
.login-box .sub { text-align: center; margin-bottom: 6px; }
label { display: block; font-size: 12.5px; font-weight: 700; margin: 15px 0 5px; color: var(--ink-2); letter-spacing: .02em; }
input {
  width: 100%; padding: 11px 13px; border: 1.5px solid #d7dde8; border-radius: 10px;
  font-size: 14.5px; font-family: inherit; background: #fbfcfe; transition: border-color .15s, box-shadow .15s;
}
input:focus { outline: none; border-color: var(--gold); box-shadow: 0 0 0 3px rgba(212,165,55,.18); }
button.primary {
  width: 100%; margin-top: 22px; border: 0; border-radius: 10px; padding: 13px;
  font-size: 15px; font-weight: 800; cursor: pointer; font-family: inherit; color: var(--navy-900);
  background: linear-gradient(135deg, var(--gold-soft), var(--gold) 70%);
  box-shadow: 0 4px 14px rgba(212,165,55,.35); transition: filter .15s, transform .1s;
}
button.primary:hover { filter: brightness(1.04); }
button.primary:active { transform: scale(.985); }
.error, .ok { border-radius: 10px; padding: 10px 13px; font-size: 13.5px; font-weight: 600; margin-top: 14px; }
.error { background: #fdeaea; color: #b91c1c; border: 1px solid #f6cfcf; }
.ok { background: #e2f7e9; color: #15803d; border: 1px solid #c3ecd1; }

/* ---- misc ---- */
.empty {
  text-align: center; padding: 46px 20px; background: var(--surface);
  border: 1.5px dashed #d7dde8; border-radius: var(--r-lg); color: var(--ink-3); font-weight: 600;
}
.empty .big { font-size: 34px; margin-bottom: 8px; }
.backlink { font-size: 13px; font-weight: 700; color: var(--ink-2); }
.backlink:hover { color: var(--ink); }
.person-head { display: flex; align-items: center; gap: 14px; margin-bottom: 4px; }

@media (max-width: 560px) {
  .nav .me span { display: none; }
  .task .btns button.act { flex: 1; }
}
"""

_FONT_LINKS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap" rel="stylesheet">'
)


def _esc(value) -> str:
    return html.escape(str(value or ""))


def _initials(name: str) -> str:
    parts = [p for p in (name or "").split() if p]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


def _avatar(name: str, cls: str = "av") -> str:
    color = AVATAR_COLORS.get(name, _AVATAR_FALLBACK)
    return f'<span class="{cls}" style="background:{color}">{_esc(_initials(name))}</span>'


def _page(title: str, body: str, user: dict | None = None, auth_page: bool = False) -> HTMLResponse:
    nav = ""
    if user:
        home_label = "Dashboard" if user["role"] == "admin" else "My Tasks"
        nav = (
            f'<div class="nav"><a href="/dashboard">{home_label}</a>'
            f'<a href="/password">Password</a><a href="/logout">Logout</a>'
            f'<span class="me">{_avatar(user["name"], "av")}<span>{_esc(user["name"])}</span></span></div>'
        )
    topbar = f"""<div class="topbar">
  <div class="brand"><div class="mark">A</div>
    <div><div class="t1">ANGC Group</div><div class="t2">Task Assistant</div></div>
  </div>{nav}
</div>"""
    body_cls = ' class="page-auth"' if auth_page else ""
    content = f'<div class="auth-wrap">{body}</div>' if auth_page else f'<div class="wrap">{body}</div>'
    html_doc = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)} — ANGC</title>{_FONT_LINKS}<style>{_BASE_CSS}</style>
</head><body{body_cls}>
{topbar}
{content}
</body></html>"""
    return HTMLResponse(html_doc)


def _status_chip(status: str) -> str:
    return (
        f'<span class="chip" style="background:{STATUS_BG[status]};color:{STATUS_COLORS[status]}">'
        f'<span class="dot"></span>{STATUS_LABELS[status]}</span>'
    )


def _empty(text: str, icon: str = "🗒️") -> str:
    return f'<div class="empty"><div class="big">{icon}</div>{text}</div>'


def _task_card(task: dict, can_update: bool, show_assignee: bool = False, can_delete: bool = False) -> str:
    buttons = ""
    if can_update:
        if task["status"] == "pending":
            buttons += _status_button(task["id"], "in_progress", "▶ Start", "b-start")
            buttons += _status_button(task["id"], "done", "✓ Mark Done", "b-done")
        elif task["status"] == "in_progress":
            buttons += _status_button(task["id"], "done", "✓ Mark Done", "b-done")
        else:
            buttons += _status_button(task["id"], "pending", "↺ Reopen", "b-reopen")
    if can_delete:
        buttons += (
            f'<form class="inline" method="post" action="/tasks/{task["id"]}/delete" '
            f'onsubmit="return confirm(\'Delete task #{task["id"]}?\')">'
            f'<button class="act b-del" type="submit">✕ Delete</button></form>'
        )
    buttons_html = f'<div class="btns">{buttons}</div>' if buttons else ""

    assignee_line = f"<span>👤 {_esc(task['assignee_name'])}</span>" if show_assignee else ""
    due_line = f"<span>📅 Due {_esc(task['due_date'])}</span>" if task.get("due_date") else ""
    return f"""<div class="task s-{task['status']}">
  <div class="head">
    <span class="title"><span class="tid">#{task['id']}</span> {_esc(task['title'])}</span>
    {_status_chip(task['status'])}
  </div>
  <div class="msg">{_esc(task['message'])}</div>
  <div class="meta"><span class="chip tag">{_esc(task['category'])}</span>
    <span>🕐 {_esc(db.to_ist_label(task['created_at']))}</span>{assignee_line}{due_line}</div>
  {buttons_html}
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


def _kpi_tile(label: str, value: int, dot_color: str) -> str:
    return f"""<div class="kpi">
  <div class="k-label"><span class="k-dot" style="background:{dot_color}"></span>{label}</div>
  <div class="k-num">{value}</div>
</div>"""


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
  <div class="mark">A</div>
  <h1>Welcome back</h1>
  <div class="sub">ANGC Task Assistant Dashboard</div>
  <form method="post" action="/login">
    <label>Email</label><input type="email" name="email" required autofocus placeholder="you@angcgroup.com">
    <label>Password</label><input type="password" name="password" required placeholder="••••••••">
    {error_html}
    <button class="primary" type="submit">Sign in</button>
  </form>
</div>"""
    return _page("Login", body, auth_page=True)


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
    open_n = sum(1 for t in db.list_tasks(assignee_id=user["id"]) if t["status"] != "done")
    cards = "".join(_task_card(t, can_update=True) for t in tasks) or _empty("Koi task nahi hai — sab clear! 🎉", "✨")
    body = f"""<h1>Namaste, {_esc(user['name'])} ji 🙏</h1>
<div class="sub">NG Sir dwara assigned — {open_n} open task{'s' if open_n != 1 else ''}</div>
{_filter_bar('/dashboard', status)}
{cards}"""
    return _page("My Tasks", body, user)


def _admin_dashboard(user: dict) -> HTMLResponse:
    stats = db.summary_stats()
    totals = stats["totals"]
    done_today_all = sum(e["done_today"] for e in stats["per_employee"])

    kpis = (
        _kpi_tile("Open", totals["pending"] + totals["in_progress"], "#d4a537")
        + _kpi_tile("Pending", totals["pending"], "#f59e0b")
        + _kpi_tile("In Progress", totals["in_progress"], "#3b82f6")
        + _kpi_tile("Done Today", done_today_all, "#22c55e")
    )

    emp_cards = ""
    for emp in stats["per_employee"]:
        open_n = emp["pending"] + emp["in_progress"]
        pct = round(emp["done"] * 100 / emp["total"]) if emp["total"] else 0
        emp_cards += f"""<a class="card" href="/admin/employee/{emp['id']}">
  <div class="head">{_avatar(emp['name'])}
    <div><div class="name">{_esc(emp['name'])}</div><div class="full">{_esc(emp['full_name'])}</div></div>
    <div class="open-n"><b>{open_n}</b><span>open</span></div>
  </div>
  <div class="meter"><div class="bar"><div class="fill" style="width:{pct}%"></div></div>
    <div class="cap">{pct}% completed · {emp['done']} of {emp['total']} total</div></div>
  <div class="stats">
    <div class="mini"><b>{emp['pending']}</b><span>Pending</span></div>
    <div class="mini"><b>{emp['in_progress']}</b><span>Active</span></div>
    <div class="mini"><b>{emp['done_today']}</b><span>Done today</span></div>
    <div class="mini"><b>{emp['new_today']}</b><span>New today</span></div>
  </div>
</a>"""

    recent = db.list_tasks(limit=15)
    recent_html = "".join(
        _task_card(t, can_update=True, show_assignee=True, can_delete=True) for t in recent
    ) or _empty("Abhi koi task nahi. WhatsApp par task bhejiye 📲")

    body = f"""<h1>Namaste, Nikhil Gupta Sir 🙏</h1>
<div class="sub">ANGC team task overview</div>
<div class="kpis">{kpis}</div>
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
        return _page("Not found", _empty("Employee nahi mila."), user)

    tasks = db.list_tasks(assignee_id=employee_id, status=status or None)
    cards = "".join(
        _task_card(t, can_update=True, can_delete=True) for t in tasks
    ) or _empty("Koi task nahi hai.")
    body = f"""<div class="person-head">{_avatar(employee['name'])}
  <div><h1>{_esc(employee['name'])} <span style="color:var(--ink-3);font-weight:600">— {_esc(employee['full_name'])}</span></h1>
  <div class="sub" style="margin:0">{_esc(employee['email'])} · {_esc(employee['phone'])}</div></div>
</div>
<div class="sub"><a class="backlink" href="/dashboard">← Back to dashboard</a></div>
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
  <div class="mark">A</div>
  <h1>Change Password</h1>
  <div class="sub">{_esc(user['email'])}</div>
  <form method="post" action="/password">
    <label>Current password</label><input type="password" name="current" required>
    <label>New password (min 6)</label><input type="password" name="new" required minlength="6">
    {note}
    <button class="primary" type="submit">Update password</button>
  </form>
</div>"""
    return _page("Change Password", body, user, auth_page=True)


@dashboard_router.post("/password")
def password_submit(request: Request, current: str = Form(...), new: str = Form(...)):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if len(new) < 6 or not db.verify_password(current, user["password_hash"]):
        return RedirectResponse("/password?error=1", status_code=303)
    db.set_password(user["id"], new)
    return RedirectResponse("/password?ok=1", status_code=303)
