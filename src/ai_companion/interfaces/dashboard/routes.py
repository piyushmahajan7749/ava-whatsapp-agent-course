"""ANGC task dashboard — server-rendered pages, no frontend build needed.

- Staff (Sandhya / Ramu / Nikhil Uikey): see and update their own tasks.
- Admin (Nikhil Gupta): summary dashboard + every employee's task list.
"""

import html
import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from ai_companion.interfaces.dashboard.auth import (
    COOKIE_NAME,
    SESSION_TTL_SECONDS,
    create_session_token,
    current_user,
)
from ai_companion.modules.angc import db, team

logger = logging.getLogger(__name__)

dashboard_router = APIRouter()

STATUS_LABELS = {"pending": "To Do", "in_progress": "In Progress", "in_review": "In Review", "done": "Done"}
# Status colors validated (CVD-checked, contrast ≥ 3:1 on light surface);
# chips/columns always pair color with a text label + dot, never color alone.
STATUS_COLORS = {"pending": "#b45309", "in_progress": "#1d4ed8", "in_review": "#7c3aed", "done": "#15803d"}
STATUS_BG = {"pending": "#fef3c7", "in_progress": "#dbeafe", "in_review": "#ede9fe", "done": "#dcfce7"}
STATUS_ACCENT = {"pending": "#f59e0b", "in_progress": "#3b82f6", "in_review": "#8b5cf6", "done": "#22c55e"}
BOARD_ORDER = ("pending", "in_progress", "in_review", "done")
# One forward step per status — rendered as a quick-action button (touch fallback for drag & drop).
NEXT_STEP = {
    "pending": ("in_progress", "▶ Start"),
    "in_progress": ("in_review", "🔍 Review"),
    "in_review": ("done", "✓ Done"),
    "done": ("pending", "↺ Reopen"),
}

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

