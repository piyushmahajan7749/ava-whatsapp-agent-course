# Tool Calling Integration Guide

## Overview

This guide explains how tool calling has been integrated into the AI Companion LangGraph architecture to enable calendar operations like checking availability and booking events.

## Architecture Changes

### Updated Flow

```
START → memory_extraction → router → context_injection → pooja_injection
→ memory_injection → conversation_node
                          ↓
                   [has tool calls?]
                      ↙        ↘
                tools_node    [no tools]
                      ↓            ↓
              conversation_node  [summarization check]
```

### Key Components

#### 1. **Calendar Tools** (`src/ai_companion/modules/calendar/google_calendar_tools.py`)

Two main tools are available:

- **`check_calendar_availability(start_time, end_time)`**

  - Check if a time slot is available
  - Parameters: ISO format timestamps (e.g., `2025-10-05T10:00:00`)
  - Returns: Availability status message

- **`book_calendar_event(start_time, end_time, event_title, event_description, attendee_email)`**
  - Book an event in the calendar
  - Parameters: Timestamps, event details, optional attendee email
  - Returns: Booking confirmation message

#### 2. **Updated Chain** (`src/ai_companion/graph/utils/chains.py`)

The `get_character_response_chain()` function now accepts an `enable_tools` parameter:

```python
chain = get_character_response_chain(
    summary="conversation summary",
    enable_tools=True  # Enables tool calling
)
```

When `enable_tools=True`:

- Tools are bound to the LLM using `.bind_tools()`
- System prompt includes tool usage instructions
- Returns raw `AIMessage` (with tool calls if triggered)

When `enable_tools=False`:

- Standard text response
- Applies `AsteriskRemovalParser()`

#### 3. **Conversation Node** (`src/ai_companion/graph/nodes.py`)

The `conversation_node` now:

- Always enables tools (LLM decides when to use them)
- Detects if response contains tool calls
- Returns `AIMessage` with tool calls for execution, or text response

#### 4. **Tools Node** (`src/ai_companion/graph/nodes.py`)

New node using LangGraph's `ToolNode`:

```python
tools_node = ToolNode(get_calendar_tools())
```

This node:

- Executes tool calls from the LLM
- Adds tool results as `ToolMessage` to conversation history
- Automatically handles tool execution errors

#### 5. **Routing Logic** (`src/ai_companion/graph/edges.py`)

New `route_after_conversation()` function:

- Checks if last message has tool calls
- Routes to `tools_node` if yes, otherwise to summarization check

#### 6. **Graph Structure** (`src/ai_companion/graph/graph.py`)

Updated graph includes:

- `tools_node` for executing tools
- Conditional edge from `conversation_node` to check for tool calls
- Loop from `tools_node` back to `conversation_node` (for LLM to respond with results)
- Passthrough `should_summarize` node for clean routing

## How It Works

### Example Conversation Flow

**User**: "Can you check if I'm available tomorrow at 2pm?"

1. **Memory extraction** → Extract any important info
2. **Router** → Determines it's a conversation workflow
3. **Context injection** → Adds schedule/pooja/memory context
4. **Conversation node** (with tools enabled):
   - LLM recognizes calendar query
   - Generates tool call: `check_calendar_availability(start_time="2025-10-04T14:00:00", end_time="2025-10-04T15:00:00")`
   - Returns `AIMessage` with tool call
5. **Route after conversation** → Detects tool call, routes to `tools_node`
6. **Tools node** → Executes the tool, returns result (e.g., "Available")
7. **Conversation node** (second pass):
   - LLM sees tool result in message history
   - Generates natural language response: "Yes, you're available tomorrow at 2pm!"
   - No tool calls this time
8. **Route after conversation** → No tool calls, proceeds to summarization check
9. **Summarization** → If needed, summarizes conversation

### Booking Example

**User**: "Book a meeting with Sarah for tomorrow 3pm to 4pm"

1. Same initial flow...
2. **Conversation node**: LLM might first ask for confirmation or generate tool call directly
3. **Tools node**: Executes `book_calendar_event(...)`
4. **Conversation node**: "✅ I've booked the meeting with Sarah for tomorrow 3pm to 4pm!"

