#!/usr/bin/env python3
"""
Test script for WhatsApp typing indicators

This script demonstrates how to use the new typing indicator functions
to show users that the bot is processing their message.
"""

import asyncio
import os
from src.ai_companion.interfaces.whatsapp.status_indicators import (
    send_typing_indicator,
    send_processing_status,
    mark_message_as_read,
    react_to_message
)

async def test_typing_indicators():
    """Test the typing indicator functionality"""
    
    # Get WhatsApp credentials from environment
    whatsapp_token = os.getenv("WHATSAPP_TOKEN")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    test_number = "+1234567890"  # Replace with actual test number
    
    if not whatsapp_token or not phone_number_id:
        print("❌ WhatsApp credentials not found in environment variables")
        print("Please set WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID")
        return
    
    print("🧪 Testing WhatsApp Typing Indicators")
    print("=" * 50)
    
    # Test 1: Basic typing indicator
    print("\n1. Testing basic typing indicator...")
    success = await send_typing_indicator(
        to_number=test_number,
        phone_number_id=phone_number_id,
        whatsapp_token=whatsapp_token,
        message_type="text"
    )
    print(f"   Result: {'✅ Success' if success else '❌ Failed'}")
    
    # Test 2: Audio processing indicator
    print("\n2. Testing audio processing indicator...")
    success = await send_typing_indicator(
        to_number=test_number,
        phone_number_id=phone_number_id,
        whatsapp_token=whatsapp_token,
        message_type="audio"
    )
    print(f"   Result: {'✅ Success' if success else '❌ Failed'}")
    
    # Test 3: Image processing indicator
    print("\n3. Testing image processing indicator...")
    success = await send_typing_indicator(
        to_number=test_number,
        phone_number_id=phone_number_id,
        whatsapp_token=whatsapp_token,
        message_type="image"
    )
    print(f"   Result: {'✅ Success' if success else '❌ Failed'}")
    
    # Test 4: Contextual processing status
    print("\n4. Testing contextual processing status...")
    success = await send_processing_status(
        to_number=test_number,
        phone_number_id=phone_number_id,
        whatsapp_token=whatsapp_token,
        workflow="conversation",
        intent="booking"
    )
    print(f"   Result: {'✅ Success' if success else '❌ Failed'}")
    
    # Test 5: Payment processing status
    print("\n5. Testing payment processing status...")
    success = await send_processing_status(
        to_number=test_number,
        phone_number_id=phone_number_id,
        whatsapp_token=whatsapp_token,
        workflow="conversation",
        intent="payment"
    )
    print(f"   Result: {'✅ Success' if success else '❌ Failed'}")
    
    print("\n" + "=" * 50)
    print("🎉 Typing indicator tests completed!")
    print("\nTo use in your WhatsApp handler:")
    print("1. Import the functions in your response handler")
    print("2. Call send_typing_indicator() immediately when message is received")
    print("3. Call send_processing_status() after detecting workflow/intent")
    print("4. Set ENABLE_TYPING_INDICATORS=true in your environment")

if __name__ == "__main__":
    asyncio.run(test_typing_indicators())
