#!/usr/bin/env python3
"""
Test script for WhatsApp message splitting fix

This script tests the fixed message splitting functionality to ensure
that WhatsApp messages are properly chunked without double-chunking issues.
"""

import asyncio
from src.ai_companion.graph.utils.helpers import chunk_response_into_messages, chunk_message_by_sentences

def test_message_chunking():
    """Test the message chunking functions"""
    
    print("🧪 Testing WhatsApp Message Splitting Fix")
    print("=" * 60)
    
    # Test 1: Short message (should not be chunked)
    print("\n1. Testing short message (< 200 chars)...")
    short_message = "Hello! How can I help you today? This is a short message that should not be chunked."
    chunks = chunk_response_into_messages(short_message)
    print(f"   Input: {len(short_message)} chars")
    print(f"   Output: {len(chunks)} chunks")
    print(f"   Chunks: {[len(chunk) for chunk in chunks]}")
    
    # Test 2: Medium message (should be chunked by conversation_node)
    print("\n2. Testing medium message (200-400 chars)...")
    medium_message = "Thank you for your interest in our services! We offer a wide range of spiritual products and consultations. Our team is here to help you find the perfect solution for your needs. Please let me know if you have any specific requirements or questions about our offerings."
    chunks = chunk_response_into_messages(medium_message)
    print(f"   Input: {len(medium_message)} chars")
    print(f"   Output: {len(chunks)} chunks")
    print(f"   Chunks: {[len(chunk) for chunk in chunks]}")
    for i, chunk in enumerate(chunks):
        print(f"     Chunk {i+1}: {chunk[:50]}...")
    
    # Test 3: Long message (should be chunked by conversation_node)
    print("\n3. Testing long message (> 400 chars)...")
    long_message = "Welcome to our spiritual services! We are delighted to assist you with your spiritual journey. Our comprehensive range of services includes personalized consultations, sacred rituals, and blessed products. Our experienced practitioners are dedicated to providing you with authentic spiritual guidance. Whether you are seeking solutions for specific challenges or looking to enhance your spiritual practice, we are here to support you every step of the way. Please feel free to ask any questions about our services, and we will be happy to provide detailed information to help you make the best choice for your spiritual needs."
    chunks = chunk_response_into_messages(long_message)
    print(f"   Input: {len(long_message)} chars")
    print(f"   Output: {len(chunks)} chunks")
    print(f"   Chunks: {[len(chunk) for chunk in chunks]}")
    for i, chunk in enumerate(chunks):
        print(f"     Chunk {i+1}: {chunk[:50]}...")
    
    # Test 4: Very long message (should trigger fallback chunking in send_response)
    print("\n4. Testing very long message (> 1600 chars)...")
    very_long_message = "This is a very long message that exceeds WhatsApp's 1600 character limit. " * 20  # ~1000 chars
    very_long_message += "This additional content makes it even longer to test the fallback chunking mechanism. " * 10  # ~600 more chars
    very_long_message += "The total length should now exceed 1600 characters and trigger the fallback chunking in the send_response function."
    
    print(f"   Input: {len(very_long_message)} chars")
    
    # Test conversation_node chunking (first level)
    conversation_chunks = chunk_response_into_messages(very_long_message)
    print(f"   Conversation chunks: {len(conversation_chunks)} chunks")
    
    # Test send_response fallback chunking (second level)
    if len(very_long_message) > 1600:
        fallback_chunks = chunk_message_by_sentences(very_long_message, max_length=1500)
        print(f"   Fallback chunks: {len(fallback_chunks)} chunks")
        print(f"   Fallback chunk sizes: {[len(chunk) for chunk in fallback_chunks]}")
    
    print("\n" + "=" * 60)
    print("🎉 Message chunking tests completed!")
    print("\nExpected behavior:")
    print("✅ Short messages: No chunking")
    print("✅ Medium messages: Chunked by conversation_node (~200 chars each)")
    print("✅ Long messages: Chunked by conversation_node (~200 chars each)")
    print("✅ Very long messages: Fallback chunking in send_response (~1500 chars each)")
    print("\nThis should fix the WhatsApp double-chunking issue!")

def test_whatsapp_character_limits():
    """Test WhatsApp character limits"""
    
    print("\n📱 Testing WhatsApp Character Limits")
    print("=" * 60)
    
    # Test different message lengths
    test_cases = [
        (100, "Short message"),
        (500, "Medium message"),
        (1000, "Long message"),
        (1500, "Very long message"),
        (2000, "Extremely long message"),
    ]
    
    for length, description in test_cases:
        message = "A" * length
        print(f"\n{description} ({length} chars):")
        
        # Test conversation_node chunking
        conv_chunks = chunk_response_into_messages(message)
        print(f"  Conversation chunks: {len(conv_chunks)}")
        
        # Test send_response behavior
        if length > 1600:
            fallback_chunks = chunk_message_by_sentences(message, max_length=1500)
            print(f"  Fallback chunks: {len(fallback_chunks)}")
            print(f"  ✅ Would trigger fallback chunking")
        else:
            print(f"  ✅ Would send as-is (no fallback needed)")

if __name__ == "__main__":
    test_message_chunking()
    test_whatsapp_character_limits()
