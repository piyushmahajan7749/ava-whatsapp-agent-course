"""ANGC executive-assistant intake — handles WhatsApp messages from NG Sir.

Flow for a director message:
- text / transcribed audio → AI extract {intent, title, category, assignee}
- intent TASK  → save to DB, notify the assignee on WhatsApp, confirm to Sir
- intent QUERY → answer from the tasks DB (status/summary questions)
- intent OTHER → short courteous Hinglish reply

Assignment priority: explicit @mention in the message > name detected by the
LLM > the category's default assignee.

Staff members can reply "done <task id>" / "start <task id>" / "tasks" on
WhatsApp; everything else lives on the dashboard.
"""

import json
import logging
import re
from datetime import datetime

import httpx
from openai import AzureOpenAI

from ai_companion.modules.angc import db, team
from ai_companion.modules.angc.db import IST
from ai_companion.settings import settings

logger = logging.getLogger(__name__)


def _ai_client() -> AzureOpenAI:
    return AzureOpenAI(
        api_key=settings.AZURE_OPENAI_API_KEY,
        azure_endpoint=settings.AZURE_OPENAI_API_ENDPOINT,
        api_version=settings.AZURE_OPENAI_API_VERSION,
    )


# ---------------------------------------------------------------------------
# AI extraction
# ---------------------------------------------------------------------------

def _category_block() -> str:
    return "\n".join(f'- "{name}": {hint}' for name, hint in team.CATEGORY_HINTS.items())


_EXTRACT_PROMPT = """You are the WhatsApp executive assistant of Nikhil Gupta Sir, Director of ANGC Group (India).
He sends short messages — often Hinglish, sometimes just a case name and an @mention — to delegate work to his team: {employees}.

Analyse his message and return JSON with these exact fields:
{{"intent":"TASK"|"QUERY"|"OTHER",
"title":string,
"category":string,
"assignee":string|null,
"due_date":"YYYY-MM-DD"|null}}

Rules:
- intent TASK: he wants work done, tracked, reminded, updated, or delegated (even a bare case name with a person's name/mention is a TASK).
- intent QUERY: he is asking about existing tasks — status, pending count, what someone is working on, summary.
- intent OTHER: greetings or anything that is neither.
- title: a short crisp task title (max 12 words), keep his own words/names as-is (do NOT translate names or case names).
- category: pick the closest from this list (use "{default_category}" when unsure):
{categories}
- assignee: ONLY if one of {employees} is named or @mentioned in the message, else null. Never invent a name.
- due_date: only if an explicit date/day is mentioned (today is {today} IST).
Return ONLY the JSON object."""


def extract_task(text: str) -> dict:
    """LLM extraction. Falls back to a safe default TASK on error."""
    prompt = _EXTRACT_PROMPT.format(
        employees=", ".join(team.EMPLOYEES.keys()),
        categories=_category_block(),
        default_category=team.DEFAULT_CATEGORY,
        today=datetime.now(IST).strftime("%Y-%m-%d (%A)"),
    )
    try:
        resp = _ai_client().chat.completions.create(
            model=settings.TEXT_MODEL_NAME,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=2000,
        )
        data = json.loads(resp.choices[0].message.content or "{}")
    except Exception as exc:
        logger.error("[angc_intake] extraction failed: %s", exc)
        data = {}

    intent = (data.get("intent") or "TASK").upper()
    if intent not in ("TASK", "QUERY", "OTHER"):
        intent = "TASK"
    category = data.get("category") or team.DEFAULT_CATEGORY
    if category not in team.CATEGORIES:
        category = team.DEFAULT_CATEGORY
    title = (data.get("title") or "").strip() or text.strip().split("\n")[0][:80]
    return {
        "intent": intent,
        "title": title,
        "category": category,
        "assignee": team.resolve_employee_name(data.get("assignee")),
        "due_date": data.get("due_date"),
    }


# ---------------------------------------------------------------------------
# WhatsApp send (fire-and-forget, same pattern as before)
# ---------------------------------------------------------------------------

