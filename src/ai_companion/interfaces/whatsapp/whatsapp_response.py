import logging
import os
import sys
import asyncio
import re
from io import BytesIO
from typing import Dict

import httpx
from fastapi import APIRouter, Request, Response
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from ai_companion.graph import graph_builder
from ai_companion.graph.utils.helpers import chunk_message_by_sentences
from ai_companion.modules.image import ImageToText
from ai_companion.modules.speech import SpeechToText, TextToSpeech
from ai_companion.modules.saarthi.broker_intake import (
    is_broker,
    classify_broker_message,
    handle_broker_text,
    handle_broker_image,
    handle_broker_lead,
)
from ai_companion.settings import settings

# Configure logging with detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Global module instances (lazy initialization to avoid import-time errors)
_speech_to_text = None
_text_to_speech = None
_image_to_text = None

def get_speech_to_text():
    """Lazy initialization of SpeechToText module."""
    global _speech_to_text
    if _speech_to_text is None:
        _speech_to_text = SpeechToText()
    return _speech_to_text

def get_text_to_speech():
    """Lazy initialization of TextToSpeech module."""
    global _text_to_speech
    if _text_to_speech is None:
        _text_to_speech = TextToSpeech()
    return _text_to_speech

def get_image_to_text():
    """Lazy initialization of ImageToText module."""
    global _image_to_text
    if _image_to_text is None:
        _image_to_text = ImageToText()
    return _image_to_text

# Router for WhatsApp respo
whatsapp_router = APIRouter()

# WhatsApp API credentials
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

# Log startup configuration
logger.info("WhatsApp module initialized")
logger.info(f"WHATSAPP_TOKEN configured: {bool(WHATSAPP_TOKEN)}")
logger.info(f"WHATSAPP_PHONE_NUMBER_ID configured: {bool(WHATSAPP_PHONE_NUMBER_ID)}")
logger.info(f"SHORT_TERM_MEMORY_DB_PATH: {settings.SHORT_TERM_MEMORY_DB_PATH}")

if not WHATSAPP_TOKEN:
    logger.error("WHATSAPP_TOKEN environment variable is not set!")
if not WHATSAPP_PHONE_NUMBER_ID:
    logger.error("WHATSAPP_PHONE_NUMBER_ID environment variable is not set!")


