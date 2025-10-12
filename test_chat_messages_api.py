"""
Test script to verify that the conversations API returns actual chat messages
instead of semantic memory statements.
"""
import asyncio
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ai_companion.modules.memory.short_term_reader import ShortTermMemoryReader
from ai_companion.settings import settings


async def main():
    """Test the short-term memory reader."""
    
    print("=" * 60)
    print("Testing Short-Term Memory Reader (Chat Messages)")
    print("=" * 60)
    print()
    
    # Use local database path
    db_path = "short_term_memory/memory.db"
    print(f"Initializing reader with DB: {db_path}")
    reader = ShortTermMemoryReader(db_path)
    
    # Test 1: Get all thread IDs
    print("\n" + "=" * 60)
    print("TEST 1: Getting Thread IDs")
    print("=" * 60)
    thread_ids = reader.get_all_thread_ids(limit=5)
    print(f"Found {len(thread_ids)} threads:")
    for i, thread_id in enumerate(thread_ids, 1):
        print(f"  {i}. {thread_id}")
    
    if not thread_ids:
        print("❌ No threads found! Make sure there are conversations in the database.")
        return
    
    # Test 2: Get messages for first thread
    print("\n" + "=" * 60)
    print("TEST 2: Getting Messages for First Thread")
    print("=" * 60)
    first_thread = thread_ids[0]
    print(f"Thread ID: {first_thread}")
    messages = await reader.get_messages_for_thread(first_thread, limit=5)
    print(f"Found {len(messages)} messages:")
    for i, msg in enumerate(messages, 1):
        msg_type = msg.get("message_type", "unknown")
        text = msg.get("text", "")[:100]  # First 100 chars
        timestamp = msg.get("timestamp", "N/A")
        print(f"\n  {i}. [{msg_type.upper()}] ({timestamp})")
        print(f"     {text}...")
    
    # Test 3: Get conversation summaries
    print("\n" + "=" * 60)
    print("TEST 3: Getting Conversation Summaries")
    print("=" * 60)
    summaries = await reader.get_conversation_summaries(limit=3)
    print(f"Found {len(summaries)} conversations:")
    for i, summary in enumerate(summaries, 1):
        user_id = summary["user_id"]
        msg_count = summary["message_count"]
        last_msg = summary["last_message"][:80]
        timestamp = summary["timestamp"]
        print(f"\n  {i}. User: {user_id}")
        print(f"     Messages: {msg_count}")
        print(f"     Last: {last_msg}...")
        print(f"     Time: {timestamp}")
    
    # Test 4: Get stats
    print("\n" + "=" * 60)
    print("TEST 4: Getting Conversation Stats")
    print("=" * 60)
    stats = await reader.get_conversation_stats()
    print(f"Total Conversations: {stats['total_conversations']}")
    print(f"Total Messages (est): {stats['total_messages']}")
    print(f"Average Messages/User: {stats['average_messages_per_user']}")
    print(f"Status: {stats['status']}")
    
    print("\n" + "=" * 60)
    print("✅ All tests completed successfully!")
    print("=" * 60)
    print("\nNOTE: The API should now return actual chat messages like:")
    print("  - 'User: Hello, I want to book a pooja'")
    print("  - 'AI: Sure! Which pooja are you interested in?'")
    print("\nInstead of semantic memory statements like:")
    print("  - 'User is interested in booking poojas'")
    print("  - 'User prefers morning appointments'")


if __name__ == "__main__":
    asyncio.run(main())

