"""Proactive WhatsApp notifications + recurrence logic for the ANGC assistant.

These are the jobs the scheduler fires (reminders, escalation, digests,
recurring-task materialization). Outbound messages are free-form: WhatsApp
Cloud API only delivers those within 24h of the recipient's last inbound
message. Outside that window Meta rejects the send and we just log it —
approved message templates would lift that limit (a later config add-on).
"""

import logging
from datetime import datetime, timezone

import httpx

from ai_companion.modules.angc import db, team
from ai_companion.modules.angc.db import IST
from ai_companion.settings import settings

logger = logging.getLogger(__name__)

_WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
_WEEKDAY_LABEL = {
    "MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday", "THU": "Thursday",
    "FRI": "Friday", "SAT": "Saturday", "SUN": "Sunday",
}


# ---------------------------------------------------------------------------
# WhatsApp send
# ---------------------------------------------------------------------------

def send_whatsapp(to_number: str, text: str) -> bool:
    token = settings.WHATSAPP_ACCESS_TOKEN
    phone_id = settings.WHATSAPP_PHONE_NUMBER_ID
    if not token or not phone_id:
        logger.warning("[notify] WA credentials not set — cannot send to %s", to_number)
        return False
    try:
        resp = httpx.post(
            f"https://graph.facebook.com/v21.0/{phone_id}/messages",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"messaging_product": "whatsapp", "to": to_number, "type": "text", "text": {"body": text}},
            timeout=15,
        )
        if resp.status_code != 200:
            # 131047 = "message outside 24h window, needs a template" — expected, non-fatal.
            logger.warning("[notify] send to %s failed %s: %s", to_number, resp.status_code, resp.text[:200])
            return False
        return True
    except Exception as exc:
        logger.error("[notify] send to %s error: %s", to_number, exc)
        return False


def _notify_directors(text: str) -> None:
    for number in team.get_director_set():
        send_whatsapp(number, text)


def _dashboard_line() -> str:
    return f"\n\n📊 Dashboard: {settings.ANGC_DASHBOARD_URL}" if settings.ANGC_DASHBOARD_URL else ""


# ---------------------------------------------------------------------------
# Recurrence
# ---------------------------------------------------------------------------

def recurrence_due(recurrence: str, day: datetime) -> bool:
    """True if a recurrence string ('daily' | 'weekly:MON' | 'monthly:15')
    falls on the given IST date."""
    rec = (recurrence or "").strip().lower()
    if rec == "daily":
        return True
    if rec.startswith("weekly:"):
        target = rec.split(":", 1)[1].upper()[:3]
        return _WEEKDAYS[day.weekday()] == target
    if rec.startswith("monthly:"):
        try:
            dom = int(rec.split(":", 1)[1])
        except ValueError:
            return False
        # Run on the given day-of-month, or the last day if the month is shorter.
        import calendar
        last = calendar.monthrange(day.year, day.month)[1]
        return day.day == min(dom, last)
    return False