/* ---- kanban board ---- */
.board { display: flex; gap: 13px; align-items: flex-start; overflow-x: auto; padding: 2px 2px 14px; -webkit-overflow-scrolling: touch; }
.col {
  flex: 1 0 252px; max-width: 330px; background: #e9edf4; border-radius: 14px;
  padding: 9px; border-top: 3px solid var(--line);
}
.col-pending { border-top-color: #f59e0b; }
.col-in_progress { border-top-color: #3b82f6; }
.col-in_review { border-top-color: #8b5cf6; }
.col-done { border-top-color: #22c55e; }
.col-head { display: flex; align-items: center; gap: 7px; padding: 4px 6px 9px; }
.col-head .k-dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.col-head .cl { font-size: 12.5px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; color: var(--ink-2); }
.col-head .cn {
  margin-left: auto; font-size: 11.5px; font-weight: 800; color: var(--ink-2);
  background: #dde3ec; border-radius: 999px; padding: 2px 9px; font-variant-numeric: tabular-nums;
}
.col-body { min-height: 70px; border-radius: 10px; transition: background .15s; }
.col.dragover { outline: 2px dashed var(--gold); outline-offset: -2px; }
.col.dragover .col-body { background: rgba(212,165,55,.08); }
.kcard {
  background: var(--surface); border: 1px solid var(--line); border-radius: 11px;
  padding: 11px 12px; margin-bottom: 9px; box-shadow: var(--shadow-sm);
  cursor: grab; transition: box-shadow .15s, transform .15s, opacity .15s;
}
.kcard:hover { box-shadow: var(--shadow-md); }
.kcard:active { cursor: grabbing; }
.kcard.dragging { opacity: .45; transform: rotate(2deg); }
.kcard .kt { font-weight: 700; font-size: 13.5px; line-height: 1.35; }
.kcard .kt .tid { color: var(--ink-3); font-weight: 700; font-size: 12px; margin-right: 3px; }
.kcard .kmsg { color: var(--ink-2); font-size: 12px; margin-top: 6px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; white-space: pre-wrap; }
.kcard .kmeta { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-top: 9px; }
.kcard .chip { padding: 2.5px 9px; font-size: 10.5px; }
.kcard .kdate { color: var(--ink-3); font-size: 11px; font-weight: 600; }
.kcard .kwho { display: inline-flex; align-items: center; gap: 5px; color: var(--ink-2); font-size: 11px; font-weight: 700; }
.kcard .kwho .av { width: 18px; height: 18px; font-size: 8.5px; }
.kcard .kacts { display: flex; gap: 6px; margin-top: 9px; }
.kcard .kacts button.act { padding: 5px 11px; font-size: 11.5px; flex: none; }
.kcard .kacts .b-x {
  margin-left: auto; background: transparent; color: var(--ink-3); border-color: transparent; padding: 5px 7px;
}
.kcard .kacts .b-x:hover { color: #b91c1c; background: #fde8e8; }
a.b-edit {
  display: inline-flex; align-items: center; border-radius: 999px; padding: 5px 11px;
  font-size: 11.5px; font-weight: 700; background: #f3f0e6; color: var(--gold-dark);
  border: 1px solid #e8e0c8; transition: filter .15s;
}
a.b-edit:hover { filter: brightness(.96); }
select {
  width: 100%; padding: 11px 13px; border: 1.5px solid #d7dde8; border-radius: 10px;
  font-size: 14.5px; font-family: inherit; background: #fbfcfe;
}
textarea {
  width: 100%; min-height: 90px; padding: 11px 13px; border: 1.5px solid #d7dde8; border-radius: 10px;
  font-size: 14.5px; font-family: inherit; background: #fbfcfe; resize: vertical;
}
textarea:focus, select:focus { outline: none; border-color: var(--gold); box-shadow: 0 0 0 3px rgba(212,165,55,.18); }
.form-box {
  max-width: 560px; background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--r-lg); padding: 24px; box-shadow: var(--shadow-sm);
}
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 0 14px; }
@media (max-width: 560px) { .form-row { grid-template-columns: 1fr; } }
table.users { width: 100%; border-collapse: collapse; background: var(--surface); border-radius: var(--r-md); overflow: hidden; box-shadow: var(--shadow-sm); }
table.users th, table.users td { text-align: left; padding: 11px 14px; font-size: 13.5px; border-bottom: 1px solid var(--line); }
table.users th { font-size: 11.5px; text-transform: uppercase; letter-spacing: .08em; color: var(--ink-3); background: var(--bg); }
.role-pill { border-radius: 999px; padding: 2.5px 10px; font-size: 11.5px; font-weight: 700; }
.role-admin { background: #f6d98a; color: #6b4e0c; }
.role-employee { background: #e3edfd; color: #1d4ed8; }

/* ---- task detail ---- */
.detail {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-lg);
  padding: clamp(18px, 3vw, 28px); box-shadow: var(--shadow-sm); max-width: 760px;
}
.detail .d-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; }
.detail h1 { font-size: clamp(18px, 2.6vw, 22px); }
.detail h2 { margin: 22px 0 10px; }
.d-msg {
  background: var(--bg); border-left: 3px solid var(--gold-soft); border-radius: 9px;
  padding: 13px 16px; margin: 16px 0; white-space: pre-wrap; color: var(--ink-2); font-size: 14px;
}
.d-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 8px 22px; }
.d-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 8px 0; border-bottom: 1px dashed var(--line); font-size: 13.5px; }
.d-row span { color: var(--ink-3); font-weight: 600; flex: none; }
.d-row b { display: inline-flex; align-items: center; gap: 7px; text-align: right; }
.d-row .av { width: 22px; height: 22px; font-size: 9.5px; }
.d-actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }

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


