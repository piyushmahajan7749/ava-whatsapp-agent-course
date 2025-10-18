"""
Improved WhatsApp Response Handler

This is an enhanced version of the WhatsApp webhook handler with:
- Immediate read receipts (double blue checkmarks)
- Emoji reactions based on intent
- Async/background processing
- Better error handling
- Message deduplication
- Status updates for long operations

To use this improved version:
1. Rename the current whatsapp_response.py to whatsapp_response_old.py
2. Rename this file to whatsapp_response.py
3. Restart the WhatsApp service
"""

import logging
import os
import sys
import asyncio
from io import BytesIO
from typing import Dict, Optional
from enum import Enum

import httpx
from fastapi import APIRouter, Request, Response
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from ai_companion.graph import graph_builder
from ai_companion.graph.utils.helpers import chunk_message_by_sentences
from ai_companion.modules.image import ImageToText
from ai_companion.modules.speech import SpeechToText, TextToSpeech
from ai_companion.settings import settings
from ai_companion.interfaces.whatsapp.status_indicators import (
    mark_message_as_read,
    react_to_message,
    get_intent_emoji,
    is_duplicate_message,
    mark_processing_start,
    mark_processing_complete,
    start_cleanup_task,
    send_typing_indicator,
    send_processing_status,
)

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

# Router for WhatsApp response
whatsapp_router = APIRouter()

# WhatsApp API credentials
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

# Feature flags (can be set via environment variables)
ENABLE_READ_RECEIPTS = os.getenv("ENABLE_READ_RECEIPTS", "true").lower() == "true"
ENABLE_EMOJI_REACTIONS = os.getenv("ENABLE_EMOJI_REACTIONS", "true").lower() == "true"
ENABLE_ASYNC_PROCESSING = os.getenv("ENABLE_ASYNC_PROCESSING", "true").lower() == "true"
ENABLE_STATUS_UPDATES = os.getenv("ENABLE_STATUS_UPDATES", "true").lower() == "true"
ENABLE_TYPING_INDICATORS = os.getenv("ENABLE_TYPING_INDICATORS", "true").lower() == "true"
MESSAGE_DEDUP_WINDOW = int(os.getenv("MESSAGE_DEDUP_WINDOW_SECONDS", "10"))

# Log startup configuration
logger.info("WhatsApp module initialized (IMPROVED VERSION)")
logger.info(f"WHATSAPP_TOKEN configured: {bool(WHATSAPP_TOKEN)}")
logger.info(f"WHATSAPP_PHONE_NUMBER_ID configured: {bool(WHATSAPP_PHONE_NUMBER_ID)}")
logger.info(f"SHORT_TERM_MEMORY_DB_PATH: {settings.SHORT_TERM_MEMORY_DB_PATH}")
logger.info(f"Feature flags: read_receipts={ENABLE_READ_RECEIPTS}, reactions={ENABLE_EMOJI_REACTIONS}, async={ENABLE_ASYNC_PROCESSING}")

if not WHATSAPP_TOKEN:
    logger.error("WHATSAPP_TOKEN environment variable is not set!")
if not WHATSAPP_PHONE_NUMBER_ID:
    logger.error("WHATSAPP_PHONE_NUMBER_ID environment variable is not set!")


class ErrorCategory(str, Enum):
    """Error categories for user-friendly messaging."""
    NETWORK = "network"
    RATE_LIMIT = "rate_limit"
    PROCESSING = "processing"
    INVALID_INPUT = "invalid_input"
    CALENDAR_ERROR = "calendar_error"


ERROR_MESSAGES = {
    ErrorCategory.NETWORK: "I'm having trouble connecting to my services. Please try again in a moment. 🔄",
    ErrorCategory.RATE_LIMIT: "I'm receiving a lot of requests right now. Please wait a moment and try again. ⏳",
    ErrorCategory.PROCESSING: "I encountered an issue processing your request. Could you try rephrasing your message? 🤔",
    ErrorCategory.INVALID_INPUT: "I'm not sure I understood that correctly. Could you provide more details? 💭",
    ErrorCategory.CALENDAR_ERROR: "I'm having trouble accessing the calendar right now. Please try your booking again in a few minutes. 📅",
}