def recurrence_label(recurrence: str) -> str:
    rec = (recurrence or "").strip().lower()
    if rec == "daily":
        return "Daily"
    if rec.startswith("weekly:"):
        return f"Every {_WEEKDAY_LABEL.get(rec.split(':', 1)[1].upper()[:3], rec)}"
    if rec.startswith("monthly:"):
        return f"Monthly (day {rec.split(':', 1)[1]})"
    return recurrence


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def run_overdue_sweep() -> dict:
    """Remind assignees of overdue tasks (once/day/task); escalate long-overdue
    ones to the director. Idempotent via the job ledger."""
    today = datetime.now(IST).date()
    today_s = today.isoformat()
    reminded = escalated = 0
    for t in db.open_tasks_with_due():
        if t["due_date"] >= today_s:
            continue
        days_late = (today - datetime.strptime(t["due_date"], "%Y-%m-%d").date()).days

        if settings.ANGC_OVERDUE_REMINDERS and t.get("assignee_phone"):
            if db.claim_job(f"reminder:{t['id']}:{today_s}"):
                urgent = "🔴 " if t.get("priority") == "urgent" else ""
                msg = (
                    f"⏰ Reminder — task pending hai\n\n"
                    f"{urgent}📋 Task #{t['id']}: {t['title']}\n"
                    f"📅 Due tha: {t['due_date']} ({days_late} din pehle)\n\n"
                    f"Update dene ke liye: done {t['id']} <note>"
                )
                if send_whatsapp(t["assignee_phone"], msg):
                    reminded += 1

        if days_late >= settings.ANGC_OVERDUE_ESCALATE_DAYS:
            if db.claim_job(f"escalate:{t['id']}:{today_s}"):
                msg = (
                    f"⚠️ Sir, ek task {days_late} din se overdue hai:\n\n"
                    f"📋 Task #{t['id']}: {t['title']}\n"
                    f"👤 {t['assignee_name']} · 📅 due {t['due_date']}"
                    f"{_dashboard_line()}"
                )
                _notify_directors(msg)
                escalated += 1
    logger.info("[notify] overdue sweep: %d reminders, %d escalations", reminded, escalated)
    return {"reminded": reminded, "escalated": escalated}


def _digest_text(kind: str, snap: dict) -> str:
    if kind == "morning":
        head = "🌅 Suprabhat Sir! Aaj ka overview:"
    else:
        head = "🌇 Sir, aaj ka summary:"
    lines = [
        head,
        "",
        f"📋 Open: {snap['open']} ({snap['pending']} to-do, {snap['in_progress']} active, {snap['in_review']} review)",
    ]
    if snap["overdue"]:
        lines.append(f"⚠️ Overdue: {snap['overdue']}")
    if kind == "evening":
        lines.append(f"✅ Aaj complete: {snap['done_today']}")
        lines.append(f"🆕 Aaj naye: {snap['new_today']}")
    lines.append("")
    lines.append("Team:")
    for e in snap["per_employee"]:
        open_n = e["pending"] + e["in_progress"] + e["in_review"]
        lines.append(f"• {e['name']}: {open_n} open, {e['done_today']} done aaj")
    return "\n".join(lines) + _dashboard_line()


def run_digest(kind: str) -> None:
    snap = db.director_daily_snapshot()
    _notify_directors(_digest_text(kind, snap))
    logger.info("[notify] %s digest sent", kind)


def materialize_recurring() -> int:
    """Create today's instances of any active recurring task due today."""
    today = datetime.now(IST)
    today_s = today.date().isoformat()
    created = 0
    for r in db.list_recurring(active_only=True):
        if r.get("last_run_date") == today_s:
            continue
        if not recurrence_due(r["recurrence"], today):
            continue
        if not db.claim_job(f"recurring:{r['id']}:{today_s}"):
            db.mark_recurring_run(r["id"], today_s)
            continue
        try:
            task = db.create_task(
                assignee_name=r["assignee_name"],
                category=r["category"],
                title=r["title"],
                message=r["message"],
                assigned_by=r.get("created_by", "NG Sir"),
                due_date=today_s,
                priority=r.get("priority", "normal"),
            )
            db.mark_recurring_run(r["id"], today_s)
            created += 1
            if settings.ANGC_NOTIFY_ASSIGNEES and task.get("assignee_phone"):
                urgent = "🔴 " if task.get("priority") == "urgent" else ""
                send_whatsapp(
                    task["assignee_phone"],
                    f"🔁 Aaj ka recurring task:\n\n{urgent}📋 Task #{task['id']}: {task['title']}\n"
                    f"🏷️ {task['category']}\n\nComplete hone par: done {task['id']}",
                )
        except Exception as exc:
            logger.error("[notify] recurring %s materialize failed: %s", r["id"], exc)
    if created:
        logger.info("[notify] materialized %d recurring tasks", created)
    return created
