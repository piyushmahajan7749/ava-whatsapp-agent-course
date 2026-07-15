"""ANGC Group team roster and task-category routing.

The bot serves Nikhil Gupta Sir (Director, ANGC Group). Tasks he sends on
WhatsApp are categorised and assigned to one of three human assistants.
Assignment priority: explicit @mention in the message > LLM-detected name >
the category's default assignee (first eligible member).
"""

import re

from ai_companion.settings import settings


def _normalize_phone(raw: str) -> str:
    """Digits only, with 91 country code for 10-digit Indian numbers."""
    digits = "".join(c for c in raw if c.isdigit())
    if len(digits) == 10:
        digits = "91" + digits
    return digits


# key = canonical short name used everywhere (LLM prompt, mentions, DB seed)
EMPLOYEES: dict[str, dict] = {
    "Sandhya": {
        "full_name": "Sandhya Dangi",
        "phone": _normalize_phone("91091 28734"),
        "email": "cspangcgroup@gmail.com",
        "aliases": ["sandhya", "sandhya dangi"],
    },
    "Ramu": {
        "full_name": "Ramu Saku",
        "phone": _normalize_phone("94754 55555"),
        "email": "ea-md@angcgroup.com",
        "aliases": ["ramu", "ramu saku"],
    },
    "Nikhil Uikey": {
        "full_name": "Nikhil Uikey",
        "phone": _normalize_phone("75090 02010"),
        "email": "cordination1angcgroup@gmail.com",
        "aliases": ["nikhil uikey", "uikey", "nikhil u"],
    },
}

# Category tag -> eligible assignees (first one is the default).
CATEGORIES: dict[str, list[str]] = {
    "WhatsApp Call Log": ["Sandhya"],
    "WhatsApp Message": ["Sandhya"],
    "Unsaved Number": ["Sandhya"],
    "WhatsApp Task": ["Sandhya", "Ramu", "Nikhil Uikey"],
    "Meeting Reminder": ["Ramu", "Nikhil Uikey"],
    "Core Team Task": ["Ramu", "Nikhil Uikey"],
    "Real-Time Task": ["Sandhya", "Ramu", "Nikhil Uikey"],
    "Daily To-Do": ["Sandhya", "Ramu", "Nikhil Uikey"],
    "Client Management": ["Sandhya", "Ramu", "Nikhil Uikey"],
    "Financial Management": ["Sandhya", "Ramu", "Nikhil Uikey"],
    "Vehicle Management": ["Ramu", "Nikhil Uikey"],
    "Event & Personal Reminder": ["Sandhya", "Ramu", "Nikhil Uikey"],
    "Expenses": ["Ramu", "Nikhil Uikey"],
    "Tour / Travel": ["Ramu", "Nikhil Uikey"],
    "Mahakal Darshan": ["Ramu", "Nikhil Uikey"],
    "Work Pendency Reminder": ["Nikhil Uikey"],
    "Staff Task": ["Nikhil Uikey"],
}

DEFAULT_CATEGORY = "Real-Time Task"

# Hints given to the LLM so it can tell categories apart.
CATEGORY_HINTS: dict[str, str] = {
    "WhatsApp Call Log": "log/follow up a WhatsApp or phone call (incoming/outgoing)",
    "WhatsApp Message": "send or follow up a WhatsApp message to someone",
    "Unsaved Number": "identify/save/handle an unknown or unsaved number",
    "WhatsApp Task": "a task received or to be coordinated over WhatsApp",
    "Meeting Reminder": "schedule, remind or prepare for a meeting",
    "Core Team Task": "task assigned to core team members",
    "Real-Time Task": "immediate ad-hoc task assignment (default)",
    "Daily To-Do": "daily to-do list item",
    "Client Management": "client case, client follow-up, case update, client coordination",
    "Financial Management": "credit/debit entries, payments, money tracking",
    "Vehicle Management": "driver, diesel, vehicle maintenance",
    "Event & Personal Reminder": "birthday/anniversary/marriage/medicine or personal reminder",
    "Expenses": "office/personal/other expense recording",
    "Tour / Travel": "tour plan, travel ticket, hotel booking",
    "Mahakal Darshan": "Mahakal darshan arrangement",
    "Work Pendency Reminder": "reminder about pending/overdue work",
    "Staff Task": "task about office staff (attendance, staff work)",
}


def get_director_set() -> set[str]:
    """Phone numbers (digits only) allowed to assign tasks (NG Sir)."""
    raw = (settings.DIRECTOR_PHONE_NUMBERS or "").strip()
    if not raw:
        return set()
    return {_normalize_phone(p) for p in raw.split(",") if p.strip()}


def is_director(phone: str) -> bool:
    return _normalize_phone(phone) in get_director_set()


def _db_roster() -> list[dict]:
    """All non-admin dashboard users (seeded assistants + admin-added employees).

    Lazy import: db imports this module at load time, so importing db at the
    top here would be circular.
    """
    from ai_companion.modules.angc import db

    try:
        return db.list_staff()
    except Exception:
        return []


def roster_names() -> list[str]:
    names = list(EMPLOYEES.keys())
    for u in _db_roster():
        if u["name"] not in names:
            names.append(u["name"])
    return names


def employee_by_phone(phone: str) -> str | None:
    """Return the employee name for a WhatsApp number, if it belongs to one."""
    digits = _normalize_phone(phone)
    for key, emp in EMPLOYEES.items():
        if emp["phone"] == digits:
            return key
    for u in _db_roster():
        if u["phone"] and u["phone"] == digits:
            return u["name"]
    return None


def resolve_employee_name(candidate: str | None) -> str | None:
    """Match a free-text name against the roster (case/whitespace tolerant)."""
    if not candidate:
        return None
    c = candidate.strip().lstrip("@~").strip().lower()
    if not c:
        return None
    for key, emp in EMPLOYEES.items():
        if c == key.lower() or c in emp["aliases"] or c == emp["full_name"].lower():
            return key
    for u in _db_roster():
        if c == u["name"].lower() or c == u["full_name"].lower():
            return u["name"]
    # partial: unique prefix match across the full roster
    names = roster_names()
    matches = [k for k in names if k.lower().startswith(c) or c.startswith(k.lower())]
    return matches[0] if len(matches) == 1 else None


_MENTION_RE = re.compile(r"@~?\u2060?([A-Za-z][A-Za-z .]{1,30})")


def extract_mention(text: str) -> str | None:
    """Find an @-mentioned team member (WhatsApp renders mentions as '@~Name')."""
    for match in _MENTION_RE.finditer(text or ""):
        resolved = resolve_employee_name(match.group(1))
        if resolved:
            return resolved
        # WhatsApp mentions may include a surname; try first token too
        first = match.group(1).split()[0]
        resolved = resolve_employee_name(first)
        if resolved:
            return resolved
    return None


def pick_assignee(category: str, hinted: str | None) -> str:
    """Final assignment: explicit hint wins (any roster member), else the category default."""
    if hinted and hinted in roster_names():
        return hinted
    eligible = CATEGORIES.get(category, CATEGORIES[DEFAULT_CATEGORY])
    return eligible[0]
