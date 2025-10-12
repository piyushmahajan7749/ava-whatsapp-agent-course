"""
Direct test of the conversations API functions without starting the server.
This tests the actual data retrieval to verify we're getting chat messages.
"""
import asyncio
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ai_companion.modules.memory.short_term_reader import ShortTermMemoryReader


async def main():
    """Test the API functions directly."""
    
    print("=" * 70)
    print("TESTING CONVERSATIONS API - ACTUAL DATA VERIFICATION")
    print("=" * 70)
    print()
    
    # Use local database path
    db_path = "short_term_memory/memory.db"
    print(f"Database: {db_path}")
    print()
    
    # Initialize the reader (same as API does)
    try:
        memory_reader = ShortTermMemoryReader(db_path)
        print("✓ Memory reader initialized")
    except Exception as e:
        print(f"✗ Failed to initialize: {e}")
        return
    
    print("\n" + "=" * 70)
    print("TEST 1: /conversations_list endpoint")
    print("=" * 70)
    print("This endpoint returns the list of all conversations")
    print()
    
    # This is what the API endpoint does
    summaries = await memory_reader.get_conversation_summaries(limit=5)
    
    if not summaries:
        print("❌ No conversations found!")
        print()
        print("This might mean:")
        print("  1. Database is empty (no conversations yet)")
        print("  2. Database path is wrong")
        print("  3. There's an error reading the data")
        return
    
    print(f"Found {len(summaries)} conversations\n")
    
    for i, summary in enumerate(summaries, 1):
        user_id = summary["user_id"]
        last_msg = summary["last_message"]
        msg_count = summary["message_count"]
        
        print(f"Conversation {i}:")
        print(f"  User ID: {user_id}")
        print(f"  Messages: {msg_count}")
        print(f"  Last message preview: {last_msg[:100]}...")
        print()
        
        # Check if this looks like a semantic memory or actual chat
        semantic_indicators = [
            "user is interested",
            "user prefers",
            "user mentioned",
            "user's name is",
            "user likes",
            "user wants"
        ]
        
        is_semantic = any(indicator in last_msg.lower() for indicator in semantic_indicators)
        
        if is_semantic:
            print(f"  ⚠️  WARNING: This looks like a SEMANTIC MEMORY statement!")
            print(f"  ❌ API is returning WRONG data (should be actual chat messages)")
        else:
            print(f"  ✓ This looks like an ACTUAL CHAT MESSAGE")
        print()
    
    print("\n" + "=" * 70)
    print("TEST 2: /conversation/{user_id} endpoint")
    print("=" * 70)
    print("This endpoint returns full conversation history for a user")
    print()
    
    # Get first user's full conversation
    first_user = summaries[0]["user_id"]
    print(f"Getting full conversation for: {first_user}\n")
    
    messages = await memory_reader.get_messages_for_thread(first_user, limit=5)
    
    if not messages:
        print("❌ No messages found!")
        return
    
    print(f"Found {len(messages)} messages:\n")
    
    for i, msg in enumerate(messages, 1):
        msg_type = msg["message_type"]
        text = msg["text"][:150]
        
        print(f"Message {i} [{msg_type.upper()}]:")
        print(f"  {text}...")
        print()
    
    print("=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    print()
    print("What the API SHOULD return:")
    print("  ✓ Actual chat messages like:")
    print('    - "Hello, I want to book a pooja"')
    print('    - "Namaste! Kaise hain aap?"')
    print('    - "Evening kal"')
    print()
    print("What the API should NOT return:")
    print("  ✗ Semantic memory statements like:")
    print('    - "User is interested in booking poojas"')
    print('    - "User prefers morning appointments"')
    print('    - "User mentioned payment"')
    print()
    print("=" * 70)
    
    # Final check
    all_messages_text = " ".join([s["last_message"] for s in summaries])
    semantic_indicators = [
        "user is interested",
        "user prefers", 
        "user mentioned",
        "user's name is",
        "user likes",
        "user wants"
    ]
    
    has_semantic = any(indicator in all_messages_text.lower() for indicator in semantic_indicators)
    
    if has_semantic:
        print("\n❌ FAIL: API is returning SEMANTIC MEMORY statements")
        print("   The code changes may not be deployed or loaded correctly.")
    else:
        print("\n✅ PASS: API is returning ACTUAL CHAT MESSAGES")
        print("   The fix is working correctly locally!")
    
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