def _send_whatsapp(to_number: str, text: str) -> None:
    token = settings.WHATSAPP_ACCESS_TOKEN
    phone_id = settings.WHATSAPP_PHONE_NUMBER_ID
    if not token or not phone_id:
        logger.warning("[angc_intake] WA credentials not set — cannot send to %s", to_number)
        return
    try:
        httpx.post(
            f"https://graph.facebook.com/v21.0/{phone_id}/messages",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "text",
                "text": {"body": text},
            },
            timeout=15,
        )
    except Exception as exc:
        logger.error("[angc_intake] WA send to %s failed: %s", to_number, exc)


# ---------------------------------------------------------------------------
# Director flow
# ---------------------------------------------------------------------------

def handle_director_message(text: str) -> str:
    """Process a message from NG Sir. Returns the Hinglish reply for him."""
    text = (text or "").strip()
    if not text:
        return "Sir, message samajh nahi aaya. Kripya task dobara bhejiye 🙏"

    extracted = extract_task(text)

    if extracted["intent"] == "QUERY":
        return _answer_query(text)
    if extracted["intent"] == "OTHER":
        return _smalltalk_reply(text)

    # Deterministic @mention beats the LLM's guess.
    mention = team.extract_mention(text)
    assignee = team.pick_assignee(extracted["category"], mention or extracted["assignee"])

    try:
        task = db.create_task(
            assignee_name=assignee,
            category=extracted["category"],
            title=extracted["title"],
            message=text,
            due_date=extracted["due_date"],
        )
    except Exception as exc:
        logger.error("[angc_intake] task save failed: %s", exc)
        return "Sir, task save karne mein dikkat aa gayi ⚠️ Kripya thodi der baad dobara try kariye."

    notified = _notify_assignee(task)

    reply = (
        "Ji Sir 🙏 Task note kar liya hai.\n\n"
        f"📋 Task #{task['id']}: {task['title']}\n"
        f"👤 Assigned to: {task['assignee_name']} ({task['assignee_full_name']})\n"
        f"🏷️ Category: {task['category']}"
    )
    if task.get("due_date"):
        reply += f"\n📅 Due: {task['due_date']}"
    if notified:
        reply += f"\n\n{task['assignee_name']} ji ko WhatsApp par inform kar diya gaya hai ✅"
    return reply


def _notify_assignee(task: dict) -> bool:
    if not settings.ANGC_NOTIFY_ASSIGNEES:
        return False
    phone = task.get("assignee_phone")
    if not phone:
        return False
    msg = (
        f"🔔 Naya task — NG Sir ki taraf se\n\n"
        f"📋 Task #{task['id']}: {task['title']}\n"
        f"🏷️ {task['category']}\n\n"
        f"Message: \"{task['message']}\""
    )
    if task.get("due_date"):
        msg += f"\n📅 Due: {task['due_date']}"
    if settings.ANGC_DASHBOARD_URL:
        msg += f"\n\nDashboard: {settings.ANGC_DASHBOARD_URL}"
    msg += f"\n\nComplete hone par yahin reply karein: done {task['id']}"
    _send_whatsapp(phone, msg)
    return True


def _answer_query(question: str) -> str:
    """Answer NG Sir's status/summary question from the tasks DB."""
    stats = db.summary_stats()
    open_tasks = [t for t in db.list_tasks(limit=60) if t["status"] != "done"]
    context_lines = ["Team summary:"]
    for emp in stats["per_employee"]:
        context_lines.append(
            f"- {emp['name']} ({emp['full_name']}): {emp['pending']} pending, "
            f"{emp['in_progress']} in progress, {emp['done_today']} completed today, {emp['done']} done total"
        )
    context_lines.append("\nOpen tasks (newest first):")
    for t in open_tasks[:25]:
        context_lines.append(
            f"- #{t['id']} [{t['status']}] {t['title']} → {t['assignee_name']} "
            f"({t['category']}, {db.to_ist_label(t['created_at'])})"
        )
    if not open_tasks:
        context_lines.append("- none, sab clear hai")

    try:
        resp = _ai_client().chat.completions.create(
            model=settings.TEXT_MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are the executive assistant of Nikhil Gupta Sir, Director of ANGC Group. "
                        "Answer his question using ONLY the task data below. Reply in respectful, natural "
                        "Hinglish (address him as 'Sir'), short and to the point, plain text for WhatsApp "
                        "(no markdown), use simple lists with task numbers where helpful.\n\n"
                        + "\n".join(context_lines)
                    ),
                },
                {"role": "user", "content": question},
            ],
            max_completion_tokens=1500,
        )
        answer = (resp.choices[0].message.content or "").strip()
        if answer:
            return answer
    except Exception as exc:
        logger.error("[angc_intake] query answer failed: %s", exc)

    # Fallback: plain summary
    lines = ["Sir, abhi ka status 👇"]
    for emp in stats["per_employee"]:
        lines.append(f"• {emp['name']}: {emp['pending']} pending, {emp['in_progress']} in progress")
    return "\n".join(lines)


