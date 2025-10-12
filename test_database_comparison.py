"""
Comprehensive test to compare SQLite (short-term) vs Qdrant (long-term) memory.
This will help identify which database the API is actually using.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from ai_companion.modules.memory.short_term_reader import ShortTermMemoryReader
from ai_companion.modules.memory.long_term.vector_store import get_vector_store
from ai_companion.settings import settings


async def main():
    print("=" * 80)
    print("DATABASE COMPARISON TEST")
    print("=" * 80)
    print()
    
    # ============================================================================
    # TEST 1: What's in SQLite (Short-Term Memory)?
    # ============================================================================
    print("TEST 1: SQLite Database (Short-Term Memory - Actual Chat Messages)")
    print("-" * 80)
    
    db_path = "short_term_memory/memory.db"
    print(f"Database path: {db_path}\n")
    
    try:
        sqlite_reader = ShortTermMemoryReader(db_path)
        
        # Get thread IDs
        thread_ids = sqlite_reader.get_all_thread_ids(limit=3)
        print(f"Found {len(thread_ids)} conversations in SQLite\n")
        
        if thread_ids:
            # Get messages from first conversation
            first_thread = thread_ids[0]
            messages = await sqlite_reader.get_messages_for_thread(first_thread, limit=3)
            
            print(f"Sample conversation (Thread: {first_thread}):")
            for i, msg in enumerate(messages[:3], 1):
                msg_type = msg['message_type'].upper()
                text = msg['text'][:100]
                print(f"  {i}. [{msg_type}] {text}...")
            
            print()
            
            # Get summaries
            summaries = await sqlite_reader.get_conversation_summaries(limit=3)
            print("Conversation summaries from SQLite:")
            for i, summary in enumerate(summaries, 1):
                user_id = summary['user_id']
                last_msg = summary['last_message'][:80]
                print(f"  {i}. {user_id}: {last_msg}...")
        else:
            print("  No conversations found in SQLite!")
            
    except Exception as e:
        print(f"ERROR reading SQLite: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print()
    
    # ============================================================================
    # TEST 2: What's in Qdrant (Long-Term Memory)?
    # ============================================================================
    print("TEST 2: Qdrant Database (Long-Term Memory - Semantic Facts)")
    print("-" * 80)
    
    try:
        vector_store = get_vector_store()
        
        # Get conversation summaries from Qdrant
        qdrant_summaries = vector_store.get_conversation_summaries(limit=3)
        
        if qdrant_summaries:
            print(f"Found {len(qdrant_summaries)} conversations in Qdrant\n")
            print("Conversation summaries from Qdrant:")
            for i, summary in enumerate(qdrant_summaries, 1):
                user_id = summary['user_id']
                last_msg = summary['last_message'][:80]
                print(f"  {i}. {user_id}: {last_msg}...")
                
            print()
            
            # Get detailed messages for first user
            if qdrant_summaries:
                first_user = qdrant_summaries[0]['user_id']
                qdrant_messages = vector_store.get_conversation_messages(first_user, limit=3)
                
                print(f"\nSample memories for {first_user} from Qdrant:")
                for i, memory in enumerate(qdrant_messages[:3], 1):
                    text = memory.text[:100]
                    print(f"  {i}. {text}...")
        else:
            print("  No conversations found in Qdrant!")
            
    except Exception as e:
        print(f"ERROR reading Qdrant: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print()
    
    # ============================================================================
    # TEST 3: Analysis - Which database should the API use?
    # ============================================================================
    print("TEST 3: Analysis")
    print("-" * 80)
    print()
    print("EXPECTED BEHAVIOR:")
    print("  SQLite should contain: Actual chat messages")
    print('    Example: "Piyush Ji, ok samajh gayi..."')
    print('    Example: "Hello, I want to book a pooja"')
    print()
    print("  Qdrant should contain: Semantic memory statements")
    print('    Example: "Born on 16/07/1990"')
    print('    Example: "User is available at 5 PM in the evening"')
    print()
    print("API SHOULD USE: SQLite (Short-Term Memory)")
    print("API SHOULD NOT USE: Qdrant (Long-Term Memory)")
    print()
    print("=" * 80)
    print()
    
    # ============================================================================
    # TEST 4: What does the API actually return?
    # ============================================================================
    print("TEST 4: What the API Functions Return")
    print("-" * 80)
    print()
    
    print("Testing the same code path the API uses...")
    print()
    
    # Simulate what the API does
    try:
        # This is what conversations_api.py does at initialization
        memory_reader = ShortTermMemoryReader(settings.SHORT_TERM_MEMORY_DB_PATH)
        print(f"✓ Memory reader initialized with: {settings.SHORT_TERM_MEMORY_DB_PATH}")
        
        # Test the get_conversation_summaries method (used by /conversations_list)
        api_summaries = await memory_reader.get_conversation_summaries(limit=3)
        
        if api_summaries:
            print(f"✓ API would return {len(api_summaries)} conversations")
            print()
            print("Sample API responses:")
            for i, summary in enumerate(api_summaries, 1):
                user_id = summary['user_id']
                last_msg = summary['last_message'][:80]
                print(f"  {i}. {user_id}")
                print(f"     Last message: {last_msg}...")
                
                # Check if this looks like semantic memory or actual chat
                semantic_indicators = [
                    "born on", "available at", "user is", "user prefers",
                    "user mentioned", "user's name", "user likes", "user wants"
                ]
                
                is_semantic = any(indicator in last_msg.lower() for indicator in semantic_indicators)
                
                if is_semantic:
                    print(f"     ⚠️  This looks like SEMANTIC MEMORY (from Qdrant)")
                else:
                    print(f"     ✓ This looks like ACTUAL CHAT MESSAGE (from SQLite)")
                print()
        else:
            print("✗ API returned no conversations!")
            
    except Exception as e:
        print(f"✗ API initialization FAILED: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print()
    print("If API returns messages with semantic patterns like:")
    print('  - "Born on 16/07/1990"')
    print('  - "User is available at 5 PM"')
    print("Then the API is incorrectly using Qdrant instead of SQLite")
    print()
    print("If API returns actual chat messages like:")
    print('  - "Piyush Ji, ok samajh gayi..."')
    print('  - "Hello, I want to book"')
    print("Then the API is correctly using SQLite")
    print()


if __name__ == "__main__":
    asyncio.run(main())

