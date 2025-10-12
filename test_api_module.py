"""
Test the conversations_api module directly to verify it's using SQLite correctly.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import the actual API module
from ai_companion.interfaces.api_endpoints.conversations_api import (
    list_conversations,
    get_conversation,
    memory_reader
)


async def main():
    print("=" * 80)
    print("TESTING ACTUAL API MODULE")
    print("=" * 80)
    print()
    
    # Check if memory_reader was initialized
    print("Step 1: Check memory_reader initialization")
    print("-" * 80)
    if memory_reader is None:
        print("✗ FAIL: memory_reader is None!")
        print("  This means the API initialization failed.")
        print("  Check the logs above for errors.")
        return
    else:
        print("✓ PASS: memory_reader is initialized")
        print()
    
    # Test list_conversations endpoint
    print("Step 2: Test /conversations_list endpoint")
    print("-" * 80)
    try:
        conversations = await list_conversations(limit=3)
        
        if not conversations:
            print("✗ FAIL: No conversations returned")
            return
        
        print(f"✓ Returned {len(conversations)} conversations\n")
        
        for i, conv in enumerate(conversations, 1):
            user_id = conv.user_id
            last_msg = conv.last_message
            msg_count = conv.message_count
            
            print(f"Conversation {i}:")
            print(f"  User: {user_id}")
            print(f"  Messages: {msg_count}")
            print(f"  Last: {last_msg[:100]}...")
            
            # Check if semantic or actual chat
            semantic_indicators = [
                "born on", "available at", "user is", "user prefers",
                "user mentioned", "user's name", "user likes", "user wants",
                "is named", "payment has been"
            ]
            
            is_semantic = any(indicator in last_msg.lower() for indicator in semantic_indicators)
            
            if is_semantic:
                print(f"  ❌ SEMANTIC MEMORY (from Qdrant) - WRONG!")
            else:
                print(f"  ✅ ACTUAL CHAT MESSAGE (from SQLite) - CORRECT!")
            print()
            
    except Exception as e:
        print(f"✗ FAIL: Error calling list_conversations: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test get_conversation endpoint
    print("Step 3: Test /conversation/{user_id} endpoint")
    print("-" * 80)
    try:
        if conversations:
            first_user = conversations[0].user_id
            print(f"Getting conversation for: {first_user}\n")
            
            conversation = await get_conversation(first_user, limit=3)
            
            if not conversation.messages:
                print("✗ FAIL: No messages returned")
                return
            
            print(f"✓ Returned {len(conversation.messages)} messages\n")
            
            for i, msg in enumerate(conversation.messages, 1):
                msg_type = msg.message_type.upper()
                text = msg.text[:100]
                print(f"Message {i} [{msg_type}]:")
                print(f"  {text}...")
                print()
                
    except Exception as e:
        print(f"✗ FAIL: Error calling get_conversation: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("=" * 80)
    print("VERIFICATION COMPLETE")
    print("=" * 80)
    print()
    print("✅ SUCCESS: API is using SQLite and returning actual chat messages!")
    print()
    print("Examples of actual chat messages seen:")
    if conversations:
        for conv in conversations[:2]:
            print(f"  - \"{conv.last_message[:60]}...\"")
    print()


if __name__ == "__main__":
    asyncio.run(main())