def _smalltalk_reply(text: str) -> str:
    try:
        resp = _ai_client().chat.completions.create(
            model=settings.SMALL_TEXT_MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are the WhatsApp executive assistant of Nikhil Gupta Sir, Director of ANGC Group. "
                        "Reply in 1-2 short lines of respectful, warm Hinglish (address him as 'Sir'). "
                        "Plain text only. If appropriate, remind him gently that he can send any task "
                        "and you will assign it to Sandhya, Ramu or Nikhil Uikey."
                    ),
                },
                {"role": "user", "content": text},
            ],
            max_completion_tokens=1000,
        )
        answer = (resp.choices[0].message.content or "").strip()
        if answer:
            return answer
    except Exception as exc:
        logger.error("[angc_intake] smalltalk reply failed: %s", exc)
    return "Ji Sir 🙏 Main hazir hoon — koi bhi task bhejiye, main team ko assign kar dunga."


# ---------------------------------------------------------------------------
# Staff flow (simple WhatsApp commands)
# ---------------------------------------------------------------------------

_DONE_RE = re.compile(r"^(?:done|complete[d]?|ho\s*gaya)\s*#?(\d+)", re.IGNORECASE)
_START_RE = re.compile(r"^(?:start|working|shuru)\s*#?(\d+)", re.IGNORECASE)


def handle_staff_message(phone: str, text: str) -> str:
    """Handle a WhatsApp message from one of the three assistants."""
    emp_key = team.employee_by_phone(phone)
    if not emp_key:
        return ""
    user = db.get_user_by_name(emp_key)
    if not user:
        return ""
    text = (text or "").strip()

    for regex, status, verb in ((_DONE_RE, "done", "complete"), (_START_RE, "in_progress", "start")):
        m = regex.match(text)
        if not m:
            continue
        task_id = int(m.group(1))
        task = db.get_task(task_id)
        if not task or task["assignee_id"] != user["id"]:
            return f"Task #{task_id} aapke naam par nahi mila 🤔 'tasks' bhejkar apni list dekh sakte hain."
        db.update_task_status(task_id, status)
        if status == "done":
            _notify_director(f"✅ {emp_key} ne Task #{task_id} complete kar diya: {task['title']}")
            return f"Shabash! Task #{task_id} complete mark ho gaya ✅"
        return f"Theek hai, Task #{task_id} in-progress mark kar diya 👍"

    if text.lower() in ("tasks", "task", "mere tasks", "list", "my tasks"):
        open_tasks = [t for t in db.list_tasks(assignee_id=user["id"], limit=30) if t["status"] != "done"]
        if not open_tasks:
            return "Aapke saare tasks clear hain 🎉"
        lines = [f"📋 {emp_key} ji, aapke open tasks:"]
        for t in open_tasks[:10]:
            flag = "🔄" if t["status"] == "in_progress" else "⏳"
            lines.append(f"{flag} #{t['id']} {t['title']} [{t['category']}]")
        lines.append("\nComplete karne par bhejein: done <task number>")
        return "\n".join(lines)

    help_text = (
        f"Namaste {emp_key} ji 🙏 Main ANGC assistant hoon.\n\n"
        "Commands:\n"
        "• tasks — apne open tasks dekhein\n"
        "• start <number> — task shuru\n"
        "• done <number> — task complete"
    )
    if settings.ANGC_DASHBOARD_URL:
        help_text += f"\n\nPoora dashboard: {settings.ANGC_DASHBOARD_URL}"
    return help_text


def _notify_director(text: str) -> None:
    if not settings.ANGC_NOTIFY_ASSIGNEES:
        return
    for number in team.get_director_set():
        _send_whatsapp(number, text)
