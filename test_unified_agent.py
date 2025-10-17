#!/usr/bin/env python3
"""
Test script for the unified agent workflow.

This script validates the simplified workflow by testing various scenarios:
- Booking intent
- Consultation inquiry
- Payment verification
- Escalation
- Tool calling
- General conversation
"""

import asyncio
import logging
from langchain_core.messages import HumanMessage

# Setup logging to see the detailed logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_scenario(graph, scenario_name, messages, thread_id="test_user"):
    """Run a test scenario through the graph."""
    print(f"\n{'='*80}")
    print(f"🧪 TESTING: {scenario_name}")
    print(f"{'='*80}\n")
    
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        # Initialize state with messages
        initial_state = {
            "messages": messages,
            "summary": "",
            "memory_context": "",
            "pooja_context": "",
            "current_activity": "",
            "apply_activity": False,
            "payment_verified": False,
        }
        
        # Run the graph
        result = await graph.ainvoke(initial_state, config)
        
        # Print results
        print(f"\n✅ Scenario completed successfully!")
        print(f"\nFinal messages count: {len(result.get('messages', []))}")
        
        # Show last AI response
        if result.get('messages'):
            last_message = result['messages'][-1]
            print(f"\nLast AI response:")
            print(f"  Type: {type(last_message).__name__}")
            if hasattr(last_message, 'content'):
                content = last_message.content[:200] if last_message.content else "(empty)"
                print(f"  Content: {content}...")
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                print(f"  Tool calls: {[tc.get('name') for tc in last_message.tool_calls]}")
        
        # Show state changes
        print(f"\nState changes:")
        print(f"  Payment verified: {result.get('payment_verified', False)}")
        print(f"  Payment status: {result.get('payment_status', 'none')}")
        print(f"  Memory context length: {len(result.get('memory_context', ''))}")
        print(f"  Pooja context length: {len(result.get('pooja_context', ''))}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Scenario failed with error: {e}")
        logger.exception(f"Error in scenario '{scenario_name}':")
        return False


async def main():
    """Run all test scenarios."""
    print(f"\n{'#'*80}")
    print(f"# UNIFIED AGENT WORKFLOW TEST SUITE")
    print(f"{'#'*80}\n")
    
    try:
        # Import the graph
        from ai_companion.graph.graph import create_workflow_graph
        
        print("📦 Creating workflow graph...")
        graph_builder = create_workflow_graph()
        graph = graph_builder.compile()
        print("✅ Graph compiled successfully!\n")
        
    except Exception as e:
        print(f"❌ Failed to create graph: {e}")
        logger.exception("Graph creation error:")
        return
    
    # Test scenarios
    scenarios = [
        {
            "name": "Booking Intent - Simple",
            "messages": [
                HumanMessage(content="I want to book a consultation with Guru Maa")
            ],
            "thread_id": "test_booking_1"
        },
        {
            "name": "Consultation Inquiry",
            "messages": [
                HumanMessage(content="How much does a consultation cost?")
            ],
            "thread_id": "test_inquiry_1"
        },
        {
            "name": "Products/Pooja Inquiry",
            "messages": [
                HumanMessage(content="Tell me about Kaal Sarp Dosh puja")
            ],
            "thread_id": "test_pooja_1"
        },
        {
            "name": "General Conversation",
            "messages": [
                HumanMessage(content="Hello! How are you?")
            ],
            "thread_id": "test_general_1"
        },
        {
            "name": "Payment Request",
            "messages": [
                HumanMessage(content="I want to book a consultation"),
                HumanMessage(content="Can you share the payment details?")
            ],
            "thread_id": "test_payment_1"
        },
        {
            "name": "Escalation - Refund Request",
            "messages": [
                HumanMessage(content="I want a refund, this is not acceptable")
            ],
            "thread_id": "test_escalation_1"
        },
    ]
    
    # Run scenarios
    results = []
    for scenario in scenarios:
        success = await test_scenario(
            graph,
            scenario["name"],
            scenario["messages"],
            scenario["thread_id"]
        )
        results.append((scenario["name"], success))
        
        # Small delay between tests
        await asyncio.sleep(1)
    
    # Summary
    print(f"\n{'='*80}")
    print(f"📊 TEST SUMMARY")
    print(f"{'='*80}\n")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\n{'='*80}")
    print(f"Results: {passed}/{total} tests passed")
    print(f"{'='*80}\n")
    
    if passed == total:
        print("🎉 All tests passed! The unified agent workflow is working correctly.")
    else:
        print(f"⚠️ {total - passed} test(s) failed. Please review the errors above.")


if __name__ == "__main__":
    asyncio.run(main())