_BOARD_JS = """
<script>
(function () {
  let dragged = null;
  let justDragged = false;

  document.querySelectorAll('.kcard[draggable="true"]').forEach(card => {
    // Click anywhere on the card (except buttons/links/forms) opens the detail view.
    card.addEventListener('click', e => {
      if (justDragged || e.target.closest('button, a, form, input')) return;
      window.location = '/tasks/' + card.dataset.id;
    });
    card.addEventListener('dragstart', e => {
      dragged = card;
      justDragged = true;
      card.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', card.dataset.id);
    });
    card.addEventListener('dragend', () => {
      card.classList.remove('dragging');
      document.querySelectorAll('.col').forEach(c => c.classList.remove('dragover'));
      dragged = null;
      setTimeout(() => { justDragged = false; }, 150);
    });
  });

  document.querySelectorAll('.col').forEach(col => {
    col.addEventListener('dragover', e => { e.preventDefault(); col.classList.add('dragover'); });
    col.addEventListener('dragleave', e => { if (!col.contains(e.relatedTarget)) col.classList.remove('dragover'); });
    col.addEventListener('drop', e => {
      e.preventDefault();
      col.classList.remove('dragover');
      if (!dragged) return;
      const status = col.dataset.status;
      const from = dragged.closest('.col');
      if (from === col) return;
      col.querySelector('.col-body').prepend(dragged);
      updateCard(dragged, status);
      refreshCounts();
      fetch('/tasks/' + dragged.dataset.id + '/status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'fetch' },
        body: 'status=' + encodeURIComponent(status),
      }).then(r => { if (!r.ok) location.reload(); })
        .catch(() => location.reload());
    });
  });

  const NEXT = {
    pending:     { to: 'in_progress', label: '\\u25B6 Start',  cls: 'b-start' },
    in_progress: { to: 'in_review',   label: '\\uD83D\\uDD0D Review', cls: 'b-start' },
    in_review:   { to: 'done',        label: '\\u2713 Done',   cls: 'b-done' },
    done:        { to: 'pending',     label: '\\u21BA Reopen', cls: 'b-reopen' },
  };

  function updateCard(card, status) {
    card.dataset.status = status;
    const form = card.querySelector('form.next');
    if (!form) return;
    const step = NEXT[status];
    form.querySelector('input[name=status]').value = step.to;
    const btn = form.querySelector('button');
    btn.textContent = step.label;
    btn.className = 'act ' + step.cls;
  }

  function refreshCounts() {
    document.querySelectorAll('.col').forEach(col => {
      const n = col.querySelectorAll('.kcard').length;
      const badge = col.querySelector('.cn');
      if (badge) badge.textContent = n;
    });
  }
})();
</script>
"""


