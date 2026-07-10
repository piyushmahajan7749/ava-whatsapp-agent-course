"""Signed-cookie sessions for the ANGC dashboard (stdlib only)."""

import hashlib
import hmac
import logging
import secrets
import time

from fastapi import Request

from ai_companion.modules.angc import db
from ai_companion.settings import settings

logger = logging.getLogger(__name__)

COOKIE_NAME = "angc_session"
SESSION_TTL_SECONDS = 14 * 24 * 3600  # 2 weeks

_secret = settings.ANGC_SESSION_SECRET
if not _secret:
    _secret = secrets.token_hex(32)
    logger.warning(
        "[dashboard] ANGC_SESSION_SECRET not set — using a random secret; "
        "all logins will reset when the app restarts."
    )


def _sign(payload: str) -> str:
    return hmac.new(_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_session_token(user_id: int) -> str:
    expires = int(time.time()) + SESSION_TTL_SECONDS
    payload = f"{user_id}.{expires}"
    return f"{payload}.{_sign(payload)}"


def verify_session_token(token: str | None) -> int | None:
    """Return the user id if the token is valid and unexpired."""
    if not token:
        return None
    parts = token.split(".")
    if len(parts) != 3:
        return None
    payload = f"{parts[0]}.{parts[1]}"
    if not hmac.compare_digest(_sign(payload), parts[2]):
        return None
    try:
        user_id, expires = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if time.time() > expires:
        return None
    return user_id


def current_user(request: Request) -> dict | None:
    user_id = verify_session_token(request.cookies.get(COOKIE_NAME))
    if user_id is None:
        return None
    return db.get_user_by_id(user_id)