def categorize_error(error: Exception) -> ErrorCategory:
    """Categorize error for user-friendly messaging."""
    error_str = str(error).lower()
    error_type = type(error).__name__.lower()
    
    if "timeout" in error_str or "connection" in error_str:
        return ErrorCategory.NETWORK
    elif "rate" in error_str or "429" in error_str:
        return ErrorCategory.RATE_LIMIT
    elif "calendar" in error_str or "google" in error_str:
        return ErrorCategory.CALENDAR_ERROR
    else:
        return ErrorCategory.PROCESSING


async def send_error_response(from_number: str, error: Exception):
    """Send user-friendly error message based on error category."""
    category = categorize_error(error)
    message = ERROR_MESSAGES.get(category, ERROR_MESSAGES[ErrorCategory.PROCESSING])
    
    logger.error(f"Sending error response to {from_number}: {category} - {error}")
    await send_response(from_number, message, "text")


@whatsapp_router.api_route("/whatsapp_response", methods=["GET", "POST"])
async def whatsapp_handler(request: Request) -> Response:
    """
    Handles incoming messages and status updates from the WhatsApp Cloud API.
    
    Improved version with:
    - Immediate read receipts
    - Emoji reactions
    - Async processing
    - Message deduplication
    """

    if request.method == "GET":
        params = request.query_params
        if params.get("hub.verify_token") == os.getenv("WHATSAPP_VERIFY_TOKEN"):
            return Response(content=params.get("hub.challenge"), status_code=200)
        return Response(content="Verification token mismatch", status_code=403)

    try:
        data = await request.json()
        logger.debug("WA webhook payload keys: %s", list(data.keys()))
        
        if "entry" not in data:
            logger.error("Missing 'entry' in webhook payload")
            return Response(content="Invalid payload structure", status_code=400)
        
        change_value = data["entry"][0]["changes"][0]["value"]
        
        if "messages" in change_value:
            message = change_value["messages"][0]
            message_id = message["id"]
            from_number = message["from"]
            message_type = message.get("type")
            
            logger.info(f"📨 Incoming message: type={message_type} from={from_number} id={message_id[:20]}...")
            
            # Check for duplicate messages
            if is_duplicate_message(from_number, message_id, MESSAGE_DEDUP_WINDOW):
                logger.info(f"🔁 Ignoring duplicate message {message_id[:20]}... from {from_number}")
                return Response(content="Duplicate message ignored", status_code=200)
            
            # Check if already processing (race condition protection)
            if not mark_processing_start(message_id):
                logger.warning(f"⚠️  Message {message_id[:20]}... already being processed")
                return Response(content="Already processing", status_code=200)
            
            # IMMEDIATE FEEDBACK: Mark as read (happens in parallel, fire-and-forget)
            if ENABLE_READ_RECEIPTS:
                asyncio.create_task(
                    mark_message_as_read(message_id, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_TOKEN)
                )
            
            # Process message (async or sync based on configuration)
            if ENABLE_ASYNC_PROCESSING:
                # Queue for background processing, return immediately
                asyncio.create_task(
                    process_message_async(message, from_number, message_id)
                )
                return Response(content="Message queued for processing", status_code=200)
            else:
                # Original synchronous processing
                try:
                    await process_message_sync(message, from_number, message_id)
                    return Response(content="Message processed", status_code=200)
                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
                    mark_processing_complete(message_id)
                    return Response(content=f"Processing error: {type(e).__name__}", status_code=500)

        elif "statuses" in change_value:
            # Status updates (delivered, read, etc.)
            logger.debug(f"Status update received: {change_value['statuses']}")
            return Response(content="Status update received", status_code=200)

        else:
            logger.warning(f"Unknown event type in webhook payload: {list(change_value.keys())}")
            return Response(content="Unknown event type", status_code=400)

    except KeyError as e:
        logger.error(f"Missing key in payload: {e}", exc_info=True)
        return Response(content=f"Invalid payload structure: {e}", status_code=400)
    except Exception as e:
        logger.error(f"Error in webhook handler: {type(e).__name__}: {e}", exc_info=True)
        return Response(content=f"Internal server error: {type(e).__name__}", status_code=500)


