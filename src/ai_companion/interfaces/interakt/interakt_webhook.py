"""
Interakt Webhook Handler for WhatsApp messages.

Handles incoming webhooks from Interakt with:
- Webhook signature verification
- Payload parsing
- Staged rollout via ALLOWLIST_NUMBERS
- Kill switch via BOT_ENABLED
- Loop prevention (direction check, message ID tracking)
- Human handoff support
- Lumi onboarding flow integration
"""

import asyncio
import hashlib
import hmac
import json
import logging
import sys
from datetime import datetime, timedelta
from typing import Dict, Optional, Set

from fastapi import APIRouter, Request, Response

from ai_companion.settings import settings
from ai_companion.modules.interakt import get_interakt_client
from ai_companion.modules.lumi import get_user_state, delete_user_state, clear_all_user_states, OnboardingStage
from ai_companion.modules.lumi.flow_handler import get_flow_handler

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Router for Interakt webhooks
interakt_router = APIRouter(tags=["interakt"])

# Message tracking for loop prevention
_processed_message_ids: Dict[str, datetime] = {}
MESSAGE_TRACKING_WINDOW = timedelta(minutes=10)

# Per-user locks to prevent concurrent processing of messages from the same user.
# Without this, two simultaneous webhook calls for the same phone number can
# interleave state reads/writes, causing conversation history to be lost.
_user_locks: Dict[str, asyncio.Lock] = {}


def _get_user_lock(phone_number: str) -> asyncio.Lock:
    """Get or create an asyncio lock for a specific phone number."""
    if phone_number not in _user_locks:
        _user_locks[phone_number] = asyncio.Lock()
    return _user_locks[phone_number]


