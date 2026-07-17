"""In-process scheduler for the ANGC assistant.

A single asyncio task started on app startup. It wakes on a fixed interval and
runs due jobs by the IST wall clock. All jobs are idempotent (guarded by the
DB job ledger), so a double wake, a restart, or a second replica never
double-sends. DB work runs in a thread so it never blocks the event loop.
"""

import asyncio
import logging
from datetime import datetime

from ai_companion.modules.angc import notify
from ai_companion.modules.angc.db import IST
from ai_companion.settings import settings

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None

# How many hours after the target hour a digest may still fire (so a late app
# start at, say, 3pm doesn't send a "morning" digest, but a brief blip does).
_DIGEST_WINDOW_H = 4


def _run_due_jobs() -> None:
    """Synchronous — runs in a worker thread. Each job self-dedupes."""
    now = datetime.now(IST)
    today = now.date().isoformat()

    try:
        notify.materialize_recurring()
    except Exception:
        logger.exception("[scheduler] recurring materialization failed")

    try:
        notify.run_overdue_sweep()
    except Exception:
        logger.exception("[scheduler] overdue sweep failed")

    from ai_companion.modules.angc import db

    morning = settings.ANGC_MORNING_DIGEST_HOUR
    if morning <= now.hour < morning + _DIGEST_WINDOW_H and db.claim_job(f"digest:morning:{today}"):
        try:
            notify.run_digest("morning")
        except Exception:
            logger.exception("[scheduler] morning digest failed")

    evening = settings.ANGC_EVENING_DIGEST_HOUR
    if evening <= now.hour < evening + _DIGEST_WINDOW_H and db.claim_job(f"digest:evening:{today}"):
        try:
            notify.run_digest("evening")
        except Exception:
            logger.exception("[scheduler] evening digest failed")


async def _loop() -> None:
    interval = max(60, settings.ANGC_SCHEDULER_INTERVAL_SECONDS)
    logger.info("[scheduler] started — interval %ds", interval)
    # Small initial delay so startup finishes before the first sweep.
    await asyncio.sleep(10)
    while True:
        try:
            await asyncio.to_thread(_run_due_jobs)
        except Exception:
            logger.exception("[scheduler] job cycle error")
        await asyncio.sleep(interval)


def start() -> None:
    global _task
    if not settings.ANGC_SCHEDULER_ENABLED:
        logger.info("[scheduler] disabled via ANGC_SCHEDULER_ENABLED")
        return
    if _task and not _task.done():
        return
    _task = asyncio.create_task(_loop())


def stop() -> None:
    global _task
    if _task and not _task.done():
        _task.cancel()
    _task = None