## Google Calendar API Integration

Currently, the tools return **mock responses**. To integrate with real Google Calendar:

### Step 1: Install Google Calendar API

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### Step 2: Set Up OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google Calendar API
4. Create OAuth 2.0 credentials
5. Download credentials JSON file
6. Save as `credentials.json` in your project root

### Step 3: Implement Authentication

Add to `google_calendar_tools.py`:

```python
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    """Authenticate and return Google Calendar service."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('calendar', 'v3', credentials=creds)
```

### Step 4: Update Tool Functions

Replace mock implementations in `check_calendar_availability` and `book_calendar_event` with actual API calls (see code comments for examples).

## Testing

### Unit Testing Tools

```python
from ai_companion.modules.calendar.google_calendar_tools import (
    check_calendar_availability,
    book_calendar_event
)

# Test availability check
result = check_calendar_availability(
    start_time="2025-10-05T10:00:00",
    end_time="2025-10-05T11:00:00"
)
print(result)

# Test event booking
result = book_calendar_event(
    start_time="2025-10-05T14:00:00",
    end_time="2025-10-05T15:00:00",
    event_title="Team Meeting",
    event_description="Weekly sync",
    attendee_email="colleague@example.com"
)
print(result)
```

### Integration Testing

Run your chatbot and try these queries:

- "Am I available tomorrow at 3pm?"
- "Check my calendar for next Monday morning"
- "Book a 30-minute meeting with John at 2pm tomorrow"
- "Schedule a dentist appointment for Friday at 10am"

## Configuration

### Disable Tools (if needed)

To disable tools for specific scenarios, modify `conversation_node`:

```python
# In nodes.py, line ~75
enable_tools = False  # Disable tools
```

Or make it conditional:

```python
# Enable only for specific workflows
enable_tools = state.get("workflow") == "conversation"
```

### Add More Tools

To add additional tools (e.g., email, database queries):

1. Create tool functions in appropriate module:

   ```python
   @tool
   def send_email(to: str, subject: str, body: str) -> str:
       """Send an email."""
       # Implementation
       return "Email sent!"
   ```

2. Update `get_calendar_tools()` or create new getter:

   ```python
   def get_all_tools():
       return [
           *get_calendar_tools(),
           send_email,
           # Add more tools
       ]
   ```

3. Update chain to bind new tools:
   ```python
   tools = get_all_tools()
   model = model.bind_tools(tools)
   ```

## Benefits of This Approach

1. **Preserves Existing Architecture**: Tool calling is added without disrupting your pipeline
2. **Selective Tool Execution**: LLM decides when to use tools (no forced tool calls)
3. **Multi-Turn Tool Interactions**: Supports multiple tool calls in a conversation
4. **Clean Separation**: Tools are separate modules, easy to test and maintain
5. **Context-Aware**: Tools have access to full conversation context and memories
6. **Flexible**: Easy to add more tools or disable when needed

## Troubleshooting

### Tools Not Being Called

- Check that `enable_tools=True` in `get_character_response_chain()`
- Verify system prompt includes tool instructions
- Ensure LLM model supports function calling (Azure OpenAI does)

### Tool Execution Errors

- Check tool function signatures match LangChain's expectations
- Verify `@tool` decorator is applied
- Review logs for specific error messages

### Infinite Loops

If the agent keeps calling tools:

- Review tool return messages (should be clear and complete)
- Ensure conversation history includes tool results
- Add max iterations limit if needed

## Next Steps

1. **Implement Google Calendar API** (replace mock responses)
2. **Add error handling** (API rate limits, auth failures)
3. **Expand tools** (add more calendar operations: delete, update events)
4. **Add other integrations** (email, database, external APIs)
5. **Implement tool result caching** (avoid redundant API calls)

## Questions?

This integration maintains your clean pipeline architecture while adding powerful tool calling capabilities. The LLM intelligently decides when to use tools, keeping the conversation natural and context-aware.
