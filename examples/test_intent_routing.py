"""
Test script for Intent-Based Routing System

This script tests the enhanced router with various user queries
to verify intent detection, confidence scoring, and stage tracking.

Usage:
    python examples/test_intent_routing.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from langchain_core.messages import HumanMessage
from ai_companion.graph.utils.chains import get_router_chain


# Test cases covering different intents and scenarios
TEST_CASES = [
    {
        "name": "Pure Booking Intent",
        "query": "I want to book a consultation with Guru Maa",
        "expected_primary": "booking",
        "expected_stage": "interested",
    },
    {
        "name": "Consultation Inquiry",
        "query": "Who is Guru Maa and what services do you offer?",
        "expected_primary": "consultation_inquiry",
        "expected_stage": "inquiry",
    },
    {
        "name": "Products/Pooja Inquiry",
        "query": "Tell me about Kalawa and how much does it cost",
        "expected_primary": "products_pooja",
        "expected_stage": "inquiry",
    },
    {
        "name": "General Greeting",
        "query": "Hello! How are you doing today?",
        "expected_primary": "general",
        "expected_stage": "general_chat",
    },
    {
        "name": "Hybrid Intent - Products + Booking",
        "query": "What is Navgrah Shanti puja price and can I book for tomorrow?",
        "expected_primary": "products_pooja",
        "expected_secondary": "booking",
        "expected_stage": "interested",
    },
    {
        "name": "Availability Check (Booking)",
        "query": "Are you available tomorrow at 2pm?",
        "expected_primary": "booking",
        "expected_stage": "interested",
    },
    {
        "name": "Payment Mention",
        "query": "Here is my payment screenshot for the consultation",
        "expected_primary": "booking",
        "expected_stage": "payment_verified",
    },
    {
        "name": "Service Pricing (Consultation Inquiry)",
        "query": "How much is a consultation and how long is the call?",
        "expected_primary": "consultation_inquiry",
        "expected_stage": "inquiry",
    },
    {
        "name": "Emotional Support (General)",
        "query": "I'm feeling very stressed and worried about my career",
        "expected_primary": "general",
        "expected_stage": "general_chat",
    },
    {
        "name": "Specific Puja Inquiry",
        "query": "I want to do Kaal Sarp Dosh puja, what's the process?",
        "expected_primary": "products_pooja",
        "expected_stage": "inquiry",
    },
]


async def test_router():
    """Test the enhanced router with various queries."""
    
    print("=" * 80)
    print("🧪 INTENT-BASED ROUTING SYSTEM TEST")
    print("=" * 80)
    print()
    
    router_chain = get_router_chain()
    
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"\n{'─' * 80}")
        print(f"Test {i}/{len(TEST_CASES)}: {test_case['name']}")
        print(f"{'─' * 80}")
        print(f"📝 Query: \"{test_case['query']}\"")
        print()
        
        # Create message
        messages = [HumanMessage(content=test_case["query"])]
        
        # Get router response
        try:
            response = await router_chain.ainvoke({"messages": messages})
            
            # Display results
            print(f"🎯 Router Decision:")
            print(f"   Media Type:       {response.response_type}")
            print(f"   Primary Intent:   {response.primary_intent}")
            print(f"   Secondary Intent: {response.secondary_intent or 'None'}")
            print(f"   Confidence:       {response.confidence:.2f}")
            print(f"   Stage:            {response.conversation_stage}")
            print(f"   Reasoning:        {response.reasoning}")
            print()
            
            # Verify expectations
            checks = []
            
            # Check primary intent
            if response.primary_intent == test_case["expected_primary"]:
                checks.append(("✅", "Primary intent matches"))
            else:
                checks.append((
                    "❌", 
                    f"Primary intent mismatch (got: {response.primary_intent}, expected: {test_case['expected_primary']})"
                ))
            
            # Check secondary intent if specified
            if "expected_secondary" in test_case:
                if response.secondary_intent == test_case["expected_secondary"]:
                    checks.append(("✅", "Secondary intent matches"))
                else:
                    checks.append((
                        "❌", 
                        f"Secondary intent mismatch (got: {response.secondary_intent}, expected: {test_case['expected_secondary']})"
                    ))
            
            # Check stage
            if response.conversation_stage == test_case["expected_stage"]:
                checks.append(("✅", "Conversation stage matches"))
            else:
                checks.append((
                    "⚠️", 
                    f"Stage mismatch (got: {response.conversation_stage}, expected: {test_case['expected_stage']})"
                ))
            
            # Check confidence (should be reasonable)
            if response.confidence >= 0.5:
                checks.append(("✅", f"Confidence is reasonable ({response.confidence:.2f})"))
            else:
                checks.append(("⚠️", f"Low confidence ({response.confidence:.2f})"))
            
            # Print checks
            print("🔍 Validation:")
            for icon, message in checks:
                print(f"   {icon} {message}")
            
            # Count result
            if all(check[0] in ["✅", "⚠️"] for check in checks):
                passed += 1
                print(f"\n✅ Test PASSED")
            else:
                failed += 1
                print(f"\n❌ Test FAILED")
                
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            failed += 1
            print(f"\n❌ Test FAILED")
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    print(f"Total Tests:  {len(TEST_CASES)}")
    print(f"Passed:       {passed} ✅")
    print(f"Failed:       {failed} ❌")
    print(f"Success Rate: {(passed/len(TEST_CASES)*100):.1f}%")
    print("=" * 80)
    
    if failed == 0:
        print("\n🎉 All tests passed! The intent routing system is working correctly.")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Review the results above.")
    
    return failed == 0


async def test_conversation_continuity():
    """Test conversation continuity across intent changes."""
    
    print("\n\n" + "=" * 80)
    print("🔄 CONVERSATION CONTINUITY TEST")
    print("=" * 80)
    print()
    
    router_chain = get_router_chain()
    
    # Simulate a conversation flow
    conversation = [
        ("Who is Guru Maa?", "consultation_inquiry"),
        ("Great! I want to book a consultation", "booking"),
        ("How much does it cost?", "consultation_inquiry"),  # Back to inquiry
        ("Ok, I'll send payment now", "booking"),  # Back to booking
    ]
    
    messages = []
    
    for i, (query, expected_intent) in enumerate(conversation, 1):
        print(f"\n{'─' * 80}")
        print(f"Message {i}: \"{query}\"")
        print(f"{'─' * 80}")
        
        # Add to conversation
        messages.append(HumanMessage(content=query))
        
        # Get router response
        try:
            response = await router_chain.ainvoke({"messages": messages[-3:]})  # Last 3 messages
            
            print(f"Intent: {response.primary_intent} (expected: {expected_intent})")
            print(f"Stage: {response.conversation_stage}")
            print(f"Confidence: {response.confidence:.2f}")
            
            if response.primary_intent == expected_intent:
                print("✅ Intent correctly identified")
            else:
                print(f"⚠️  Intent mismatch")
            
            # Simulate AI response
            messages.append(HumanMessage(content="[AI Response]"))
            
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
    
    print("\n" + "=" * 80)
    print("✅ Conversation continuity test completed")
    print("=" * 80)


async def main():
    """Run all tests."""
    try:
        # Test router with various queries
        success = await test_router()
        
        # Test conversation continuity
        await test_conversation_continuity()
        
        # Exit code
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ FATAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    print("\n🚀 Starting Intent Routing Tests...\n")
    asyncio.run(main())

