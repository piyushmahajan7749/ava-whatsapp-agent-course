# Chat Messages API Fix

## Problem

The conversation list API was showing **semantic memory statements** from Qdrant (long-term memory) instead of **actual chat messages** from the conversation history.

### What was showing (INCORRECT):

- "User is interested in booking poojas"
- "User prefers morning appointments"
- "User's name is Piyush"

### What should show (CORRECT):

- "User: Hello, I want to book a pooja"
- "AI: Namaste! Kaise hain aap?"
- "User: Evening kal"

## Root Cause

The system has **two separate memory systems**:

1. **Long-term Memory (Qdrant)** - Stores semantic facts/memories extracted from conversations

   - Location: Qdrant vector database
   - Purpose: Store important user preferences, facts, context for AI responses
   - Example: "User prefers morning slots", "User's favorite deity is Krishna"

2. **Short-term Memory (SQLite)** - Stores actual chat message history
   - Location: `short_term_memory/memory.db` (LangGraph checkpoints)
   - Purpose: Store the full conversation history for context window
   - Example: Actual "User: Hi" and "AI: Hello!" messages

**The API was fetching from the wrong database!** It was fetching from Qdrant (long-term) instead of SQLite (short-term).

## Solution

### Files Created

1. **`src/ai_companion/modules/memory/short_term_reader.py`**
   - New module to read actual chat messages from SQLite database
   - Uses LangGraph's `AsyncSqliteSaver` to properly deserialize checkpoints
   - Provides methods:
     - `get_all_thread_ids()` - Get list of all user conversations
     - `get_messages_for_thread()` - Get all messages for a specific user
     - `get_conversation_summaries()` - Get summary of all conversations
     - `get_conversation_stats()` - Get statistics about conversations

### Files Modified

2. **`src/ai_companion/interfaces/api_endpoints/conversations_api.py`**
   - Changed from using `VectorStore` (Qdrant) to `ShortTermMemoryReader` (SQLite)
   - Updated all endpoints to fetch from short-term memory:
     - `/conversations_list` - Lists all conversations with real chat messages
     - `/conversation/{user_id}` - Gets full conversation history for a user
     - `/conversations_search` - Searches through actual chat messages
     - `/conversations_stats` - Gets statistics from chat history
     - `/debug_memory` - New debug endpoint to check memory reader status

## Technical Details

### How LangGraph Stores Messages

LangGraph uses SQLite with a specific structure:

```
checkpoints table:
  - thread_id: User identifier (phone number or UUID)
  - checkpoint: BLOB containing serialized state
  - checkpoint contains:
    - channel_values:
      - messages: Array of LangChain message objects
```

### Checkpoint Access Pattern

```python
# Get checkpoint tuple
checkpoint_tuple = await memory.aget_tuple(config)

# Extract messages from channel_values
checkpoint = checkpoint_tuple.checkpoint
channel_values = checkpoint.get("channel_values", {})
messages = channel_values.get("messages", [])

# Convert LangChain messages to simple dicts
for msg in messages:
    if isinstance(msg, BaseMessage):
        chat_message = {
            "text": msg.content,
            "timestamp": msg.additional_kwargs.get("timestamp"),
            "message_type": "user" if isinstance(msg, HumanMessage) else "assistant",
            "message_id": msg.id
        }
```

## Testing

### Test Script

Run `python test_chat_messages_api.py` to verify:

- ✅ Can read thread IDs from database
- ✅ Can extract actual chat messages
- ✅ Can generate conversation summaries with real messages
- ✅ Can calculate accurate statistics

### Example Output

```
TEST 2: Getting Messages for First Thread
============================================================
Thread ID: 919303609133
Found 5 messages:

  1. [ASSISTANT] (2025-10-09T19:55:26)
     Bahut accha ji 🌸
     Main aapko abhi payment QR code bhej rahi hoon.

  2. [USER] (2025-10-09T19:55:26)
     Kab ka milegs

  3. [ASSISTANT] (2025-10-09T19:55:26)
     Han ji, usually 2-3 din ke andar slot mil jata hai 👍
```

## API Endpoints

### GET /conversations_list

Returns list of recent conversations with real chat messages.

**Example Response:**

```json
[
  {
    "user_id": "919303402193",
    "last_message": "Namaste Piyush ji 😊 Kaise hain aap?",
    "timestamp": "2025-10-09T19:55:26.517121",
    "message_count": 16,
    "score": 1.0
  }
]
```

### GET /conversation/{user_id}

Returns full conversation history for a specific user.

**Example Response:**

```json
{
  "user_id": "919303402193",
  "messages": [
    {
      "text": "Hello, I want to book a pooja",
      "timestamp": "2025-10-09T19:50:00",
      "message_type": "user",
      "message_id": "msg_123"
    },
    {
      "text": "Namaste! Kaise hain aap?",
      "timestamp": "2025-10-09T19:50:05",
      "message_type": "assistant",
      "message_id": "msg_124"
    }
  ],
  "total_messages": 16
}
```

### GET /conversations_stats

Returns overall statistics about conversations.

**Example Response:**

```json
{
  "total_conversations": 4,
  "total_messages": 40,
  "average_messages_per_user": 10.0,
  "status": "real_data"
}
```

## Database Paths

- **Development/Local**: `short_term_memory/memory.db`
- **Production/Docker**: `/app/data/memory.db` (configured in settings)

## Benefits

1. **Correct Data**: Frontend now shows actual conversation history
2. **Better UX**: Users can see real chat messages they sent/received
3. **Accurate Counts**: Message counts reflect actual chat history
4. **Proper Separation**: Long-term memory (Qdrant) and short-term memory (SQLite) are now properly separated
5. **Scalable**: Can handle large conversation histories efficiently

## Future Enhancements

1. **Add pagination**: For conversations with many messages
2. **Add filtering**: By date range, message type, etc.
3. **Add full-text search**: Search within message content
4. **Add export**: Export conversations to JSON/CSV
5. **Add analytics**: Message frequency, response times, etc.

## Deployment Notes

- No new environment variables required
- No database migrations needed
- Backward compatible with existing data
- Works with both WhatsApp (phone numbers) and Chainlit (UUIDs) as thread IDs

## Status

✅ **COMPLETE** - The API now correctly returns actual chat messages from SQLite short-term memory instead of semantic memory statements from Qdrant.
