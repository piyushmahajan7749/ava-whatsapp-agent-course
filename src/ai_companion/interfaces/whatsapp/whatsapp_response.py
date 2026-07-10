"""ANGC executive-assistant WhatsApp webhook.

Routing:
- NG Sir (DIRECTOR_PHONE_NUMBERS)  → task intake / status queries
- Team members (Sandhya/Ramu/Nikhil Uikey) → simple task commands
- Anyone else → polite decline (this is a private assistant)
"""

import asyncio
import logging
import os
import re
import sys
from collections import deque

import httpx
from fastapi import APIRouter, Request, Response

from ai_companion.modules.angc import task_intake, team
from ai_companion.modules.speech import SpeechToText
from ai_companion.settings import settings

# Webhook de-duplication: Meta retries the webhook if we don't return 200 fast
# enough, which would re-run intake and double-create tasks. Track
# recently-seen WhatsApp message ids and skip repeats.
_PROCESSED_MESSAGE_IDS: deque = deque(maxlen=3000)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

_speech_to_text = None


def get_speech_to_text():
    """Lazy initialization of SpeechToText module."""
    global _speech_to_text
    if _speech_to_text is None:
        _speech_to_text = SpeechToText()
    return _speech_to_text


whatsapp_router = APIRouter()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

logger.info("WhatsApp module initialized (ANGC assistant)")
logger.info(f"WHATSAPP_TOKEN configured: {bool(WHATSAPP_TOKEN)}")
logger.info(f"WHATSAPP_PHONE_NUMBER_ID configured: {bool(WHATSAPP_PHONE_NUMBER_ID)}")
logger.info(f"DIRECTOR_PHONE_NUMBERS configured: {bool(settings.DIRECTOR_PHONE_NUMBERS)}")

if not WHATSAPP_TOKEN:
    logger.error("WHATSAPP_TOKEN environment variable is not set!")
if not WHATSAPP_PHONE_NUMBER_ID:
    logger.error("WHATSAPP_PHONE_NUMBER_ID environment variable is not set!")
if not settings.DIRECTOR_PHONE_NUMBERS:
    logger.error("DIRECTOR_PHONE_NUMBERS is not set — no one can assign tasks!")

_UNKNOWN_SENDER_REPLY = (
    "Namaste 🙏 Yeh ANGC Group ka private executive assistant hai. "
    "Aapka number hamari team list mein nahi hai, isliye main aapki request "
    "process nahi kar sakta. Kripya ANGC office se sampark karein."
)


def _finalize_whatsapp_text(text: str, max_chars: int = 1500) -> str:
    """
    Make WhatsApp text safe:
    - Keep within a safe char limit (<1600)
    - Avoid sending cut-off mid-sentence by trimming to the last sentence boundary
    """
    if not text:
        return ""

    # Collapse runs of spaces/tabs but PRESERVE line breaks so a list of tasks
    # stays readable (one per line) instead of one flat blob.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.strip() for line in text.split("\n")).strip()
    if not text:
        return ""

    if len(text) <= max_chars:
        return text

    # If we must cut, prefer the last completed sentence (Hindi danda aware).
    sentence_end_re = re.compile(r"[.!?\n।]")
    cut = text[:max_chars].strip()
    matches = list(sentence_end_re.finditer(cut))
    if matches:
        cut = cut[: matches[-1].end()].strip()
    return cut