def _finalize_whatsapp_text(text: str, max_chars: int = 1500) -> str:
    """
    Make WhatsApp text safe:
    - Keep within a safe char limit (<1600)
    - Avoid sending cut-off mid-sentence by trimming to the last sentence boundary
    """
    if not text:
        return ""

    text = " ".join(text.split()).strip()
    if not text:
        return ""

    # If the model stops mid-sentence (token cap), prefer last completed sentence even if short.
    sentence_end_re = re.compile(r"[.!?\n\u0964]")  # includes Hindi danda '।'

    def trim_to_last_sentence(s: str) -> str:
        matches = list(sentence_end_re.finditer(s))
        if not matches:
            return s.strip()
        last_end = matches[-1].end()
        trimmed = s[:last_end].strip()
        return trimmed if trimmed else s.strip()

    # First, enforce max chars (WhatsApp hard limit is ~1600 for text body)
    if len(text) > max_chars:
        text = text[:max_chars].strip()
        text = trim_to_last_sentence(text)
        return text

    # Otherwise, still ensure we don't end mid-sentence if a completed one exists.
    if not sentence_end_re.search(text[-1:]):
        trimmed = trim_to_last_sentence(text)
        if trimmed:
            return trimmed

    return text


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
        logger.debug("WA webhook payload keys: %s", list(data.keys()))
        logger.debug("Full payload: %s", data)
        
        if "entry" not in data:
            logger.error("Missing 'entry' in webhook payload")
            return Response(content="Invalid payload structure", status_code=400)
        
        change_value = data["entry"][0]["changes"][0]["value"]
        if "messages" in change_value:
            message = change_value["messages"][0]
            from_number = message["from"]
            session_id = from_number

            # WhatsApp profile name — passed to the graph so the CRM lead gets a name.
            wa_profile_name = None
            try:
                wa_profile_name = change_value.get("contacts", [{}])[0].get("profile", {}).get("name")
            except (IndexError, AttributeError):
                pass

            msg_type = message.get("type", "text")
            logger.info("Incoming message: type=%s from=%s", msg_type, from_number)

            # ---- Broker intake: bypass the lead-qualification graph ----
            if is_broker(from_number):
                logger.info("[broker] message from known broker %s", from_number)
                reply = ""

                if msg_type == "image":
                    # Images are always listing photos; caption may also carry listing text
                    caption = message["image"].get("caption", "").strip()
                    if caption:
                        # Save as listing first so the photo has something to attach to
                        await asyncio.to_thread(handle_broker_text, from_number, caption, wa_profile_name)
                    media_id = message["image"]["id"]
                    mime_type = message["image"].get("mime_type", "image/jpeg")
                    reply = await asyncio.to_thread(handle_broker_image, from_number, media_id, mime_type)
                    if not reply and caption:
                        reply = "✅ Listing saved! Send more photos to add them 📸"

                elif msg_type == "audio":
                    # Transcribe first, then classify
                    audio_bytes = await download_media(message["audio"]["id"])
                    transcribed = await get_speech_to_text().transcribe(audio_bytes)
                    logger.info("[broker] audio transcribed (%d chars): %s", len(transcribed), transcribed[:120])
                    msg_class = await asyncio.to_thread(classify_broker_message, transcribed)
                    logger.info("[broker] classified as: %s", msg_class)
                    if msg_class == "lead":
                        reply = await asyncio.to_thread(handle_broker_lead, from_number, transcribed, wa_profile_name)
                    else:
                        reply = await asyncio.to_thread(handle_broker_text, from_number, transcribed, wa_profile_name)

                elif msg_type == "text":
                    text = message["text"]["body"].strip()
                    msg_class = await asyncio.to_thread(classify_broker_message, text)
                    logger.info("[broker] text classified as: %s", msg_class)
                    if msg_class == "lead":
                        reply = await asyncio.to_thread(handle_broker_lead, from_number, text, wa_profile_name)
                    else:
                        reply = await asyncio.to_thread(handle_broker_text, from_number, text, wa_profile_name)

                if reply:
                    await send_response(from_number, reply, "text")
                return Response(content="Broker intake processed", status_code=200)
            # ---- End broker intake ----

            # Get user message and handle different message types
            content = ""

            if msg_type == "audio":
                content = await process_audio_message(message)
            elif msg_type == "image":
                # Get image caption if any
                content = message.get("image", {}).get("caption", "")
                # Download and analyze image
                image_bytes = await download_media(message["image"]["id"])
                try:
                    description = await get_image_to_text().analyze_image(
                        image_bytes,
                        "Please describe what you see in this image in the context of our conversation.",
                    )
                    content += f"\n[Image Analysis: {description}]"
                except Exception as e:
                    logger.warning(f"Failed to analyze image: {e}")
            else:
                content = message["text"]["body"]

            # Process message through the graph agent
            try:
                async with AsyncSqliteSaver.from_conn_string(settings.SHORT_TERM_MEMORY_DB_PATH) as short_term_memory:
                    logger.info("Opening database connection to: %s", settings.SHORT_TERM_MEMORY_DB_PATH)
                    graph = graph_builder.compile(checkpointer=short_term_memory)
                    logger.debug("Graph invoke: thread_id=%s", session_id)
                    await graph.ainvoke(
                        {
                            "messages": [
                                HumanMessage(
                                    content=content,
                                    additional_kwargs={
                                        "wa_type": message.get("type"),
                                        "wa_profile_name": wa_profile_name,
                                    },
                                )
                            ]
                        },
                        {"configurable": {"thread_id": session_id}},
                    )

                    # Get the workflow type and response from the state
                    output_state = await graph.aget_state(config={"configurable": {"thread_id": session_id}})
            except Exception as graph_error:
                logger.error(f"Graph processing error: {type(graph_error).__name__}: {graph_error}", exc_info=True)
                raise

            workflow = output_state.values.get("workflow", "conversation")
            
            # Extract ALL AI messages from the current conversation turn
            # The conversation_node creates multiple AIMessages when chunking responses
            all_messages = output_state.values["messages"]
            ai_messages = [msg for msg in all_messages if hasattr(msg, 'content') and msg.__class__.__name__ == 'AIMessage']
            
            # Get the most recent AI messages (from current turn)
            # Find the *last* user message to get only the AI response for this turn
            # (Using the first HumanMessage causes old AI chunks to be re-sent.)
            user_message_index = -1
            for i in range(len(all_messages) - 1, -1, -1):
                msg = all_messages[i]
                if hasattr(msg, "content") and msg.__class__.__name__ == "HumanMessage":
                    user_message_index = i
                    break
            
            # Get AI messages after the last user message
            recent_ai_messages = []
            if user_message_index >= 0:
                recent_ai_messages = [msg for msg in all_messages[user_message_index+1:] 
                                    if hasattr(msg, 'content') and msg.__class__.__name__ == 'AIMessage']
            else:
                # Fallback: get all AI messages
                recent_ai_messages = ai_messages

            # Always combine to a single response for WhatsApp to avoid duplicate/fragmented sends.
            # WhatsApp API has a 1600 char limit; send_response() will chunk only if needed.
            response_message = " ".join([msg.content.strip() for msg in recent_ai_messages if msg.content and msg.content.strip()]).strip()
            if not response_message:
                response_message = "Sorry—I couldn’t generate a response. Please try again."
            
            attachment_image_path = output_state.values.get("attachment_image_path")
            logger.info("Graph output: workflow=%s, ai_messages_count=%d", 
                       workflow, len(recent_ai_messages))

            # Handle different response types based on workflow
            if workflow == "audio":
                audio_buffer = output_state.values["audio_buffer"]
                success = await send_response(from_number, response_message, "audio", audio_buffer)
            elif workflow == "image":
                image_path = output_state.values["image_path"]
                with open(image_path, "rb") as f:
                    image_data = f.read()
                success = await send_response(from_number, response_message, "image", image_data)
            else:
                # For text workflow, send exactly one message (short + stable UX)
                if attachment_image_path:
                    try:
                        with open(attachment_image_path, "rb") as f:
                            image_data = f.read()
                        success = await send_response(from_number, response_message, "image", image_data)
                    except Exception:
                        logger.exception("Failed to attach QR image; falling back to text")
                        success = await send_response(from_number, response_message, "text")
                else:
                    success = await send_response(from_number, response_message, "text")

            if not success:
                return Response(content="Failed to send message", status_code=500)

            # Mirror the bot reply into the Saarthi CRM transcript (non-fatal).
            try:
                from ai_companion.modules.saarthi.client import get_saarthi_client

                saarthi = get_saarthi_client()
                if saarthi.configured and response_message:
                    await asyncio.to_thread(saarthi.record_outbound, from_number, response_message)
            except Exception as crm_error:
                logger.error(f"Failed to record outbound in Saarthi CRM (non-fatal): {crm_error}")

            return Response(content="Message processed", status_code=200)

        elif "statuses" in change_value:
            return Response(content="Status update received", status_code=200)

        else:
            return Response(content="Unknown event type", status_code=400)

    except KeyError as e:
        logger.error(f"Missing key in payload: {e}", exc_info=True)
        return Response(content=f"Invalid payload structure: {e}", status_code=400)
    except Exception as e:
        logger.error(f"Error processing message: {type(e).__name__}: {e}", exc_info=True)
        logger.error(f"Error type: {type(e)}")
        logger.error(f"Error details: {str(e)}")
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


