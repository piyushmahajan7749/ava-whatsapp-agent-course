"""
Test script for calendar tool calling functionality.

This script demonstrates how the AI companion uses tools to check availability
and book calendar events.
"""

import asyncio
from langchain_core.messages import HumanMessage

from ai_companion.graph.graph import graph


async def test_tool_calling():
    """Test the calendar tool calling functionality."""
    
    print("=" * 60)
    print("Testing Calendar Tool Calling Integration")
    print("=" * 60)
    
    # Test 1: Check availability
    print("\n📅 Test 1: Checking calendar availability")
    print("-" * 60)
    
    test_messages = [
        HumanMessage(content="Can you check if I'm available tomorrow at 2pm to 3pm?")
    ]
    
    config = {"configurable": {"thread_id": "test-thread-1"}}
    
    print(f"User: {test_messages[0].content}")
    print("\nProcessing...\n")
    
    try:
        result = await graph.ainvoke(
            {"messages": test_messages},
            config=config
        )
        
        # Print the conversation
        for msg in result["messages"]:
            if hasattr(msg, 'content') and msg.content:
                role = msg.__class__.__name__.replace("Message", "")
                print(f"{role}: {msg.content}")
            elif hasattr(msg, 'tool_calls') and msg.tool_calls:
                print(f"\n🔧 Tool Calls: {[tc['name'] for tc in msg.tool_calls]}")
        
        print("\n✅ Test 1 completed successfully!")
        
    except Exception as e:
        print(f"❌ Error in Test 1: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Test 2: Book an event
    print("\n" + "=" * 60)
    print("📅 Test 2: Booking a calendar event")
    print("-" * 60)
    
    test_messages_2 = [
        HumanMessage(content="Book a team meeting for next Monday at 10am to 11am")
    ]
    
    config_2 = {"configurable": {"thread_id": "test-thread-2"}}
    
    print(f"User: {test_messages_2[0].content}")
    print("\nProcessing...\n")
    
    try:
        result = await graph.ainvoke(
            {"messages": test_messages_2},
            config=config_2
        )
        
        # Print the conversation
        for msg in result["messages"]:
            if hasattr(msg, 'content') and msg.content:
                role = msg.__class__.__name__.replace("Message", "")
                print(f"{role}: {msg.content}")
            elif hasattr(msg, 'tool_calls') and msg.tool_calls:
                print(f"\n🔧 Tool Calls: {[tc['name'] for tc in msg.tool_calls]}")
        
        print("\n✅ Test 2 completed successfully!")
        
    except Exception as e:
        print(f"❌ Error in Test 2: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Test 3: Regular conversation (no tools)
    print("\n" + "=" * 60)
    print("💬 Test 3: Regular conversation (should not trigger tools)")
    print("-" * 60)
    
    test_messages_3 = [
        HumanMessage(content="Hello! How are you today?")
    ]
    
    config_3 = {"configurable": {"thread_id": "test-thread-3"}}
    
    print(f"User: {test_messages_3[0].content}")
    print("\nProcessing...\n")
    
    try:
        result = await graph.ainvoke(
            {"messages": test_messages_3},
            config=config_3
        )
        
        # Print the conversation
        tool_called = False
        for msg in result["messages"]:
            if hasattr(msg, 'content') and msg.content:
                role = msg.__class__.__name__.replace("Message", "")
                print(f"{role}: {msg.content}")
            elif hasattr(msg, 'tool_calls') and msg.tool_calls:
                tool_called = True
                print(f"\n🔧 Tool Calls: {[tc['name'] for tc in msg.tool_calls]}")
        
        if not tool_called:
            print("\n✅ Test 3 completed successfully! (No tools called as expected)")
        else:
            print("\n⚠️  Test 3: Tools were called unexpectedly")
        
    except Exception as e:
        print(f"❌ Error in Test 3: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_tool_calling())