@whatsapp_router.api_route("/whatsapp_response", methods=["GET", "POST"])
async def whatsapp_handler(request: Request) -> Response:
    """Handles incoming messages and status updates from the WhatsApp Cloud API."""

    if request.method == "GET":
        params = request.query_params
        if params.get("hub.verify_token") == os.getenv("WHATSAPP_VERIFY_TOKEN"):
            return Response(content=params.get("hub.challenge"), status_code=200)
        return Response(content="Verification token mismatch", status_code=403)

    try:
        data = await request.json()

        if "entry" not in data:
            logger.error("Missing 'entry' in webhook payload")
            return Response(content="Invalid payload structure", status_code=400)

        change_value = data["entry"][0]["changes"][0]["value"]

        if "statuses" in change_value:
            return Response(content="Status update received", status_code=200)
        if "messages" not in change_value:
            return Response(content="Unknown event type", status_code=400)

        message = change_value["messages"][0]
        from_number = message["from"]

        # Skip duplicate webhook deliveries (Meta retries).
        message_id = message.get("id")
        if message_id:
            if message_id in _PROCESSED_MESSAGE_IDS:
                logger.info("Duplicate webhook for message %s — ignoring", message_id)
                return Response(content="Duplicate ignored", status_code=200)
            _PROCESSED_MESSAGE_IDS.append(message_id)

        msg_type = message.get("type", "text")
        logger.info("Incoming message: type=%s from=%s", msg_type, from_number)

        # ---- Director (NG Sir): task assignment / queries ----
        if team.is_director(from_number):
            reply = ""

            if msg_type == "audio":
                try:
                    audio_bytes = await download_media(message["audio"]["id"])
                    transcribed = await get_speech_to_text().transcribe(audio_bytes)
                    logger.info("[angc] voice note transcribed (%d chars)", len(transcribed))
                    reply = await asyncio.to_thread(task_intake.handle_director_message, transcribed)
                except Exception:
                    logger.exception("[angc] voice note handling failed")
                    reply = "Sir, voice note process nahi ho paya ⚠️ Kripya text mein bhej dijiye."

            elif msg_type == "image":
                caption = message.get("image", {}).get("caption", "").strip()
                if caption:
                    reply = await asyncio.to_thread(task_intake.handle_director_message, caption)
                else:
                    reply = (
                        "Sir, photo mil gayi 🙏 Kripya iske saath caption mein task likh kar "
                        "bhejiye taaki main use team ko assign kar sakun."
                    )

            elif msg_type == "text":
                text = message["text"]["body"].strip()
                reply = await asyncio.to_thread(task_intake.handle_director_message, text)

            else:
                reply = "Sir, is type ka message abhi support nahi hai. Text ya voice note bhejiye 🙏"

            if reply:
                await send_response(from_number, reply)
            return Response(content="Director message processed", status_code=200)

        # ---- Team members: task commands ----
        if team.employee_by_phone(from_number):
            if msg_type == "text":
                text = message["text"]["body"].strip()
            elif msg_type == "audio":
                try:
                    audio_bytes = await download_media(message["audio"]["id"])
                    text = await get_speech_to_text().transcribe(audio_bytes)
                except Exception:
                    logger.exception("[angc] staff voice note failed")
                    text = ""
            else:
                text = ""
            reply = await asyncio.to_thread(task_intake.handle_staff_message, from_number, text)
            if reply:
                await send_response(from_number, reply)
            return Response(content="Staff message processed", status_code=200)

        # ---- Unknown sender ----
        logger.info("Message from unknown number %s — sending polite decline", from_number)
        await send_response(from_number, _UNKNOWN_SENDER_REPLY)
        return Response(content="Unknown sender handled", status_code=200)

    except KeyError as e:
        logger.error(f"Missing key in payload: {e}", exc_info=True)
        return Response(content=f"Invalid payload structure: {e}", status_code=400)
    except Exception as e:
        logger.error(f"Error processing message: {type(e).__name__}: {e}", exc_info=True)
        return Response(content=f"Internal server error: {type(e).__name__}", status_code=500)


async def download_media(media_id: str) -> bytes:
    """Download media from WhatsApp."""
    media_metadata_url = f"https://graph.facebook.com/v21.0/{media_id}"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}

    async with httpx.AsyncClient() as client:
        metadata_response = await client.get(media_metadata_url, headers=headers)
        metadata_response.raise_for_status()
        metadata = metadata_response.json()
        download_url = metadata.get("url")

        media_response = await client.get(download_url, headers=headers)
        media_response.raise_for_status()
        return media_response.content


async def send_response(from_number: str, response_text: str) -> bool:
    """Send a single safe text message via the WhatsApp Cloud API."""
    body = _finalize_whatsapp_text(response_text, max_chars=1500)
    if not body:
        return False

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    json_data = {
        "messaging_product": "whatsapp",
        "to": from_number,
        "type": "text",
        "text": {"body": body},
    }

    logger.info(f"Sending message ({len(body)} chars) to {from_number}")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_NUMBER_ID}/messages",
            headers=headers,
            json=json_data,
        )

    if response.status_code != 200:
        logger.error(f"Failed to send message: {response.text}")
        return False
    return True
