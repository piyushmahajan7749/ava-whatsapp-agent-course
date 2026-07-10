# ANGC Assistant branch

WhatsApp executive assistant for **Nikhil Gupta Sir (NG Sir)**, Director of ANGC Group,
repurposed from the `saarthi` real-estate bot. Sir sends a task on WhatsApp (Hinglish,
often just a case name + `@mention`); the bot categorises it, assigns it to one of the
three assistants, saves it to the tasks DB, notifies the assignee on WhatsApp, and
confirms back respectfully in Hinglish.

## How it works

```
WhatsApp Cloud API webhook  →  /whatsapp_response (FastAPI)
        │
        ├─ NG Sir (DIRECTOR_PHONE_NUMBERS)
        │    ├─ TASK  → LLM extract {title, category, assignee} → SQLite → notify assignee
        │    ├─ QUERY → answer status/summary questions from the DB
        │    └─ OTHER → short courteous Hinglish reply
        │
        ├─ Team member (roster numbers)
        │    └─ commands: "tasks", "start <id>", "done <id>" (done → NG Sir notified)
        │
        └─ Anyone else → polite decline
```

- Assignment priority: **@mention in the message** (e.g. `@~Sandhya`) beats the LLM's
  guess, which beats the category's default assignee.
- Voice notes are transcribed (Groq Whisper) and treated as tasks.
- Images need a caption; the caption is the task.

## Team & categories

Roster and the category → assignee table live in
[team.py](src/ai_companion/modules/angc/team.py). Categories with a single owner
(e.g. *Work Pendency Reminder* → Nikhil Uikey, *WhatsApp Message* → Sandhya)
auto-assign; multi-owner categories default to the first eligible member unless
Sir mentions someone.

## Dashboard

Server-rendered pages on the same app (no separate frontend):

| URL | Who | What |
|---|---|---|
| `/login` | all | email + password |
| `/dashboard` | staff | own tasks: tag, message, date, status buttons |
| `/dashboard` | admin | team summary cards + recent tasks |
| `/admin/employee/{id}` | admin | one employee's full task list with filters |
| `/password` | all | change own password |

Seeded users (password = `ANGC_DEFAULT_PASSWORD`, default `Angc@2026` — everyone
should change it after first login):

- **Admin:** Nikhil Gupta — `ANGC_ADMIN_EMAIL` (default `director@angcgroup.com`)
- Sandhya Dangi — `cspangcgroup@gmail.com`
- Ramu Saku — `ea-md@angcgroup.com`
- Nikhil Uikey — `cordination1angcgroup@gmail.com`

## Storage

Single SQLite file (`ANGC_DB_PATH`, default `data/angc_tasks.db` → `/app/data/...`
in the container — mount persistent storage there, same as the memory DB was).
Tables: `users`, `tasks`. No external CRM dependency remains on this branch.

## Key files

- [task_intake.py](src/ai_companion/modules/angc/task_intake.py) — LLM extraction + director/staff flows
- [team.py](src/ai_companion/modules/angc/team.py) — roster, categories, mention resolution
- [db.py](src/ai_companion/modules/angc/db.py) — SQLite store, users, tasks, stats
- [whatsapp_response.py](src/ai_companion/interfaces/whatsapp/whatsapp_response.py) — webhook routing
- [routes.py](src/ai_companion/interfaces/dashboard/routes.py) — dashboard pages
- [tests/test_angc.py](tests/test_angc.py) — unit tests (`uv run --with pytest pytest tests/test_angc.py`)

## Run locally

```bash
uv run uvicorn ai_companion.interfaces.whatsapp.webhook_endpoint:app --port 8080
```

Required env (see `.env.example`): Azure OpenAI creds + deployment names,
WhatsApp Cloud API creds, `DIRECTOR_PHONE_NUMBERS`. Deployment to Azure Container
Apps is unchanged (`make azure-update`); remember to set the new ANGC_* env vars
and a real `ANGC_SESSION_SECRET` there.
