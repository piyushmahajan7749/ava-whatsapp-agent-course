"""
WhatsApp Status Indicators Module

Provides functions to send status updates to users via WhatsApp Cloud API:
- Mark messages as read (double blue checkmarks)
- Send emoji reactions
- Track message deduplication
"""

import logging
import asyncio
from typing import Optional
from datetime import datetime, timedelta
from collections import defaultdict

import httpx

logger = logging.getLogger(__name__)

# In-memory message tracking (for production, consider Redis)
_recent_messages = defaultdict(dict)  # {phone: {message_id: timestamp}}
_processing_messages = set()  # Set of message_ids currently being processed


async def mark_message_as_read(
    message_id: str,
    phone_number_id: str,
    whatsapp_token: str,
    timeout: float = 5.0
) -> bool:
    """
    Mark a WhatsApp message as read (shows double blue checkmarks to user).
    
    This should be called immediately upon receiving a message to provide
    instant feedback to the user that their message was received.
    
    Args:
        message_id: The ID of the message to mark as read
        phone_number_id: Your WhatsApp Business phone number ID
        whatsapp_token: WhatsApp access token
        timeout: Request timeout in seconds
        
    Returns:
        True if successful, False otherwise
    """
    headers = {
        "Authorization": f"Bearer {whatsapp_token}",
        "Content-Type": "application/json",
    }
    
    json_data = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"https://graph.facebook.com/v21.0/{phone_number_id}/messages",
                headers=headers,
                json=json_data,
            )
            
            if response.status_code == 200:
                logger.info(f"✓ Marked message {message_id[:20]}... as read")
                return True
            else:
                logger.warning(
                    f"Failed to mark message as read: {response.status_code} - {response.text}"
                )
                return False
                
    except httpx.TimeoutException:
        logger.warning(f"Timeout marking message {message_id[:20]}... as read")
        return False
    except Exception as e:
        logger.error(f"Error marking message as read: {e}")
        return False


async def react_to_message(
    message_id: str,
    to_number: str,
    phone_number_id: str,
    whatsapp_token: str,
    emoji: str = "👀",
    timeout: float = 5.0
) -> bool:
    """
    React to a WhatsApp message with an emoji.
    
    This provides additional acknowledgment and can show the type of processing
    happening (e.g., 🎨 for image generation, 📅 for calendar operations).
    
    Args:
        message_id: The ID of the message to react to
        to_number: The phone number to send the reaction to
        phone_number_id: Your WhatsApp Business phone number ID
        whatsapp_token: WhatsApp access token
        emoji: Emoji to react with (default: 👀)
        timeout: Request timeout in seconds
        
    Returns:
        True if successful, False otherwise
    """
    headers = {
        "Authorization": f"Bearer {whatsapp_token}",
        "Content-Type": "application/json",
    }
    
    json_data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "reaction",
        "reaction": {
            "message_id": message_id,
            "emoji": emoji
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"https://graph.facebook.com/v21.0/{phone_number_id}/messages",
                headers=headers,
                json=json_data,
            )
            
            if response.status_code == 200:
                logger.info(f"✓ Reacted to message {message_id[:20]}... with {emoji}")
                return True
            else:
                logger.warning(
                    f"Failed to react to message: {response.status_code} - {response.text}"
                )
                return False
                
    except httpx.TimeoutException:
        logger.warning(f"Timeout reacting to message {message_id[:20]}...")
        return False
    except Exception as e:
        logger.error(f"Error reacting to message: {e}")
        return False


def get_intent_emoji(workflow: str, primary_intent: str, conversation_stage: str) -> Optional[str]:
    """
    Get an appropriate emoji based on the detected workflow and intent.
    
    Args:
        workflow: The workflow type (conversation/image/audio)
        primary_intent: The primary intent (booking/consultation_inquiry/products_pooja/general)
        conversation_stage: The conversation stage
        
    Returns:
        Emoji string or None if no specific emoji is appropriate
    """
    # Workflow-based emojis
    if workflow == "image":
        return "🎨"
    elif workflow == "audio":
        return "🎤"
    
    # Intent-based emojis
    if primary_intent == "booking":
        return "📅"
    elif "payment" in conversation_stage:
        return "💰"
    elif primary_intent == "products_pooja":
        return "🙏"
    
    # Default: only react for specific cases, not every message
    return None


def is_duplicate_message(from_number: str, message_id: str, window_seconds: int = 10) -> bool:
    """
    Check if a message was recently processed to prevent duplicate handling.
    
    This prevents issues when users rapidly send the same message multiple times
    due to perceived slowness.
    
    Args:
        from_number: Phone number of sender
        message_id: Message ID to check
        window_seconds: Time window in seconds to check for duplicates
        
    Returns:
        True if message is a duplicate, False otherwise
    """
    now = datetime.now()
    
    # Clean old entries for this phone number
    if from_number in _recent_messages:
        _recent_messages[from_number] = {
            mid: ts for mid, ts in _recent_messages[from_number].items()
            if (now - ts).total_seconds() < window_seconds
        }
    
    # Check if this message was seen
    if message_id in _recent_messages[from_number]:
        logger.info(f"Duplicate message detected: {message_id[:20]}... from {from_number}")
        return True
    
    # Track this message
    _recent_messages[from_number][message_id] = now
    return False


def mark_processing_start(message_id: str) -> bool:
    """
    Mark a message as currently being processed.
    
    Returns False if already processing (race condition protection).
    """
    if message_id in _processing_messages:
        return False
    _processing_messages.add(message_id)
    return True


def mark_processing_complete(message_id: str):
    """Mark a message as done processing."""
    _processing_messages.discard(message_id)


def cleanup_old_tracking_data(max_age_minutes: int = 30):
    """
    Clean up old tracking data to prevent memory leaks.
    
    Should be called periodically (e.g., via background task).
    """
    now = datetime.now()
    cutoff = now - timedelta(minutes=max_age_minutes)
    
    # Clean recent messages
    phones_to_remove = []
    for phone, messages in _recent_messages.items():
        old_messages = [mid for mid, ts in messages.items() if ts < cutoff]
        for mid in old_messages:
            del messages[mid]
        if not messages:
            phones_to_remove.append(phone)
    
    for phone in phones_to_remove:
        del _recent_messages[phone]
    
    logger.debug(f"Cleaned up tracking data for {len(phones_to_remove)} phone numbers")


# Background task for periodic cleanup
async def start_cleanup_task(interval_minutes: int = 10):
    """
    Start a background task that periodically cleans up old tracking data.
    
    Args:
        interval_minutes: How often to run cleanup (default: 10 minutes)
    """
    while True:
        await asyncio.sleep(interval_minutes * 60)
        try:
            cleanup_old_tracking_data()
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")

