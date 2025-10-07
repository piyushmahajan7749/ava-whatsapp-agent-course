"""
Test script for human escalation scenarios.

Tests various escalation triggers:
- Refund requests
- Complaints
- Human representative requests
- Billing disputes
- General dissatisfaction
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from ai_companion.graph import graph_builder
from ai_companion.settings import settings


async def test_escalation_scenario(scenario_name: str, user_message: str, thread_id: str = "test_escalation"):
    """Test a single escalation scenario."""
    print(f"\n{'='*80}")
    print(f"🧪 Testing: {scenario_name}")
    print(f"{'='*80}")
    print(f"User: {user_message}")
    print(f"-" * 80)
    
    try:
        async with AsyncSqliteSaver.from_conn_string(settings.SHORT_TERM_MEMORY_DB_PATH) as memory:
            graph = graph_builder.compile(checkpointer=memory)
            
            # Invoke the graph
            result = await graph.ainvoke(
                {"messages": [HumanMessage(content=user_message)]},
                {"configurable": {"thread_id": thread_id}}
            )
            
            # Get the state
            state = await graph.aget_state(config={"configurable": {"thread_id": thread_id}})
            
            # Extract routing information
            workflow = state.values.get("workflow", "unknown")
            primary_intent = state.values.get("primary_intent", "unknown")
            conversation_stage = state.values.get("conversation_stage", "unknown")
            confidence = state.values.get("confidence", 0.0)
            
            # Get bot response
            bot_response = state.values["messages"][-1].content if state.values.get("messages") else "No response"
            
            print(f"\n📊 ROUTING ANALYSIS:")
            print(f"   Workflow: {workflow}")
            print(f"   Primary Intent: {primary_intent}")
            print(f"   Conversation Stage: {conversation_stage}")
            print(f"   Confidence: {confidence:.2f}")
            
            print(f"\n🤖 BOT RESPONSE:")
            print(f"   {bot_response}")
            
            # Validation
            print(f"\n✅ VALIDATION:")
            if primary_intent == "escalation_needed":
                print("   ✓ Correctly identified as escalation_needed")
            else:
                print(f"   ✗ FAILED - Intent was '{primary_intent}' instead of 'escalation_needed'")
            
            if "wa.me" in bot_response or "919131036482" in bot_response:
                print("   ✓ WhatsApp contact link provided")
            else:
                print("   ✗ WARNING - No WhatsApp link detected in response")
            
            if any(word in bot_response.lower() for word in ["sorry", "understand", "apologize"]):
                print("   ✓ Empathetic language detected")
            else:
                print("   ✗ WARNING - No empathetic language detected")
            
            return primary_intent == "escalation_needed"
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """Run all escalation test scenarios."""
    print("\n" + "="*80)
    print("🚨 HUMAN ESCALATION SYSTEM - COMPREHENSIVE TEST SUITE")
    print("="*80)
    
    test_scenarios = [
        # Refund requests
        ("Refund Request - Direct", "I want a refund", "test_refund_1"),
        ("Refund Request - Detailed", "I paid for a consultation but want my money back now", "test_refund_2"),
        ("Refund Request - Angry", "This is unacceptable! I want my ₹2100 refunded immediately!", "test_refund_3"),
        
        # Complaints
        ("Complaint - Service Quality", "Your service is terrible, I'm very disappointed", "test_complaint_1"),
        ("Complaint - Not Satisfied", "I'm not satisfied with the consultation at all", "test_complaint_2"),
        
        # Human representative requests
        ("Human Request - Direct", "Can I speak to a real person?", "test_human_1"),
        ("Human Request - Manager", "I need to talk to your manager", "test_human_2"),
        ("Human Request - Human Help", "I want to talk to a human, not a bot", "test_human_3"),
        
        # Billing disputes
        ("Billing Dispute - Double Charge", "I was charged twice for the same booking", "test_billing_1"),
        ("Billing Dispute - Wrong Amount", "You charged me the wrong amount", "test_billing_2"),
        
        # General frustration
        ("Frustration - Multiple Issues", "This is so frustrating, nothing is working properly", "test_frustration_1"),
        ("Dissatisfaction - Cancel", "Cancel my order, I don't want this anymore", "test_cancel_1"),
    ]
    
    results = []
    
    for scenario_name, user_message, thread_id in test_scenarios:
        success = await test_escalation_scenario(scenario_name, user_message, thread_id)
        results.append((scenario_name, success))
        await asyncio.sleep(1)  # Small delay between tests
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST RESULTS SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for scenario_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {scenario_name}")
    
    print(f"\n{'='*80}")
    print(f"Total: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    print(f"{'='*80}\n")
    
    return passed == total


async def test_non_escalation_scenarios():
    """Test that normal queries don't trigger escalation."""
    print("\n" + "="*80)
    print("🔍 NON-ESCALATION TEST - Ensuring false positives don't occur")
    print("="*80)
    
    non_escalation_scenarios = [
        ("Normal Booking", "I want to book a consultation", "test_normal_1"),
        ("Asking About Refund Policy", "What is your refund policy?", "test_normal_2"),
        ("General Question", "How much does a consultation cost?", "test_normal_3"),
        ("Friendly Chat", "Hello, how are you?", "test_normal_4"),
    ]
    
    results = []
    
    for scenario_name, user_message, thread_id in non_escalation_scenarios:
        print(f"\n{'='*80}")
        print(f"🧪 Testing Non-Escalation: {scenario_name}")
        print(f"{'='*80}")
        print(f"User: {user_message}")
        print(f"-" * 80)
        
        try:
            async with AsyncSqliteSaver.from_conn_string(settings.SHORT_TERM_MEMORY_DB_PATH) as memory:
                graph = graph_builder.compile(checkpointer=memory)
                
                await graph.ainvoke(
                    {"messages": [HumanMessage(content=user_message)]},
                    {"configurable": {"thread_id": thread_id}}
                )
                
                state = await graph.aget_state(config={"configurable": {"thread_id": thread_id}})
                primary_intent = state.values.get("primary_intent", "unknown")
                
                print(f"\n📊 Intent Detected: {primary_intent}")
                
                if primary_intent != "escalation_needed":
                    print(f"   ✓ Correctly NOT identified as escalation")
                    results.append((scenario_name, True))
                else:
                    print(f"   ✗ FAILED - False positive: Should NOT be escalation")
                    results.append((scenario_name, False))
                    
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            results.append((scenario_name, False))
        
        await asyncio.sleep(1)
    
    # Summary
    print("\n" + "="*80)
    print("📊 NON-ESCALATION TEST RESULTS")
    print("="*80)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for scenario_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {scenario_name}")
    
    print(f"\n{'='*80}")
    print(f"Total: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    print(f"{'='*80}\n")
    
    return passed == total


if __name__ == "__main__":
    async def main():
        print("\n🚀 Starting Escalation System Tests...\n")
        
        # Test escalation scenarios
        escalation_success = await run_all_tests()
        
        # Test non-escalation scenarios (false positive check)
        non_escalation_success = await test_non_escalation_scenarios()
        
        # Final summary
        print("\n" + "="*80)
        print("🎯 FINAL TEST RESULTS")
        print("="*80)
        print(f"Escalation Detection: {'✅ PASS' if escalation_success else '❌ FAIL'}")
        print(f"False Positive Prevention: {'✅ PASS' if non_escalation_success else '❌ FAIL'}")
        print("="*80)
        
        if escalation_success and non_escalation_success:
            print("\n✅ ALL TESTS PASSED - Escalation system is working correctly!")
            return 0
        else:
            print("\n❌ SOME TESTS FAILED - Please review the results above.")
            return 1
    
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