def _verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify webhook signature using HMAC-SHA256.

    Args:
        payload: Raw request body bytes
        signature: Signature from request header
        secret: Webhook secret key

    Returns:
        True if signature is valid
    """
    if not secret or not signature:
        return False

    # Compute expected signature
    expected_signature = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    # Compare signatures (timing-safe comparison)
    return hmac.compare_digest(expected_signature, signature)


def _get_allowlist_numbers() -> Set[str]:
    """Get allowlist numbers from settings."""
    allowlist_str = settings.ALLOWLIST_NUMBERS
    if not allowlist_str:
        return set()
    return {n.strip() for n in allowlist_str.split(",") if n.strip()}


def _is_bot_enabled() -> bool:
    """Check if bot is enabled (kill switch)."""
    return settings.BOT_ENABLED


def _normalize_phone_number(phone: str) -> str:
    """
    Normalize phone number to E.164 format without +.

    Args:
        phone: Phone number in various formats

    Returns:
        Normalized phone number (e.g., "919131036482")
    """
    # Remove all non-numeric characters
    normalized = "".join(c for c in phone if c.isdigit())
    return normalized


def _is_duplicate_message(message_id: str) -> bool:
    """Check if message was already processed."""
    now = datetime.now()

    # Clean old entries
    global _processed_message_ids
    _processed_message_ids = {
        mid: ts
        for mid, ts in _processed_message_ids.items()
        if now - ts < MESSAGE_TRACKING_WINDOW
    }

    if message_id in _processed_message_ids:
        return True

    _processed_message_ids[message_id] = now
    return False


@interakt_router.post("/interakt_webhook")
async def interakt_webhook_handler(request: Request) -> Response:
    """
    Handle incoming webhooks from Interakt.

    Interakt webhook payload structure (message_received):
    {
        "version": "1.0",
        "timestamp": "2022-06-03T05:57:57.496889",
        "type": "message_received",
        "data": {
            "customer": {
                "id": "uuid",
                "channel_phone_number": "917003705584",
                "traits": { "name": "...", ... }
            },
            "message": {
                "id": "uuid",
                "chat_message_type": "CustomerMessage",
                "message_status": "Sent",
                "message_content_type": "Text",
                "message": "Thank you",
                ...
            }
        }
    }
    """
    # KILL SWITCH CHECK - Return 200 OK but do nothing
    if not _is_bot_enabled():
        logger.info("[INTERAKT_WEBHOOK] Bot disabled (BOT_ENABLED=false)")
        return Response(content="OK (bot disabled)", status_code=200)

    try:
        # Get raw body for signature verification
        body = await request.body()

        # SIGNATURE VERIFICATION (if secret is configured)
        webhook_secret = settings.INTERAKT_WEBHOOK_SECRET
        if webhook_secret:
            # Interakt sends signature in X-Interakt-Signature header
            signature = request.headers.get("X-Interakt-Signature", "")
            if not signature:
                # Also check common alternative headers
                signature = request.headers.get("X-Hub-Signature-256", "")
                if signature and signature.startswith("sha256="):
                    signature = signature[7:]  # Remove "sha256=" prefix

            if not _verify_webhook_signature(body, signature, webhook_secret):
                logger.warning("[INTERAKT_WEBHOOK] Invalid webhook signature")
                return Response(content="Invalid signature", status_code=401)

            logger.debug("[INTERAKT_WEBHOOK] Signature verified")

        data = json.loads(body)
        logger.debug(f"[INTERAKT_WEBHOOK] Payload: {data}")

        # Check webhook type - only process incoming messages
        webhook_type = data.get("type", "")
        if webhook_type != "message_received":
            logger.debug(f"[INTERAKT_WEBHOOK] Ignoring type: {webhook_type}")
            return Response(content="OK (ignored)", status_code=200)

        # Extract message data
        message_data = data.get("data", {}).get("message", {})
        customer_data = data.get("data", {}).get("customer", {})

        message_id = message_data.get("id", "")
        message_text = message_data.get("message", "")
        message_type = message_data.get("chat_message_type", "")
        content_type = message_data.get("message_content_type", "")
        phone_number = customer_data.get("channel_phone_number", "")
        customer_name = customer_data.get("traits", {}).get("name", "")

        # Normalize phone number (E.164 without +)
        phone_number = _normalize_phone_number(phone_number)

        logger.info(
            f"[INTERAKT_WEBHOOK] Message: type={message_type}, "
            f"from={phone_number}, content_type={content_type}"
        )

        # LOOP PREVENTION: Only process customer messages
        if message_type != "CustomerMessage":
            logger.info(f"[INTERAKT_WEBHOOK] Ignoring message type: {message_type}")
            return Response(content="OK (not customer message)", status_code=200)

        # LOOP PREVENTION: Check for duplicate
        if message_id and _is_duplicate_message(message_id):
            logger.info(f"[INTERAKT_WEBHOOK] Duplicate message: {message_id[:20]}")
            return Response(content="OK (duplicate)", status_code=200)

        # STAGED ROLLOUT: Check allowlist
        allowlist = _get_allowlist_numbers()
        if allowlist and phone_number not in allowlist:
            logger.info(f"[INTERAKT_WEBHOOK] {phone_number} not in allowlist")
            return Response(content="OK (not in allowlist)", status_code=200)

        # Support text, button, and list messages
        supported_types = ("Text", "text", "Button", "button", "List", "list")
        if content_type not in supported_types:
            logger.info(f"[INTERAKT_WEBHOOK] Unsupported content: {content_type}")
            return Response(content="OK (unsupported content)", status_code=200)

        # For button/list replies, extract the selection title
        is_button = content_type.lower() in ("button", "list")
        if is_button:
            message_text = (
                message_data.get("selectedOption", {}).get("title", "")
                or message_data.get("button_reply", {}).get("title", "")
                or message_data.get("list_reply", {}).get("title", "")
                or message_text
            )

        # Serialize all processing for the same phone number to prevent
        # concurrent state reads/writes from corrupting conversation history.
        async with _get_user_lock(phone_number):
            # Check if user is in handoff state - don't respond
            user_state = get_user_state(phone_number)
            if user_state and user_state.stage == OnboardingStage.HUMAN_HANDOFF:
                logger.info(f"[INTERAKT_WEBHOOK] {phone_number} in human handoff - not responding")
                return Response(content="OK (human handoff)", status_code=200)

            # Process with Lumi flow
            flow_handler = get_flow_handler()

            flow_response = await flow_handler.handle_message(
                phone_number=phone_number,
                message_text=message_text,
                is_button_response=is_button,
            )

            # If crisis or handoff, log but don't send AI response
            if flow_response.is_crisis:
                logger.warning(f"[INTERAKT_WEBHOOK] CRISIS for {phone_number}")
                # Send crisis resources, then stop AI responses
                await _send_messages(phone_number, flow_response.messages)
                return Response(content="OK (crisis - handed off)", status_code=200)

            if flow_response.is_handoff:
                logger.info(f"[INTERAKT_WEBHOOK] Handoff for {phone_number}: {flow_response.handoff_reason}")
                # Send handoff message, then stop AI responses
                await _send_messages(phone_number, flow_response.messages)
                return Response(content="OK (handed off)", status_code=200)

            # Send responses
            if flow_response.messages:
                await _send_messages(phone_number, flow_response.messages, flow_response.buttons)

            # Send friction message separately (if present)
            if flow_response.friction_message:
                await _send_messages(
                    phone_number,
                    [flow_response.friction_message],
                    flow_response.friction_buttons,
                )

        logger.info(f"[INTERAKT_WEBHOOK] Processed message for {phone_number}")
        return Response(content="OK", status_code=200)

    except Exception as e:
        logger.error(f"[INTERAKT_WEBHOOK] Error: {e}", exc_info=True)
        # Always return 200 to prevent Interakt from disabling webhook
        return Response(content="OK (error logged)", status_code=200)


async def _send_messages(
    phone_number: str,
    messages: list,
    buttons: Optional[list] = None,
) -> bool:
    """
    Send messages via Interakt.

    Sends all messages as plain text except the last one, which is sent
    with interactive buttons if buttons are provided.

    Args:
        phone_number: User's phone number
        messages: List of message strings to send
        buttons: Optional button options for last message

    Returns:
        True if all messages sent successfully
    """
    interakt_client = get_interakt_client()
    if not interakt_client:
        logger.error("[INTERAKT_WEBHOOK] Interakt client not configured")
        return False

    try:
        if not messages:
            return True

        # Send all messages as plain text
        for msg in messages[:-1]:
            await interakt_client.send_text_message(phone_number, msg)

        # For the last message, append button options as text if provided
        last_message = messages[-1]
        if buttons and len(buttons) > 0:
            options_text = "\n".join(
                f"• {btn['title']}" for btn in buttons
            )
            last_message = f"{last_message}\n\n{options_text}"

        await interakt_client.send_text_message(phone_number, last_message)

        return True

    except Exception as e:
        logger.error(f"[INTERAKT_WEBHOOK] Send error: {e}")
        return False


@interakt_router.get("/interakt_webhook")
async def interakt_webhook_verify(request: Request) -> Response:
    """
    Handle webhook verification (if Interakt requires it).

    Some webhook providers send a GET request for verification.
    """
    logger.info("[INTERAKT_WEBHOOK] Verification GET request received")
    return Response(content="OK", status_code=200)


@interakt_router.get("/interakt_health")
async def interakt_health_check() -> dict:
    """Health check endpoint for Interakt integration."""
    interakt_client = get_interakt_client()
    return {
        "status": "healthy",
        "bot_enabled": _is_bot_enabled(),
        "interakt_configured": interakt_client is not None,
        "allowlist_active": bool(_get_allowlist_numbers()),
        "allowlist_count": len(_get_allowlist_numbers()),
    }


@interakt_router.post("/lumi_reset/{phone_number}")
async def lumi_reset_user(phone_number: str) -> dict:
    """Reset Lumi conversation state for a phone number (for testing)."""
    phone_number = _normalize_phone_number(phone_number)
    state = get_user_state(phone_number)
    if not state:
        return {"status": "not_found", "phone_number": phone_number}

    deleted = delete_user_state(phone_number)
    logger.info(f"[INTERAKT_WEBHOOK] Reset user state for {phone_number}: {deleted}")
    return {
        "status": "reset" if deleted else "error",
        "phone_number": phone_number,
        "previous_stage": state.stage.value if state.stage else None,
    }


@interakt_router.post("/lumi_clear_all")
async def lumi_clear_all() -> dict:
    """Clear ALL Lumi conversation states. Gives every user a fresh start."""
    count = clear_all_user_states()
    logger.info(f"[INTERAKT_WEBHOOK] Cleared all conversations: {count}")
    return {
        "status": "cleared",
        "conversations_deleted": count,
    }
