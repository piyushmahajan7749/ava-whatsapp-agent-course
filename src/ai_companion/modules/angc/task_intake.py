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
{{"intent":"TASK"|"EDIT"|"DELETE"|"QUERY"|"OTHER",
"task_id":number|null,
"title":string,
"category":string,
"assignee":string|null,
"due_date":"YYYY-MM-DD"|null}}

Rules:
- intent TASK: he wants NEW work done, tracked, reminded, or delegated (even a bare case name with a person's name/mention is a TASK).
- intent EDIT: he refers to an EXISTING task number and wants it changed/corrected/reassigned (e.g. "task 3 edit karo", "task 5 mein badlav", "task 2 Ramu ko de do"). Set task_id.
- intent DELETE: he wants an existing task number cancelled/removed ("task 3 cancel/delete/hata do"). Set task_id.
- intent QUERY: he is asking about existing tasks — status, pending count, what someone is working on, summary.
- intent OTHER: greetings or anything that is neither.
- task_id: only for EDIT/DELETE, the task number he mentions; else null.
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
    if intent not in ("TASK", "EDIT", "DELETE", "QUERY", "OTHER"):
        intent = "TASK"
    category = data.get("category") or team.DEFAULT_CATEGORY
    if category not in team.CATEGORIES:
        category = team.DEFAULT_CATEGORY
    title = (data.get("title") or "").strip() or text.strip().split("\n")[0][:80]
    try:
        task_id = int(data.get("task_id"))
    except (TypeError, ValueError):
        task_id = None
    return {
        "intent": intent,
        "task_id": task_id,
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

# Deterministic fast-paths ("edit task 3 - ...", "task 3 delete") so common
# commands never depend on the LLM.
_DIR_EDIT_RE = re.compile(
    r"^(?:edit|update|change)\s*task\s*#?(\d+)\s*[-–:.,]*\s*(.*)$"
    r"|^task\s*#?(\d+)\s*(?:edit|update)\s*(?:karo|kar\s*do)?\s*[-–:.,]*\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)
_DIR_DELETE_RE = re.compile(
    r"^(?:delete|remove|cancel)\s*task\s*#?(\d+)\s*$"
    r"|^task\s*#?(\d+)\s*(?:delete|cancel|remove|hata\s*do|hatao|cancel\s*karo)\s*\.?\s*$",
    re.IGNORECASE,
)


def handle_director_message(text: str) -> str:
    """Process a message from NG Sir. Returns the Hinglish reply for him."""
    text = (text or "").strip()
    if not text:
        return "Sir, message samajh nahi aaya. Kripya task dobara bhejiye 🙏"

    m = _DIR_EDIT_RE.match(text)
    if m:
        task_id = int(m.group(1) or m.group(3))
        return _handle_edit(task_id, (m.group(2) or m.group(4) or "").strip())
    m = _DIR_DELETE_RE.match(text)
    if m:
        return _handle_delete(int(m.group(1) or m.group(2)))

    extracted = extract_task(text)

    if extracted["intent"] == "EDIT" and extracted["task_id"]:
        return _handle_edit(extracted["task_id"], text)
    if extracted["intent"] == "DELETE" and extracted["task_id"]:
        return _handle_delete(extracted["task_id"])
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


def _task_card(task: dict) -> str:
    card = (
        f"📋 Task #{task['id']}: {task['title']}\n"
        f"👤 Assigned to: {task['assignee_name']} ({task['assignee_full_name']})\n"
        f"🏷️ Category: {task['category']}"
    )
    if task.get("due_date"):
        card += f"\n📅 Due: {task['due_date']}"
    return card


_REASSIGN_FILLER = {
    "edit", "update", "change", "task", "karo", "kar", "kardo", "do", "de",
    "dedo", "ko", "se", "ji", "ka", "ki", "ke", "transfer", "assign",
    "reassign", "abhi", "please", "pls", "is", "ye", "yeh", "wala", "isko",
}


def _is_reassign_only(text: str) -> bool:
    """True if the edit text is just 'give task N to <member>' with no new content."""
    t = text.lower()
    for key, emp in team.EMPLOYEES.items():
        for alias in {key.lower(), emp["full_name"].lower(), *emp["aliases"]}:
            t = t.replace(alias, " ")
    words = re.findall(r"[a-zऀ-ॿ]+", t)
    return all(w in _REASSIGN_FILLER for w in words)


def _handle_edit(task_id: int, new_text: str) -> str:
    task = db.get_task(task_id)
    if not task:
        return f"Sir, Task #{task_id} nahi mila 🤔 'edit task <number> - naya detail' format mein bhejiye."
    if not new_text:
        return (
            f"Sir, Task #{task_id} mein kya badalna hai?\n"
            f"Aise bhejiye: edit task {task_id} - naya detail"
        )

    old_assignee = task["assignee_name"]
    mention = team.extract_mention(new_text)

    if _is_reassign_only(new_text):
        # Pure transfer ("task 3 Ramu ko de do") — keep title/message/category.
        new_assignee = mention or team.resolve_employee_name(
            next((w for w in new_text.replace("@~", " ").split() if team.resolve_employee_name(w)), None)
        )
        extracted = None
        updates: dict = {}
    else:
        # Content changed — re-extract fields from the corrected text; ignore its intent.
        extracted = extract_task(new_text)
        updates = {
            "title": extracted["title"],
            "message": new_text,
            "category": extracted["category"],
        }
        if extracted["due_date"]:
            updates["due_date"] = extracted["due_date"]
        new_assignee = mention or extracted["assignee"]

    reassigned = bool(new_assignee and new_assignee != old_assignee)
    if reassigned:
        user = db.get_user_by_name(new_assignee)
        if user:
            updates["assignee_id"] = user["id"]
    if not updates:
        return (
            f"Sir, Task #{task_id} mein koi badlav samajh nahi aaya 🙏\n"
            f"Aise bhejiye: edit task {task_id} - naya detail"
        )

    updated = db.update_task_fields(task_id, **updates)
    if not updated:
        return "Sir, task update karne mein dikkat aa gayi ⚠️ Kripya dobara try kariye."

    if settings.ANGC_NOTIFY_ASSIGNEES:
        if reassigned:
            old_user = db.get_user_by_name(old_assignee)
            if old_user and old_user.get("phone"):
                _send_whatsapp(
                    old_user["phone"],
                    f"ℹ️ Task #{task_id} ({task['title']}) ab aapke paas nahi hai — "
                    f"NG Sir ne {updated['assignee_name']} ji ko de diya hai.",
                )
            if updated.get("assignee_phone"):
                _send_whatsapp(
                    updated["assignee_phone"],
                    f"🔔 Task aapko transfer hua — NG Sir ki taraf se\n\n{_task_card(updated)}\n\n"
                    f"Complete hone par yahin reply karein: done {task_id}",
                )
        elif updated.get("assignee_phone"):
            _send_whatsapp(
                updated["assignee_phone"],
                f"✏️ Task #{task_id} update hua hai — NG Sir ki taraf se\n\n{_task_card(updated)}",
            )

    reply = f"Ji Sir 🙏 Task #{task_id} update kar diya hai.\n\n{_task_card(updated)}"
    if reassigned:
        reply += f"\n\n{old_assignee} ji se lekar {updated['assignee_name']} ji ko de diya gaya hai ✅"
    elif updated.get("assignee_phone"):
        reply += f"\n\n{updated['assignee_name']} ji ko update bhej diya gaya hai ✅"
    return reply


def _handle_delete(task_id: int) -> str:
    task = db.get_task(task_id)
    if not task:
        return f"Sir, Task #{task_id} nahi mila 🤔 Shayad pehle hi delete ho chuka hai."
    db.delete_task(task_id)
    if settings.ANGC_NOTIFY_ASSIGNEES and task.get("assignee_phone"):
        _send_whatsapp(
            task["assignee_phone"],
            f"❌ Task #{task_id} cancel ho gaya hai — NG Sir ki taraf se\n\n"
            f"📋 {task['title']}\n\nIs par kaam karne ki zaroorat nahi hai.",
        )
    return (
        f"Ji Sir 🙏 Task #{task_id} delete kar diya hai.\n\n"
        f"📋 {task['title']} ({task['assignee_name']})\n\n"
        f"{task['assignee_name']} ji ko inform kar diya gaya hai ✅"
    )


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
