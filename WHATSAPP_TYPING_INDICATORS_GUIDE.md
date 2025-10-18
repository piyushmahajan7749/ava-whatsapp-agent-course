# WhatsApp Typing Indicators Implementation Guide

## Overview

This guide explains how to implement "typing indicators" for your WhatsApp agent. Since the official WhatsApp Cloud API doesn't support native typing indicators, we use alternative methods to show users that the bot is processing their message.

## What We've Implemented

### 1. **Status Messages as Typing Indicators**

Instead of a traditional typing indicator, we send quick status messages that show the bot is processing:

- `⏳ Processing your message...` (for text)
- `🎤 Transcribing your audio message...` (for audio)
- `🖼️ Analyzing your image...` (for images)
- `📅 Checking calendar availability...` (for bookings)
- `💰 Verifying payment details...` (for payments)

### 2. **Contextual Processing Status**

Based on detected workflow and intent, we send specific status messages:

- **Booking requests**: "📅 Checking calendar availability..."
- **Consultation inquiries**: "🤝 Preparing consultation details..."
- **Pooja products**: "🙏 Looking up pooja products..."
- **Image analysis**: "🎨 Analyzing your image..."
- **Audio transcription**: "🎤 Transcribing your audio..."

## Implementation Details

### New Functions Added

#### `send_typing_indicator()`

```python
async def send_typing_indicator(
    to_number: str,
    phone_number_id: str,
    whatsapp_token: str,
    message_type: str = "text",
    timeout: float = 5.0
) -> bool:
```

Sends a basic typing indicator based on message type.

#### `send_processing_status()`

```python
async def send_processing_status(
    to_number: str,
    phone_number_id: str,
    whatsapp_token: str,
    workflow: str,
    intent: str = None,
    timeout: float = 5.0
) -> bool:
```

Sends contextual processing status based on detected workflow and intent.

### Configuration

Add this environment variable to enable/disable typing indicators:

```bash
ENABLE_TYPING_INDICATORS=true
```

## Integration Steps

### 1. **Update Your WhatsApp Handler**

In your WhatsApp response handler, add these imports:

```python
from ai_companion.interfaces.whatsapp.status_indicators import (
    send_typing_indicator,
    send_processing_status,
    # ... other existing imports
)
```

### 2. **Add Typing Indicators to Message Processing**

In your message processing function, add typing indicators:

```python
async def process_message_async(message: Dict, from_number: str, message_id: str):
    try:
        # Extract message content
        content = await extract_message_content(message)
        message_type = message.get("type")

        # Send immediate typing indicator
        if ENABLE_TYPING_INDICATORS:
            asyncio.create_task(
                send_typing_indicator(from_number, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_TOKEN, message_type)
            )

        # ... process message through graph ...

        # Send contextual processing status
        if ENABLE_TYPING_INDICATORS:
            workflow = output_state.values.get("workflow", "conversation")
            primary_intent = output_state.values.get("primary_intent", "general")
            asyncio.create_task(
                send_processing_status(from_number, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_TOKEN, workflow, primary_intent)
            )

        # Send final response
        await send_response_from_state(from_number, output_state)

    except Exception as e:
        # Handle errors
        pass
```

### 3. **Environment Configuration**

Add these environment variables to your `.env` file:

```bash
# Enable typing indicators
ENABLE_TYPING_INDICATORS=true

# Other existing WhatsApp settings
WHATSAPP_TOKEN=your_token_here
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
```

## User Experience Flow

### Before (No Typing Indicators)

1. User sends message
2. User sees no feedback
3. User might send duplicate messages
4. Bot responds after 5-10 seconds

### After (With Typing Indicators)

1. User sends message
2. **Immediately**: Bot shows "⏳ Processing your message..."
3. **After intent detection**: Bot shows "📅 Checking calendar availability..."
4. **Final response**: Bot sends the actual response

## Testing

### 1. **Test the Functions**

```bash
python test_typing_indicator.py
```

### 2. **Test with Real Messages**

1. Send a text message to your bot
2. You should see immediate status messages
3. Check that the final response still comes through

### 3. **Test Different Message Types**

- **Text**: Should show "⏳ Processing your message..."
- **Audio**: Should show "🎤 Transcribing your audio message..."
- **Image**: Should show "🖼️ Analyzing your image..."

## Best Practices

### 1. **Timing**

- Send typing indicator **immediately** when message is received
- Send processing status **after** detecting workflow/intent
- Don't send too many status messages (max 2-3 per conversation)

### 2. **Message Types**

- Use appropriate emojis for different message types
- Keep status messages short and clear
- Use contextual messages based on detected intent

### 3. **Error Handling**

- If typing indicator fails, don't block the main response
- Log errors but continue processing
- Fall back gracefully if status messages fail

## Limitations

### WhatsApp Cloud API Limitations

- **No native typing indicator**: WhatsApp Cloud API doesn't support real typing indicators
- **Status messages**: We use text messages as "typing indicators"
- **Rate limits**: Be mindful of WhatsApp API rate limits

### Alternative Approaches

1. **Mark as Read**: Always mark messages as read immediately
2. **Emoji Reactions**: Use emoji reactions to show processing status
3. **Status Messages**: Send brief status messages (our approach)
4. **Quick Responses**: Respond with "Got it, processing..." immediately

## Troubleshooting

### Common Issues

1. **Typing indicators not showing**

   - Check `ENABLE_TYPING_INDICATORS=true`
   - Verify WhatsApp credentials
   - Check logs for errors

2. **Too many status messages**

   - Reduce the number of status messages sent
   - Use more specific conditions for when to send them

3. **Status messages appearing after response**
   - Check the order of operations in your handler
   - Ensure status messages are sent before the final response

### Debug Mode

Enable debug logging to see typing indicator activity:

```python
import logging
logging.getLogger("ai_companion.interfaces.whatsapp.status_indicators").setLevel(logging.DEBUG)
```

## Conclusion

While WhatsApp Cloud API doesn't support native typing indicators, our implementation provides a great user experience by:

1. **Immediate feedback** when messages are received
2. **Contextual status updates** based on what the bot is doing
3. **Clear communication** about processing stages
4. **Reduced user anxiety** about whether their message was received

This approach significantly improves the user experience and makes your WhatsApp bot feel more responsive and human-like.