async def process_message_sync(message: Dict, from_number: str, message_id: str):
    """
    Process message synchronously (original flow).
    
    This is the original processing logic, kept for backward compatibility
    or when async processing is disabled.
    """
    try:
        # Extract message content
        content = await extract_message_content(message)
        session_id = from_number
        
        # Process through graph
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
        
        # Send reaction based on detected intent/workflow (if enabled)
        if ENABLE_EMOJI_REACTIONS:
            workflow = output_state.values.get("workflow", "conversation")
            primary_intent = output_state.values.get("primary_intent", "general")
            conversation_stage = output_state.values.get("conversation_stage", "inquiry")
            
            emoji = get_intent_emoji(workflow, primary_intent, conversation_stage)
            if emoji:
                asyncio.create_task(
                    react_to_message(message_id, from_number, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_TOKEN, emoji)
                )
        
        # Send response
        await send_response_from_state(from_number, output_state)
        
        logger.info(f"✅ Successfully processed message {message_id[:20]}... for {from_number}")
        
    finally:
        mark_processing_complete(message_id)


async def process_message_async(message: Dict, from_number: str, message_id: str):
    """
    Process message asynchronously in the background.
    
    This allows the webhook to return immediately while processing happens
    in the background. Provides better UX for long-running operations.
    """
    try:
        # Extract message content
        content = await extract_message_content(message)
        session_id = from_number
        message_type = message.get("type")
        
        # Send immediate typing indicator
        if ENABLE_TYPING_INDICATORS:
            asyncio.create_task(
                send_typing_indicator(from_number, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_TOKEN, message_type)
            )
        
        # For long operations (image generation, audio), send status update after 5 seconds
        status_update_task = None
        if ENABLE_STATUS_UPDATES and message_type in ["audio", "image"]:
            status_update_task = asyncio.create_task(
                send_delayed_status_update(from_number, message_type)
            )
        
        # Process through graph
        async with AsyncSqliteSaver.from_conn_string(settings.SHORT_TERM_MEMORY_DB_PATH) as short_term_memory:
            logger.info("Opening database connection to: %s", settings.SHORT_TERM_MEMORY_DB_PATH)
            graph = graph_builder.compile(checkpointer=short_term_memory)
            logger.debug("Graph invoke: thread_id=%s", session_id)
            
            await graph.ainvoke(
                {"messages": [HumanMessage(content=content, additional_kwargs={"wa_type": message_type})]},
                {"configurable": {"thread_id": session_id}},
            )
            
            # Get the workflow type and response from the state
            output_state = await graph.aget_state(config={"configurable": {"thread_id": session_id}})
        
        # Cancel status update if still pending
        if status_update_task and not status_update_task.done():
            status_update_task.cancel()
        
        # Send reaction based on detected intent/workflow (if enabled)
        if ENABLE_EMOJI_REACTIONS:
            workflow = output_state.values.get("workflow", "conversation")
            primary_intent = output_state.values.get("primary_intent", "general")
            conversation_stage = output_state.values.get("conversation_stage", "inquiry")
            
            emoji = get_intent_emoji(workflow, primary_intent, conversation_stage)
            if emoji:
                asyncio.create_task(
                    react_to_message(message_id, from_number, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_TOKEN, emoji)
                )
        
        # Send response
        await send_response_from_state(from_number, output_state)
        
        logger.info(f"✅ Successfully processed message {message_id[:20]}... for {from_number}")
        
    except Exception as e:
        logger.error(f"❌ Error processing message {message_id[:20]}...: {e}", exc_info=True)
        await send_error_response(from_number, e)
    finally:
        mark_processing_complete(message_id)


async def send_delayed_status_update(from_number: str, message_type: str, delay_seconds: int = 5):
    """
    Send a status update after a delay if processing is taking too long.
    
    This helps manage user expectations for long-running operations.
    """
    await asyncio.sleep(delay_seconds)
    
    # Send appropriate status message based on message type
    status_messages = {
        "audio": "🎤 Transcribing your audio message...",
        "image": "🖼️ Analyzing your image...",
    }
    
    message = status_messages.get(message_type, "⏳ Processing your request...")
    await send_response(from_number, message, "text")
    logger.info(f"📢 Sent status update to {from_number}: {message}")


async def extract_message_content(message: Dict) -> str:
    """
    Extract content from different message types (text/audio/image).
    
    Args:
        message: WhatsApp message object
        
    Returns:
        Extracted content as string
    """
    message_type = message["type"]
    content = ""
    
    if message_type == "audio":
        content = await process_audio_message(message)
    elif message_type == "image":
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
    else:  # text
        content = message["text"]["body"]
    
    return content


