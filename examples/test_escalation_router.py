"""
Lightweight test for escalation intent detection in the router.

Tests the router's ability to detect escalation_needed intent
without requiring full database integration.

Usage:
    python examples/test_escalation_router.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from langchain_core.messages import HumanMessage
from ai_companion.graph.utils.chains import get_router_chain


async def test_escalation_intent(scenario_name: str, user_message: str, expected_intent: str):
    """Test router escalation detection for a single scenario."""
    print(f"\n{'='*80}")
    print(f"🧪 {scenario_name}")
    print(f"{'='*80}")
    print(f"User: \"{user_message}\"")
    print(f"-" * 80)
    
    try:
        chain = get_router_chain()
        response = await chain.ainvoke({"messages": [HumanMessage(content=user_message)]})
        
        print(f"\n📊 ROUTER ANALYSIS:")
        print(f"   Primary Intent: {response.primary_intent}")
        print(f"   Conversation Stage: {response.conversation_stage}")
        print(f"   Confidence: {response.confidence:.2f}")
        print(f"   Reasoning: {response.reasoning}")
        
        # Validation
        print(f"\n✅ VALIDATION:")
        if response.primary_intent == expected_intent:
            print(f"   ✓ PASS - Correctly identified as '{expected_intent}'")
            return True
        else:
            print(f"   ✗ FAIL - Expected '{expected_intent}' but got '{response.primary_intent}'")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_escalation_tests():
    """Test that escalation scenarios are correctly detected."""
    print("\n" + "="*80)
    print("🚨 ESCALATION INTENT DETECTION TESTS")
    print("="*80)
    
    test_cases = [
        # Refund requests (English)
        ("Refund Request - Direct", "I want a refund", "escalation_needed"),
        ("Refund Request - Detailed", "I paid for a consultation but want my money back now", "escalation_needed"),
        ("Refund Request - Angry", "This is unacceptable! I want my ₹2100 refunded immediately!", "escalation_needed"),
        
        # Refund requests (Hinglish)
        ("Refund Request - Hindi Direct", "Mujhe refund chahiye", "escalation_needed"),
        ("Refund Request - Hindi Demand", "Mera paisa wapas karo", "escalation_needed"),
        ("Refund Request - Hindi Angry", "Ye bilkul galat hai! Mera paisa turant wapas do!", "escalation_needed"),
        
        # Complaints (English)
        ("Complaint - Service Quality", "Your service is terrible, I'm very disappointed", "escalation_needed"),
        ("Complaint - Not Satisfied", "I'm not satisfied with the consultation at all", "escalation_needed"),
        
        # Complaints (Hinglish)
        ("Complaint - Hindi Service", "Ye service bahut bekaar hai", "escalation_needed"),
        ("Complaint - Hindi Not Satisfied", "Main satisfied nahi hoon consultation se", "escalation_needed"),
        
        # Human representative requests (English)
        ("Human Request - Direct", "Can I speak to a real person?", "escalation_needed"),
        ("Human Request - Manager", "I need to talk to your manager", "escalation_needed"),
        ("Human Request - Human Help", "I want to talk to a human, not a bot", "escalation_needed"),
        
        # Human representative requests (Hinglish)
        ("Human Request - Hindi Direct", "Kisi insaan se baat karni hai", "escalation_needed"),
        ("Human Request - Hindi Manager", "Manager se baat karao", "escalation_needed"),
        
        # Billing disputes (English)
        ("Billing Dispute - Double Charge", "I was charged twice for the same booking", "escalation_needed"),
        ("Billing Dispute - Wrong Amount", "You charged me the wrong amount", "escalation_needed"),
        
        # Billing disputes (Hinglish)
        ("Billing Dispute - Hindi Double", "Do baar charge ho gaya hai", "escalation_needed"),
        ("Billing Dispute - Hindi Wrong", "Galat amount charge kiya hai", "escalation_needed"),
        
        # General frustration
        ("Frustration - Multiple Issues", "This is so frustrating, nothing is working properly", "escalation_needed"),
        ("Dissatisfaction - Cancel", "Cancel my order, I don't want this anymore", "escalation_needed"),
        ("Frustration - Hindi", "Bahut frustrating hai ye, kuch bhi theek se kaam nahi kar raha", "escalation_needed"),
    ]
    
    results = []
    for scenario_name, user_message, expected_intent in test_cases:
        success = await test_escalation_intent(scenario_name, user_message, expected_intent)
        results.append((scenario_name, success))
        await asyncio.sleep(0.5)
    
    return results


async def run_non_escalation_tests():
    """Test that normal queries don't trigger false escalation."""
    print("\n" + "="*80)
    print("🔍 FALSE POSITIVE PREVENTION TESTS")
    print("="*80)
    
    test_cases = [
        # English non-escalation
        ("Normal Booking", "I want to book a consultation", "booking"),
        ("Asking About Refund Policy", "What is your refund policy?", "consultation_inquiry"),
        ("General Question", "How much does a consultation cost?", "consultation_inquiry"),
        ("Friendly Chat", "Hello, how are you?", "general"),
        ("Product Inquiry", "Tell me about Kalawa", "products_pooja"),
        ("Availability Check", "Are you available tomorrow at 2pm?", "booking"),
        
        # Hinglish non-escalation (should NOT trigger escalation)
        ("Hindi Booking", "Main consultation book karna chahta hoon", "booking"),
        ("Hindi Refund Policy Question", "Refund policy kya hai?", "consultation_inquiry"),
        ("Hindi Price Question", "Consultation ki fees kitni hai?", "consultation_inquiry"),
        ("Hindi Greeting", "Namaste, kaise ho aap?", "general"),
        ("Hindi Product Inquiry", "Kalawa ke baare mein batao", "products_pooja"),
        ("Hindi Availability", "Kal 2 baje available ho?", "booking"),
    ]
    
    results = []
    for scenario_name, user_message, expected_intent in test_cases:
        success = await test_escalation_intent(scenario_name, user_message, expected_intent)
        results.append((scenario_name, success))
        await asyncio.sleep(0.5)
    
    return results


def print_summary(title: str, results: list):
    """Print test results summary."""
    print(f"\n{'='*80}")
    print(f"📊 {title}")
    print(f"{'='*80}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for scenario_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {scenario_name}")
    
    print(f"\n{'-'*80}")
    print(f"Total: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    print(f"{'='*80}\n")
    
    return passed == total


async def main():
    """Run all escalation router tests."""
    print("\n🚀 Starting Escalation Router Tests...\n")
    
    # Test escalation detection
    escalation_results = await run_escalation_tests()
    escalation_success = print_summary("ESCALATION DETECTION RESULTS", escalation_results)
    
    # Test false positive prevention
    non_escalation_results = await run_non_escalation_tests()
    non_escalation_success = print_summary("FALSE POSITIVE PREVENTION RESULTS", non_escalation_results)
    
    # Final summary
    print("\n" + "="*80)
    print("🎯 FINAL RESULTS")
    print("="*80)
    print(f"Escalation Detection: {'✅ PASS' if escalation_success else '❌ FAIL'}")
    print(f"False Positive Prevention: {'✅ PASS' if non_escalation_success else '❌ FAIL'}")
    print("="*80)
    
    if escalation_success and non_escalation_success:
        print("\n✅ ALL TESTS PASSED - Escalation router is working correctly!")
        print("\n💡 Next Steps:")
        print("   - Update CUSTOMER_SERVICE_PHONE and CUSTOMER_SERVICE_WHATSAPP in knowledge.py")
        print("   - Test with actual WhatsApp integration")
        print("   - Monitor escalation logs in production")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED - Review results above and adjust router prompts.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

