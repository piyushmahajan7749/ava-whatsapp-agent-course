"""Minimal RFC 5545 (iCalendar) feed builder — no external deps.

Generates a subscribable .ics feed of tasks-by-due-date. Calendar apps
(Google Calendar, Apple Calendar, Outlook) poll the feed URL periodically,
so the feed always reflects the latest task list/status without the user
re-subscribing.
"""

from datetime import datetime, timezone

from ai_companion.modules.angc.db import IST

_STATUS_LABEL = {"pending": "To Do", "in_progress": "In Progress", "in_review": "In Review", "done": "Done"}
_STATUS_EMOJI = {"pending": "⏳", "in_progress": "🔄", "in_review": "🔍", "done": "✅"}


def _fold(line: str) -> str:
    """RFC 5545 line folding: no physical line may exceed 75 octets."""
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line
    parts, chunk = [], b""
    for byte in encoded:
        chunk += bytes([byte])
        if len(chunk) == 74:
            parts.append(chunk)
            chunk = b""
    if chunk:
        parts.append(chunk)
    return ("\r\n ").join(p.decode("utf-8", errors="ignore") for p in parts)


def _escape(text: str) -> str:
    return (
        (text or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _today_ist_compact() -> str:
    return datetime.now(IST).strftime("%Y%m%d")


def build_ics(tasks: list[dict], calendar_name: str, feed_uid_domain: str = "angc-assistant.local") -> str:
    """tasks: rows from db.list_tasks() — only ones with a due_date are placed on the calendar."""
    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    today = _today_ist_compact()

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ANGC Group//Task Assistant//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(calendar_name)}",
        "X-WR-TIMEZONE:Asia/Kolkata",
        "REFRESH-INTERVAL;VALUE=DURATION:PT30M",
        "X-PUBLISHED-TTL:PT30M",
    ]

    for t in tasks:
        due = (t.get("due_date") or "").replace("-", "")
        if not due or len(due) != 8:
            continue
        status = t.get("status", "pending")
        overdue = due < today and status != "done"
        emoji = "⚠️" if overdue else _STATUS_EMOJI.get(status, "")
        assignee = f" — {t['assignee_name']}" if t.get("assignee_name") else ""
        summary = f"{emoji} {t['title']}{assignee}".strip()

        desc_bits = [
            f"Status: {_STATUS_LABEL.get(status, status)}",
            f"Category: {t.get('category', '')}",
        ]
        if t.get("assignee_name"):
            desc_bits.append(f"Assigned to: {t['assignee_name']}")
        if t.get("assigned_by"):
            desc_bits.append(f"Assigned by: {t['assigned_by']}")
        if t.get("message"):
            desc_bits.append("")
            desc_bits.append(t["message"])
        description = "\\n".join(_escape(b) for b in desc_bits)

        lines += [
            "BEGIN:VEVENT",
            f"UID:task-{t['id']}@{feed_uid_domain}",
            f"DTSTAMP:{now_stamp}",
            f"DTSTART;VALUE=DATE:{due}",
            f"SUMMARY:{_escape(summary)}",
            f"DESCRIPTION:{description}",
            f"CATEGORIES:{_escape(t.get('category', ''))}",
            "STATUS:CONFIRMED",
            f"LAST-MODIFIED:{now_stamp}",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