async def process_audio_message(message: Dict) -> str:
    """Download and transcribe audio message."""
    audio_id = message["audio"]["id"]
    media_metadata_url = f"https://graph.facebook.com/v21.0/{audio_id}"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}

    async with httpx.AsyncClient() as client:
        metadata_response = await client.get(media_metadata_url, headers=headers)
        metadata_response.raise_for_status()
        metadata = metadata_response.json()
        download_url = metadata.get("url")

    # Download the audio file
    async with httpx.AsyncClient() as client:
        audio_response = await client.get(download_url, headers=headers)
        audio_response.raise_for_status()

    # Prepare for transcription
    audio_buffer = BytesIO(audio_response.content)
    audio_buffer.seek(0)
    audio_data = audio_buffer.read()

    return await get_speech_to_text().transcribe(audio_data)


async def send_response(
    from_number: str,
    response_text: str,
    message_type: str = "text",
    media_content: bytes = None,
) -> bool:
    """
    Send response to user via WhatsApp API.
    For text messages, automatically chunks long messages at sentence boundaries.
    """
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }

    if message_type in ["audio", "image"]:
        try:
            mime_type = "audio/mpeg" if message_type == "audio" else "image/png"
            media_buffer = BytesIO(media_content)
            media_id = await upload_media(media_buffer, mime_type)
            json_data = {
                "messaging_product": "whatsapp",
                "to": from_number,
                "type": message_type,
                message_type: {"id": media_id},
            }

            # Add caption for images
            if message_type == "image":
                json_data["image"]["caption"] = response_text
                
            logger.debug("WA send payload headers=%s body=%s", headers, json_data)
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_NUMBER_ID}/messages",
                    headers=headers,
                    json=json_data,
                )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Media upload failed, falling back to text: {e}")
            message_type = "text"

    # For text messages, send exactly one message and keep it safe.
    if message_type == "text":
        body = _finalize_whatsapp_text(response_text, max_chars=1500)
        if not body:
            body = "Sorry—I couldn’t generate a response. Please try again."

        json_data = {
            "messaging_product": "whatsapp",
            "to": from_number,
            "type": "text",
            "text": {"body": body},
        }

        logger.info(f"Sending single message ({len(body)} chars) to {from_number}")
        logger.debug("WA send body: %s...", body[:120])

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
    
    return False


async def upload_media(media_content: BytesIO, mime_type: str) -> str:
    """Upload media to WhatsApp servers."""
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    files = {"file": ("response.mp3", media_content, mime_type)}
    data = {"messaging_product": "whatsapp", "type": mime_type}

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_NUMBER_ID}/media",
            headers=headers,
            files=files,
            data=data,
        )
        result = response.json()

    if "id" not in result:
        raise Exception("Failed to upload media")
    return result["id"]
