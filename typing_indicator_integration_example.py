#!/usr/bin/env python3
"""
Example integration of typing indicators into WhatsApp handler

This shows how to add typing indicators to your existing WhatsApp response handler.
"""

import asyncio
import os
from typing import Dict

# Import the typing indicator functions
from src.ai_companion.interfaces.whatsapp.status_indicators import (
    send_typing_indicator,
    send_processing_status,
    mark_message_as_read
)

# Your existing WhatsApp credentials
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
ENABLE_TYPING_INDICATORS = os.getenv("ENABLE_TYPING_INDICATORS", "true").lower() == "true"

async def enhanced_whatsapp_handler(message: Dict, from_number: str, message_id: str):
    """
    Enhanced WhatsApp handler with typing indicators
    
    This is an example of how to integrate typing indicators into your
    existing WhatsApp message processing workflow.
    """
    
    try:
        # 1. IMMEDIATE: Mark message as read (shows double blue checkmarks)
        await mark_message_as_read(
            message_id=message_id,
            phone_number_id=WHATSAPP_PHONE_NUMBER_ID,
            whatsapp_token=WHATSAPP_TOKEN
        )
        
        # 2. IMMEDIATE: Send typing indicator
        if ENABLE_TYPING_INDICATORS:
            message_type = message.get("type", "text")
            await send_typing_indicator(
                to_number=from_number,
                phone_number_id=WHATSAPP_PHONE_NUMBER_ID,
                whatsapp_token=WHATSAPP_TOKEN,
                message_type=message_type
            )
        
        # 3. PROCESS: Your existing message processing logic
        # ... extract content, process through graph, etc ...
        
        # Simulate processing time
        await asyncio.sleep(2)
        
        # 4. AFTER INTENT DETECTION: Send contextual processing status
        if ENABLE_TYPING_INDICATORS:
            # These would come from your graph processing
            detected_workflow = "conversation"  # or "image", "audio"
            detected_intent = "booking"  # or "consultation_inquiry", "products_pooja"
            
            await send_processing_status(
                to_number=from_number,
                phone_number_id=WHATSAPP_PHONE_NUMBER_ID,
                whatsapp_token=WHATSAPP_TOKEN,
                workflow=detected_workflow,
                intent=detected_intent
            )
        
        # 5. FINAL: Send your actual response
        # ... your existing response sending logic ...
        
        print(f"✅ Processed message {message_id[:20]}... for {from_number}")
        
    except Exception as e:
        print(f"❌ Error processing message: {e}")

# Example usage
async def main():
    """Example of how to use the enhanced handler"""
    
    # Simulate a WhatsApp message
    sample_message = {
        "type": "text",
        "text": {"body": "I want to book a consultation"},
        "from": "+1234567890",
        "id": "wamid.test123"
    }
    
    print("🧪 Testing Enhanced WhatsApp Handler with Typing Indicators")
    print("=" * 60)
    
    await enhanced_whatsapp_handler(
        message=sample_message,
        from_number=sample_message["from"],
        message_id=sample_message["id"]
    )
    
    print("\n🎉 Test completed!")
    print("\nTo integrate into your existing handler:")
    print("1. Import the typing indicator functions")
    print("2. Add typing indicators at the beginning of message processing")
    print("3. Add contextual status after intent detection")
    print("4. Set ENABLE_TYPING_INDICATORS=true in your environment")

if __name__ == "__main__":
    asyncio.run(main())