def _page(title: str, body: str, user: dict | None = None, auth_page: bool = False, script: str = "") -> HTMLResponse:
    nav = ""
    if user:
        home_label = "Dashboard" if user["role"] == "admin" else "My Tasks"
        team_link = '<a href="/admin/users">Team</a>' if user["role"] == "admin" else ""
        nav = (
            f'<div class="nav"><a href="/dashboard">{home_label}</a>{team_link}'
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
{script}
</body></html>"""
    return HTMLResponse(html_doc)



def _empty(text: str, icon: str = "🗒️") -> str:
    return f'<div class="empty"><div class="big">{icon}</div>{text}</div>'





def _kcard(task: dict, show_assignee: bool = False, can_delete: bool = False) -> str:
    next_status, next_label = NEXT_STEP[task["status"]]
    next_cls = {"in_progress": "b-start", "in_review": "b-start", "done": "b-done", "pending": "b-reopen"}[next_status]
    actions = (
        f'<form class="inline next" method="post" action="/tasks/{task["id"]}/status">'
        f'<input type="hidden" name="status" value="{next_status}">'
        f'<button class="act {next_cls}" type="submit">{next_label}</button></form>'
    )
    if can_delete:
        actions += (
            f'<form class="inline" method="post" action="/tasks/{task["id"]}/delete" '
            f'onsubmit="return confirm(\'Delete task #{task["id"]}?\')">'
            f'<button class="act b-x" type="submit" title="Delete">✕</button></form>'
        )
    actions += f'<a class="act b-edit" href="/tasks/{task["id"]}/edit" title="Edit">✎ Edit</a>'
    who = f'<span class="kwho">{_avatar(task["assignee_name"], "av")}{_esc(task["assignee_name"])}</span>' if show_assignee else ""
    due = f'<span class="kdate">📅 {_esc(task["due_date"])}</span>' if task.get("due_date") else ""
    return f"""<div class="kcard" draggable="true" data-id="{task['id']}" data-status="{task['status']}" title="Open task #{task['id']}">
  <div class="kt"><span class="tid">#{task['id']}</span><a href="/tasks/{task['id']}" style="color:inherit">{_esc(task['title'])}</a></div>
  <div class="kmsg">{_esc(task['message'])}</div>
  <div class="kmeta"><span class="chip tag">{_esc(task['category'])}</span>{who}{due}
    <span class="kdate">🕐 {_esc(db.to_ist_label(task['created_at']).split(',')[0])}</span></div>
  <div class="kacts">{actions}</div>
</div>"""


def _kanban(tasks: list[dict], show_assignee: bool = False, can_delete: bool = False) -> str:
    cols = ""
    for status in BOARD_ORDER:
        col_tasks = [t for t in tasks if t["status"] == status]
        cards = "".join(_kcard(t, show_assignee, can_delete) for t in col_tasks)
        cols += f"""<div class="col col-{status}" data-status="{status}">
  <div class="col-head"><span class="k-dot" style="background:{STATUS_ACCENT[status]}"></span>
    <span class="cl">{STATUS_LABELS[status]}</span><span class="cn">{len(col_tasks)}</span></div>
  <div class="col-body">{cards}</div>
</div>"""
    return f'<div class="board">{cols}</div>'


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

    tasks = db.list_tasks(assignee_id=user["id"])
    open_n = sum(1 for t in tasks if t["status"] != "done")
    board = _kanban(tasks) if tasks else _empty("Koi task nahi hai — sab clear! 🎉", "✨")
    body = f"""<h1>Namaste, {_esc(user['name'])} ji 🙏</h1>
<div class="sub">NG Sir dwara assigned — {open_n} open task{'s' if open_n != 1 else ''} · cards ko drag karke lane badal sakte hain</div>
{board}"""
    return _page("My Tasks", body, user, script=_BOARD_JS)


def _admin_dashboard(user: dict) -> HTMLResponse:
    stats = db.summary_stats()
    totals = stats["totals"]
    done_today_all = sum(e["done_today"] for e in stats["per_employee"])

    kpis = (
        _kpi_tile("Open", totals["pending"] + totals["in_progress"] + totals["in_review"], "#d4a537")
        + _kpi_tile("To Do", totals["pending"], "#f59e0b")
        + _kpi_tile("In Progress", totals["in_progress"], "#3b82f6")
        + _kpi_tile("In Review", totals["in_review"], "#8b5cf6")
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
    <div class="mini"><b>{emp['pending']}</b><span>To Do</span></div>
    <div class="mini"><b>{emp['in_progress']}</b><span>Active</span></div>
    <div class="mini"><b>{emp['in_review']}</b><span>Review</span></div>
    <div class="mini"><b>{emp['done_today']}</b><span>Done today</span></div>
  </div>
</a>"""

    all_tasks = db.list_tasks(limit=100)
    board = (
        _kanban(all_tasks, show_assignee=True, can_delete=True)
        if all_tasks
        else _empty("Abhi koi task nahi. WhatsApp par task bhejiye 📲")
    )

    body = f"""<h1>Namaste, Nikhil Gupta Sir 🙏</h1>
<div class="sub">ANGC team task overview · cards ko drag karke lane badal sakte hain</div>
<div class="kpis">{kpis}</div>
<div class="cards">{emp_cards}</div>
<h2>Task board</h2>
{board}"""
    return _page("Admin Dashboard", body, user, script=_BOARD_JS)


@dashboard_router.get("/admin/employee/{employee_id}", response_class=HTMLResponse)
def employee_tasks(request: Request, employee_id: int, status: str = ""):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role"] != "admin":
        return RedirectResponse("/dashboard")

    employee = db.get_user_by_id(employee_id)
    if not employee or employee["role"] == "admin":
        return _page("Not found", _empty("Employee nahi mila."), user)

    tasks = db.list_tasks(assignee_id=employee_id)
    board = _kanban(tasks, can_delete=True) if tasks else _empty("Koi task nahi hai.")
    body = f"""<div class="person-head">{_avatar(employee['name'])}
  <div><h1>{_esc(employee['name'])} <span style="color:var(--ink-3);font-weight:600">— {_esc(employee['full_name'])}</span></h1>
  <div class="sub" style="margin:0">{_esc(employee['email'])} · {_esc(employee['phone'])}</div></div>
</div>
<div class="sub"><a class="backlink" href="/dashboard">← Back to dashboard</a></div>
{board}"""
    return _page(f"{employee['name']} tasks", body, user, script=_BOARD_JS)


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
    # Drag & drop updates come via fetch — no redirect needed.
    if request.headers.get("x-requested-with") == "fetch":
        return Response(status_code=204)
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


def _can_touch(user: dict, task: dict) -> bool:
    return user["role"] == "admin" or task["assignee_id"] == user["id"]


@dashboard_router.get("/tasks/{task_id}", response_class=HTMLResponse)
def task_detail(request: Request, task_id: int):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login")
    task = db.get_task(task_id)
    if not task or not _can_touch(user, task):
        return RedirectResponse("/dashboard")

    # Status mover: one button per lane, current one highlighted & inert.
    status_btns = ""
    for s in BOARD_ORDER:
        if s == task["status"]:
            status_btns += (
                f'<span class="chip" style="background:{STATUS_BG[s]};color:{STATUS_COLORS[s]};'
                f'padding:8px 16px;font-size:13px"><span class="dot"></span>{STATUS_LABELS[s]}</span>'
            )
        else:
            status_btns += (
                f'<form class="inline" method="post" action="/tasks/{task["id"]}/status">'
                f'<input type="hidden" name="status" value="{s}">'
                f'<button class="act b-reopen" type="submit">→ {STATUS_LABELS[s]}</button></form>'
            )

    admin_actions = ""
    if user["role"] == "admin":
        admin_actions = (
            f'<form class="inline" method="post" action="/tasks/{task["id"]}/delete" '
            f'onsubmit="return confirm(\'Delete task #{task["id"]}?\')">'
            f'<button class="act b-del" type="submit">✕ Delete task</button></form>'
        )

    due_row = f'<div class="d-row"><span>📅 Due date</span><b>{_esc(task["due_date"])}</b></div>' if task.get("due_date") else ""
    completed_row = (
        f'<div class="d-row"><span>✅ Completed</span><b>{_esc(db.to_ist_label(task["completed_at"]))}</b></div>'
        if task.get("completed_at") else ""
    )

    body = f"""<div class="sub" style="margin-bottom:10px"><a class="backlink" href="/dashboard">← Back to board</a></div>
<div class="detail">
  <div class="d-head">
    <h1><span class="tid" style="color:var(--ink-3)">#{task['id']}</span> {_esc(task['title'])}</h1>
    {_status_chip_lg(task['status'])}
  </div>
  <div class="d-msg">{_esc(task['message'])}</div>
  <div class="d-grid">
    <div class="d-row"><span>👤 Assigned to</span><b>{_avatar(task['assignee_name'], 'av')} {_esc(task['assignee_name'])} ({_esc(task['assignee_full_name'])})</b></div>
    <div class="d-row"><span>🏷️ Category</span><b><span class="chip tag">{_esc(task['category'])}</span></b></div>
    <div class="d-row"><span>👔 Assigned by</span><b>{_esc(task['assigned_by'])}</b></div>
    <div class="d-row"><span>🕐 Created</span><b>{_esc(db.to_ist_label(task['created_at']))}</b></div>
    <div class="d-row"><span>♻️ Updated</span><b>{_esc(db.to_ist_label(task['updated_at']))}</b></div>
    {due_row}{completed_row}
  </div>
  <h2>Move to</h2>
  <div class="d-actions">{status_btns}</div>
  <h2>Actions</h2>
  <div class="d-actions">
    <a class="act b-edit" style="font-size:12.5px;padding:7px 15px" href="/tasks/{task['id']}/edit">✎ Edit task</a>
    {admin_actions}
  </div>
</div>"""
    return _page(f"Task #{task['id']}", body, user)


def _status_chip_lg(status: str) -> str:
    return (
        f'<span class="chip" style="background:{STATUS_BG[status]};color:{STATUS_COLORS[status]};'
        f'padding:7px 15px;font-size:13px;flex:none"><span class="dot"></span>{STATUS_LABELS[status]}</span>'
    )


@dashboard_router.get("/tasks/{task_id}/edit", response_class=HTMLResponse)
def edit_task_page(request: Request, task_id: int, error: str = ""):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login")
    task = db.get_task(task_id)
    if not task or not _can_touch(user, task):
        return RedirectResponse("/dashboard")

    cat_options = "".join(
        f'<option value="{_esc(c)}"{" selected" if c == task["category"] else ""}>{_esc(c)}</option>'
        for c in team.CATEGORIES
    )
    assignee_field = ""
    if user["role"] == "admin":
        opts = "".join(
            f'<option value="{u["id"]}"{" selected" if u["id"] == task["assignee_id"] else ""}>'
            f'{_esc(u["name"])} ({_esc(u["full_name"])})</option>'
            for u in db.list_staff()
        )
        assignee_field = f"<label>Assignee</label><select name=\"assignee_id\">{opts}</select>"
    error_html = '<div class="error">Title khaali nahi ho sakta.</div>' if error else ""

    body = f"""<h1>Edit Task #{task['id']}</h1>
<div class="sub"><a class="backlink" href="/dashboard">← Back</a></div>
<div class="form-box">
  <form method="post" action="/tasks/{task['id']}/edit">
    <label>Title</label><input name="title" required value="{_esc(task['title'])}">
    <label>Details / message</label><textarea name="message">{_esc(task['message'])}</textarea>
    <div class="form-row">
      <div><label>Category</label><select name="category">{cat_options}</select></div>
      <div><label>Due date (optional)</label><input type="date" name="due_date" value="{_esc(task.get('due_date') or '')}"></div>
    </div>
    {assignee_field}
    {error_html}
    <button class="primary" type="submit">Save changes</button>
  </form>
</div>"""
    return _page(f"Edit #{task['id']}", body, user)


@dashboard_router.post("/tasks/{task_id}/edit")
def edit_task_submit(
    request: Request,
    task_id: int,
    title: str = Form(...),
    message: str = Form(""),
    category: str = Form(...),
    due_date: str = Form(""),
    assignee_id: int | None = Form(None),
):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    task = db.get_task(task_id)
    if not task or not _can_touch(user, task):
        return RedirectResponse("/dashboard", status_code=303)
    if not title.strip():
        return RedirectResponse(f"/tasks/{task_id}/edit?error=1", status_code=303)

    fields: dict = {
        "title": title.strip(),
        "message": message.strip() or task["message"],
        "due_date": due_date.strip() or None,
    }
    if category in team.CATEGORIES:
        fields["category"] = category
    # Only the admin can reassign.
    if user["role"] == "admin" and assignee_id:
        target = db.get_user_by_id(assignee_id)
        if target and target["role"] != "admin":
            fields["assignee_id"] = assignee_id
    db.update_task_fields(task_id, **fields)
    return RedirectResponse("/dashboard", status_code=303)


@dashboard_router.get("/admin/users", response_class=HTMLResponse)
def users_page(request: Request, ok: str = "", error: str = ""):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role"] != "admin":
        return RedirectResponse("/dashboard")

    rows = ""
    for u in [user] + db.list_staff():
        role_cls = "role-admin" if u["role"] == "admin" else "role-employee"
        role_label = "Admin" if u["role"] == "admin" else "Employee"
        rows += (
            f"<tr><td>{_avatar(u['name'], 'av')} </td><td><b>{_esc(u['name'])}</b><br>"
            f"<span style='color:var(--ink-3);font-size:12px'>{_esc(u['full_name'])}</span></td>"
            f"<td>{_esc(u['email'])}</td><td>{_esc(u['phone'])}</td>"
            f"<td><span class='role-pill {role_cls}'>{role_label}</span></td></tr>"
        )

    note = ""
    if ok:
        note = '<div class="ok">Employee add ho gaya ✅ Default password unhe batayein.</div>'
    elif error == "dup":
        note = '<div class="error">Is email se user pehle se hai.</div>'
    elif error:
        note = '<div class="error">Name, email aur password (min 6) zaroori hain.</div>'

    body = f"""<h1>Team</h1>
<div class="sub">Dashboard users — employees apne hi tasks dekh aur edit kar sakte hain</div>
<table class="users">
  <tr><th></th><th>Name</th><th>Email</th><th>WhatsApp</th><th>Role</th></tr>
  {rows}
</table>
<h2>Add employee</h2>
<div class="form-box">
  <form method="post" action="/admin/users">
    <div class="form-row">
      <div><label>Short name (for @mentions)</label><input name="name" required placeholder="e.g. Rahul"></div>
      <div><label>Full name</label><input name="full_name" placeholder="e.g. Rahul Sharma"></div>
    </div>
    <div class="form-row">
      <div><label>Email (login)</label><input type="email" name="email" required></div>
      <div><label>WhatsApp number (optional)</label><input name="phone" placeholder="98xxxxxxx"></div>
    </div>
    <label>Password</label><input name="password" required minlength="6">
    {note}
    <button class="primary" type="submit">Add employee</button>
  </form>
</div>"""
    return _page("Team", body, user)


@dashboard_router.post("/admin/users")
def users_create(
    request: Request,
    name: str = Form(...),
    full_name: str = Form(""),
    email: str = Form(...),
    phone: str = Form(""),
    password: str = Form(...),
):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] != "admin":
        return RedirectResponse("/dashboard", status_code=303)
    if not name.strip() or not email.strip() or len(password) < 6:
        return RedirectResponse("/admin/users?error=1", status_code=303)
    if db.get_user_by_email(email):
        return RedirectResponse("/admin/users?error=dup", status_code=303)
    db.create_user(name, full_name, email, phone, password, role="employee")
    return RedirectResponse("/admin/users?ok=1", status_code=303)


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
