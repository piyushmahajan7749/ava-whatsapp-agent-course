import logging
import os
import sys
import asyncio
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
from ai_companion.modules.chatwoot import get_chatwoot_client
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

# Global module instances
speech_to_text = SpeechToText()
text_to_speech = TextToSpeech()
image_to_text = ImageToText()

# Chatwoot client (optional - only if configured)
chatwoot_client = get_chatwoot_client()

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

            # Get user message and handle different message types
            content = ""
            logger.info("Incoming message: type=%s from=%s", message.get("type"), from_number)

            if message["type"] == "audio":
                content = await process_audio_message(message)
            elif message["type"] == "image":
                # Get image caption if any
                content = message.get("image", {}).get("caption", "")
                # Download and analyze image
                image_bytes = await download_media(message["image"]["id"])
                try:
                    description = await image_to_text.analyze_image(
                        image_bytes,
                        "Please describe what you see in this image in the context of our conversation.",
                    )
                    content += f"\n[Image Analysis: {description}]"
                except Exception as e:
                    logger.warning(f"Failed to analyze image: {e}")
            else:
                content = message["text"]["body"]

            # Forward message to Chatwoot (if configured)
            chatwoot_conversation_id = None
            if chatwoot_client:
                try:
                    logger.info(f"Forwarding message to Chatwoot from {from_number}")
                    contact_id, chatwoot_conversation_id = await chatwoot_client.forward_incoming_message(
                        phone_number=from_number,
                        message_text=content,
                    )
                    logger.info(f"Message forwarded to Chatwoot conversation: {chatwoot_conversation_id}")
                except Exception as chatwoot_error:
                    logger.error(f"Failed to forward to Chatwoot (non-fatal): {chatwoot_error}")
                    # Continue processing even if Chatwoot fails

            # Process message through the graph agent
            try:
                async with AsyncSqliteSaver.from_conn_string(settings.SHORT_TERM_MEMORY_DB_PATH) as short_term_memory:
                    logger.info("Opening database connection to: %s", settings.SHORT_TERM_MEMORY_DB_PATH)
                    graph = graph_builder.compile(checkpointer=short_term_memory)
                    logger.debug("Graph invoke: thread_id=%s", session_id)
                    await graph.ainvoke(
                        {"messages": [HumanMessage(content=content, additional_kwargs={"wa_type": message.get("type")})]},
                        {"configurable": {"thread_id": session_id}},
                    )

                    # Get the workflow type and response from the state
                    output_state = await graph.aget_state(config={"configurable": {"thread_id": session_id}})
            except Exception as graph_error:
                logger.error(f"Graph processing error: {type(graph_error).__name__}: {graph_error}", exc_info=True)
                raise

            workflow = output_state.values.get("workflow", "conversation")
            response_message = output_state.values["messages"][-1].content
            attachment_image_path = output_state.values.get("attachment_image_path")
            logger.info("Graph output: workflow=%s, response_preview='%s'", workflow, response_message[:200])

            # Check if AI should respond (Chatwoot handoff detection)
            should_ai_reply = True
            if chatwoot_client and chatwoot_conversation_id:
                try:
                    should_ai_reply = await chatwoot_client.should_ai_respond(chatwoot_conversation_id)
                    if not should_ai_reply:
                        logger.info(f"Human has taken over conversation {chatwoot_conversation_id} - skipping AI reply")
                        return Response(content="Message processed (human handling)", status_code=200)
                except Exception as handoff_error:
                    logger.error(f"Error checking handoff status (continuing with AI): {handoff_error}")
                    should_ai_reply = True

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

            # Forward AI reply to Chatwoot (if configured and message sent successfully)
            if chatwoot_client and chatwoot_conversation_id and success:
                try:
                    await chatwoot_client.forward_ai_reply(
                        conversation_id=chatwoot_conversation_id,
                        reply_text=response_message,
                    )
                    logger.info(f"AI reply forwarded to Chatwoot conversation: {chatwoot_conversation_id}")
                except Exception as chatwoot_error:
                    logger.error(f"Failed to forward AI reply to Chatwoot (non-fatal): {chatwoot_error}")

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

    return await speech_to_text.transcribe(audio_data)


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

    # For text messages, chunk at sentence boundaries to avoid overwhelming users
    if message_type == "text":
        chunks = chunk_message_by_sentences(response_text, max_length=600)
        logger.info(f"Sending {len(chunks)} message chunk(s) to {from_number}")
        
        all_success = True
        for i, chunk in enumerate(chunks):
            json_data = {
                "messaging_product": "whatsapp",
                "to": from_number,
                "type": "text",
                "text": {"body": chunk},
            }
            
            logger.debug(f"WA send chunk {i+1}/{len(chunks)}: {chunk[:100]}...")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_NUMBER_ID}/messages",
                    headers=headers,
                    json=json_data,
                )
            
            if response.status_code != 200:
                logger.error(f"Failed to send chunk {i+1}/{len(chunks)}: {response.text}")
                all_success = False
            
            # Small delay between chunks to ensure proper ordering
            if i < len(chunks) - 1:
                await asyncio.sleep(0.5)
        
        return all_success
    
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