async def send_response_from_state(from_number: str, output_state):
    """
    Send response based on the graph output state.
    
    Handles different workflow types (conversation/audio/image) and attachments.
    """
    workflow = output_state.values.get("workflow", "conversation")
    attachment_image_path = output_state.values.get("attachment_image_path")
    
    # Get all AI messages from the current conversation turn
    all_messages = output_state.values["messages"]
    ai_messages = [msg for msg in all_messages if hasattr(msg, 'content') and msg.__class__.__name__ == 'AIMessage']
    
    # Get the most recent AI messages (from current turn)
    # Find where the user message starts to get only the AI response
    user_message_index = -1
    for i, msg in enumerate(all_messages):
        if hasattr(msg, 'content') and msg.__class__.__name__ == 'HumanMessage':
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
    
    logger.info(f"Sending response: workflow={workflow}, ai_messages_count={len(recent_ai_messages)}")
    
    # Handle different response types based on workflow
    if workflow == "audio":
        audio_buffer = output_state.values["audio_buffer"]
        # For audio, combine messages since we need to send as single audio
        response_message = " ".join([msg.content for msg in recent_ai_messages if msg.content.strip()])
        success = await send_response(from_number, response_message, "audio", audio_buffer)
    elif workflow == "image":
        image_path = output_state.values["image_path"]
        with open(image_path, "rb") as f:
            image_data = f.read()
        # For image, combine messages since we need to send as single image with caption
        response_message = " ".join([msg.content for msg in recent_ai_messages if msg.content.strip()])
        success = await send_response(from_number, response_message, "image", image_data)
    else:
        # For text workflow, send each pre-chunked AI message separately
        if attachment_image_path:
            try:
                with open(attachment_image_path, "rb") as f:
                    image_data = f.read()
                # For image attachment, combine messages
                response_message = " ".join([msg.content for msg in recent_ai_messages if msg.content.strip()])
                success = await send_response(from_number, response_message, "image", image_data)
            except Exception:
                logger.exception("Failed to attach image; falling back to text")
                # Send each pre-chunked AI message separately
                success = True
                for i, ai_msg in enumerate(recent_ai_messages):
                    if ai_msg.content.strip():
                        logger.info(f"Sending WhatsApp message chunk {i+1}/{len(recent_ai_messages)}: {ai_msg.content[:100]}...")
                        chunk_success = await send_response(from_number, ai_msg.content, "text")
                        if not chunk_success:
                            success = False
                            logger.error(f"Failed to send chunk {i+1}/{len(recent_ai_messages)}")
                        
                        # Small delay between messages to ensure proper ordering
                        if i < len(recent_ai_messages) - 1:
                            await asyncio.sleep(0.5)
        else:
            # Send each pre-chunked AI message separately for better WhatsApp UX
            success = True
            for i, ai_msg in enumerate(recent_ai_messages):
                if ai_msg.content.strip():
                    logger.info(f"Sending WhatsApp message chunk {i+1}/{len(recent_ai_messages)}: {ai_msg.content[:100]}...")
                    chunk_success = await send_response(from_number, ai_msg.content, "text")
                    if not chunk_success:
                        success = False
                        logger.error(f"Failed to send chunk {i+1}/{len(recent_ai_messages)}")
                    
                    # Small delay between messages to ensure proper ordering
                    if i < len(recent_ai_messages) - 1:
                        await asyncio.sleep(0.5)
    
    if not success:
        logger.error(f"❌ Failed to send response to {from_number}")


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

    # For text messages, only chunk if message exceeds WhatsApp's 1600 char limit
    if message_type == "text":
        # Check if message exceeds WhatsApp's character limit
        if len(response_text) > 1600:
            # Fallback chunking for very long messages
            chunks = chunk_message_by_sentences(response_text, max_length=1500)
            logger.info(f"Message exceeds 1600 chars, splitting into {len(chunks)} chunks for {from_number}")
        else:
            # Send as-is (already chunked by conversation_node)
            chunks = [response_text]
            logger.info(f"Sending single message ({len(response_text)} chars) to {from_number}")
        
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


# Start cleanup task on module load (runs in background)
asyncio.create_task(start_cleanup_task(interval_minutes=10))

